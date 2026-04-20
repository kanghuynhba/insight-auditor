# src/services/chunk_ingestion_service.py
import asyncio
import logging

from src.core.models import Book
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.persistence.vector_base_repository import VectorRepository

logger = logging.getLogger(__name__)


class ChunkIngestionService:
    def __init__(
        self,
        chunker: Chunker,
        vector_repo: VectorRepository,
        max_workers: int = 8,
    ):
        self.chunker = chunker
        self.vector_repo = vector_repo
        self.semaphore = asyncio.Semaphore(max_workers)

    async def _process_single_section(self, section):
        async with self.semaphore:
            # Execute the CPU-heavy chunking in a separate thread
            return await asyncio.to_thread(self.chunker.chunk_section, section=section)

    async def ingest_book(self, book: Book) -> None:
        """Processes book into chunks and saves to Vector Store"""
        if not book.all_sections:
            logger.warning(f"Book '{book.title}' has no sections to ingest.")
            return

        tasks = [self._process_single_section(s) for s in book.all_sections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_chunks = []
        for result in results:
            if isinstance(result, list):
                all_chunks.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Chunking failed for a section: {result}")

        if all_chunks:
            # Batch save is significantly faster for Vector Stores
            await self.vector_repo.save_chunks(all_chunks)
            logger.info(
                f"Successfully vectorized {len(all_chunks)} chunks for '{book.title}'."
            )
