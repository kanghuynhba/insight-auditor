"""Async fact-extraction service with an internal in-memory job store.

The service owns a plain ``dict`` for job tracking.  No ``JobStore`` class
and no ``ExtractionJobModel`` / ``ExtractionStatusModel`` are used here.
The router receives a lightweight ``dict`` and maps it to the appropriate
response DTO (:class:`~src.response.extract_fact_response.ExtractFactResponse`).

Design principles
-----------------
* Services never import ``src/request/`` or ``src/response/``.
* Services never import entities directly (only via ``TYPE_CHECKING``).
* All entity-to-model conversion happens in ``src/converter/entity_to_model.py``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks

from src.core.enums import ExtractionStatus
from src.core.helpers import now
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.persistence.base_repository import Repository
from src.index.operations.extract_facts import extract_facts
from src.infrastructure.chunking.chunker import Chunker
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)

if TYPE_CHECKING:
    from src.core.atomic_fact import AtomicFact
    from src.core.section import Section
    from src.core.text_chunk import TextChunk

logger = logging.getLogger(__name__)

# Type alias for a job-store entry.
_JobEntry = Dict[str, Any]


class FactsExtractionService:
    """Extracts atomic facts from section text chunks using an LLM.

    Architecture notes
    ------------------
    * The service schedules the actual work in FastAPI ``BackgroundTasks``.
    * Job metadata is tracked in an internal ``dict`` – no external
      ``JobStore`` class or shared singleton is needed.
    * The router remains free of business logic; it only calls
      :meth:`start_extraction` and converts the returned dict to a response DTO.
    * Services never import ``src/request/`` or ``src/response/``.
    """

    def __init__(
        self,
        llm: LLMCompletion,
        chunker: Optional[Chunker] = None,
        section_repo: Optional[Repository["Section"]] = None,
        fact_repo: Optional[Repository["AtomicFact"]] = None,
        concurrency: int = 1,
    ) -> None:
        self.llm = llm
        self.chunker = chunker
        self.section_repo = section_repo
        self.fact_repo = fact_repo
        self.semaphore = asyncio.Semaphore(concurrency)
        # Internal job store: job_id → _JobEntry dict
        self._jobs: Dict[str, _JobEntry] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_extraction(
        self,
        section_id: str,
        force: bool,
        background_tasks: BackgroundTasks,
    ) -> _JobEntry:
        """Enqueue a background extraction task and return a job-info dict immediately.

        The section's ``extraction_status`` is **not** set to PENDING here;
        that happens inside :meth:`_run_extraction` so the DB update occurs in
        the background task's own session context.

        Args:
            section_id:       The section to extract facts from.
            force:            When ``True``, existing facts are deleted first.
            background_tasks: FastAPI's ``BackgroundTasks`` instance injected
                              by the router.

        Returns:
            A plain ``dict`` with keys ``job_id``, ``section_id``, ``status``,
            ``created_at``, and ``message``.  The router maps this to
            :class:`~src.response.extract_fact_response.ExtractFactResponse`.
        """
        job_id = str(uuid4())
        created: datetime = now()

        entry: _JobEntry = {
            "job_id": job_id,
            "section_id": section_id,
            "status": "pending",
            "progress": 0.0,
            "created_at": created,
            "message": None,
            "result_summary": None,
            "error": None,
            "completed_at": None,
        }

        async with self._lock:
            self._jobs[job_id] = entry

        background_tasks.add_task(self._run_extraction, section_id, force, job_id)
        logger.info("Enqueued extraction job %s for section %s", job_id, section_id)

        # Return a copy so the caller sees the immutable snapshot at enqueue time.
        return {k: v for k, v in entry.items()}

    async def get_extraction_status(self, job_id: str) -> _JobEntry:
        """Return the current status of an extraction job as a plain dict.

        Args:
            job_id: The UUID string returned by :meth:`start_extraction`.

        Returns:
            A dict with job state fields.  The router converts this to the
            appropriate response DTO.

        Raises:
            ValueError: When *job_id* is not found in the internal store.
        """
        async with self._lock:
            entry = self._jobs.get(job_id)
        if entry is None:
            raise ValueError(f"Extraction job {job_id!r} not found")
        return {k: v for k, v in entry.items()}

    # ------------------------------------------------------------------
    # Private – background task
    # ------------------------------------------------------------------

    async def _run_extraction(
        self,
        section_id: str,
        force: bool,
        job_id: str,
    ) -> None:
        """Perform fact extraction for *section_id* and keep the job dict updated.

        This method runs in the background.  It:
        1. Marks the job and section as ``running`` / ``PENDING``.
        2. Chunks the section text.
        3. Extracts facts from each chunk concurrently (bounded by ``semaphore``).
        4. Persists facts, updates the section status to ``DONE`` or ``ERROR``.
        5. Updates the internal job dict with the final status.

        Args:
            section_id: The section to process.
            force:      Whether to delete pre-existing facts first.
            job_id:     The UUID of the job entry in :attr:`_jobs`.
        """
        await self._set_job_field(job_id, "status", "running")

        try:
            section = await self.section_repo.find_by_id(section_id)  # type: ignore[union-attr]
            if not section:
                raise ValueError(f"Section {section_id} not found")

            # Mark section as PENDING in DB
            section.extraction_status = ExtractionStatus.PENDING
            await self.section_repo.save(section)  # type: ignore[union-attr]
            await self.section_repo.session.commit()  # type: ignore[union-attr]

            logger.info(
                "[job=%s] Extracting facts for section %s (force=%s)",
                job_id,
                section_id,
                force,
            )

            chunks: List["TextChunk"] = self.chunker.chunk_section(section)  # type: ignore[union-attr]

            if not chunks:
                logger.warning(
                    "[job=%s] No chunks found for section %s", job_id, section_id
                )
                await self._finalise_job(job_id, section_id, "completed", 0)
                return

            tasks = [self._process_chunk(chunk, force) for chunk in chunks]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            failed = any(isinstance(r, Exception) for r in results)
            all_facts = self._aggregate(results)

            # Update section status in DB
            section = await self.section_repo.find_by_id(section_id)  # type: ignore[union-attr]
            if section:
                section.extraction_status = (
                    ExtractionStatus.ERROR if failed else ExtractionStatus.DONE
                )
                await self.section_repo.save(section)  # type: ignore[union-attr]
                await self.section_repo.session.commit()  # type: ignore[union-attr]

            if failed:
                failed_count = sum(1 for r in results if isinstance(r, Exception))
                logger.warning("[job=%s] %d chunk(s) failed", job_id, failed_count)

            await self._finalise_job(
                job_id,
                section_id,
                "failed" if failed else "completed",
                len(all_facts),
            )

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "[job=%s] Unexpected error during extraction: %s", job_id, exc
            )
            try:
                await self.section_repo.session.rollback()  # type: ignore[union-attr]
                section = await self.section_repo.find_by_id(section_id)  # type: ignore[union-attr]
                if section:
                    section.extraction_status = ExtractionStatus.ERROR
                    await self.section_repo.save(section)  # type: ignore[union-attr]
                    await self.section_repo.session.commit()  # type: ignore[union-attr]
            except Exception:  # pylint: disable=broad-except
                pass  # best-effort rollback

            async with self._lock:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = str(exc)
                self._jobs[job_id]["completed_at"] = now()

    async def _finalise_job(
        self,
        job_id: str,
        section_id: str,
        status: str,
        fact_count: int,
    ) -> None:
        """Update the job dict with the final status after extraction completes."""
        async with self._lock:
            self._jobs[job_id]["status"] = status
            self._jobs[job_id]["progress"] = 1.0
            self._jobs[job_id]["result_summary"] = f"{fact_count} facts extracted"
            self._jobs[job_id]["completed_at"] = now()
        logger.info(
            "[job=%s] Extraction %s: %d facts for section %s",
            job_id,
            status,
            fact_count,
            section_id,
        )

    async def _set_job_field(self, job_id: str, field: str, value: Any) -> None:
        """Thread-safe helper to update a single field in the job dict."""
        async with self._lock:
            self._jobs[job_id][field] = value

    async def _process_chunk(
        self, chunk: "TextChunk", force: bool = False
    ) -> List["AtomicFact"]:
        """Extract (and optionally delete existing) facts from a single chunk."""
        async with self.semaphore:
            if force:
                await self.fact_repo.delete_by_chunk(chunk.id)  # type: ignore[union-attr]
                await self.fact_repo.session.flush()  # type: ignore[union-attr]
            else:
                existing_facts = await self.fact_repo.find_by_chunk(chunk.id)  # type: ignore[union-attr]
                if existing_facts:
                    logger.info("Skipping chunk %s (already processed)", chunk.id[:8])
                    return existing_facts

            facts = await extract_facts(
                chunk=chunk,
                llm=self.llm,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
            )

            if facts:
                await self.fact_repo.save_all(facts)  # type: ignore[union-attr]
                logger.info("Saved %d facts from chunk %s", len(facts), chunk.id[:8])
            return facts

    @staticmethod
    def _aggregate(results: list) -> List["AtomicFact"]:
        """Flatten gathered task results, logging and skipping exceptions."""
        all_facts: List["AtomicFact"] = []
        for res in results:
            if isinstance(res, Exception):
                logger.error("Chunk processing failed: %s", res)
            elif res:
                all_facts.extend(res)
        return all_facts
