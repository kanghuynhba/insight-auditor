from pathlib import Path

import pytest

from src.api.routers import books
from src.domain import Book, ProcessingJob
from src.domain.section import Section
from src.domain.toc_node import TocNode
from src.jobs import JOB_PARSE_BOOK, QUEUE_PARSE
from src.workers import parse_worker


class FakeUploadFile:
    filename = "sample.pdf"


class FakeUploadStore:
    def __init__(self):
        self.saved_book = None

    async def save_book(self, book):
        self.saved_book = book
        return book


class FakeIngestion:
    def __init__(self):
        self.store = FakeUploadStore()


class FakeJobs:
    def __init__(self):
        self.book_id = None

    async def enqueue_parse_book(self, book_id):
        self.book_id = book_id
        return ProcessingJob(
            id="job-1",
            job_type=JOB_PARSE_BOOK,
            queue_name=QUEUE_PARSE,
            resource_type="book",
            resource_id=book_id,
        )


@pytest.mark.asyncio
async def test_upload_creates_minimal_book_and_parse_job(monkeypatch, tmp_path):
    upload_path = tmp_path / "sample.pdf"

    async def fake_save_upload(file):
        upload_path.write_text("pdf", encoding="utf-8")
        return upload_path

    monkeypatch.setattr(books, "save_upload", fake_save_upload)
    ingestion = FakeIngestion()
    jobs = FakeJobs()

    response = await books.upload_book(
        file=FakeUploadFile(),
        ingestion=ingestion,
        jobs=jobs,
    )

    saved_book = ingestion.store.saved_book
    assert saved_book is not None
    assert saved_book.id == response.book_id
    assert saved_book.upload_status == "uploaded"
    assert saved_book.source_format == "pdf"
    assert saved_book.file_path == str(upload_path)
    assert jobs.book_id == saved_book.id
    assert response.job_id == "job-1"
    assert response.status == "uploaded"


class FakeParseStore:
    def __init__(self, book):
        self.book = book
        self.commits = 0
        self.deleted_book_id = None
        self.deleted_chunks_book_id = None
        self.saved_chunks = False

    async def get_book(self, book_id):
        return self.book if self.book.id == book_id else None

    async def save_book(self, book):
        self.book = book
        return book

    async def delete_sections_by_book(self, book_id):
        self.deleted_book_id = book_id

    async def delete_book_chunks(self, book_id):
        self.deleted_chunks_book_id = book_id

    async def save_chunks(self, chunks):
        self.saved_chunks = True

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


class FakeLoader:
    def __init__(self, toc_root):
        self.toc_root = toc_root

    def extract_raw(self, path):
        return type(
            "Extracted",
            (),
            {
                "title": "Parsed Title",
                "author": "Parsed Author",
                "toc_root": self.toc_root,
            },
        )()


class FakeBookIngestion:
    def __init__(self, store, llm, settings):
        self.store = store
        self.ingested_book = None

    def _loaders(self):
        return {"pdf": FakeLoader(make_toc_root())}

    async def ingest_chunks(self, book):
        self.ingested_book = book
        await self.store.save_chunks([])


def make_toc_root():
    section = Section(id="section-1", raw_text="Some text.")
    return TocNode(
        id="fake_root",
        title="Root",
        level=0,
        order=0,
        children=[
            TocNode(
                id="toc-1",
                title="Chapter 1",
                level=1,
                order=0,
                section_id=section.id,
                section=section,
                href="1",
            )
        ],
    )


@pytest.mark.asyncio
async def test_parse_worker_marks_book_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(parse_worker, "BookIngestion", FakeBookIngestion)
    book = Book(
        id="book-1",
        title="sample",
        author=None,
        source_format="pdf",
        file_path=str(tmp_path / "sample.pdf"),
        source_filename="sample.pdf",
        upload_status="uploaded",
        table_of_content=[],
    )
    store = FakeParseStore(book)
    job = ProcessingJob(
        job_type=JOB_PARSE_BOOK,
        queue_name=QUEUE_PARSE,
        resource_type="book",
        resource_id=book.id,
    )

    message = await parse_worker.ParseWorker(store, "llm", "settings").handle(job)

    assert message == "Book parsed"
    assert store.book.upload_status == "ready"
    assert store.book.title == "Parsed Title"
    assert store.book.author == "Parsed Author"
    assert store.book.table_of_content
    assert store.book.sections[0].title == "Chapter 1"
    assert store.deleted_book_id == "book-1"
    assert store.deleted_chunks_book_id == "book-1"


@pytest.mark.asyncio
async def test_parse_worker_retry_deletes_existing_sections_and_chunks(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(parse_worker, "BookIngestion", FakeBookIngestion)
    book = Book(
        id="book-1",
        title="partially parsed",
        author=None,
        source_format="pdf",
        file_path=str(tmp_path / "sample.pdf"),
        source_filename="sample.pdf",
        upload_status="failed",
        table_of_content=[{"title": "Old chapter"}],
    )
    store = FakeParseStore(book)
    job = ProcessingJob(
        job_type=JOB_PARSE_BOOK,
        queue_name=QUEUE_PARSE,
        resource_type="book",
        resource_id=book.id,
    )

    message = await parse_worker.ParseWorker(store, "llm", "settings").handle(job)

    assert message == "Book parsed"
    assert store.book.upload_status == "ready"
    assert store.deleted_book_id == "book-1"
    assert store.deleted_chunks_book_id == "book-1"


@pytest.mark.asyncio
async def test_parse_worker_marks_book_failed_on_error(monkeypatch, tmp_path):
    class FailingBookIngestion(FakeBookIngestion):
        def _loaders(self):
            raise RuntimeError("parse failed")

    monkeypatch.setattr(parse_worker, "BookIngestion", FailingBookIngestion)
    book = Book(
        id="book-1",
        title="sample",
        author=None,
        source_format="pdf",
        file_path=str(tmp_path / "sample.pdf"),
        source_filename="sample.pdf",
        upload_status="uploaded",
        table_of_content=[],
    )
    store = FakeParseStore(book)
    job = ProcessingJob(
        job_type=JOB_PARSE_BOOK,
        queue_name=QUEUE_PARSE,
        resource_type="book",
        resource_id=book.id,
    )

    with pytest.raises(RuntimeError, match="parse failed"):
        await parse_worker.ParseWorker(store, "llm", "settings").handle(job)

    assert store.book.upload_status == "failed"
