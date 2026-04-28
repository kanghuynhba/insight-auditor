from typing import Dict, Type, TypeVar
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.entity import Entity
from src.core.book import Book
from src.core.section import Section
from src.core.table_of_content import TableOfContent
from src.core.atomic_fact import AtomicFact
from src.core.summary import Summary
from src.core.audit import AuditReport
from src.core.fact_validation import FactValidationResult

from src.infrastructure.persistence.base_repository import Repository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.section_repo import SectionRepository
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.infrastructure.persistence.fact_validation_repo import (
    FactValidationResultRepository,
)

T = TypeVar("T", bound=Entity)


class RepositoryFactory:
    _REPO_MAP: Dict[Type[Entity], Type[Repository]] = {
        Book: BookRepository,
        TableOfContent: TableOfContentRepository,
        Section: SectionRepository,
        AtomicFact: AtomicFactRepository,
        Summary: SummaryRepository,
        AuditReport: AuditReportRepository,
        FactValidationResult: FactValidationResultRepository,
    }

    @classmethod
    def create(cls, session: AsyncSession, entity_model: Type[T]) -> Repository[T]:
        """Returns the specialized repository for an entity, or a generic one."""
        repo_class = cls._REPO_MAP.get(entity_model)

        if repo_class:
            return repo_class(session, entity_model)

        # Fallback to generic repository for simple CRUD
        return Repository(session, entity_model)
