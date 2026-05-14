import logging
from pathlib import Path
from typing import Dict
from src.infrastructure.persistence.base_repository import Repository
from src.core.book import Book
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import ExtractedBookData, Loader
from src.services.toc_service import TOCService

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

        book_id = loader.get_stable_id(file_path)

        existing_book = await self.book_repo.find_by_id(book_id)

        if existing_book:
            logger.info(f"Book (ID: {book_id}) already exists. Skipping.")
            return existing_book

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

        saved_book = await self.book_repo.save(book)
        await self.book_repo.session.commit()
        return saved_book
