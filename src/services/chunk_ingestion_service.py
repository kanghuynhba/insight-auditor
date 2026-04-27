# src/services/chunk_ingestion_service.py
import asyncio
import logging
from typing import List

from src.core.models import Book
from src.core.text_chunk import TextChunk
from src.index.operations.embed_chunks import embed_chunks
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.llm.embedding.embedding import LLMEmbedding
from src.infrastructure.persistence.vector_base_repository import VectorRepository

logger = logging.getLogger(__name__)


class ChunkIngestionService:
    # ingest_book(Book) -> Chunking -> LLMEmbedding -> save_chunks(List[TextChunk])
    def __init__(
        self,
        chunker: Chunker,
        embedder: LLMEmbedding,
        vector_repo: VectorRepository,
        embedding_batch_size: int = 40,
        max_workers: int = 8,
    ):
        self.chunker = chunker
        self.embedder = embedder
        self.vector_repo = vector_repo
        self.embedding_batch_size = embedding_batch_size
        self.semaphore = asyncio.Semaphore(max_workers)

    async def ingest_book(self, book: Book) -> None:
        """Processes book into chunks, embeds them, and saves to Vector Store."""
        if not book.all_sections:
            logger.warning(f"Book '{book.title}' has no sections to ingest.")
            return

        # 1. Parallel Chunking (CPU-bound)
        tasks = [self._process_single_section(s) for s in book.all_sections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_chunks: List[TextChunk] = []
        for result in results:
            if isinstance(result, list):
                all_chunks.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Chunking failed for a section: {result}")

        if not all_chunks:
            return

        try:
            # 2. Batch Embedding (Network-bound)
            # We handle this in chunks if the book is massive to avoid payload limits
            logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")

            # 3. Hydrate Chunks with Vectors
            # Using model_copy because TextChunk is frozen=True
            enriched_chunks = await embed_chunks(
                chunks=all_chunks,
                embedder=self.embedder,
                batch_size=self.embedding_batch_size,
            )
            # 4. Batch Save (IO-bound)
            await self.vector_repo.save_chunks(enriched_chunks)

            logger.info(
                f"Successfully ingested {len(enriched_chunks)} chunks for '{book.title}'."
            )

        except Exception as e:
            logger.error(f"Failed to embed or save chunks for book {book.id}: {e}")
            raise

    async def _process_single_section(self, section):
        async with self.semaphore:
            # Offload CPU-heavy chunking to a thread pool
            return await asyncio.to_thread(self.chunker.chunk_section, section=section)
