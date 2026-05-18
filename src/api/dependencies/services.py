# src/api/dependencies/services.py
"""FastAPI dependency providers for service layer objects.

All providers are **synchronous** factory functions that FastAPI calls per
request (or per-dependency lifetime, depending on the scope).

Changes from the original
-------------------------
* ``get_book_extraction_service`` now wires up the refactored
  :class:`~src.services.book_extraction_service.BookExtractionService`.
* ``get_facts_extraction_service`` no longer needs ``BackgroundTasks`` in the
  constructor – the router passes it directly to ``start_extraction``.
* ``get_audit_service`` remains identical in shape but now returns the
  refactored service.
* ``get_section_repo`` is exported from this module (the router imports it
  from here so it has one consistent import point).
"""

from __future__ import annotations

from fastapi import Depends

from src.api.dependencies.llm import get_llm_completion, get_llm_embedding
from src.api.dependencies.storages import (
    get_atomic_fact_repo,
    get_audit_report_repo,
    get_book_repo,
    get_section_repo,
    get_summary_repo,
)
from src.api.dependencies.vector import get_vector_repo
from src.core.config import get_settings
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.llm.embedding.lite_llm_embedding import LiteLLMEmbedding
from src.infrastructure.loaders.epub_loader import EpubLoader
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.section_repo import SectionRepository
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.services.audit_service import AuditService
from src.services.book_extraction_service import BookExtractionService
from src.services.chunk_ingestion_service import ChunkIngestionService
from src.services.facts_extraction_service import FactsExtractionService
from src.services.facts_read_service import FactsReadService
from src.services.toc_service import TOCService

settings = get_settings()

# Re-export so routers can use a single import path
__all__ = [
    "get_book_repo",
    "get_section_repo",
    "get_book_extraction_service",
    "get_toc_service",
    "get_chunk_ingestion_service",
    "get_facts_extraction_service",
    "get_facts_read_service",
    "get_audit_service",
]


# ---------------------------------------------------------------------------
# Book services
# ---------------------------------------------------------------------------


def get_book_extraction_service(
    book_repo: BookRepository = Depends(get_book_repo),
) -> BookExtractionService:
    """Provide a :class:`~src.services.book_extraction_service.BookExtractionService`.

    Loaders are constructed once per request; they are cheap stateless objects.
    """
    loaders = {
        FileType.Pdf: PdfLoader(settings),
        FileType.Epub: EpubLoader(settings),
    }
    return BookExtractionService(loaders, book_repo)


def get_toc_service() -> TOCService:
    """Provide a :class:`~src.services.toc_service.TOCService` (stateless)."""
    return TOCService()


# ---------------------------------------------------------------------------
# Chunk ingestion (unchanged)
# ---------------------------------------------------------------------------


def get_chunk_ingestion_service(
    chunker: NaturalBoundaryChunker = Depends(lambda: NaturalBoundaryChunker(settings)),
    embedder: LiteLLMEmbedding = Depends(get_llm_embedding),
    vector_repo: VectorRepository = Depends(get_vector_repo),
    toc_service: TOCService = Depends(get_toc_service),
) -> ChunkIngestionService:
    """Provide a :class:`~src.services.chunk_ingestion_service.ChunkIngestionService`."""
    return ChunkIngestionService(chunker, embedder, vector_repo, toc_service)


# ---------------------------------------------------------------------------
# Facts extraction (refactored – no BackgroundTasks in constructor)
# ---------------------------------------------------------------------------


def get_facts_extraction_service(
    llm: LiteLLMCompletion = Depends(get_llm_completion),
    chunker: NaturalBoundaryChunker = Depends(lambda: NaturalBoundaryChunker(settings)),
    section_repo: SectionRepository = Depends(get_section_repo),
    fact_repo: AtomicFactRepository = Depends(get_atomic_fact_repo),
) -> FactsExtractionService:
    """Provide a :class:`~src.services.facts_extraction_service.FactsExtractionService`.

    ``BackgroundTasks`` is **not** injected here; the router passes it as an
    argument to ``start_extraction`` on a per-request basis.
    """
    return FactsExtractionService(
        llm=llm,
        chunker=chunker,
        section_repo=section_repo,
        fact_repo=fact_repo,
    )


# ---------------------------------------------------------------------------
# Facts read service
# ---------------------------------------------------------------------------


def get_facts_read_service(
    fact_repo: AtomicFactRepository = Depends(get_atomic_fact_repo),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> FactsReadService:
    """Provide a :class:`~src.services.facts_read_service.FactsReadService`."""
    return FactsReadService(fact_repo, section_repo)


# ---------------------------------------------------------------------------
# Audit service
# ---------------------------------------------------------------------------


def get_audit_service(
    llm: LiteLLMCompletion = Depends(get_llm_completion),
    fact_repo: AtomicFactRepository = Depends(get_atomic_fact_repo),
    summary_repo: SummaryRepository = Depends(get_summary_repo),
    audit_repo: AuditReportRepository = Depends(get_audit_report_repo),
) -> AuditService:
    """Provide a :class:`~src.services.audit_service.AuditService`."""
    return AuditService(llm, fact_repo, summary_repo, audit_repo)
