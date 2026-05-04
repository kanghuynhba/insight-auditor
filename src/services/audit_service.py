# services/audit_service.py
from src.core.config import get_settings
from src.core.summary import Summary
from src.core.audit import AuditReport
from src.index.operations.validate_facts import validate_facts
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.services.score_calculation_service import (
    compute_score,
)  # we keep compute_score only


class AuditService:
    def __init__(
        self,
        llm: LLMCompletion,
        fact_repo: AtomicFactRepository,
        summary_repo: SummaryRepository,
        audit_repo: AuditReportRepository,
    ):
        self.llm = llm
        self.fact_repo = fact_repo
        self.summary_repo = summary_repo
        self.audit_repo = audit_repo
        self.settings = get_settings()

    async def evaluate_summary(
        self,
        section_id: str,
        summary_text: str,
    ) -> AuditReport:
        # Gate: minimum word count
        word_count = len(summary_text.split())
        if word_count < self.settings.min_summary_words:
            raise ValueError(
                f"Summary too short (min {self.settings.min_summary_words} words)"
            )

        # Fetch all atomic facts for this section (using path_id prefix)
        candidate_facts = await self.fact_repo.find_by_section(section_id)
        if not candidate_facts:
            raise ValueError(
                "No atomic facts found for this section – run ingestion first."
            )

        # Retrieve previous attempt (if any) for improvement tracking
        previous_summaries = await self.summary_repo.get_by_section(section_id)
        previous_summary = previous_summaries[-1] if previous_summaries else None
        previous_report = None
        if previous_summary:
            reports = await self.audit_repo.get_history_by_section(section_id)
            previous_report = reports[-1] if reports else None

        # Call LLM to validate facts (returns list of FactValidationResult without report_id)
        validations = await validate_facts(
            llm=self.llm,
            summary=summary_text,
            facts=candidate_facts,
            previous_summary=previous_summary,
            previous_report=previous_report,
        )

        # Compute weighted score (using compute_score from score_calculation_service)
        score = compute_score(validations, candidate_facts)
        score_delta = score - previous_report.score if previous_report else None

        # Save user summary
        attempt_number = len(previous_summaries) + 1
        summary = Summary(
            section_id=section_id,
            text=summary_text,
            attempt_number=attempt_number,
        )
        summary = await self.summary_repo.save(summary)

        # Create audit report (no lists inside)
        report = AuditReport(
            summary_id=summary.id,
            section_id=section_id,
            score=score,
            score_delta=score_delta,
        )

        # Attach validations (this automatically sets report_id on each FactValidationResult)
        for v in validations:
            # v already has atomic_fact_id, status, evidence, confidence, improved
            # but missing report_id – will be set via relationship
            report.validations.append(v)

        # Save report – cascade will insert all FactValidationResult rows
        await self.audit_repo.save(report)

        return report
