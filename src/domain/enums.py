# src/core/enums.py
from enum import Enum, IntEnum
from typing import Union


class Tier(IntEnum):
    CRITICAL = 1
    IMPORTANT = 2
    NUANCE = 3

    @property
    def weight(self) -> int:
        """Heavier weight for critical facts in scoring logic."""
        return {1: 3, 2: 2, 3: 1}[self.value]

    @classmethod
    def from_rank(cls, rank: Union[int, str, None]) -> "Tier":
        if rank is None:
            return cls.NUANCE
        try:
            val = int(rank)
            if val in (1, 2, 3):
                return cls(val)
            return cls.NUANCE
        except (ValueError, TypeError):
            pass
        if isinstance(rank, str):
            try:
                return cls[rank.upper()]
            except KeyError:
                pass
        return cls.NUANCE

    def to_rank(self) -> int:
        """Returns the integer rank (1, 2, 3) used in LLM prompts."""
        return self.value


class FactStatus(str, Enum):
    FOUND = "found"
    PARTIAL = "partial"
    MISSING = "missing"
    CONTRADICTED = "contradicted"


class ExtractionStatus(str, Enum):
    NONE = "NONE"  # uppercase to match DB enum
    PENDING = "PENDING"
    DONE = "DONE"
    ERROR = "ERROR"
