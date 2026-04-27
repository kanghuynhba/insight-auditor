from typing import List, Optional
from src.response.base import BaseSchema


class ChapterSummary(BaseSchema):
    """Used in upload response and book list (lightweight)."""

    id: str
    title: str
    path_id: str
    section_count: int


class BookUploadResponse(BaseSchema):
    """Response for POST /books/upload (SRS §6.2)."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    total_chapters: int
    chapters: List[ChapterSummary]  # summary, not full hierarchy


class BookSummary(BaseSchema):
    """Response for GET /books (list all books)."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    total_chapters: int


class SectionResponse(BaseSchema):
    """Section inside a chapter (no raw_text, no chapter_id)."""

    id: str
    title: str
    path_id: str
    level: int
    word_count: int
    extraction_status: str  # "NONE", "PENDING", "DONE", "ERROR"


class ChapterDetailResponse(BaseSchema):
    """Chapter with its sections (used in full book hierarchy)."""

    id: str
    title: str
    path_id: str
    index: int
    sections: List[SectionResponse]


class BookDetailResponse(BaseSchema):
    """Full book hierarchy (SRS §6.2 GET /books/{book_id})."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    chapters: List[ChapterDetailResponse]
