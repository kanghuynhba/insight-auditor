# src/core/book.py
from typing import Any, List, Optional
from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship

from src.domain.entity import Entity


class Book(Entity, table=True):
    __tablename__: str = "book"

    title: str = Field(index=True, nullable=False)
    author: Optional[str] = None
    source_format: str = Field(nullable=False)
    file_path: str = Field(nullable=False)
    source_filename: str = Field(nullable=False)
    upload_status: str = Field(default="uploaded", nullable=False, index=True)
    table_of_content: List[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )

    sections: List["Section"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
