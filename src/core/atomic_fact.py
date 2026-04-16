import json
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic import ConfigDict, ValidationError, field_validator
from sqlalchemy import JSON, TEXT
from sqlmodel import Column, Field, Relationship
from src.core.entity import Entity
from src.core.enums import Tier

if TYPE_CHECKING:
    from src.core.models import Section

TIER_WEIGHTS = {Tier.CRITICAL: 3, Tier.IMPORTANT: 2, Tier.NUANCE: 1}


class AtomicFact(Entity, table=True):
    __tablename__ = "atomic_facts"
    section_id: str = Field(foreign_key="sections.id", index=True)
    path_id: str = Field(index=True)

    point: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    reason: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))

    rank: Tier = Field(default=Tier.NUANCE, index=True)

    # Metadata
    questions: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Relationships
    section: "Section" = Relationship(back_populates="atomic_facts")

    @property
    def weight(self) -> int:
        """Returns weight based on Tier: Critical=3, Important=2, Nuance=1"""
        return TIER_WEIGHTS.get(self.rank, 0)

    @field_validator("rank", mode="before")
    @classmethod
    def coerce_rank(cls, v: Any) -> Any:
        """
        Only coerce if a value exists.
        Returning None allows Pydantic to trigger the required field error.
        """
        return Tier.from_rank(v)

    model_config = ConfigDict(validate_assignment=True)
