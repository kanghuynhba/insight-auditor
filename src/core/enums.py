# src/core/enums.py

from enum import Enum, IntEnum

from src.core.exceptions import UnsupportedFormatError


class Tier(IntEnum):
    CRITICAL = 3
    IMPORTANT = 2
    NUANCE = 1


class FactStatus(str, Enum):
    FOUND = "Found"
    PARTIAL = "Partial"
    MISSING = "Missing"
    CONTRADICTED = "Contradicted"
