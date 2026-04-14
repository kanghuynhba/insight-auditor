# src/core/atomic_fact.py

from enum import IntEnum
from typing import Union

from pydantic import BaseModel, Field, field_validator
from src.core.enums import Tier
from src.core.helpers import new_id

TIER_WEIGHTS = {Tier.CRITICAL: 3, Tier.IMPORTANT: 2, Tier.NUANCE: 1}


class AtomicFact(BaseModel):
    id: str = Field(default_factory=new_id)
    section_id: str
    path_id: str
    point: str
    rank: Tier
    reason: str

    @property
    def weight(self) -> int:
        return TIER_WEIGHTS[self.rank]

    @field_validator("rank", mode="before")
    @classmethod
    def coerce_rank(cls, v: Union[int, str, "Tier", None]) -> "Tier":
        """Automatically convert integer/string ranks to Tier enum."""
        if isinstance(v, Tier):
            return v
        return Tier.from_rank(v)

    model_config = {"frozen": True}
