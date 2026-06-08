"""Models returned by the ingestion module."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TocNodeModel(BaseModel):
    id: str
    title: str
    level: int
    order: int
    section_id: Optional[str] = None
    href: Optional[str] = None
    children: List["TocNodeModel"] = []

    model_config = {"frozen": True}


class BookSummaryModel(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    source_format: str
    upload_status: str = "ready"

    model_config = {"frozen": True}


class BookDetailModel(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    source_format: str
    upload_status: str = "ready"
    file_url: str
    toc: TocNodeModel

    model_config = {"frozen": True}


class ExtractionResultModel(BaseModel):
    book_id: str
    status: str
    message: Optional[str] = None

    model_config = {"frozen": True}
