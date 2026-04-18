#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select

from src.core.config import get_settings
from src.core.models import Book, Chapter, Section
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.persistence.atomic_facts_repo import AtomicFactRepository
from src.services.extraction import ExtractionService

# INCREASE LOGGING LEVEL FOR LLM CALLS
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_sections_by_book(
    db_context: DatabaseContext, book_id: str
) -> list[Section]:
    async with db_context.get_session() as session:
        stmt = (
            select(Section)
            .join(Chapter, Section.chapter_id == Chapter.id)
            .join(Book, Chapter.book_id == Book.id)
            .where(Book.id == book_id)
        )
        result = await session.exec(stmt)
        return [s for s in result.all() if s.raw_text and s.raw_text.strip()]


async def run_extraction(book_id: str = None, process_all: bool = False):
    settings = get_settings()
    db_context = DatabaseContext(settings.mariadb_url)

    llm_params = settings.litellm_config
    llm = LiteLLMCompletion(
        model=llm_params["model"],
        api_key=llm_params["api_key"],
        api_base=llm_params["base_url"],
        api_version=llm_params["api_version"],
    )

    # Lower concurrency to 2 or 3 initially to see if it's a rate-limiting hang
    extraction_service = ExtractionService(
        llm=llm,
        db_context=db_context,
        concurrency=2,
    )

    try:
        async with db_context.get_session() as session:
            books_result = await session.exec(select(Book))
            all_books = books_result.all()

        if not all_books:
            logger.error("No books found.")
            return

        books_to_process = all_books if process_all else [all_books[0]]
        if book_id:
            books_to_process = [b for b in all_books if b.id == book_id]

        for book in books_to_process:
            logger.info(f"Processing: {book.title}")

            # Use a wait_for to ensure the service doesn't hang the whole script forever
            try:
                # Give it a 5-minute window to start showing progress
                await asyncio.wait_for(
                    extraction_service.extract_facts_for_book(book.id), timeout=600
                )
            except asyncio.TimeoutError:
                logger.error(f"Extraction for {book.title} timed out after 10 minutes.")
                continue

            # Retrieve results
            sections = await get_sections_by_book(db_context, book.id)
            async with db_context.get_session() as session:
                repo = AtomicFactRepository(session)
                all_results = []
                for section in sections:
                    facts = await repo.find_by_section(section.id)
                    for f in facts:
                        all_results.append({"section": section.title, "fact": f.point})

                if all_results:
                    print(json.dumps(all_results, indent=2))
                else:
                    logger.warning(
                        f"No facts found in DB for {book.title} after extraction."
                    )

    finally:
        await db_context.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", help="Specific book ID")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    try:
        asyncio.run(run_extraction(book_id=args.book_id, process_all=args.all))
    except KeyboardInterrupt:
        logger.info("Manual Stop.")
    except Exception:
        logger.exception("Fatal Error")


if __name__ == "__main__":
    main()
