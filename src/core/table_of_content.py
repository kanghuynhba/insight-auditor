from typing import List, Optional
from sqlmodel import Field, Relationship
from src.core.entity import Entity
from src.core.section import Section


class TableOfContent(Entity, table=True):
    __tablename__ = "table_of_content"

    book_id: str = Field(foreign_key="book.id", index=True)
    section_id: str = Field(foreign_key="section.id", index=True, unique=True)
    parent_id: Optional[str] = Field(
        default=None, foreign_key="table_of_content.id", index=True
    )
    level: int
    order: int
    title: str

    # Relationships
    book: Optional["Book"] = Relationship(back_populates="toc")
    section: Optional["Section"] = Relationship(
        back_populates="toc_entry",
        sa_relationship_kwargs={
            "lazy": "selectin",  # ← Eager load the Section when the TOC is loaded
        },
    )
    parent: Optional["TableOfContent"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "TableOfContent.id"},
    )
    children: List["TableOfContent"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",  # ← Also eager for children (though not strictly required here)
        },
    )
