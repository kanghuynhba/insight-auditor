# src/model/section_models.py
"""Service models for sections and their extracted facts."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, computed_field

from src.model.fact_models import AtomicFactModel


class SectionModel(BaseModel):
    """Immutable service model for a content section."""

    id: str
    raw_text: Optional[str] = None
    extraction_status: str  # NONE | PENDING | DONE | ERROR

    @computed_field  # type: ignore[misc]
    @property
    def word_count(self) -> int:
        """Number of words in ``raw_text``, 0 when absent."""
        if not self.raw_text:
            return 0
        return len(self.raw_text.split())

    model_config = {"frozen": True}


class FactsModel(BaseModel):
    """Aggregated facts payload returned by :class:`~src.services.facts_read_service.FactsReadService`."""

    section_id: str
    extraction_status: str
    facts: List[AtomicFactModel]
    hints: List[str] = []

    model_config = {"frozen": True}
