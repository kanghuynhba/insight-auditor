#: AsyncSession infrastructure/chunking/chunker.py
from abc import ABC, abstractmethod
from typing import Any

from src.core.models import Section
from src.core.config import Settings
from src.core.text_chunk import TextChunk


class Chunker(ABC):

    @abstractmethod
    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def chunk_section(self, section: Section) -> list[TextChunk]:
        pass
