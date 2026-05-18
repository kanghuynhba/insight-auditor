# src/services/book_extraction_service.py
"""Book extraction service.

Changes from the original
-------------------------
* :meth:`extract_and_persist_metadata` now returns an
  :class:`~src.model.book_models.ExtractionResultModel` instead of a raw
  ``Book`` entity.  This keeps entities confined to the repository layer.
* The internal logic is unchanged; it simply wraps the result before returning.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from src.converter.entity_to_model import book_entity_to_summary_model
from src.core.book import Book
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import ExtractedBookData, Loader
from src.infrastructure.persistence.base_repository import Repository
from src.model.book_models import BookSummaryModel, ExtractionResultModel
from src.services.toc_service import TOCService

logger = logging.getLogger(__name__)


class BookExtractionService:
    """Orchestrates book structural extraction and persistence.

    The service uses deterministic IDs (computed from file content) to prevent
    duplicate records.  It returns a lightweight
    :class:`~src.model.book_models.ExtractionResultModel` so the router can
    decide the HTTP status code without touching entities.
    """

    def __init__(
        self,
        loaders: Dict[FileType, Loader],
        book_repo: Repository[Book],
    ) -> None:
        self.loaders = loaders
        self.book_repo = book_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_and_persist_metadata(
        self, file_path: Path, file_type: FileType
    ) -> ExtractionResultModel:
        """Extract book metadata from *file_path* and persist it to the database.

        When the book already exists (determined by its stable content hash ID),
        the existing record is returned with ``status="exists"``.  When the book
        is new, it is persisted and returned with ``status="new"``.

        Args:
            file_path: Path to the temporary upload file.
            file_type: The detected :class:`~src.infrastructure.loaders.file_type.FileType`.

        Returns:
            An immutable :class:`~src.model.book_models.ExtractionResultModel`.

        Raises:
            ValueError: When no loader is registered for ``file_type``.
        """
        loader = self.loaders.get(file_type)
        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        book_id = loader.get_stable_id(file_path)
        existing_book = await self.book_repo.find_by_id(book_id)

        if existing_book:
            logger.info(f"Book (ID: {book_id}) already exists. Skipping extraction.")
            return ExtractionResultModel(
                book_id=book_id,
                status="exists",
                message="Book already present in the database.",
            )

        extracted_book: ExtractedBookData = loader.extract_raw(file_path)
        table_of_contents = TOCService.to_entities(extracted_book.toc_root, book_id)

        book = Book(
            id=book_id,
            title=extracted_book.title,
            author=extracted_book.author,
            source_format=file_type.value,
            file_path=str(file_path),
            source_filename=file_path.name,
            table_of_contents=table_of_contents,
        )

        await self.book_repo.save(book)
        await self.book_repo.session.commit()

        logger.info(
            f"New book persisted (ID: {book_id}, title: {extracted_book.title!r})"
        )
        return ExtractionResultModel(
            book_id=book_id,
            status="new",
            message=None,
        )

    async def get_book_summary(self, book_id: str) -> BookSummaryModel | None:
        """Fetch a book by ID and return its summary model, or ``None`` when not found.

        Args:
            book_id: The book's stable content-hash ID.

        Returns:
            A :class:`~src.model.book_models.BookSummaryModel`, or ``None``.
        """
        book = await self.book_repo.find_by_id(book_id)
        if not book:
            return None
        return book_entity_to_summary_model(book)

    async def get_books(self) -> list[BookSummaryModel]:
        """Return all books as summary models.

        Returns:
            A list of :class:`~src.model.book_models.BookSummaryModel` objects,
            possibly empty.
        """
        books = await self.book_repo.find_all()
        return [book_entity_to_summary_model(b) for b in books]
