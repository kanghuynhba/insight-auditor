from datetime import datetime
from typing import Any, Optional

from src.domain.processing_job import ProcessingJob
from src.response.base import BaseSchema


class ProcessingJobResponse(BaseSchema):
    id: str
    job_type: str
    queue_name: str
    status: str
    resource_type: str
    resource_id: str
    payload: Optional[dict[str, Any]] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime

    @classmethod
    def from_job(cls, job: ProcessingJob) -> "ProcessingJobResponse":
        return cls(
            id=job.id,
            job_type=job.job_type,
            queue_name=job.queue_name,
            status=job.status,
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            payload=job.payload,
            progress=job.progress,
            message=job.message,
            error=job.error,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            updated_at=job.updated_at,
        )
