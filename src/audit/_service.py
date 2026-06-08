"""Audit facade."""

from __future__ import annotations

from typing import Optional

from src.audit._models import AuditReportModel, FactFeedbackModel
from src.audit._scorer import compute_score
from src.audit._validator import validate_facts
from src.domain import AuditReport, ExtractionStatus, Summary
from src.llm import LLMGateway
from src.store import Store


class AuditGateway:
    """Public interface for hints, summary evaluation, and audit history."""

    def __init__(self, store: Store, llm: LLMGateway, settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings

    async def hints(
        self,
        section_id: str,
        attempt_number: Optional[int] = None,
        max_hints: int = 5,
    ) -> list[str]:
        await self._require_done_section(
            section_id,
            "No facts extracted for this section - call facts/extraction first",
        )
        facts = await self.store.get_facts_by_section(section_id)
        sorted_facts = sorted(facts, key=lambda fact: fact.rank.value)
        hints: list[str] = []
        for fact in sorted_facts:
            if fact.questions:
                hints.append(fact.questions[0])
            if len(hints) >= max_hints:
                break
        return hints

    async def evaluate(self, section_id: str, summary_text: str) -> AuditReportModel:
        await self._require_done_section(
            section_id,
            "Atomic facts not ready – please wait for extraction to complete",
        )
        if len(summary_text.split()) < self.settings.min_summary_words:
            raise ValueError(
                f"Summary too short (min {self.settings.min_summary_words} words)"
            )

        candidate_facts = await self.store.get_facts_by_section(section_id)
        if not candidate_facts:
            raise ValueError(
                "No atomic facts found for this section – run ingestion first."
            )

        previous_summaries = await self.store.get_summaries_by_section(section_id)
        previous_summary = previous_summaries[-1] if previous_summaries else None
        previous_report = None
        if previous_summary:
            reports = await self.store.get_audit_history_by_section(section_id)
            previous_report = reports[-1] if reports else None

        validations = await validate_facts(
            llm=self.llm.completion,
            summary=summary_text,
            facts=candidate_facts,
            previous_summary=previous_summary,
            previous_report=previous_report,
        )

        score = compute_score(validations, candidate_facts)
        score_delta = score - previous_report.score if previous_report else None

        attempt_number = len(previous_summaries) + 1
        summary = Summary(
            section_id=section_id,
            text=summary_text,
            attempt_number=attempt_number,
        )
        summary = await self.store.save_summary(summary)

        report = AuditReport(
            summary_id=summary.id,
            score=score,
            score_delta=score_delta,
        )
        for validation in validations:
            report.validations.append(validation)

        await self.store.save_audit(report)
        await self.store.commit()

        fact_points = {fact.id: (fact.point or "") for fact in candidate_facts}
        fact_ranks = {fact.id: fact.rank.value for fact in candidate_facts}
        return self._report_model(
            report=report,
            attempt_number=attempt_number,
            fact_points=fact_points,
            fact_ranks=fact_ranks,
        )

    async def history(self, section_id: str) -> list[AuditReportModel]:
        reports = await self.store.get_audit_history_by_section(section_id)
        result = []
        for report in reports:
            attempt_number = report.summary.attempt_number if report.summary else 1
            fact_points: dict[str, str] = {}
            fact_ranks: dict[str, int] = {}
            for validation in report.validations:
                fact = await self.store.get_fact(validation.atomic_fact_id)
                if fact:
                    fact_points[fact.id] = fact.point or ""
                    fact_ranks[fact.id] = fact.rank.value
            result.append(
                self._report_model(
                    report=report,
                    attempt_number=attempt_number,
                    fact_points=fact_points,
                    fact_ranks=fact_ranks,
                )
            )
        return result

    async def get_report(self, audit_report_id: str) -> AuditReportModel | None:
        report = await self.store.get_audit_report(audit_report_id)
        if not report:
            return None

        attempt_number = report.summary.attempt_number if report.summary else 1
        fact_points: dict[str, str] = {}
        fact_ranks: dict[str, int] = {}
        for validation in report.validations:
            fact = await self.store.get_fact(validation.atomic_fact_id)
            if fact:
                fact_points[fact.id] = fact.point or ""
                fact_ranks[fact.id] = fact.rank.value

        return self._report_model(
            report=report,
            attempt_number=attempt_number,
            fact_points=fact_points,
            fact_ranks=fact_ranks,
        )

    async def _require_done_section(self, section_id: str, not_ready_message: str):
        section = await self.store.get_section(section_id)
        if not section:
            raise KeyError("Section not found")
        if section.extraction_status != ExtractionStatus.DONE:
            raise RuntimeError(not_ready_message)
        return section

    @staticmethod
    def _report_model(
        report: AuditReport,
        attempt_number: int,
        fact_points: dict[str, str],
        fact_ranks: dict[str, int],
    ) -> AuditReportModel:
        return AuditReportModel(
            id=report.id,
            summary_id=report.summary_id,
            score=report.score,
            score_delta=report.score_delta,
            attempt_number=attempt_number,
            fact_feedback=[
                FactFeedbackModel(
                    fact_id=validation.atomic_fact_id,
                    point=fact_points.get(validation.atomic_fact_id, ""),
                    rank=fact_ranks.get(validation.atomic_fact_id, 3),
                    status=(
                        validation.status.value
                        if hasattr(validation.status, "value")
                        else str(validation.status)
                    ),
                    evidence=validation.evidence or "",
                    confidence=validation.confidence,
                    improved=validation.improved,
                )
                for validation in report.validations
            ],
        )
