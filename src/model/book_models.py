# src/model/book_models.py
"""Service models for books – the immutable internal API contract between services and routers."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.model.toc_node_model import TocNodeModel


class BookSummaryModel(BaseModel):
    """Lightweight book representation used in list views."""

    id: str
    title: str
    author: Optional[str] = None
    source_format: str

    model_config = {"frozen": True}


class BookDetailModel(BaseModel):
    """Full book detail including the TOC tree and download URL."""

    id: str
    title: str
    author: Optional[str] = None
    source_format: str
    file_url: str
    toc: TocNodeModel

    model_config = {"frozen": True}


class ExtractionResultModel(BaseModel):
    """Result of a metadata-extraction attempt.

    ``status`` is ``"new"`` when the book was just created or ``"exists"``
    when it was already present in the database.
    """

    book_id: str
    status: str  # "new" | "exists"
    message: Optional[str] = None

    model_config = {"frozen": True}
