# src/services/ingestion.py
import asyncio
import logging
from pathlib import Path
from typing import Dict

# Domain Repositories and Persistence Adapters
from src.core.models import Book, Chapter, Section
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader
from src.infrastructure.persistence.vector_base_repository import VectorRepository

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        chunker: Chunker,
        loaders: Dict[FileType, Loader],
        vector_repo: VectorRepository,
        db_context: DatabaseContext,  # Injected for transactional unit of work
        max_workers: int = 8,
    ):
        self.loaders = loaders
        self.chunker = chunker
        self.vector_repo = vector_repo
        self.db_context = db_context
        self.semaphore = asyncio.Semaphore(max_workers)

    async def _process_section(self, section, book_id: str) -> int:
        async with self.semaphore:
            chunks = self.chunker.chunk_section(
                section_id=section.id,  # Keyword argument
                book_id=book_id,  # Keyword argument
                path_id=section.path_id,  # Keyword argument
                text=section.raw_text,
            )
            if chunks:
                # FIX: Remove asyncio.to_thread. Call it directly with await.
                await self.vector_repo.save_chunks(chunks)
                return len(chunks)
            return 0

    async def ingest_file(
        self, file_path: Path, file_type: FileType, book_id: str | None = None
    ) -> Book:
        """
        Orchestrates full ingestion:
        1. Parse file structure.
        2. Process vector chunks concurrently.
        3. Persist metadata to MariaDB as a single atomic transaction.
        """
        loader = self.loaders.get(file_type)
        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        # 1. Load the domain model (Book, Chapters, and Sections with raw_text)
        book = loader.load(file_path)

        # Apply deterministic ID if provided (Client-Side Identity)
        if book_id:
            book.id = book_id
            for chapter in book.chapters:
                chapter.book_id = book_id

        if not book.all_sections:
            raise ValueError(
                f"Loader returned a book with no sections for: {file_path}"
            )

        # 2. Process Vector Embeddings Concurrently
        tasks = [
            self._process_section(section, book.id) for section in book.all_sections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_chunks = 0
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(
                    f"Section {book.all_sections[i].path_id} vectoring failed: {res}"
                )
            else:
                total_chunks += res

        if total_chunks == 0:
            raise RuntimeError(f"Ingestion produced 0 chunks for '{file_path}'.")

        # 3. Persistence Unit of Work (MariaDB)
        async with self.db_context.get_session() as session:
            # Initialize repositories with the managed session
            book_repo = self.db_context.get_repository(session, Book)
            chapter_repo = self.db_context.get_repository(session, Chapter)
            section_repo = self.db_context.get_repository(session, Section)

            try:
                # Metadata save: SQLModel automatically ignores 'raw_text'
                # because sa_column=None in core/models.py
                await book_repo.save(book)

                for chapter in book.chapters:
                    await chapter_repo.save(chapter)

                for section in book.all_sections:
                    await section_repo.save(section)

                # Commit all metadata at once
                await session.commit()
                logger.info(
                    f"Persisted book '{book.title}' with {total_chunks} chunks."
                )

            except Exception as e:
                await session.rollback()
                logger.error(f"Metadata persistence failed, rolling back: {e}")
                raise

        return book
