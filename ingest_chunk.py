import asyncio
import logging

from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.core.config import get_settings
from src.core.models import Book, Chapter, Section
from src.core.text_chunk import TextChunk
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.adapters.vectors.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.llm.embedding.lite_llm_embedding import LiteLLMEmbedding
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.services.chunk_ingestion_service import ChunkIngestionService

logger = logging.getLogger(__name__)


async def initialize_vector_storage(vector_ctx: VectorDatabaseContext, table_name: str):
    db = await vector_ctx.connect()
    try:
        await db.open_table(table_name)
        logger.info(f"LanceDB table '{table_name}' verified.")
    except Exception:
        logger.info(
            f"Table '{table_name}' not found. Initializing with TextChunk schema..."
        )
        await db.create_table(table_name, schema=TextChunk, mode="overwrite")


async def run_ingestion():
    settings = get_settings()

    db_context = DatabaseContext(connection_url=str(settings.mariadb_url))
    vector_ctx = VectorDatabaseContext(settings)

    await initialize_vector_storage(vector_ctx, settings.vector_index_name)

    vector_repo = await ChunkRepository.create(settings=settings, vector_ctx=vector_ctx)
    chunker = NaturalBoundaryChunker(settings=settings)
    embedder = LiteLLMEmbedding(config=settings.embedding_model)

    service = ChunkIngestionService(
        chunker=chunker,
        embedder=embedder,
        vector_repo=vector_repo,
        embedding_batch_size=100,
        max_workers=8,
    )

    async with db_context.get_session() as session:
        statement = select(Book).options(
            selectinload(Book.chapters).selectinload(Chapter.sections)
        )
        results = await session.exec(statement)
        books = results.all()

        if not books:
            logger.error("No books found in MariaDB.")
            return

        for book in books:
            existing_chunks = await vector_repo.get_chunks_by_book(book.id)
            if len(existing_chunks) > 0:
                logger.info(
                    f"Skipping '{book.title}': {len(existing_chunks)} chunks exist."
                )
                continue

            logger.info(f"Ingesting: {book.title}...")
            try:
                await service.ingest_book(book)
                logger.info(f"Successfully vectorized '{book.title}'.")
            except Exception as e:
                logger.error(f"Failed to ingest '{book.title}': {str(e)}")

    await db_context.engine.dispose()
    logger.info("Ingestion process complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_ingestion())
