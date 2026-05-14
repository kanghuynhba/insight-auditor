# src/services/chunk_ingestion_service.py
import asyncio
import logging
from typing import List, Optional

from src.core.book import Book
from src.core.toc_node import TocNode
from src.core.text_chunk import TextChunk
from src.index.operations.embed_chunks import embed_chunks
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.llm.embedding.embedding import LLMEmbedding
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.services.toc_service import TOCService

logger = logging.getLogger(__name__)


class ChunkIngestionService:
    def __init__(
        self,
        chunker: Chunker,
        embedder: LLMEmbedding,
        vector_repo: VectorRepository,
        toc_service: TOCService,
        embedding_batch_size: int = 40,
        max_workers: int = 8,
    ):
        self.chunker = chunker
        self.embedder = embedder
        self.vector_repo = vector_repo
        self.toc_service = toc_service
        self.embedding_batch_size = embedding_batch_size
        self.semaphore = asyncio.Semaphore(max_workers)

    async def ingest_book(self, book: Book) -> None:
        """
        Ingest all sections of a book using TocNode business objects.
        Assumes book.table_of_contents is already loaded with sections.
        """
        # Convert to TocNode tree
        toc_root = self.toc_service.to_tree(book.table_of_contents)
        if not toc_root or not toc_root.children:
            logger.warning(f"Book '{book.title}' has no TOC entries.")
            return

        # Get all sections with their chapter titles
        sections_to_process = self._collect_sections_with_chapters(toc_root)

        if not sections_to_process:
            logger.warning(f"Book '{book.title}' has no valid sections to ingest.")
            return

        # Process all sections in parallel
        tasks = [
            self._process_single_section(section, book.title, chapter_title)
            for section, chapter_title in sections_to_process
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all chunks
        all_chunks: List[TextChunk] = []
        for result in results:
            if isinstance(result, list):
                all_chunks.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Chunking failed for a section: {result}")

        if not all_chunks:
            logger.warning(f"No chunks generated for book '{book.title}'.")
            return

        # Generate embeddings and save
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

    def _collect_sections_with_chapters(self, root_node: TocNode) -> List[tuple]:
        """
        Traverse the TOC tree and collect all sections with their hierarchical title path.
        Returns list of (section, hierarchical_title) tuples.
        Example: "Chapter 1 > Section 1.1 > Subsection 1.1.1"
        """
        result = []
        self._traverse_and_collect(root_node, [], result)
        return result

    def _traverse_and_collect(
        self, node: TocNode, title_path: List[str], result: List[tuple]
    ) -> None:
        """
        Recursively traverse the TOC tree.
        Builds the full hierarchical title path as we go deeper.
        When hitting a section with content, add to result with the complete path.
        """
        # Add current node title to the path (skip fake root level 0)
        if node.level > 0:
            title_path.append(node.title)

        # If this node has a section with content, add it with the full path
        if node.section and node.section.raw_text:
            hierarchical_title = " > ".join(title_path)
            result.append((node.section, hierarchical_title))

        # Recursively process children
        for child in node.children:
            self._traverse_and_collect(child, title_path.copy(), result)

    async def _process_single_section(
        self, section, book_title: str, chapter_title: str
    ) -> List[TextChunk]:
        """Process a single section: attach metadata and chunk it."""
        # Attach temporary attributes so the chunker can use them
        section._book_title = book_title
        section._chapter_title = chapter_title

        async with self.semaphore:
            return await asyncio.to_thread(self.chunker.chunk_section, section=section)
