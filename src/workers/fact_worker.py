import asyncio
import logging

from src.domain import AtomicFact, ExtractionStatus, ProcessingJob, Section, TextChunk
from src.extraction._parser import extract_facts
from src.ingestion._chunking import ChunkContext, NaturalBoundaryChunker
from src.llm import LLMGateway
from src.llm.prompts.extract_atomic_facts import ATOMIC_FACT_SYSTEM, ATOMIC_FACT_USER
from src.store import Store

logger = logging.getLogger(__name__)


class FactWorker:
    def __init__(self, store: Store, llm: LLMGateway, settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings
        self.chunker = NaturalBoundaryChunker(settings)
        self.semaphore = asyncio.Semaphore(1)

    async def handle(self, job: ProcessingJob) -> str:
        section_id = job.resource_id
        force = bool((job.payload or {}).get("force", False))

        section = await self.store.get_section(section_id)
        if not section:
            raise ValueError(f"Section {section_id!r} not found")

        if section.extraction_status == ExtractionStatus.DONE and not force:
            return "Facts already extracted"

        section.extraction_status = ExtractionStatus.PENDING
        await self.store.save_section(section)
        await self.store.commit()

        try:
            chunks = await self.store.get_chunks_by_section(section_id)
            if not chunks:
                chunks = self._chunk_section(section)

            if not chunks:
                section.extraction_status = ExtractionStatus.DONE
                await self.store.save_section(section)
                await self.store.commit()
                return "0 facts extracted"

            results = await asyncio.gather(
                *(self._process_chunk(chunk, force) for chunk in chunks),
                return_exceptions=True,
            )
            failed = [result for result in results if isinstance(result, Exception)]
            if failed:
                raise failed[0]

            fact_count = sum(len(result) for result in results if isinstance(result, list))

            section = await self.store.get_section(section_id)
            if section:
                section.extraction_status = ExtractionStatus.DONE
                await self.store.save_section(section)
            await self.store.commit()
            return f"{fact_count} facts extracted"
        except Exception:
            await self.store.rollback()
            section = await self.store.get_section(section_id)
            if section:
                section.extraction_status = ExtractionStatus.ERROR
                await self.store.save_section(section)
                await self.store.commit()
            raise

    def _chunk_section(self, section: Section) -> list[TextChunk]:
        return self.chunker.chunk_section(
            section,
            context=ChunkContext(
                book_id=section.book_id or "",
                section_title=section.title,
            ),
        )

    async def _process_chunk(
        self, chunk: TextChunk, force: bool = False
    ) -> list[AtomicFact]:
        async with self.semaphore:
            if force:
                await self.store.delete_facts_by_chunk(chunk.id)
                await self.store.session.flush()
            else:
                existing_facts = await self.store.get_facts_by_chunk(chunk.id)
                if existing_facts:
                    logger.info("Skipping chunk %s (already processed)", chunk.id[:8])
                    return existing_facts

            facts = await extract_facts(
                chunk=chunk,
                llm=self.llm.completion,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
            )

            if facts:
                await self.store.save_facts(facts)
            return facts
