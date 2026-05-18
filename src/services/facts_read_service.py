# src/services/facts_read_service.py
"""Read-only service for atomic facts and hints.

Changes from the original
-------------------------
* :meth:`get_facts_by_section` now returns a
  :class:`~src.model.section_models.FactsModel` instead of a
  ``FactsResponse`` response DTO.  Response conversion is the router's job.
* :meth:`get_hints` now returns ``List[str]`` instead of ``List[HintResponse]``.
  The router calls :func:`~src.converter.model_to_response.hints_to_response`
  to produce the DTO.
"""

from __future__ import annotations

from typing import List, Optional

from src.converter.entity_to_model import atomic_fact_entity_to_model
from src.core.atomic_fact import AtomicFact
from src.core.enums import ExtractionStatus
from src.core.exceptions import ExtractionNotReadyError
from src.core.section import Section
from src.infrastructure.persistence.base_repository import Repository
from src.model.section_models import FactsModel


class FactsReadService:
    """Provides read access to extracted atomic facts and study hints.

    All methods return **service models** (or primitive types); they never
    import response DTOs.
    """

    def __init__(
        self,
        fact_repo: Repository[AtomicFact],
        section_repo: Repository[Section],
    ) -> None:
        self.fact_repo = fact_repo
        self.section_repo = section_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_facts_by_section(self, section_id: str) -> FactsModel:
        """Return a :class:`~src.model.section_models.FactsModel` for *section_id*.

        Args:
            section_id: The section to fetch facts for.

        Returns:
            An immutable :class:`~src.model.section_models.FactsModel`.

        Raises:
            ValueError: When *section_id* does not exist in the database.
            :class:`~src.core.exceptions.ExtractionNotReadyError`: When the
                section's extraction status is not ``DONE``.
        """
        section = await self.section_repo.find_by_id(section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        if section.extraction_status != ExtractionStatus.DONE:
            raise ExtractionNotReadyError(
                status=section.extraction_status,
                message="No facts extracted yet",
            )

        facts = await self.fact_repo.find_by_section(section_id)
        return FactsModel(
            section_id=section_id,
            extraction_status=ExtractionStatus.DONE,
            facts=[atomic_fact_entity_to_model(f) for f in facts],
            hints=[],
        )

    async def get_hints(
        self,
        section_id: str,
        attempt_number: Optional[int] = None,
        max_hints: int = 5,
    ) -> List[str]:
        """Return up to *max_hints* question strings, ordered by fact rank.

        High-priority (Critical, rank 1) facts come first.

        Args:
            section_id:     The section to fetch hints for.
            attempt_number: Optional – reserved for future filtering by attempt.
            max_hints:      Maximum number of hints to return (default 5).

        Returns:
            A list of hint strings (possibly empty when no facts exist).
        """
        facts = await self.fact_repo.find_by_section(section_id)
        if not facts:
            return []

        sorted_facts = sorted(facts, key=lambda f: f.rank.value)  # Critical first
        hints: List[str] = []
        for fact in sorted_facts:
            if fact.questions:
                hints.append(fact.questions[0])
            if len(hints) >= max_hints:
                break

        return hints
