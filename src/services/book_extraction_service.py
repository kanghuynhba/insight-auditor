import logging
from pathlib import Path
from typing import Dict

from src.core.models import Book
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader

logger = logging.getLogger(__name__)


class BookExtractionService:
    # file_path -> Loader -> save(Book)
    def __init__(self, loaders: Dict[FileType, Loader], db_context: DatabaseContext):
        self.loaders = loaders
        self.db_context = db_context

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

        async with self.db_context.get_session() as session:
            existing_book = await session.get(Book, book.id)
            if existing_book:
                logger.info(
                    f"Book '{book.title}' (ID: {book.id}) already exists. Skipping."
                )
                return existing_book

            try:
                # Add the hierarchy to the session
                session.add(book)

                # Mimics the streaming write/commit pattern
                await session.commit()
                logger.info(f"Successfully persisted metadata for '{book.title}'.")
                return book

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to persist book '{book.title}': {e}")
                raise e
