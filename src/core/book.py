from typing import List, Optional
from pydantic import field_validator
from sqlmodel import Field, Relationship
from src.core.entity import Entity
from src.core.table_of_content import TableOfContent
from src.core.section import Section
from src.infrastructure.loaders.file_type import FileType


class Book(Entity, table=True):
    __tablename__: str = "book"
    title: str = Field(index=True)
    author: Optional[str] = None
    source_format: FileType
    file_path: str
    source_filename: str
    total_chapters: int = 0

    # Relationship – cascade inside sa_relationship_kwargs
    toc: List["TableOfContent"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",  # Eager load entire TOC tree
            "order_by": "TableOfContent.order",
        },
    )

    @property
    def all_sections(self) -> List["Section"]:
        return [t.section for t in self.toc if t.section]

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Book title cannot be empty")
        return v.strip()
