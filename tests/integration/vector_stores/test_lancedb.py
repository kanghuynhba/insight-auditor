import os
from pathlib import Path

import pytest
from lancedb.embeddings import EmbeddingFunctionRegistry
from src.core.config import get_settings
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.databases.vectors.lancedb_repo import LanceDBRepository
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.services.ingestion import IngestionService


def test_ingestion_pipeline_integration():
    settings = get_settings()
    # No registry setup needed anymore

    vector_db = LanceDBRepository(settings)
    chunker = NaturalBoundaryChunker(settings)
    loaders = {FileType.Pdf: PdfLoader(settings)}
    service = IngestionService(chunker=chunker, loaders=loaders, vector_db=vector_db)

    pdf_path = Path("uploads/ai_engineering.pdf")
    if not pdf_path.exists():
        pytest.skip(f"Test file not found at {pdf_path}")

    loader = loaders[FileType.Pdf]
    book = loader.load(pdf_path)
    print(f"\n📖 Book loaded: '{book.title}' — {len(book.all_sections)} sections")

    book = service.ingest_file(pdf_path, FileType.Pdf)

    df = vector_db._table.to_pandas()
    print(f"📊 Chunks stored: {len(df)}")
    assert len(df) > 0
    assert "vector" in df.columns
    assert len(df["vector"].iloc[0]) == 1536
    print("✅ Done.")
