# src/core/book.py
from typing import List, Optional
from sqlmodel import Field, Relationship

from src.core.entity import Entity


class Book(Entity, table=True):
    __tablename__: str = "book"

    title: str = Field(index=True, nullable=False)
    author: Optional[str] = None
    source_format: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    source_filename: str = Field(nullable=False)

    table_of_contents: List["TableOfContent"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
