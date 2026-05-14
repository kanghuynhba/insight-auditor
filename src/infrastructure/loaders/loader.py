from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.core.toc_node import TocNode


@dataclass(frozen=True)
class ExtractedBookData:
    """
    Typed container for data extracted from a file.
    Prevents 'stringly-typed' dictionaries and 'unknown unknowns'.
    """

    title: str
    author: Optional[str]
    toc_root: TocNode


class Loader(ABC):
    """Abstract contract for all document parsing strategies."""

    @abstractmethod
    def get_stable_id(self, path: Path) -> str:
        """Computes a stable ID for the given file, used to prevent duplicates."""
        pass

    @abstractmethod
    def extract_raw(self, path: Path) -> ExtractedBookData:
        """Parses a file and returns a structured Book domain model."""
        pass
