from fastapi import Depends
from src.infrastructure.loaders.epub_loader import EpubLoader
from src.infrastructure.persistence.task_repo import TaskRepository
from src.services.task_service import TaskService
from src.core.config import get_settings
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.llm.embedding.lite_llm_embedding import LiteLLMEmbedding
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.section_repo import SectionRepository
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.infrastructure.persistence.audit_report_repo import AuditReportRepository
from src.services.book_extraction_service import BookExtractionService
from src.services.chunk_ingestion_service import ChunkIngestionService
from src.services.facts_extraction_service import FactsExtractionService
from src.services.audit_service import AuditService
from src.services.toc_service import TOCService
from src.api.dependencies.llm import get_llm_completion, get_llm_embedding
from src.api.dependencies.storages import (
    get_book_repo,
    get_section_repo,
    get_atomic_fact_repo,
    get_audit_report_repo,
    get_summary_repo,
    get_task_repo,
    get_section_repo,
)
from src.api.dependencies.vector import get_vector_repo

settings = get_settings()


def get_book_extraction_service(
    book_repo: BookRepository = Depends(get_book_repo),
) -> BookExtractionService:
    loaders = {
        FileType.Pdf: PdfLoader(settings),
        FileType.Epub: EpubLoader(settings),
    }
    return BookExtractionService(loaders, book_repo)


def get_toc_service():
    return TOCService()


def get_chunk_ingestion_service(
    chunker: NaturalBoundaryChunker = Depends(lambda: NaturalBoundaryChunker(settings)),
    embedder: LiteLLMEmbedding = Depends(get_llm_embedding),
    vector_repo: VectorRepository = Depends(get_vector_repo),
    toc_service: TOCService = Depends(get_toc_service),
) -> ChunkIngestionService:
    return ChunkIngestionService(chunker, embedder, vector_repo, toc_service)


def get_facts_extraction_service(
    llm: LiteLLMCompletion = Depends(get_llm_completion),
    section_repo: SectionRepository = Depends(get_section_repo),
    fact_repo: AtomicFactRepository = Depends(get_atomic_fact_repo),
    vector_repo: VectorRepository = Depends(get_vector_repo),
) -> FactsExtractionService:
    return FactsExtractionService(llm, section_repo, fact_repo, vector_repo)


def get_audit_service(
    llm: LiteLLMCompletion = Depends(get_llm_completion),
    fact_repo: AtomicFactRepository = Depends(get_atomic_fact_repo),
    summary_repo: SummaryRepository = Depends(get_summary_repo),
    audit_repo: AuditReportRepository = Depends(get_audit_report_repo),
) -> AuditService:
    return AuditService(llm, fact_repo, summary_repo, audit_repo)


def get_task_service(task_repo: TaskRepository = Depends(get_task_repo)):
    return TaskService(task_repo)
