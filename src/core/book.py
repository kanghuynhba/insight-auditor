# src/core/book.py

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
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


Book.model_rebuild()
