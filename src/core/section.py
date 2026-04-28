from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field, Relationship
from src.core.helpers import word_count
from src.core.enums import ExtractionStatus
from src.core.atomic_fact import AtomicFact
from src.core.summary import Summary
from src.core.entity import Entity


class Section(Entity, table=True):
    __tablename__: str = "section"
    book_id: str = Field(foreign_key="book.id", index=True)
    path_id: str = Field(index=True)
    parent_path_id: Optional[str] = None
    title: str
    level: int

    toc_entry: Optional["TableOfContent"] = Relationship(back_populates="section")

    # Relationships
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
        return word_count(self.raw_text)
