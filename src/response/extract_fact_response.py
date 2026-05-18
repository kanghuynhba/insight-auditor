"""Response DTO for the POST /sections/{section_id}/extract-facts endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from src.response.base import BaseSchema


class ExtractFactResponse(BaseSchema):
    """HTTP 202 body returned immediately after an extraction job is enqueued.

    The client can store ``job_id`` and poll a status endpoint (when available)
    to track progress.  ``status`` will always be ``"pending"`` at creation time
    and may transition to ``"running"``, ``"completed"``, or ``"failed"``
    while the background task executes.
    """

    job_id: str
    section_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    message: Optional[str] = None
