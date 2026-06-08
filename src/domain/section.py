# src/core/section.py
from typing import List, Optional
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field, Relationship
from src.domain.entity import Entity
from src.domain.atomic_fact import AtomicFact
from src.domain.summary import Summary


class Section(Entity, table=True):
    __tablename__: str = "section"

    book_id: Optional[str] = Field(default=None, foreign_key="book.id", index=True)
    title: str = Field(default="", nullable=False)
    level: int = Field(default=0, nullable=False)
    order: int = Field(default=0, nullable=False)
    href: Optional[str] = Field(default=None)
    raw_text: Optional[str] = Field(
        default=None, sa_column=Column(MEDIUMTEXT, nullable=True)
    )
    extraction_status: str = Field(
        default="NONE", nullable=False  # NONE | PENDING | DONE | ERROR
    )

    # Relationships
    book: Optional["Book"] = Relationship(back_populates="sections")
    atomic_facts: List["AtomicFact"] = Relationship(back_populates="section")
    summaries: List["Summary"] = Relationship(back_populates="section")

    @property
    def word_count(self) -> int:
        if not self.raw_text:
            return 0
        return len(self.raw_text.split())
