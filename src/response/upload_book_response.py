"""Response DTOs for the /books endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from src.response.base import BaseSchema


class UploadBookResponse(BaseSchema):
    """Response returned after uploading a book file.

    ``status`` is ``"uploaded"`` for queued parse jobs. ``"new"`` and
    ``"exists"`` are kept for compatibility with older ingestion responses.
    ``message`` is an optional human-readable annotation (e.g. a reason
    the upload was skipped).
    """

    book_id: str
    status: Literal["uploaded", "new", "exists"]
    job_id: Optional[str] = None
    message: Optional[str] = None
