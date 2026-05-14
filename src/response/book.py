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


class BookDetailResponse(BaseSchema):
    """Full book details with nested TOC (including fake root)."""

    id: str
    title: str
    author: Optional[str]
    source_format: str
    file_url: str
    toc: TocNodeResponse
