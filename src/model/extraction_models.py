# src/model/extraction_models.py
"""Service models for async extraction jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class ExtractionJobModel(BaseModel):
    """Returned immediately when an async extraction job is enqueued.

    Routers convert this to an HTTP 202 Accepted response so the client
    can poll :class:`ExtractionStatusModel` using the ``job_id``.
    """

    job_id: str
    section_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    message: Optional[str] = None

    model_config = {"frozen": True}


class ExtractionStatusModel(BaseModel):
    """Snapshot of an in-flight or completed extraction job."""

    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: Optional[float] = None  # 0.0 – 1.0
    result_summary: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

    model_config = {"frozen": True}
