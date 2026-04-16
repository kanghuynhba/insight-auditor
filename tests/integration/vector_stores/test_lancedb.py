# tests/integration/vector_stores/test_lancedb.py
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel
from src.core.config import get_settings
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.services.ingestion import IngestionService


@pytest.mark.asyncio
async def test_ingestion_pipeline_integration():
    settings = get_settings()
    pdf_path = Path("uploads/ddia.pdf")
    if not pdf_path.exists():
        pytest.skip(f"Test file not found at {pdf_path}")

    # Setup real dependencies
    vector_db = ChunkRepository(settings)
    chunker = NaturalBoundaryChunker(settings)
    loaders = {FileType.Pdf: PdfLoader(settings)}
    db_context = DatabaseContext(str(settings.mariadb_url))

    # Create database schema (tables) – but first drop the obsolete word_count column
    async with db_context.engine.begin() as conn:
        # Drop all tables to start clean (optional, but ensures no leftover columns)
        await conn.run_sync(SQLModel.metadata.drop_all)

        # Ensure the word_count column is removed if it somehow persists
        try:
            await conn.execute(text("ALTER TABLE sections DROP COLUMN word_count"))
        except Exception:
            pass  # Column doesn't exist, that's fine

        await conn.run_sync(SQLModel.metadata.create_all)

    service = IngestionService(
        chunker=chunker,
        loaders=loaders,
        vector_db=vector_db,
        db_context=db_context,
        max_workers=4,
    )

    book = await service.ingest_file(pdf_path, FileType.Pdf)
    assert book.id is not None

    # Verify chunks were stored
    chunks = await vector_db.get_chunks_by_book(book.id)
    assert len(chunks) > 0
    assert "vector" in chunks[0]
    assert len(chunks[0]["vector"]) == 1536

    # Cleanup
    vector_db.delete_book(book.id)
    async with db_context.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_context.engine.dispose()
