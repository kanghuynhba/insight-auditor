import asyncio
import logging
from typing import List, Optional
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.chunking.chunker import Chunker
from src.core.exceptions import ExtractionNotReadyError
from src.core.enums import ExtractionStatus
from src.core.text_chunk import TextChunk
from src.infrastructure.persistence.base_repository import Repository
from src.core.atomic_fact import AtomicFact
from src.core.section import Section
from src.index.operations.extract_facts import extract_facts
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.core.config import get_settings
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)

logger = logging.getLogger(__name__)


class FactsExtractionService:
    def __init__(
        self,
        llm: LLMCompletion,
        chunker: Optional[Chunker] = None,
        section_repo: Repository[Section] = None,
        fact_repo: Repository[AtomicFact] = None,
        concurrency: int = 1,
    ):
        self.llm = llm
        self.section_repo = section_repo
        self.fact_repo = fact_repo
        self.semaphore = asyncio.Semaphore(concurrency)
        self.chunker = chunker

    async def extract_facts_by_section(
        self,
        section_id: str,
        force: bool = False,
    ) -> List[AtomicFact]:
        """
        Extract atomic facts from all chunks of a section.

        Args:
            section_id: The section to process
            force: If True, delete existing facts for the section before extraction

        Returns:
            List of extracted AtomicFact objects
        """
        section = await self.section_repo.find_by_id(section_id)
        if not section:
            logger.error(f"Section {section_id} not found")
            return []

        logger.info(f"Extracting facts for section {section_id} (force={force})")

        chunks: List[TextChunk] = self.chunker.chunk_section(section)

        if not chunks:
            logger.warning(f"No chunks found for section {section_id}")
            return []

        try:
            # Process all chunks concurrently
            tasks = [self._process_chunk(chunk, force) for chunk in chunks]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for failures and aggregate successful facts
            failed = any(isinstance(r, Exception) for r in results)
            all_facts = self._aggregate(results)

            # Update section status based on outcome
            section = await self.section_repo.find_by_id(section_id)
            if section:
                section.extraction_status = (
                    ExtractionStatus.ERROR if failed else ExtractionStatus.DONE
                )
                await self.section_repo.save(section)
                await self.section_repo.session.commit()

            if failed:
                logger.warning(
                    f"Section {section_id} completed with {sum(1 for r in results if isinstance(r, Exception))} failed chunks"
                )

            return all_facts

        except Exception as e:
            # Unexpected error – rollback and mark section as ERROR
            await self.section_repo.session.rollback()
            section = await self.section_repo.find_by_id(section_id)
            if section:
                section.extraction_status = ExtractionStatus.ERROR
                await self.section_repo.save(section)
                await self.section_repo.session.commit()
            logger.exception(
                f"Unexpected error during fact extraction for section {section_id}: {e}"
            )
            raise

    async def _process_chunk(
        self, chunk: TextChunk, force: bool = False
    ) -> List[AtomicFact]:
        async with self.semaphore:
            # B-01: delete existing facts if forced
            if force:
                # Ensure fact_repo has delete_by_chunk method
                await self.fact_repo.delete_by_chunk(chunk.id)
                await self.fact_repo.session.flush()
            else:
                existing_facts = await self.fact_repo.find_by_chunk(chunk.id)
                if existing_facts:
                    logger.info(f"Skipping chunk {chunk.id[:8]} (already processed)")
                    return existing_facts

            facts = await extract_facts(
                chunk=chunk,
                llm=self.llm,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
            )

            if facts:
                await self.fact_repo.save_all(facts)
                logger.info(f"Saved {len(facts)} facts from chunk {chunk.id[:8]}")
            return facts

    @staticmethod
    def _aggregate(results: list) -> List[AtomicFact]:
        all_facts = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Chunk processing failed: {res}")
            elif res:
                all_facts.extend(res)
        return all_facts

    # Optional: book‑level extraction (kept as is, but also update status?)
    # For now, it doesn't use task_service – could be extended later.
    # async def extract_facts_for_book(self, book_id: str) -> List[AtomicFact]:
    #     logger.info(f"Extracting facts for book {book_id}")
    #     section_ids = await self.section_repo.get_ids_by_book(book_id)
    #     if not section_ids:
    #         return []
    #     tasks = [self.extract_facts_by_section(sid) for sid in section_ids]
    #     results = await asyncio.gather(*tasks, return_exceptions=True)
    #     return self._aggregate(results)
