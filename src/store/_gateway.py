"""Unified persistence gateway.

The gateway hides concrete SQL repositories and the vector repository behind a
small public interface. Existing repositories remain in place as private
implementation details during migration.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domain import (
    AtomicFact,
    AuditReport,
    Book,
    FactValidationResult,
    ProcessingJob,
    Section,
    Summary,
    TextChunk,
)
from src.domain.helpers import now
from src.store._sql._facts import AtomicFactRepository
from src.store._sql._jobs import ProcessingJobRepository
from src.store._sql._audits import AuditReportRepository
from src.store._sql._books import BookRepository
from src.store._sql._validations import (
    FactValidationResultRepository,
)
from src.store._sql._sections import SectionRepository
from src.store._sql._summaries import SummaryRepository
from src.store._vector._base import VectorRepository
from src.store._models import DeleteBookResultModel

logger = logging.getLogger(__name__)


class Store:
    """One object for SQL and vector persistence operations."""

    def __init__(self, session: AsyncSession, vector_repo: VectorRepository) -> None:
        self.session = session
        self.vector_repo = vector_repo
        self.books = BookRepository(session)
        self.sections = SectionRepository(session)
        self.facts = AtomicFactRepository(session)
        self.jobs = ProcessingJobRepository(session)
        self.summaries = SummaryRepository(session)
        self.audits = AuditReportRepository(session)
        self.validations = FactValidationResultRepository(session)

    async def get_book(self, book_id: str) -> Book | None:
        return await self.books.find_by_id(book_id)

    async def get_all_books(self) -> list[Book]:
        return await self.books.find_all()

    async def save_book(self, book: Book) -> Book:
        return await self.books.save(book)

    async def delete_book(self, book_id: str) -> DeleteBookResultModel:
        book = await self.get_book(book_id)
        if not book:
            raise ValueError(f"Book {book_id!r} not found")

        section_ids = await self._section_ids_for_book(book_id)
        summary_ids = await self._summary_ids_for_sections(section_ids)
        report_ids = await self._report_ids_for_summaries(summary_ids)
        fact_ids = await self._fact_ids_for_sections(section_ids)

        try:
            await self._delete_book_relational_rows(
                book_id=book_id,
                section_ids=section_ids,
                summary_ids=summary_ids,
                report_ids=report_ids,
                fact_ids=fact_ids,
            )
            await self.delete_book_chunks(book_id)
            await self.commit()
        except Exception:
            await self.rollback()
            raise

        self._delete_source_file(book.file_path)
        return DeleteBookResultModel(
            book_id=book_id,
            deleted_sections=len(section_ids),
            deleted_summaries=len(summary_ids),
            deleted_reports=len(report_ids),
            deleted_facts=len(fact_ids),
        )

    async def delete_book_chunks(self, book_id: str) -> None:
        await self.vector_repo.delete_book(book_id)

    async def get_section(self, section_id: str) -> Section | None:
        stmt = select(Section).where(Section.id == section_id)
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def save_section(self, section: Section) -> Section:
        return await self.sections.save(section)

    async def delete_sections_by_book(self, book_id: str) -> None:
        await self.session.exec(delete(Section).where(Section.book_id == book_id))

    async def save_chunks(self, chunks: list[TextChunk]) -> None:
        await self.vector_repo.save_chunks(chunks)

    async def create_processing_job(
        self,
        *,
        job_type: str,
        queue_name: str,
        resource_type: str,
        resource_id: str,
        payload: dict | None = None,
        max_attempts: int = 3,
        message: str | None = None,
    ) -> ProcessingJob:
        job = ProcessingJob(
            job_type=job_type,
            queue_name=queue_name,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            max_attempts=max_attempts,
            message=message,
            progress=0.0,
        )
        await self.jobs.save(job)
        return job

    async def get_processing_job(self, job_id: str) -> ProcessingJob | None:
        return await self.jobs.find_by_id(job_id)

    async def find_active_job(
        self, job_type: str, resource_type: str, resource_id: str
    ) -> ProcessingJob | None:
        return await self.jobs.find_active(job_type, resource_type, resource_id)

    async def list_processing_jobs(
        self,
        *,
        status: str | None = None,
        queue_name: str | None = None,
        job_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[ProcessingJob]:
        return await self.jobs.list_filtered(
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
        stale_before = now() - timedelta(seconds=timeout_seconds)
        stale_jobs = await self.jobs.list_stale_running(queue_name, stale_before, limit)
        recovered: list[ProcessingJob] = []

        for job in stale_jobs:
            if job.attempts < job.max_attempts:
                updated = await self.update_processing_job_status(
                    job.id,
                    "queued",
                    message="Recovered stale running job",
                    error=job.error,
                    progress=job.progress,
                )
            else:
                updated = await self.update_processing_job_status(
                    job.id,
                    "failed",
                    message="Stale running job exceeded max attempts",
                    error=job.error or "Job exceeded stale running timeout",
                    progress=1.0,
                )
            if updated:
                recovered.append(updated)

        return recovered

    async def update_processing_job_status(
        self,
        job_id: str,
        status: str,
        *,
        message: str | None = None,
        error: str | None = None,
        progress: float | None = None,
    ) -> ProcessingJob | None:
        return await self.jobs.update_status(
            job_id,
            status,
            message=message,
            error=error,
            progress=progress,
        )

    async def increment_processing_job_attempt(
        self, job_id: str
    ) -> ProcessingJob | None:
        return await self.jobs.increment_attempt(job_id)

    async def list_queued_jobs(
        self, queue_name: str, limit: int = 10
    ) -> list[ProcessingJob]:
        return await self.jobs.list_queued(queue_name, limit)

    async def claim_next_job(self, queue_name: str) -> ProcessingJob | None:
        return await self.jobs.claim_next(queue_name)

    async def mark_job_running(self, job_id: str) -> ProcessingJob | None:
        return await self.update_processing_job_status(
            job_id, "running", progress=0.0
        )

    async def mark_job_succeeded(
        self, job_id: str, message: str | None = None
    ) -> ProcessingJob | None:
        return await self.update_processing_job_status(
            job_id, "succeeded", message=message, progress=1.0
        )

    async def mark_job_failed(
        self, job_id: str, error: str
    ) -> ProcessingJob | None:
        return await self.update_processing_job_status(
            job_id, "failed", error=error, progress=1.0
        )

    async def search_chunks(
        self, query_vector: list[float], book_id: str, top_k: int = 5
    ) -> list[dict]:
        return await self.vector_repo.search_chunks(query_vector, book_id, top_k)

    async def get_chunks_by_book(self, book_id: str) -> list[TextChunk]:
        return await self.vector_repo.get_chunks_by_book(book_id)

    async def get_chunks_by_section(self, section_id: str) -> list[TextChunk]:
        return await self.vector_repo.get_chunks_by_section(section_id)

    async def get_facts_by_section(self, section_id: str) -> list[AtomicFact]:
        return await self.facts.find_by_section(section_id)

    async def get_fact(self, fact_id: str) -> AtomicFact | None:
        return await self.facts.find_by_id(fact_id)

    async def get_facts_by_chunk(self, chunk_id: str) -> list[AtomicFact]:
        return await self.facts.find_by_chunk(chunk_id)

    async def save_facts(self, facts: list[AtomicFact]) -> list[AtomicFact]:
        return await self.facts.save_all(facts)

    async def delete_facts_by_chunk(self, chunk_id: str) -> None:
        await self.facts.delete_by_chunk(chunk_id)

    async def get_summaries_by_section(self, section_id: str) -> list[Summary]:
        return await self.summaries.get_by_section(section_id)

    async def latest_summary_attempt(self, section_id: str) -> int:
        return await self.summaries.get_latest_attempt(section_id)

    async def save_summary(self, summary: Summary) -> Summary:
        return await self.summaries.save(summary)

    async def save_audit(self, report: AuditReport) -> AuditReport:
        return await self.audits.save(report)

    async def get_audit_report(self, audit_report_id: str) -> AuditReport | None:
        return await self.audits.get_detail(audit_report_id)

    async def get_audit_history_by_section(self, section_id: str) -> list[AuditReport]:
        return await self.audits.get_history_by_section(section_id)

    async def get_validations_by_fact(
        self, atomic_fact_id: str
    ) -> list[FactValidationResult]:
        return await self.validations.get_fact_validation_by_atomic_facts(
            atomic_fact_id
        )

    async def get_validations_by_report(
        self, report_id: str
    ) -> list[FactValidationResult]:
        return await self.validations.get_fact_validation_by_report(report_id)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def _section_ids_for_book(self, book_id: str) -> list[str]:
        stmt = select(Section.id).where(Section.book_id == book_id)
        result = await self.session.exec(stmt)
        return [section_id for section_id in result.all() if section_id]

    async def _summary_ids_for_sections(self, section_ids: list[str]) -> list[str]:
        if not section_ids:
            return []
        stmt = select(Summary.id).where(Summary.section_id.in_(section_ids))
        result = await self.session.exec(stmt)
        return list(result.all())

    async def _report_ids_for_summaries(self, summary_ids: list[str]) -> list[str]:
        if not summary_ids:
            return []
        stmt = select(AuditReport.id).where(AuditReport.summary_id.in_(summary_ids))
        result = await self.session.exec(stmt)
        return list(result.all())

    async def _fact_ids_for_sections(self, section_ids: list[str]) -> list[str]:
        if not section_ids:
            return []
        stmt = select(AtomicFact.id).where(AtomicFact.section_id.in_(section_ids))
        result = await self.session.exec(stmt)
        return list(result.all())

    async def _delete_book_relational_rows(
        self,
        book_id: str,
        section_ids: list[str],
        summary_ids: list[str],
        report_ids: list[str],
        fact_ids: list[str],
    ) -> None:
        if report_ids:
            await self.session.exec(
                delete(FactValidationResult).where(
                    FactValidationResult.report_id.in_(report_ids)
                )
            )
        if fact_ids:
            await self.session.exec(
                delete(FactValidationResult).where(
                    FactValidationResult.atomic_fact_id.in_(fact_ids)
                )
            )
            await self.session.exec(delete(AtomicFact).where(AtomicFact.id.in_(fact_ids)))
        if report_ids:
            await self.session.exec(
                delete(AuditReport).where(AuditReport.id.in_(report_ids))
            )
        if summary_ids:
            await self.session.exec(delete(Summary).where(Summary.id.in_(summary_ids)))

        if section_ids:
            await self.session.exec(delete(Section).where(Section.id.in_(section_ids)))

        await self.session.exec(delete(Book).where(Book.id == book_id))

    @staticmethod
    def _delete_source_file(file_path: str) -> None:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete source file %s", file_path, exc_info=True)
