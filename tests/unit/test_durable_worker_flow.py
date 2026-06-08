from pathlib import Path

import pytest

from src.api.routers import books, jobs as jobs_router, sections
from src.domain import AtomicFact, Book, ExtractionStatus, ProcessingJob, TextChunk
from src.domain.section import Section
from src.domain.toc_node import TocNode
from src.extraction import FactExtraction
from src.jobs import JOB_EXTRACT_FACTS, JOB_PARSE_BOOK, QUEUE_FACT, QUEUE_PARSE, JobService
from src.response.job import ProcessingJobResponse
from src.workers import fact_worker, parse_worker, runner


class FakeUploadFile:
    filename = "sample.pdf"


class FakeSettings:
    chunk_size = 400
    chunk_overlap = 40
    job_retry_base_delay_seconds = 0.0


class DurableFlowStore:
    def __init__(self):
        self.books: dict[str, Book] = {}
        self.sections: dict[str, Section] = {}
        self.jobs: dict[str, ProcessingJob] = {}
        self.chunks: list[TextChunk] = []
        self.facts: list[AtomicFact] = []
        self.commits = 0

    async def save_book(self, book):
        self.books[book.id] = book
        for section in book.sections:
            section.book_id = book.id
            self.sections[section.id] = section
        return book

    async def get_book(self, book_id):
        return self.books.get(book_id)

    async def delete_book_chunks(self, book_id):
        self.chunks = [chunk for chunk in self.chunks if chunk.book_id != book_id]

    async def delete_sections_by_book(self, book_id):
        self.sections = {
            section_id: section
            for section_id, section in self.sections.items()
            if section.book_id != book_id
        }

    async def save_chunks(self, chunks):
        self.chunks.extend(chunks)

    async def get_section(self, section_id):
        return self.sections.get(section_id)

    async def save_section(self, section):
        self.sections[section.id] = section
        return section

    async def get_chunks_by_section(self, section_id):
        return [chunk for chunk in self.chunks if chunk.section_id == section_id]

    async def get_facts_by_chunk(self, chunk_id):
        return [fact for fact in self.facts if fact.chunk_id == chunk_id]

    async def get_facts_by_section(self, section_id):
        return [fact for fact in self.facts if fact.section_id == section_id]

    async def save_facts(self, facts):
        self.facts.extend(facts)
        return facts

    async def delete_facts_by_chunk(self, chunk_id):
        self.facts = [fact for fact in self.facts if fact.chunk_id != chunk_id]

    async def create_processing_job(self, **kwargs):
        job = ProcessingJob(**kwargs)
        self.jobs[job.id] = job
        return job

    async def get_processing_job(self, job_id):
        return self.jobs.get(job_id)

    async def find_active_job(self, job_type, resource_type, resource_id):
        for job in self.jobs.values():
            if (
                job.job_type == job_type
                and job.resource_type == resource_type
                and job.resource_id == resource_id
                and job.status in {"queued", "running"}
            ):
                return job
        return None

    async def update_processing_job_status(self, job_id, status, **kwargs):
        job = self.jobs[job_id]
        job.status = status
        for key, value in kwargs.items():
            if value is not None and hasattr(job, key):
                setattr(job, key, value)
        return job

    async def mark_job_succeeded(self, job_id, message=None):
        return await self.update_processing_job_status(
            job_id, "succeeded", message=message, progress=1.0
        )

    async def mark_job_failed(self, job_id, error):
        return await self.update_processing_job_status(
            job_id, "failed", error=error, progress=1.0
        )

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


class FakeIngestion:
    def __init__(self, store):
        self.store = store


class FakeLoader:
    def extract_raw(self, path):
        section = Section(
            id="section-1",
            title="Chapter 1",
            level=1,
            order=0,
            href="chapter-1",
            raw_text="Durable queues move slow textbook work out of requests.",
        )
        toc_root = TocNode(
            id="root",
            title="Root",
            level=0,
            order=0,
            children=[
                TocNode(
                    id="toc-1",
                    title=section.title,
                    level=1,
                    order=0,
                    section_id=section.id,
                    section=section,
                    href=section.href,
                )
            ],
        )
        return type(
            "ExtractedBook",
            (),
            {"title": "Parsed Book", "author": "Author", "toc_root": toc_root},
        )()


class FakeBookIngestion:
    def __init__(self, store, llm, settings):
        self.store = store

    def _loaders(self):
        return {parse_worker.FileType.Pdf: FakeLoader()}

    async def ingest_chunks(self, book):
        chunks = [
            TextChunk(
                id=f"chunk-{section.id}",
                book_id=book.id,
                section_id=section.id,
                text=section.raw_text or "",
                chunk_index=0,
                chunk_level="sentence_group",
                start_char=0,
                end_char=len(section.raw_text or ""),
            )
            for section in book.sections
        ]
        await self.store.save_chunks(chunks)


@pytest.mark.asyncio
async def test_durable_parse_and_fact_worker_flow(monkeypatch, tmp_path):
    store = DurableFlowStore()
    job_service = JobService(store)
    upload_path = tmp_path / "sample.pdf"

    async def fake_save_upload(file):
        upload_path.write_text("pdf", encoding="utf-8")
        return upload_path

    async def fake_extract_facts(**kwargs):
        chunk = kwargs["chunk"]
        return [
            AtomicFact(
                section_id=chunk.section_id,
                chunk_id=chunk.id,
                point="Durable queues move slow work out of requests.",
                reason="The chunk states this directly.",
                questions=["What do durable queues move?"],
            )
        ]

    monkeypatch.setattr(books, "save_upload", fake_save_upload)
    monkeypatch.setattr(parse_worker, "BookIngestion", FakeBookIngestion)
    monkeypatch.setattr(fact_worker, "extract_facts", fake_extract_facts)

    upload_response = await books.upload_book(
        file=FakeUploadFile(),
        ingestion=FakeIngestion(store),
        jobs=job_service,
    )

    book = await store.get_book(upload_response.book_id)
    parse_job = await store.get_processing_job(upload_response.job_id)
    assert book is not None
    assert book.upload_status == "uploaded"
    assert parse_job is not None
    assert parse_job.job_type == JOB_PARSE_BOOK
    assert parse_job.queue_name == QUEUE_PARSE

    parse_job.status = "running"
    parse_job.attempts = 1
    await runner.process_job(parse_job, store, llm=None, settings=None)

    assert book.upload_status == "ready"
    assert store.sections["section-1"].title == "Chapter 1"
    assert store.chunks[0].section_id == "section-1"

    extraction_response = await sections.extract_facts(
        section_id="section-1",
        force=False,
        extraction=FactExtraction(store),
        jobs=job_service,
    )
    extract_job = await store.get_processing_job(extraction_response.extraction_job_id)
    assert extract_job is not None
    assert extract_job.job_type == JOB_EXTRACT_FACTS
    assert extract_job.queue_name == QUEUE_FACT
    assert extract_job.payload == {"force": False}

    duplicate_response = await sections.extract_facts(
        section_id="section-1",
        force=False,
        extraction=FactExtraction(store),
        jobs=job_service,
    )
    assert duplicate_response.extraction_job_id == extract_job.id

    forced_response = await sections.extract_facts(
        section_id="section-1",
        force=True,
        extraction=FactExtraction(store),
        jobs=job_service,
    )
    assert forced_response.extraction_job_id != extract_job.id
    forced_job = await store.get_processing_job(forced_response.extraction_job_id)
    assert forced_job.payload == {"force": True}

    extract_job.status = "running"
    extract_job.attempts = 1
    await runner.process_job(
        extract_job,
        store,
        llm=type("LLM", (), {"completion": None})(),
        settings=FakeSettings(),
    )

    section = await store.get_section("section-1")
    assert section.extraction_status == ExtractionStatus.DONE

    facts = await sections.get_facts("section-1", extraction=FactExtraction(store))
    assert len(facts) == 1
    assert facts[0].point == "Durable queues move slow work out of requests."

    job_response = await jobs_router.get_job(
        extract_job.id,
        jobs=job_service,
    )
    assert isinstance(job_response, ProcessingJobResponse)
    assert job_response.status == "succeeded"
    assert job_response.resource_id == "section-1"
