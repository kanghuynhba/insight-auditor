# src/services/chunk_ingestion_service.py
import asyncio
import logging
from typing import List

from src.core.book import Book
from src.core.text_chunk import TextChunk
from src.index.operations.embed_chunks import embed_chunks
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.llm.embedding.embedding import LLMEmbedding
from src.infrastructure.persistence.vector_base_repository import VectorRepository

logger = logging.getLogger(__name__)


class ChunkIngestionService:
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
        if not book.all_sections:
            logger.warning(f"Book '{book.title}' has no sections to ingest.")
            return

        # Build a map from section_id to its chapter title (root TOC ancestor)
        section_to_chapter = {}
        # book.toc is expected to be loaded (by selectinload) before calling this method
        if book.toc:
            toc_map = {t.id: t for t in book.toc}
            for toc in book.toc:
                if toc.section_id:
                    # climb up to the root (parent_id == None) to get the chapter title
                    cur = toc
                    while cur.parent_id and cur.parent_id in toc_map:
                        cur = toc_map[cur.parent_id]
                    section_to_chapter[toc.section_id] = cur.title

        # Process sections in parallel
        tasks = [
            self._process_single_section(
                section,
                book_title=book.title,
                chapter_title=section_to_chapter.get(section.id, ""),
            )
            for section in book.all_sections
        ]
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
            logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
            enriched_chunks = await embed_chunks(
                chunks=all_chunks,
                embedder=self.embedder,
                batch_size=self.embedding_batch_size,
            )
            await self.vector_repo.save_chunks(enriched_chunks)
            logger.info(
                f"Successfully ingested {len(enriched_chunks)} chunks for '{book.title}'."
            )
        except Exception as e:
            logger.error(f"Failed to embed or save chunks for book {book.id}: {e}")
            raise

    async def _process_single_section(
        self, section, book_title: str, chapter_title: str
    ):
        # Attach temporary attributes so the chunker can use them
        section._book_title = book_title
        section._chapter_title = chapter_title
        async with self.semaphore:
            return await asyncio.to_thread(self.chunker.chunk_section, section=section)
