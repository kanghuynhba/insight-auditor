from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from src.core.helpers import _new_id


class TextChunk(BaseModel):
    """Represents a strictly sized slice of text ready for vector embedding."""

    id: str = Field(default_factory=_new_id)
    book_id: str
    section_id: str
    path_id: str
    text: str
    chunk_index: int  # position within the section
    chunk_level: str  # "paragraph" | "sentence" | "word_window"
    word_count: int = 0
    context_text: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())
        if not self.word_count:
            self.word_count = len(self.text.split())

    @property
    def metadata(self) -> dict:
        """ChromaDB metadata dict"""
        return {
            "book_id": self.book_id,
            "section_id": self.section_id,
            "path_id": self.path_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "chunk_level": self.chunk_level,
            "context_text": self.context_text,
        }

    model_config = {"frozen": True}
