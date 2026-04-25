import asyncio
import logging
from typing import Any, List

from src.core.text_chunk import TextChunk
from src.infrastructure.persistence.base_repository import Repository
from src.core.atomic_fact import AtomicFact
from src.core.models import Section
from src.index.operations.extract_facts import extract_facts
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)

logger = logging.getLogger(__name__)


class FactsExtractionService:
    # get_chunks_by_book(Book) -> extract_facts_for_book -> save(AtomicFact)
    # get_chunks_by_section(Book) -> extract_facts_for_section -> save(AtomicFact)
    def __init__(
        self,
        llm: LLMCompletion,
        section_repo: Repository[Section],
        fact_repo: Repository[AtomicFact],
        vector_repo: VectorRepository,
        concurrency: int = 5,
    ):
        self.llm = llm
        self.vector_repo = vector_repo
        self.section_repo = section_repo
        self.fact_repo = fact_repo
        self.semaphore = asyncio.Semaphore(concurrency)

    async def extract_facts_for_book(self, book_id: str) -> List[AtomicFact]:
        """
        Orchestrates extraction across a book by delegating to section-level tasks.
        """
        logger.info(f"Workflow started: extract_facts_for_book (ID: {book_id})")

        # 1. Fetch only IDs to keep the 'orchestrator' light
        section_ids = await self.section_repo.get_ids_by_book(book_id)

        if not section_ids:
            logger.warning(f"No sections found for book {book_id}.")
            return []

        # 2. Process each section.
        # Note: extract_facts_by_section handles its own chunks and DB sessions.
        tasks = [self.extract_facts_by_section(sid) for sid in section_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._aggregate(results)

    async def extract_facts_by_section(self, section_id: str) -> List[AtomicFact]:
        """
        Fetches chunks for a specific section and processes them.
        """
        # Fetch chunks from Vector Storage (LanceDB)
        chunks = await self.vector_repo.get_chunks_by_section(section_id)

        if not chunks:
            return []

        # Process chunks with controlled concurrency via self.semaphore
        tasks = [self._process_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._aggregate(results)

    async def _process_chunk(self, chunk: TextChunk) -> List[AtomicFact]:
        async with self.semaphore:
            # 1. IMMEDIATE CHECK: Open a quick session just to check existence
            existing_facts = await self.fact_repo.find_by_chunk(chunk.id)

            if existing_facts:
                # Log at INFO level so you can see the skipped chunks clearly
                logger.info(f"SKIPPING: Chunk {chunk.id[:8]} (Already processed)")
                return existing_facts

            # 2. LLM CALL: Only reached if the chunk is NOT in the database
            # This is where the tokens are spent.
            facts = await extract_facts(
                chunk=chunk,
                llm=self.llm,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
            )

            # 3. PERSISTENCE: Open a new session to save the new facts
            if facts:
                await self.fact_repo.save_all(facts)
                logger.info(f"SAVED: Chunk {chunk.id[:8]} ({len(facts)} facts)")

            return facts

    @staticmethod
    def _aggregate(results: list) -> List[AtomicFact]:
        all_facts: List[AtomicFact] = []
        for res in results:
            if isinstance(res, Exception):
                # Error handling matches the 'WorkflowFunctionOutput' pattern
                logger.error(f"Task encountered error: {res}")
            elif res:
                all_facts.extend(res)
        return all_facts
