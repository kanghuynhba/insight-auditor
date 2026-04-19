# src/services/extraction.py
import asyncio
import logging
from typing import Dict, List, Set

from src.core.atomic_fact import AtomicFact
from src.core.models import Section
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(
        self,
        llm: LLMCompletion,
        db_context: DatabaseContext,
        concurrency: int = 5,
    ):
        self.llm = llm
        self.db_context = db_context
        self.semaphore = asyncio.Semaphore(concurrency)
        self._section_locks: Dict[str, asyncio.Lock] = {}
        self._processed_sections: Set[str] = set()

    async def extract_facts_for_book(self, book_id: str) -> List[AtomicFact]:
        """
        Fetches all Sections for a book from MariaDB and concurrently
        extracts AtomicFacts for each one that hasn't been processed yet.
        """

        self._processed_sections.clear()
        self._section_locks.clear()

        logger.info(f"Starting extraction for book: {book_id}")

        sections = await self._fetch_sections(book_id)
        if not sections:
            logger.warning(f"No sections found for book {book_id}.")
            return []

        tasks = [self._process_section(section) for section in sections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._aggregate(results)

    async def _fetch_sections(self, book_id: str) -> List[Section]:
        async with self.db_context.get_session() as session:
            repo = self.db_context.get_repository(session, Section)
            return await repo.find_by_book(book_id)

    async def _process_section(self, section: Section) -> List[AtomicFact]:
        """
        Idempotent per-section worker:
          1. Fast in-memory check
          2. Per-section lock (prevents duplicate LLM calls under concurrency)
          3. DB check (persistence layer dedup)
          4. LLM extraction + save
        """
        if section.id in self._processed_sections:
            return []

        async with self.semaphore:
            lock = self._section_locks.setdefault(section.id, asyncio.Lock())

            async with lock:
                # Re-check after acquiring lock (another coroutine may have finished first)
                if section.id in self._processed_sections:
                    return []

                async with self.db_context.get_session() as session:
                    fact_repo = self.db_context.get_repository(session, AtomicFact)

                    existing = await fact_repo.find_by_section(section.id)
                    if existing:
                        self._processed_sections.add(section.id)
                        return existing

                    if not section.raw_text:
                        logger.warning(
                            f"Section {section.id} has no raw_text — skipping."
                        )
                        return []

                    facts = await self._extract_and_save(session, fact_repo, section)
                    self._processed_sections.add(section.id)
                    return facts

    async def _extract_and_save(
        self, session, fact_repo, section: Section
    ) -> List[AtomicFact]:
        """Calls the LLM (off the event loop) and persists the resulting facts."""

        logger.debug(f"LLM extraction for section: {section.path_id}")

        # extract_atomic_facts is sync → run in a thread to avoid blocking
        facts: List[AtomicFact] = await asyncio.to_thread(
            extract_atomic_facts,
            self.llm,
            ATOMIC_FACT_SYSTEM,
            ATOMIC_FACT_USER,
            section.raw_text,
            section.path_id,
            section.id,
        )

        for fact in facts:
            await fact_repo.save(fact)

        await session.commit()
        logger.info(f"Section {section.path_id}: saved {len(facts)} facts.")
        return facts

    @staticmethod
    def _aggregate(results: list) -> List[AtomicFact]:
        all_facts: List[AtomicFact] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Section failed: {result}", exc_info=result)
            elif result:
                all_facts.extend(result)
        return all_facts
