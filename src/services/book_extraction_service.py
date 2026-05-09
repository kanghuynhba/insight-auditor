import logging
from pathlib import Path
from typing import Dict
from src.infrastructure.persistence.base_repository import Repository
from src.core.book import Book
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader

logger = logging.getLogger(__name__)


class BookExtractionService:
    # file_path -> Loader -> save(Book)
    def __init__(
        self,
        loaders: Dict[FileType, Loader],
        book_repo: Repository[Book],
    ):
        self.loaders = loaders
        self.book_repo = book_repo

    async def extract_and_persist_metadata(
        self, file_path: Path, file_type: FileType
    ) -> Book:
        """
        Orchestrates book structural extraction and persistence.
        Uses deterministic IDs from the loader to prevent duplicates.
        """
        loader = self.loaders.get(file_type)
        if not loader:
            raise ValueError(f"No loader found for {file_type}")

        book = loader.load(file_path)

        existing_book = await self.book_repo.find_by_id(book.id)

        if existing_book:
            logger.info(
                f"Book '{book.title}' (ID: {book.id}) already exists. Skipping."
            )
            return existing_book

        saved_book = await self.book_repo.save(book)
        await self.book_repo.session.commit()
        return saved_book
