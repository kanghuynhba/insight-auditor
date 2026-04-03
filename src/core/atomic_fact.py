# src/core/atomic_fact.py

from enum import IntEnum

from pydantic import BaseModel, Field
from src.core.enums import Tier
from src.core.helpers import _new_id

TIER_WEIGHTS = {Tier.CRITICAL: 3, Tier.IMPORTANT: 2, Tier.NUANCE: 1}


class AtomicFact(BaseModel):
    id: str = Field(default_factory=_new_id)
    section_id: str
    path_id: str
    point: str
    rank: Tier
    reason: str

    @property
    def weight(self) -> int:
        return TIER_WEIGHTS[self.rank]

    model_config = {"frozen": True}
