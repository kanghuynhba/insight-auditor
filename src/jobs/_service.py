from src.domain.processing_job import ProcessingJob
from src.jobs._constants import (
    JOB_AUDIT_SUMMARY,
    JOB_EXTRACT_FACTS,
    JOB_PARSE_BOOK,
    JOB_QUEUE_MAP,
    JOB_RESOURCE_MAP,
)
from src.store import Store


class JobService:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def enqueue(
        self,
        *,
        job_type: str,
        resource_id: str,
        payload: dict | None = None,
        max_attempts: int = 3,
        dedupe_active: bool = True,
    ) -> ProcessingJob:
        queue_name = JOB_QUEUE_MAP[job_type]
        resource_type = JOB_RESOURCE_MAP[job_type]
        if dedupe_active:
            active_job = await self.find_active_job(
                job_type=job_type,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            if active_job:
                await self.store.commit()
                return active_job

        job = await self.store.create_processing_job(
            job_type=job_type,
            queue_name=queue_name,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            max_attempts=max_attempts,
        )
        await self.store.commit()
        return job

    async def find_active_job(
        self, job_type: str, resource_type: str, resource_id: str
    ) -> ProcessingJob | None:
        return await self.store.find_active_job(job_type, resource_type, resource_id)

    async def enqueue_parse_book(self, book_id: str) -> ProcessingJob:
        return await self.enqueue(job_type=JOB_PARSE_BOOK, resource_id=book_id)

    async def enqueue_extract_facts(
        self, section_id: str, *, force: bool = False
    ) -> ProcessingJob:
        return await self.enqueue(
            job_type=JOB_EXTRACT_FACTS,
            resource_id=section_id,
            payload={"force": force},
            dedupe_active=not force,
        )

    async def enqueue_audit_summary(self, summary_id: str) -> ProcessingJob:
        return await self.enqueue(job_type=JOB_AUDIT_SUMMARY, resource_id=summary_id)

    async def get_job(self, job_id: str) -> ProcessingJob | None:
        return await self.store.get_processing_job(job_id)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        queue_name: str | None = None,
        job_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[ProcessingJob]:
        return await self.store.list_processing_jobs(
            status=status,
            queue_name=queue_name,
            job_type=job_type,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )

    async def recover_stale_running_jobs(
        self, queue_name: str, timeout_seconds: int, limit: int = 10
    ) -> list[ProcessingJob]:
        jobs = await self.store.recover_stale_running_jobs(
            queue_name, timeout_seconds, limit
        )
        await self.store.commit()
        return jobs
