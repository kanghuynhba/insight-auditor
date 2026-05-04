import asyncio
import logging
from typing import List, Optional
from src.core.exceptions import ExtractionNotReadyError
from src.core.enums import ExtractionStatus
from src.services.task_service import TaskService
from src.core.text_chunk import TextChunk
from src.infrastructure.persistence.base_repository import Repository
from src.core.atomic_fact import AtomicFact
from src.core.section import Section
from src.index.operations.extract_facts import extract_facts
from src.infrastructure.llm.completion.completion import LLMCompletion
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
        section_repo: Repository[Section],
        fact_repo: Repository[AtomicFact],
        vector_repo: VectorRepository,
        task_service: Optional[TaskService] = None,
        concurrency: int = 1,
    ):
        self.llm = llm
        self.vector_repo = vector_repo
        self.section_repo = section_repo
        self.fact_repo = fact_repo
        self.task_service = task_service
        self.semaphore = asyncio.Semaphore(concurrency)

    async def extract_facts_by_section(
        self,
        section_id: str,
        force: bool = False,
        task_id: Optional[str] = None,
    ) -> List[AtomicFact]:
        chunks = await self.vector_repo.get_chunks_by_section(section_id)
        if not chunks:
            logger.warning(f"No chunks found for section {section_id}")
            return []

        try:
            if self.task_service and task_id:
                await self.task_service.start(task_id)

            tasks = [self._process_chunk(chunk, force) for chunk in chunks]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # B-07: compute failed once
            failed = any(isinstance(r, Exception) for r in results)
            all_facts = self._aggregate(results)

            section = await self.section_repo.find_by_id(section_id)
            if section:
                if failed:
                    section.extraction_status = ExtractionStatus.ERROR
                else:
                    section.extraction_status = ExtractionStatus.DONE
                await self.section_repo.save(section)
                await self.section_repo.session.commit()

            if self.task_service and task_id:
                await self.task_service.done(
                    task_id, result={"facts_extracted": len(all_facts)}
                )
            return all_facts

        except Exception as e:
            # B-03: rollback first, then update section status in a clean state
            await self.section_repo.session.rollback()
            section = await self.section_repo.find_by_id(section_id)
            if section:
                section.extraction_status = ExtractionStatus.ERROR
                await self.section_repo.save(section)
                await self.section_repo.session.commit()
            if self.task_service and task_id:
                await self.task_service.error(task_id, exc=e)
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

    async def generate_hints(
        self,
        section_id: str,
        attempt_number: Optional[int] = None,
        max_hints: int = 5,
    ) -> List[str]:
        """Return one question per fact, prioritized by rank."""
        facts = await self.fact_repo.find_by_section(section_id)
        if not facts:
            return []

        # (Optional) filter by attempt_number – would need audit_repo
        # For now, ignore attempt_number.

        sorted_facts = sorted(facts, key=lambda f: f.rank.value)  # Critical first
        hints = []
        for fact in sorted_facts:
            if fact.questions:
                hints.append(fact.questions[0])
            if len(hints) >= max_hints:
                break
        return hints

    async def get_facts_for_section(self, section_id: str) -> dict:
        """Return formatted facts or raise ValueError with status."""
        section = await self.section_repo.find_by_id(section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        if section.extraction_status != ExtractionStatus.DONE:
            raise ExtractionNotReadyError(
                status=section.extraction_status.value,
                message="No facts extracted yet",
            )
        facts = await self.fact_repo.find_by_section(section_id)
        return {
            "section_id": section_id,
            "extraction_status": "done",
            "facts": [f.model_dump() for f in facts],
        }

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
