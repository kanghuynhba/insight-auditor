# src/response/book.py
from typing import List, Optional
from src.response.toc_node_response import TocNodeResponse
from src.response.base import BaseSchema


class BookSummary(BaseSchema):
    """Book summary for list view."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    upload_status: str = "ready"


class BookDetailResponse(BaseSchema):
    """Full book details with nested TOC (including fake root)."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    upload_status: str = "ready"
    file_url: str
    toc: TocNodeResponse


class DeleteBookResponse(BaseSchema):
    """Response returned after deleting a book and derived data."""

    book_id: str
    deleted_sections: int
    deleted_summaries: int
    deleted_reports: int
    deleted_facts: int
