# src/core/enums.py

from enum import Enum
from src.services.exceptions import UnsupportedFormatError

class Tier(IntEnum):
    CRITICAL = 3,
    IMPORTANT = 2,
    NUANCE = 1,

class FactStatus(str, Enum):
    FOUND = "Found"
    PARTIAL = "Partial"
    MISSING = "Missing"
    CONTRADICTED = "Contradicted"

class FileFormat(str, Enum):
    PDF="pdf"
    EPUB="epub"

    @classmethod
    def from_filename(cls, filename: str) -> "FileFormat":
        if not filename:
            raise UnsupportedFormatError("Filename is missing!")

        ext = filename.split(".")[-1].lower()

        try:
            return cls(ext)
        except ValueError:
            raise UnsupportedFormatError(
                f"Unsupport file format: '.{ext}'. Only PDF and EPUB are allowed!"
            )


