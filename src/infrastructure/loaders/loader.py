from abc import ABC, abstractmethod
from pathlib import Path

from src.core.models import Book


class Loader(ABC):
    """Abstract contract for all document parsing strategies."""

    @abstractmethod
    def load(self, path: Path) -> Book:
        """Parses a file and returns a structured Book domain model."""
        pass
