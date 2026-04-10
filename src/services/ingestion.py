# src/services/ingestion.py
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict

from src.core.models import Book
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.databases.vectors.vector_store import VectorStore
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader


class IngestionService:
    def __init__(
        self,
        chunker: Chunker,
        loaders: Dict[FileType, Loader],
        vector_db: VectorStore,
        max_workers: int = 8,
    ):
        self.loaders = loaders
        self.chunker = chunker
        self.vector_db = vector_db
        self.max_workers = max_workers

    def _process_section(self, section, book_id: str) -> int:
        chunks = self.chunker.chunk_section(
            section_id=section.id,
            book_id=book_id,
            path_id=section.path_id,
            text=section.raw_text,
        )
        if chunks:
            self.vector_db.save_chunks(chunks)
            return len(chunks)
        return 0

    def ingest_file(self, file_path: Path, file_type: FileType) -> Book:
        loader = self.loaders.get(file_type)

        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        book = loader.load(file_path)

        if not book.all_sections:
            raise ValueError(
                f"Loader returned a book with no sections for: {file_path}"
            )

        total_chunks_created = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_section, section, book.id): section
                for section in book.all_sections
            }
            for future in as_completed(futures):
                try:
                    total_chunks_created += future.result()
                except Exception as e:
                    section = futures[future]
                    print(f"Section {section.path_id} failed: {e}")

        if total_chunks_created == 0:
            raise RuntimeError(
                f"Ingestion produced 0 chunks for '{file_path}'. "
                "Check that sections have non-empty raw_text and the chunker threshold."
            )

        return book
