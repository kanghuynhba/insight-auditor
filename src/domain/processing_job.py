from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field

from src.domain.entity import Entity
from src.domain.helpers import now


class ProcessingJob(Entity, table=True):
    __tablename__ = "processing_job"

    job_type: str = Field(nullable=False, index=True)
    queue_name: str = Field(nullable=False, index=True)
    status: str = Field(default="queued", nullable=False, index=True)
    resource_type: str = Field(nullable=False, index=True)
    resource_id: str = Field(nullable=False, index=True)
    payload: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    progress: Optional[float] = Field(default=None, nullable=True)
    message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    attempts: int = Field(default=0, nullable=False)
    max_attempts: int = Field(default=3, nullable=False)
    started_at: Optional[datetime] = Field(default=None, nullable=True)
    completed_at: Optional[datetime] = Field(default=None, nullable=True)
    updated_at: datetime = Field(default_factory=now, nullable=False)
