#: AsyncSession infrastructure/chunking/chunker.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.domain.section import Section
from src.domain.config import Settings
from src.domain.text_chunk import TextChunk


@dataclass(frozen=True)
class ChunkContext:
    book_id: str
    book_title: str = ""
    chapter_title: str = ""
    section_title: str = ""


class Chunker(ABC):

    @abstractmethod
    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def chunk_section(
        self, section: Section, context: ChunkContext | None = None
    ) -> list[TextChunk]:
        pass
