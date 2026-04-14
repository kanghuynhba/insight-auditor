# src/services/extraction.py
import asyncio
import logging
import re
from typing import List

from src.core.atomic_fact import AtomicFact
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.databases.vectors.lancedb_repo import LanceDBRepository
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)
from src.infrastructure.storage.mariadb_storage import MariaDBStorage

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service to extract atomic facts from chunks stored in LanceDB."""

    def __init__(
        self,
        llm: LiteLLMCompletion,
        vector_db: LanceDBRepository,
        fact_storage: MariaDBStorage,
        concurrency: int = 8,
    ):
        self.llm = llm
        self.vector_db = vector_db
        self.fact_storage = fact_storage
        self.concurrency = concurrency

    async def extract_facts_for_book(self, book_id: str) -> List[AtomicFact]:
        """
        Extract atomic facts from all chunks belonging to a book.
        Returns a list of all extracted AtomicFact objects.
        """
        logger.info(f"Fetching chunks for book {book_id}")
        chunks = await self.vector_db.get_chunks_by_book(book_id)
        logger.info(f"Found {len(chunks)} chunks to process")

        semaphore = asyncio.Semaphore(self.concurrency)

        async def process_chunk(chunk: dict):
            async with semaphore:
                chunk_id = chunk["id"]
                # Skip if this chunk was already processed
                if await self._is_chunk_processed(chunk_id):
                    logger.debug(f"Chunk {chunk_id} already processed, skipping")
                    return []

                logger.debug(f"Extracting facts from chunk {chunk_id}")
                # Run the synchronous LLM call in a thread
                facts = await asyncio.to_thread(
                    extract_atomic_facts,
                    self.llm,
                    ATOMIC_FACT_SYSTEM,
                    ATOMIC_FACT_USER,
                    chunk["text"],
                    chunk["path_id"],
                    chunk["section_id"],
                )
                # Store each fact
                for fact in facts:
                    key = f"fact:{fact.section_id}:{fact.id}"
                    await self.fact_storage.set(key, fact)
                # Mark chunk as processed
                await self._mark_chunk_processed(chunk_id)
                logger.info(f"Chunk {chunk_id}: extracted {len(facts)} facts")
                return facts

        # Process all chunks concurrently with semaphore
        tasks = [process_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        all_facts = [fact for facts in results for fact in facts]
        all_facts = self._deduplicate_facts(all_facts)
        logger.info(f"Total facts extracted: {len(all_facts)}")
        return all_facts

    async def _is_chunk_processed(self, chunk_id: str) -> bool:
        """Check if a chunk has already been processed."""
        key = f"processed_chunk:{chunk_id}"
        return await self.fact_storage.get(key) is not None

    async def _mark_chunk_processed(self, chunk_id: str) -> None:
        """Mark a chunk as processed."""
        key = f"processed_chunk:{chunk_id}"
        await self.fact_storage.set(key, "done")

    def _deduplicate_facts(self, facts: list[AtomicFact]) -> list[AtomicFact]:
        """Remove near-duplicate facts by normalizing and comparing point text."""
        seen = set()
        unique = []
        for fact in facts:
            # Normalize: lowercase, strip punctuation, collapse whitespace
            key = re.sub(r"[^a-z0-9 ]", "", fact.point.lower())
            key = re.sub(r"\s+", " ", key).strip()
            # Use first 80 characters as fingerprint (catches paraphrases)
            fingerprint = key[:80]
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(fact)
        return unique
