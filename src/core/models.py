from typing import List, Optional

from pydantic import field_validator
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field, Relationship
from src.core.enums import ExtractionStatus
from src.core.atomic_fact import AtomicFact
from src.core.summary import Summary
from src.core.entity import Entity
from src.infrastructure.loaders.file_type import FileType


class Book(Entity, table=True):
    __tablename__: str = "book"
    title: str = Field(index=True)
    author: Optional[str] = None
    source_format: FileType
    file_path: str
    source_filename: str
    total_chapters: int = 0

    chapters: List["Chapter"] = Relationship(
        back_populates="book", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Book title cannot be empty")
        return v.strip()

    @property
    def all_sections(self) -> List["Section"]:
        return [sec for ch in self.chapters for sec in ch.sections]


class Chapter(Entity, table=True):
    __tablename__: str = "chapter"
    title: str
    path_id: str = Field(index=True)
    index: int = Field(default=0)
    structural_map: Optional[str] = None

    book_id: str = Field(sa_column=Column(ForeignKey("book.id"), index=True))
    book: Optional["Book"] = Relationship(back_populates="chapters")
    sections: List["Section"] = Relationship(
        back_populates="chapter",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    @field_validator("index")
    @classmethod
    def index_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Chapter index must be >= 0")
        return v


class Section(Entity, table=True):
    __tablename__: str = "section"
    path_id: str = Field(index=True)
    parent_path_id: Optional[str] = None
    title: str
    level: int

    # Relationships
    chapter_id: str = Field(sa_column=Column(ForeignKey("chapter.id"), index=True))
    chapter: Optional["Chapter"] = Relationship(back_populates="sections")

    atomic_facts: List["AtomicFact"] = Relationship(back_populates="section")
    summaries: List["Summary"] = Relationship(back_populates="section")

    raw_text: Optional[str] = Field(
        default=None, sa_column=Column(MEDIUMTEXT, nullable=True)
    )

    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.NONE, nullable=False
    )

    @property
    def word_count(self) -> int:
        if not self.raw_text:
            return 0
        return len(self.raw_text.split())
