import json
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic import ConfigDict, ValidationError, field_validator
from sqlalchemy import JSON, TEXT
from sqlmodel import Column, Field, Relationship
from src.core.entity import Entity
from src.core.enums import Tier
from src.core.models import Section

TIER_WEIGHTS = {Tier.CRITICAL: 3, Tier.IMPORTANT: 2, Tier.NUANCE: 1}


class AtomicFact(Entity, table=True):
    __tablename__ = "atomic_facts"

    section_id: str = Field(foreign_key="sections.id", index=True)
    path_id: str = Field(index=True)
    point: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    reason: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    rank: Tier = Field(default=Tier.NUANCE, index=True)

    # Character-level provenance span into the parent section's raw text.
    # text[start_char:end_char] reproduces the grounding passage.
    start_char: Optional[int] = Field(default=None, nullable=True)
    end_char: Optional[int] = Field(default=None, nullable=True)

    # Metadata
    questions: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Relationships
    section: "Section" = Relationship(back_populates="atomic_facts")

    @property
    def weight(self) -> int:
        """Returns weight based on Tier: Critical=3, Important=2, Nuance=1"""
        return TIER_WEIGHTS.get(self.rank, 0)

    @property
    def span_length(self) -> Optional[int]:
        """Returns the character length of the grounding span, or None if unset."""
        if self.start_char is not None and self.end_char is not None:
            return self.end_char - self.start_char
        return None

    def grounding_text(self, section_text: str) -> Optional[str]:
        """
        Slices the grounding passage out of the parent section's raw text.

        Usage:
            passage = fact.grounding_text(section.raw_text)
        """
        if self.start_char is None or self.end_char is None:
            return None
        return section_text[self.start_char : self.end_char]

    @field_validator("rank", mode="before")
    @classmethod
    def coerce_rank(cls, v: Any) -> Any:
        """
        Only coerce if a value exists.
        Returning None allows Pydantic to trigger the required field error.
        """
        return Tier.from_rank(v)

    @field_validator("end_char", mode="after")
    @classmethod
    def validate_span(cls, end_char: Optional[int], info: Any) -> Optional[int]:
        """Ensure end_char > start_char when both are provided."""
        start_char = (info.data or {}).get("start_char")
        if start_char is not None and end_char is not None:
            if end_char <= start_char:
                raise ValueError(
                    f"end_char ({end_char}) must be greater than start_char ({start_char})"
                )
        return end_char

    model_config = ConfigDict(validate_assignment=True)
