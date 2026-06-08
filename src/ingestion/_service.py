"""Book ingestion facade."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List

from src.domain import Book, TextChunk
from src.domain.toc_node import TocNode
from src.ingestion._embedding import embed_chunks
from src.ingestion._chunking import ChunkContext, NaturalBoundaryChunker
from src.ingestion._loaders import EpubLoader, FileType, PdfLoader
from src.llm import LLMGateway
from src.ingestion._models import (
    BookDetailModel,
    BookSummaryModel,
    ExtractionResultModel,
    TocNodeModel,
)
from src.ingestion._toc import TOCService
from src.store import DeleteBookResultModel, Store

logger = logging.getLogger(__name__)


class BookIngestion:
    """Public interface for book metadata, chunk ingestion, and deletion."""

    def __init__(self, store: Store, llm: LLMGateway, settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings
        self.toc_service = TOCService()
        self.chunker = NaturalBoundaryChunker(self.settings)
        self.embedding_batch_size = 40
        self.semaphore = asyncio.Semaphore(8)

    async def ingest_metadata(
        self, file_path: Path, file_type: FileType
    ) -> ExtractionResultModel:
        loader = self._loaders().get(file_type)
        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        book_id = loader.get_stable_id(file_path)
        existing_book = await self.store.get_book(book_id)

        if existing_book:
            logger.info("Book (ID: %s) already exists. Skipping extraction.", book_id)
            return ExtractionResultModel(
                book_id=book_id,
                status="exists",
                message="Book already present in the database.",
            )

        extracted_book = loader.extract_raw(file_path)
        table_of_content = TOCService.to_book_toc(extracted_book.toc_root, book_id)
        sections = extracted_book.toc_root.get_all_sections()

        book = Book(
            id=book_id,
            title=extracted_book.title,
            author=extracted_book.author,
            source_format=file_type.value,
            file_path=str(file_path),
            source_filename=file_path.name,
            table_of_content=table_of_content,
            sections=sections,
        )

        await self.store.save_book(book)
        await self.store.commit()

        logger.info("New book persisted (ID: %s, title: %r)", book_id, extracted_book.title)
        return ExtractionResultModel(
            book_id=book_id,
            status="new",
            message=None,
        )

    async def ingest_upload_file(
        self, file_path: Path, filename: str, extracted_books_dir: Path
    ) -> ExtractionResultModel:
        file_type = FileType.from_filename(filename)
        result = await self.ingest_metadata(file_path, file_type)
        if file_type == FileType.Epub:
            EpubLoader.extract_to_static(file_path, result.book_id, extracted_books_dir)
        return result

    async def ingest_chunks(self, book: Book) -> None:
        toc_root = self.toc_service.to_toc_node_tree(
            book.table_of_content, book.sections
        )
        if not toc_root or not toc_root.children:
            logger.warning("Book %r has no TOC entries.", book.title)
            return

        sections_to_process = self._collect_sections_with_chapters(toc_root)
        if not sections_to_process:
            logger.warning("Book %r has no valid sections to ingest.", book.title)
            return

        tasks = [
            self._process_single_section(section, book.title, chapter_title)
            for section, chapter_title in sections_to_process
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_chunks: List[TextChunk] = []
        for result in results:
            if isinstance(result, list):
                all_chunks.extend(result)
            elif isinstance(result, Exception):
                logger.error("Chunking failed for a section: %s", result)

        if not all_chunks:
            logger.warning("No chunks generated for book %r.", book.title)
            return

        try:
            logger.info("Generating embeddings for %d chunks...", len(all_chunks))
            enriched_chunks = await embed_chunks(
                chunks=all_chunks,
                embedder=self.llm.embedding,
                batch_size=self.embedding_batch_size,
            )
            await self.store.save_chunks(enriched_chunks)
            logger.info(
                "Successfully ingested %d chunks for %r.",
                len(enriched_chunks),
                book.title,
            )
        except Exception as exc:
            logger.error("Failed to embed or save chunks for book %s: %s", book.id, exc)
            raise

    async def delete_book(self, book_id: str) -> DeleteBookResultModel:
        return await self.store.delete_book(book_id)

    async def get_book(self, book_id: str) -> Book | None:
        return await self.store.get_book(book_id)

    async def get_book_detail(
        self, book_id: str, file_url: str
    ) -> BookDetailModel | None:
        book = await self.store.get_book(book_id)
        if not book:
            return None

        toc_model = self.to_toc_tree(book.table_of_content, book.sections)
        if not toc_model:
            return None
        return BookDetailModel(
            id=book.id,
            title=book.title,
            author=book.author,
            source_format=book.source_format,
            file_url=file_url,
            toc=toc_model,
        )

    async def get_books(self) -> list[BookSummaryModel]:
        books = await self.store.get_all_books()
        return [
            BookSummaryModel(
                id=book.id,
                title=book.title,
                author=book.author,
                source_format=book.source_format,
                upload_status=book.upload_status,
            )
            for book in books
        ]

    def to_toc_tree(self, toc_data, sections=None) -> TocNodeModel | None:
        return self.toc_service.to_tree(toc_data, sections)

    def _loaders(self):
        return {
            FileType.Pdf: PdfLoader(self.settings),
            FileType.Epub: EpubLoader(self.settings),
        }

    def _collect_sections_with_chapters(self, root_node: TocNode) -> List[tuple]:
        result = []
        self._traverse_and_collect(root_node, [], result)
        return result

    def _traverse_and_collect(
        self, node: TocNode, title_path: List[str], result: List[tuple]
    ) -> None:
        if node.level > 0:
            title_path.append(node.title)

        if node.section and node.section.raw_text:
            hierarchical_title = " > ".join(title_path)
            result.append((node.section, hierarchical_title))

        for child in node.children:
            self._traverse_and_collect(child, title_path.copy(), result)

    async def _process_single_section(
        self, section, book_title: str, chapter_title: str
    ) -> List[TextChunk]:
        context = ChunkContext(
            book_id=section.book_id,
            book_title=book_title,
            chapter_title=chapter_title,
            section_title=section.title,
        )
        async with self.semaphore:
            return await asyncio.to_thread(
                self.chunker.chunk_section,
                section=section,
                context=context,
            )
