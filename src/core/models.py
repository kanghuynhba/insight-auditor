# src/core/models.py

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from src.core.atomic_fact import AtomicFact
from src.core.chapter import Chapter
from src.core.enums import FileFormat
from src.core.helpers import _new_id, _now


class Book(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str
    author: Optional[str] = None
    source_format: FileFormat
    file_path: Path
    source_filename: str
    total_chapters: int = 0
    chapters: list[Chapter] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=_now)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Book title cannot be empty")
        return v.strip()

    model_config = {"frozen": True}


class Chapter(BaseModel):
    id: str = Field(default_factory=_new_id)
    book_id: str
    title: str
    # If there are Section inside Chapter
    path_id: str
    index: int
    sections: list[Section] = Field(default_factory=list)
    # LLM-generated of this chapter
    structural_map: str | None = None

    @field_validator("index")
    @classmethod
    def index_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Chapter index must be >= 0")
        return v

    model_config = {"frozen": True}


class Section(BaseModel):
    id: str = Field(default_factory=_new_id)
    chapter_id: str
    # "001.002.003"
    path_id: str
    # "001.002"
    parent_path_id: str | None
    title: str
    raw_text: str
    atomic_facts: list[AtomicFact]
    level: int

    word_count: int = 0

    # TODO Need to understand this
    @model_validator(mode="after")
    def compute_word_count(self) -> "Section":
        if self.word_count == 0 and self.raw_text:
            count = len(self.raw_text.split())
            # Standard assignment fails on frozen models, so we bypass:
            object.__setattr__(self, "word_count", count)
        return self

    model_config = {"frozen": True}
