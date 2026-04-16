# tests/integration/test_full_pipeline.py
import hashlib
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel
from src.core.config import get_settings
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.book_repo import BookRepository
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.services.extraction import ExtractionService
from src.services.ingestion import IngestionService


def get_deterministic_book_id(pdf_path: Path) -> str:
    return hashlib.md5(str(pdf_path.absolute()).encode()).hexdigest()[:16]


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_integration():
    settings = get_settings()
    pdf_path = Path("uploads/ddia.pdf")
    if not pdf_path.exists():
        pytest.skip(f"Test file not found at {pdf_path}")

    # 1. Setup Infrastructure
    vector_db = ChunkRepository(settings)
    chunker = NaturalBoundaryChunker(settings)
    loaders = {FileType.Pdf: PdfLoader(settings)}
    db_context = DatabaseContext(str(settings.mariadb_url))

    # Create database schema
    async with db_context.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    ingestion_service = IngestionService(
        chunker=chunker,
        loaders=loaders,
        vector_db=vector_db,
        db_context=db_context,
    )

    # 2. Ingestion
    print("\n--- Starting ingestion ---")
    book = await ingestion_service.ingest_file(pdf_path, FileType.Pdf)
    print(f"Ingested book: {book.title}, sections: {len(book.all_sections)}")

    # Verify LanceDB Chunks
    chunks = await vector_db.get_chunks_by_book(book.id)
    assert len(chunks) > 0, "No chunks were stored in LanceDB"

    # 3. Extraction Setup
    llm_config = settings.litellm_config
    llm = LiteLLMCompletion(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        api_base=llm_config["base_url"],
        api_version=llm_config.get("api_version"),
    )

    extraction_service = ExtractionService(
        llm=llm,
        db_context=db_context,
        concurrency=4,
    )

    # 4. Extraction Execution
    print("\n--- Starting fact extraction ---")
    all_facts = await extraction_service.extract_facts_for_book(book.id)
    print(f"Extracted {len(all_facts)} atomic facts")

    # 5. Validation using Repositories
    async with db_context.get_session() as session:
        book_repo = BookRepository(session)
        saved_book = await book_repo.find_by_id(book.id)
        assert saved_book is not None, "Book was not found in MariaDB"
        assert saved_book.title == book.title

        # Count atomic facts
        result = await session.execute(text("SELECT COUNT(*) FROM atomicfact"))
        fact_count = result.scalar()
        assert fact_count > 0, "No facts found in MariaDB atomicfact table"

    print("Test completed successfully (data verified in LanceDB and MariaDB).")

    # Cleanup
    vector_db.delete_book(book.id)
    async with db_context.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_context.engine.dispose()
