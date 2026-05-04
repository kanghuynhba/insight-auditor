# src/core/table_of_content.py
from typing import Optional
from sqlmodel import Field, Relationship
from src.core.entity import Entity


class TableOfContent(Entity, table=True):
    __tablename__: str = "table_of_content"

    title: str = Field(nullable=False)
    book_id: str = Field(foreign_key="book.id", nullable=False, index=True)
    section_id: Optional[str] = Field(
        default=None, foreign_key="section.id", unique=True, index=True
    )
    # 1=chapter, 2=section, etc
    level: int = Field(nullable=False)
    # reading order for DFS reconstruction
    order: int = Field(nullable=False)

    # Relationships (foreign keys are auto-created)
    book: Optional["Book"] = Relationship(back_populates="table_of_contents")
    section: Optional["Section"] = Relationship(
        back_populates="table_of_content",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "single_parent": True,
            "lazy": "selectin",
        },
    )
