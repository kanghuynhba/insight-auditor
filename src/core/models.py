# src/core/models.py

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from src.core.helpers import new_id, now
from src.infrastructure.loaders.file_type import FileType


class Section(BaseModel):
    id: str = Field(default_factory=new_id)
    chapter_id: str
    path_id: str
    parent_path_id: Optional[str] = None
    title: str
    raw_text: str
    atomic_facts: List[Any] = Field(
        default_factory=list
    )  # Replace 'any' with AtomicFact
    level: int
    word_count: int = 0

    @model_validator(mode="after")
    def compute_word_count(self) -> "Section":
        if self.word_count == 0 and self.raw_text:
            count = len(self.raw_text.split())
            # object.__setattr__ is the correct way to bypass the 'frozen' restriction
            object.__setattr__(self, "word_count", count)
        return self

    model_config = {"frozen": True}


class Chapter(BaseModel):
    id: str = Field(default_factory=new_id)
    book_id: str
    title: str
    path_id: str
    index: int
    sections: List[Section] = Field(default_factory=list)
    structural_map: Optional[str] = None

    @field_validator("index")
    @classmethod
    def index_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Chapter index must be >= 0")
        return v

    model_config = {"frozen": True}


class Book(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    author: Optional[str] = None
    source_format: FileType
    file_path: Path
    source_filename: str
    total_chapters: int = 0
    chapters: List[Chapter] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=now)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Book title cannot be empty")
        return v.strip()

    @property
    def all_sections(self) -> List[Section]:
        """Flattens the chapter-section hierarchy"""
        return [sec for ch in self.chapters for sec in ch.sections]

    model_config = {"frozen": True}


Section.model_rebuild()
Chapter.model_rebuild()
Book.model_rebuild()
