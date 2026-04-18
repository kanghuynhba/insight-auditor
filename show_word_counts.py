#!/usr/bin/env python3
"""
Display word count for each section in the database, ordered by path_id.
Usage: python show_section_word_counts.py [--book-id <id>] [--limit N]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from src.core.config import get_settings
from src.core.models import Section
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def show_word_counts(book_id: str = None, limit: int = None):
    settings = get_settings()
    db_context = DatabaseContext(str(settings.mariadb_url))

    async with db_context.get_session() as session:
        # Build query with ORDER BY path_id
        stmt = select(Section).order_by(Section.path_id)
        
        if book_id:
            from src.core.models import Chapter
            stmt = stmt.join(Chapter).where(Chapter.book_id == book_id)
        if limit:
            stmt = stmt.limit(limit)

        result = await session.exec(stmt)
        sections = result.all()

        if not sections:
            print("No sections found.")
            return

        # Print header
        print(f"{'Path':<20} {'Word Count':<12} {'Title'}")
        print("-" * 80)

        total_words = 0
        for section in sections:
            # Compute word count from raw_text if available
            if section.raw_text:
                word_count = len(section.raw_text.split())
            else:
                word_count = 0

            total_words += word_count
            # Truncate title if too long
            title = section.title[:50] if section.title else ""
            print(f"{section.path_id:<20} {word_count:<12} {title}")

        print("-" * 80)
        print(f"Total sections: {len(sections)}")
        print(f"Total words across all sections: {total_words}")


def main():
    parser = argparse.ArgumentParser(description="Show word count per section, ordered by path_id")
    parser.add_argument("--book-id", help="Filter by book ID (optional)")
    parser.add_argument("--limit", type=int, help="Limit number of sections shown")
    args = parser.parse_args()

    try:
        asyncio.run(show_word_counts(book_id=args.book_id, limit=args.limit))
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        logger.exception("Error")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
