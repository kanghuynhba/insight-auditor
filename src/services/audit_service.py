# src/services/audit_service.py
"""Audit service – evaluates user-written summaries against extracted facts.

Changes from the original
-------------------------
* :meth:`evaluate_summary` now returns an
  :class:`~src.model.audit_models.AuditReportModel` instead of a raw
  ``AuditReport`` entity.  The router converts this to
  :class:`~src.response.audit_report.AuditReportResponse`.
* A new helper :meth:`get_history_by_section` exposes audit history as
  a list of models so the router's ``GET /evaluations`` endpoint is also thin.
"""

from __future__ import annotations

import logging
from typing import List

from src.converter.entity_to_model import audit_report_entity_to_model
from src.core.audit import AuditReport
from src.core.config import get_settings
from src.core.summary import Summary
from src.index.operations.validate_facts import validate_facts
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.model.audit_models import AuditReportModel
from src.services.score_calculation_service import compute_score

logger = logging.getLogger(__name__)


class AuditService:
    """Validates a user's summary against the section's atomic facts and
    persists an audit report.

    All public methods return **service models**; no response DTOs are used here.
    """

    def __init__(
        self,
        llm: LLMCompletion,
        fact_repo: AtomicFactRepository,
        summary_repo: SummaryRepository,
        audit_repo: AuditReportRepository,
    ) -> None:
        self.llm = llm
        self.fact_repo = fact_repo
        self.summary_repo = summary_repo
        self.audit_repo = audit_repo
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate_summary(
        self,
        section_id: str,
        summary_text: str,
    ) -> AuditReportModel:
        """Evaluate *summary_text* against the section's atomic facts.

        Args:
            section_id:   The section whose facts will be used for validation.
            summary_text: The plain-text summary submitted by the user.

        Returns:
            An immutable :class:`~src.model.audit_models.AuditReportModel`
            containing the score, delta, and per-fact feedback.

        Raises:
            ValueError: When the summary is too short or no facts exist.
        """
        # Gate: minimum word count
        word_count = len(summary_text.split())
        if word_count < self.settings.min_summary_words:
            raise ValueError(
                f"Summary too short (min {self.settings.min_summary_words} words)"
            )

        # Fetch all atomic facts for this section
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

        # Call LLM to validate facts
        validations = await validate_facts(
            llm=self.llm,
            summary=summary_text,
            facts=candidate_facts,
            previous_summary=previous_summary,
            previous_report=previous_report,
        )

        # Compute weighted score
        score = compute_score(validations, candidate_facts)
        score_delta = score - previous_report.score if previous_report else None

        # Persist the user summary
        attempt_number = len(previous_summaries) + 1
        summary = Summary(
            section_id=section_id,
            text=summary_text,
            attempt_number=attempt_number,
        )
        summary = await self.summary_repo.save(summary)

        # Build and persist the audit report
        report = AuditReport(
            summary_id=summary.id,
            section_id=section_id,
            score=score,
            score_delta=score_delta,
        )
        for v in validations:
            report.validations.append(v)

        await self.audit_repo.save(report)

        # Build lookup maps for the converter
        fact_points = {f.id: (f.point or "") for f in candidate_facts}
        fact_ranks = {f.id: f.rank.value for f in candidate_facts}

        return audit_report_entity_to_model(
            report=report,
            attempt_number=attempt_number,
            fact_points=fact_points,
            fact_ranks=fact_ranks,
        )

    async def get_history_by_section(self, section_id: str) -> List[AuditReportModel]:
        """Return all past audit reports for *section_id* as service models.

        Args:
            section_id: The section whose evaluation history is requested.

        Returns:
            A list of :class:`~src.model.audit_models.AuditReportModel` objects
            ordered chronologically (oldest first), possibly empty.
        """
        reports = await self.audit_repo.get_history_by_section(section_id)
        result = []
        for report in reports:
            attempt_number = report.summary.attempt_number if report.summary else 1
            fact_points: dict[str, str] = {}
            fact_ranks: dict[str, int] = {}
            for v in report.validations:
                fact = await self.fact_repo.find_by_id(v.atomic_fact_id)
                if fact:
                    fact_points[fact.id] = fact.point or ""
                    fact_ranks[fact.id] = fact.rank.value
            result.append(
                audit_report_entity_to_model(
                    report=report,
                    attempt_number=attempt_number,
                    fact_points=fact_points,
                    fact_ranks=fact_ranks,
                )
            )
        return result
