from collections.abc import AsyncGenerator
from fastapi import Depends
from src.core.task import Task
from src.infrastructure.persistence.task_repo import TaskRepository
from src.api.dependencies.database import get_db_context
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from sqlmodel.ext.asyncio.session import AsyncSession

from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.chapter_repo import ChapterRepository
from src.infrastructure.persistence.fact_validation_repo import (
    FactValidationResultRepository,
)
from src.infrastructure.persistence.section_repo import SectionRepository
from src.infrastructure.persistence.summary_repo import SummaryRepository


async def get_session(
    db: DatabaseContext = Depends(get_db_context),
) -> AsyncGenerator[AsyncSession, None]:
    async with db.get_session() as session:
        yield session


def get_book_repo(session: AsyncSession = Depends(get_session)) -> BookRepository:
    return BookRepository(session)


def get_chapter_repo(session: AsyncSession = Depends(get_session)) -> ChapterRepository:
    return ChapterRepository(session)


def get_section_repo(session: AsyncSession = Depends(get_session)) -> SectionRepository:
    return SectionRepository(session)


def get_atomic_fact_repo(
    session: AsyncSession = Depends(get_session),
) -> AtomicFactRepository:
    return AtomicFactRepository(session)


def get_summary_repo(session: AsyncSession = Depends(get_session)) -> SummaryRepository:
    return SummaryRepository(session)


def get_audit_report_repo(
    session: AsyncSession = Depends(get_session),
) -> AuditReportRepository:
    return AuditReportRepository(session)


def get_fact_validation_repo(
    session: AsyncSession = Depends(get_session),
) -> FactValidationResultRepository:
    return FactValidationResultRepository(session)


async def get_task_repo(session: AsyncSession = Depends(get_session)) -> TaskRepository:
    return TaskRepository(session)
