"""Response DTOs for the /books endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from src.response.base import BaseSchema


class UploadBookResponse(BaseSchema):
    """Response returned after uploading a book file.

    ``status`` is either ``"new"`` (book was ingested) or ``"exists"``
    (book was already present – idempotent upload).
    ``message`` is an optional human-readable annotation (e.g. a reason
    the upload was skipped).
    """

    book_id: str
    status: Literal["new", "exists"]
    message: Optional[str] = None
