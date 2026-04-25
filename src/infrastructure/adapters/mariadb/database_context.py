# src/infrastructure/adapters/mariadb/database_context.py

from contextlib import asynccontextmanager
from typing import Dict, Type, TypeVar

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.fact_validation import FactValidation
from src.infrastructure.persistence.fact_validation_repo import FactValidationRepository
from src.core.audit import AuditReport
from src.core.summary import Summary
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from infrastructure.persistence.summary_repo import SummaryRepository
from src.core.atomic_fact import AtomicFact

# Import Entities
from src.core.entity import Entity
from src.core.models import Book, Chapter, Section
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.base_repository import Repository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.chapter_repo import ChapterRepository
from src.infrastructure.persistence.section_repo import SectionRepository

T = TypeVar("T", bound=Entity)


class DatabaseContext:
    _REPO_MAP: Dict[Type[Entity], Type[Repository]] = {
        Book: BookRepository,
        Chapter: ChapterRepository,
        Section: SectionRepository,
        AtomicFact: AtomicFactRepository,
        Summary: SummaryRepository,
        AuditReport: AuditReportRepository,
        FactValidation: FactValidationRepository,
    }

    def __init__(self, connection_url: str):
        # It manages connections, timeouts, and the pool size.
        self.engine = create_async_engine(
            connection_url,
            pool_size=30,
            max_overflow=50,
            pool_timeout=30,
            pool_recycle=3600,
        )

        # This is your 'Session Factory' (Connection Factory)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self):
        async with self.session_factory() as session:
            yield session

    def get_repository(
        self, session: AsyncSession, entity_model: Type[T]
    ) -> Repository[T]:
        """
        Dynamically returns the specialized repository for a given entity model.
        Falls back to the generic Repository if no specialized class is mapped.
        """
        repo_class = self._REPO_MAP.get(entity_model, Repository)
        return (
            repo_class(session)
            if repo_class is not Repository
            else Repository(session, entity_model)
        )

    async def initialize_database(self) -> None:
        """Create all tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
