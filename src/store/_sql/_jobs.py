from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domain.helpers import now
from src.domain.processing_job import ProcessingJob
from src.store._sql._base import Repository


class ProcessingJobRepository(Repository[ProcessingJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ProcessingJob)

    async def list_queued(self, queue_name: str, limit: int = 10) -> list[ProcessingJob]:
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.queue_name == queue_name,
                ProcessingJob.status == "queued",
            )
            .order_by(ProcessingJob.created_at)
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_filtered(
        self,
        *,
        status: str | None = None,
        queue_name: str | None = None,
        job_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[ProcessingJob]:
        stmt = select(ProcessingJob)
        if status:
            stmt = stmt.where(ProcessingJob.status == status)
        if queue_name:
            stmt = stmt.where(ProcessingJob.queue_name == queue_name)
        if job_type:
            stmt = stmt.where(ProcessingJob.job_type == job_type)
        if resource_type:
            stmt = stmt.where(ProcessingJob.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(ProcessingJob.resource_id == resource_id)

        stmt = stmt.order_by(ProcessingJob.created_at.desc()).limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_stale_running(
        self, queue_name: str, stale_before: datetime, limit: int = 10
    ) -> list[ProcessingJob]:
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.queue_name == queue_name,
                ProcessingJob.status == "running",
                ProcessingJob.updated_at < stale_before,
            )
            .order_by(ProcessingJob.updated_at)
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def find_active(
        self, job_type: str, resource_type: str, resource_id: str
    ) -> Optional[ProcessingJob]:
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.job_type == job_type,
                ProcessingJob.resource_type == resource_type,
                ProcessingJob.resource_id == resource_id,
                ProcessingJob.status.in_(["queued", "running"]),
            )
            .order_by(ProcessingJob.created_at)
            .limit(1)
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def claim_next(self, queue_name: str) -> Optional[ProcessingJob]:
        queued = await self.list_queued(queue_name, limit=1)
        if not queued:
            return None

        job = queued[0]
        timestamp = now()
        stmt = (
            update(ProcessingJob)
            .where(ProcessingJob.id == job.id, ProcessingJob.status == "queued")
            .values(
                status="running",
                attempts=ProcessingJob.attempts + 1,
                started_at=timestamp,
                updated_at=timestamp,
                error=None,
            )
        )
        result = await self.session.exec(stmt)
        if getattr(result, "rowcount", 0) != 1:
            return None
        await self.session.commit()
        return await self.find_by_id(job.id)

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        message: str | None = None,
        error: str | None = None,
        progress: float | None = None,
    ) -> ProcessingJob | None:
        job = await self.find_by_id(job_id)
        if not job:
            return None

        timestamp = now()
        job.status = status
        job.updated_at = timestamp
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        if error is not None:
            job.error = error
        if status == "running" and job.started_at is None:
            job.started_at = timestamp
        if status in {"succeeded", "failed", "cancelled"}:
            job.completed_at = timestamp

        self.session.add(job)
        return job

    async def increment_attempt(self, job_id: str) -> ProcessingJob | None:
        job = await self.find_by_id(job_id)
        if not job:
            return None
        job.attempts += 1
        job.updated_at = now()
        self.session.add(job)
        return job
