#!/usr/bin/env python3
"""
Ingest a PDF file, then extract atomic facts from its LanceDB chunks
using only the non-overlapping body text.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import SQLModel, delete, select
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.pdf_loader import PdfLoader
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)
from src.services.ingestion import IngestionService

from src.core.atomic_fact import AtomicFact
from src.core.config import get_settings
from src.core.models import Book, Section

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def init_db(db_context: DatabaseContext) -> None:
    """Create all tables if they don't exist."""
    async with db_context.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables verified/created.")


async def get_section_texts(
    db_context: DatabaseContext, section_ids: set[str]
) -> dict[str, str]:
    """Batch-fetch raw_text for a set of section IDs."""
    if not section_ids:
        return {}
    async with db_context.get_session() as session:
        stmt = select(Section.id, Section.raw_text).where(Section.id.in_(section_ids))
        result = await session.exec(stmt)
        return {row.id: row.raw_text for row in result.all() if row.raw_text}


async def cleanup_book(
    book_id: str,
    vector_db: ChunkRepository,
    db_context: DatabaseContext,
) -> None:
    """
    Remove all artefacts created for a book on failure.

    Deletes (in order):
      1. LanceDB vectors          – via chunk_repo
      2. Section rows             – cascade from Book, but deleted explicitly
                                    in case FK constraints are not set to CASCADE
      3. Book row
    """
    logger.info(f"Rolling back ingestion for book {book_id} …")
    try:
        # 1. Remove vectors from LanceDB
        vector_db.delete_book(book_id)
    except Exception:
        logger.warning(
            "Could not remove LanceDB vectors during cleanup.", exc_info=True
        )

    try:
        async with db_context.get_session() as session:
            # 2. Remove sections (atomic facts cascade from section or are left
            #    orphaned — adjust the where-clause if you have a separate
            #    atomic_facts table with a book_id column)
            await session.exec(delete(Section).where(Section.book_id == book_id))
            # 3. Remove the book itself
            await session.exec(delete(Book).where(Book.id == book_id))
            await session.commit()
            logger.info(f"Database cleanup complete for book {book_id}.")
    except Exception:
        logger.warning("Could not remove DB rows during cleanup.", exc_info=True)


async def extract_facts_from_chunks(
    book_id: str,
    chunk_repo: ChunkRepository,
    db_context: DatabaseContext,
    llm: LiteLLMCompletion,
    concurrency: int = 3,
) -> list[AtomicFact]:
    """
    Retrieve chunks, slice out non-overlapping body text, extract facts.

    FIX: Each concurrent task opens its own DB session so we never share
    a single AsyncSession across concurrent coroutines.
    """
    chunks = await chunk_repo.get_chunks_by_book(book_id)
    if not chunks:
        logger.warning(f"No chunks found for book {book_id}")
        return []

    section_ids = {chunk["section_id"] for chunk in chunks}
    section_texts = await get_section_texts(db_context, section_ids)

    logger.info(f"Processing {len(chunks)} chunks for book {book_id}")

    semaphore = asyncio.Semaphore(concurrency)
    all_facts: list[AtomicFact] = []

    async def process_one_chunk(chunk: dict) -> list[AtomicFact]:
        async with semaphore:
            section_id = chunk["section_id"]
            raw_text = section_texts.get(section_id)
            if not raw_text:
                logger.warning(
                    f"Missing raw_text for section {section_id}, skipping chunk"
                )
                return []

            start = chunk.get("start_char", 0)
            end = chunk.get("end_char", len(raw_text))

            if start < 0 or end > len(raw_text) or start >= end:
                logger.warning(
                    f"Invalid span for chunk {chunk['id']}: "
                    f"start={start}, end={end}, len={len(raw_text)}. "
                    "Using fallback (full chunk text)."
                )
                body_text = chunk.get("text", "")
            else:
                body_text = raw_text[start:end]

            if not body_text or not body_text.strip():
                return []

            path_id = chunk["path_id"]

            facts = await asyncio.to_thread(
                extract_atomic_facts,
                llm,
                ATOMIC_FACT_SYSTEM,
                ATOMIC_FACT_USER,
                body_text,
                path_id,
                section_id,
            )

            if not facts:
                return []

            # FIX: each task gets its own session — no shared-session race condition
            async with db_context.get_session() as session:
                repo = AtomicFactRepository(session)
                for fact in facts:
                    await repo.save(fact)
                await session.commit()

            return facts

    results = await asyncio.gather(
        *[process_one_chunk(chunk) for chunk in chunks],
        return_exceptions=True,  # don't let one failure cancel everything
    )

    for i, res in enumerate(results):
        if isinstance(res, BaseException):
            logger.error(f"Chunk {i} failed: {res}")
        elif isinstance(res, list):
            all_facts.extend(res)

    logger.info(f"Extracted {len(all_facts)} atomic facts from {len(chunks)} chunks")
    return all_facts


async def ingest_and_extract(pdf_path: Path, concurrency: int = 3) -> None:
    """Ingest the PDF, then extract atomic facts from its chunks."""
    settings = get_settings()
    db_context = DatabaseContext(settings.mariadb_url)

    await init_db(db_context)

    chunker = NaturalBoundaryChunker(settings)
    loaders = {FileType.Pdf: PdfLoader(settings)}
    vector_db = ChunkRepository(settings)

    ingestion_service = IngestionService(
        chunker=chunker,
        loaders=loaders,
        vector_db=vector_db,
        db_context=db_context,
    )

    llm = LiteLLMCompletion(config=settings.generative_model)

    book = None
    try:
        # 1. Ingest
        logger.info(f"Ingesting {pdf_path} …")
        book = await ingestion_service.ingest_file(pdf_path, FileType.Pdf)
        logger.info(f"Ingested book: {book.title!r} (id: {book.id})")

        # 2. Extract facts (each chunk task manages its own session)
        facts = await extract_facts_from_chunks(
            book_id=book.id,
            chunk_repo=vector_db,
            db_context=db_context,
            llm=llm,
            concurrency=concurrency,
        )

        # 3. Output
        output = [
            {
                "section_id": fact.section_id,
                "fact": fact.point,
                "rank": fact.rank.value if hasattr(fact.rank, "value") else fact.rank,
                "questions": fact.questions,
            }
            for fact in facts
        ]

        if output:
            print(json.dumps(output, indent=2))
        else:
            logger.warning("No facts extracted.")

    except Exception as e:
        logger.exception(f"Failed: {e}")
        # FIX: full cleanup — vectors + sections + book
        if book and book.id:
            await cleanup_book(book.id, vector_db, db_context)
        raise

    finally:
        await db_context.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a PDF and extract atomic facts from its chunks."
    )
    parser.add_argument(
        "pdf_file",
        help="Path to the PDF file (e.g., uploads/ddia.pdf)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent LLM calls (default: 3)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_file)
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        sys.exit(1)

    try:
        asyncio.run(ingest_and_extract(pdf_path, concurrency=args.concurrency))
    except KeyboardInterrupt:
        logger.info("Manual stop.")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
