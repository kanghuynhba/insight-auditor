"""Books router – thin HTTP layer.

Each handler:
1. Parses the request (path params, query params, body).
2. Calls the appropriate service to get a **service model**.
3. Converts the service model to a **response DTO** via a converter function.
4. Returns the HTTP response.

No business logic lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from src.api.dependencies.wiring import get_ingestion, get_job_service
from src.api.storage import save_upload
from src.domain import Book, UnsupportedFormatError, new_id
from src.ingestion._loaders import FileType
from src.ingestion import (
    BookIngestion,
    book_detail_response,
    book_summary_response,
    delete_book_response,
)
from src.jobs import JobService
from src.response.book import BookDetailResponse, BookSummary, DeleteBookResponse
from src.response.upload_book_response import UploadBookResponse

router = APIRouter(prefix="/books", tags=["books"])

EXTRACTED_BOOKS_DIR = Path("extracted_books")


# ---------------------------------------------------------------------------
# GET /books
# ---------------------------------------------------------------------------


@router.get("", response_model=List[BookSummary])
async def list_books(
    ingestion: BookIngestion = Depends(get_ingestion),
) -> List[BookSummary]:
    """List all books.

    Returns a flat list of :class:`~src.response.book.BookSummary` DTOs.
    """
    models = await ingestion.get_books()
    return [book_summary_response(model) for model in models]


# ---------------------------------------------------------------------------
# GET /books/{book_id}
# ---------------------------------------------------------------------------


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    request: Request,
    ingestion: BookIngestion = Depends(get_ingestion),
) -> BookDetailResponse:
    """Retrieve full book details including the TOC tree.

    The ``file_url`` field in the response points to
    ``GET /books/{book_id}/file``.
    """
    file_url = str(request.url_for("get_book_file", book_id=book_id))
    detail_model = await ingestion.get_book_detail(book_id, file_url)
    if not detail_model:
        raise HTTPException(404, "Book not found")

    return book_detail_response(detail_model)


# ---------------------------------------------------------------------------
# GET /books/{book_id}/file
# ---------------------------------------------------------------------------


@router.get("/{book_id}/file")
async def get_book_file(
    book_id: str,
    ingestion: BookIngestion = Depends(get_ingestion),
) -> FileResponse:
    """Serve the original source file (EPUB or PDF) for download."""
    book = await ingestion.get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    media_type = (
        "application/epub+zip" if book.source_format == "epub" else "application/pdf"
    )
    return FileResponse(
        path=book.file_path,
        media_type=media_type,
        filename=book.source_filename,
    )


# ---------------------------------------------------------------------------
# DELETE /books/{book_id}
# ---------------------------------------------------------------------------


@router.delete("/{book_id}", response_model=DeleteBookResponse)
async def delete_book(
    book_id: str,
    ingestion: BookIngestion = Depends(get_ingestion),
) -> DeleteBookResponse:
    """Delete a book plus its sections, facts, summaries, audit data, and chunks."""
    try:
        result = await ingestion.delete_book(book_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Delete failed: {exc}") from exc

    return delete_book_response(result)


# ---------------------------------------------------------------------------
# POST /books/upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=UploadBookResponse, status_code=202)
async def upload_book(
    file: UploadFile = File(...),
    ingestion: BookIngestion = Depends(get_ingestion),
    jobs: JobService = Depends(get_job_service),
) -> UploadBookResponse:
    """Store an uploaded book and enqueue durable parsing work."""
    filename = file.filename or ""
    try:
        file_type = FileType.from_filename(filename)
    except UnsupportedFormatError as exc:
        raise HTTPException(400, str(exc)) from exc

    upload_path = await save_upload(file)
    book_id = new_id()
    try:
        book = Book(
            id=book_id,
            title=Path(filename).stem or "Untitled",
            author=None,
            source_format=file_type.value,
            file_path=str(upload_path),
            source_filename=filename,
            upload_status="uploaded",
            table_of_content=[],
        )
        await ingestion.store.save_book(book)
        job = await jobs.enqueue_parse_book(book.id)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Upload failed: {exc}") from exc

    return UploadBookResponse(
        book_id=book.id,
        job_id=job.id,
        status="uploaded",
        message="Book uploaded. Parsing job queued.",
    )
