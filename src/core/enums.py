# src/core/enums.py

from enum import Enum, IntEnum
from typing import Union


class Tier(IntEnum):
    CRITICAL = 1
    IMPORTANT = 2
    NUANCE = 3

    @property
    def weight(self) -> int:
        return {1: 3, 2: 2, 3: 1}[self.value]

    @classmethod
    def from_rank(cls, rank: Union[int, str, None] = None) -> "Tier":
        """
        Convert a rank value (int or string) to a Tier enum.

        Args:
            rank: Integer (1, 2, 3) or string ("CRITICAL", "IMPORTANT", "NUANCE")
                  Defaults to NUANCE if None or invalid.

        Returns:
            Tier enum value

        Examples:
            Tier.from_rank(1) -> Tier.CRITICAL
            Tier.from_rank(2) -> Tier.IMPORTANT
            Tier.from_rank(3) -> Tier.NUANCE
            Tier.from_rank("IMPORTANT") -> Tier.IMPORTANT
            Tier.from_rank(None) -> Tier.NUANCE
        """
        # Handle None or empty input
        if rank is None:
            return cls.NUANCE

        # Handle string input (e.g., "CRITICAL", "IMPORTANT", "NUANCE")
        if isinstance(rank, str):
            try:
                return cls[rank.upper()]
            except KeyError:
                # Try to convert string to int if it's numeric
                if rank.isdigit():
                    return cls.from_rank(int(rank))
                return cls.NUANCE

        # Handle integer input (1, 2, 3)
        # Note: LLM prompts use 1=CRITICAL, 2=IMPORTANT, 3=NUANCE
        if isinstance(rank, int):
            if rank == 1:
                return cls.CRITICAL
            elif rank == 2:
                return cls.IMPORTANT
            elif rank == 3:
                return cls.NUANCE
            return cls.NUANCE

        # Fallback for any other type
        return cls.NUANCE

    def to_rank(self) -> int:
        """
        Convert Tier enum to prompt rank integer.

        Returns:
            Integer rank for prompts (1=CRITICAL, 2=IMPORTANT, 3=NUANCE)

        Examples:
            Tier.CRITICAL.to_rank() -> 1
            Tier.IMPORTANT.to_rank() -> 2
            Tier.NUANCE.to_rank() -> 3
        """
        if self == Tier.CRITICAL:
            return 1
        elif self == Tier.IMPORTANT:
            return 2
        else:  # NUANCE
            return 3


class FactStatus(str, Enum):
    FOUND = "Found"
    PARTIAL = "Partial"
    MISSING = "Missing"
    CONTRADICTED = "Contradicted"
