# src/core/section.py
from typing import List, Optional
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field, Relationship
from src.core.entity import Entity
from src.core.atomic_fact import AtomicFact
from src.core.summary import Summary
from src.core.table_of_content import TableOfContent


class Section(Entity, table=True):
    __tablename__: str = "section"

    raw_text: Optional[str] = Field(
        default=None, sa_column=Column(MEDIUMTEXT, nullable=True)
    )
    extraction_status: str = Field(
        default="NONE", nullable=False  # NONE | PENDING | DONE | ERROR
    )

    # Relationships
    atomic_facts: List["AtomicFact"] = Relationship(back_populates="section")
    summaries: List["Summary"] = Relationship(back_populates="section")
    table_of_content: Optional["TableOfContent"] = Relationship(
        back_populates="section"
    )

    @property
    def word_count(self) -> int:
        if not self.raw_text:
            return 0
        return len(self.raw_text.split())
