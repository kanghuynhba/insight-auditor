import asyncio
import logging

from sqlmodel import select

from src.core.config import get_settings
from src.core.models import Book
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.adapters.vectors.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.services.facts_extraction_service import FactsExtractionService

logger = logging.getLogger(__name__)


async def run_fact_extraction() -> None:
    settings = get_settings()

    # 1. Initialize Infrastructure
    # Note: generative_model in settings should be your Azure deployment name
    llm = LiteLLMCompletion(settings.generative_model)
    db_context = DatabaseContext(connection_url=str(settings.mariadb_url))
    vector_ctx = VectorDatabaseContext(settings)

    # 2. Database Initialization
    # This creates the new 'atomic_facts' table since the old one was renamed.
    logger.info("Initializing database and ensuring tables exist...")
    await db_context.initialize_database()

    # Initialize Vector Store
    vector_repo = await ChunkRepository.create(settings=settings, vector_ctx=vector_ctx)

    # 3. Setup Service
    # Concurrency=20 is a sweet spot for your 8M TPM quota and 30-pool size.
    service = FactsExtractionService(
        llm=llm, db_context=db_context, vector_repo=vector_repo, concurrency=20
    )

    async with db_context.get_session() as session:
        statement = select(Book.id, Book.title)
        result = await session.exec(statement)
        all_books = result.all()

        if not all_books:
            logger.error("No books found! Check your 'books' table.")
            return

        logger.info(
            f"Found {len(all_books)} books. Starting high-precision extraction..."
        )

        for book_id, title in all_books:
            logger.info(f"--- Processing: {title} ---")
            try:
                # This calls your updated extract_facts with span re-basing
                facts = await service.extract_facts_for_book(book_id)
                logger.info(f"Successfully extracted {len(facts)} clean facts.")
            except Exception as e:
                logger.error(f"Error processing {title}: {str(e)}")
                continue

    # 4. Final Cleanup
    await db_context.engine.dispose()
    logger.info("All tasks complete. Connection pool disposed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_fact_extraction())
