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

from src.api.dependencies.services import (
    get_book_extraction_service,
    get_book_repo,
    get_toc_service,
)
from src.api.storage import save_upload
from src.converter.entity_to_model import book_entity_to_detail_model, toc_node_to_model
from src.converter.model_to_response import (
    book_detail_model_to_response,
    book_summary_model_to_response,
)
from src.core.exceptions import UnsupportedFormatError
from src.infrastructure.loaders.epub_loader import EpubLoader
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.persistence.book_repo import BookRepository
from src.response.book import BookDetailResponse, BookSummary
from src.response.toc_node_response import TocNodeResponse
from src.response.upload_book_response import UploadBookResponse
from src.services.book_extraction_service import BookExtractionService
from src.services.toc_service import TOCService

router = APIRouter(prefix="/books", tags=["books"])

EXTRACTED_BOOKS_DIR = Path("extracted_books")


# ---------------------------------------------------------------------------
# GET /books
# ---------------------------------------------------------------------------


@router.get("", response_model=List[BookSummary])
async def list_books(
    book_extraction: BookExtractionService = Depends(get_book_extraction_service),
) -> List[BookSummary]:
    """List all books.

    Returns a flat list of :class:`~src.response.book.BookSummary` DTOs.
    """
    models = await book_extraction.get_books()
    return [book_summary_model_to_response(m) for m in models]


# ---------------------------------------------------------------------------
# GET /books/{book_id}
# ---------------------------------------------------------------------------


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    request: Request,
    book_repo: BookRepository = Depends(get_book_repo),
    toc_service: TOCService = Depends(get_toc_service),
) -> BookDetailResponse:
    """Retrieve full book details including the TOC tree.

    The ``file_url`` field in the response points to
    ``GET /books/{book_id}/file``.
    """
    book = await book_repo.find_by_id(book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    toc_model = toc_service.to_tree(book.table_of_contents)
    file_url = str(request.url_for("get_book_file", book_id=book_id))

    detail_model = book_entity_to_detail_model(book, toc_model, file_url)
    return book_detail_model_to_response(detail_model)


# ---------------------------------------------------------------------------
# GET /books/{book_id}/file
# ---------------------------------------------------------------------------


@router.get("/{book_id}/file")
async def get_book_file(
    book_id: str,
    book_repo: BookRepository = Depends(get_book_repo),
) -> FileResponse:
    """Serve the original source file (EPUB or PDF) for download."""
    book = await book_repo.find_by_id(book_id)
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
# POST /books/upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=UploadBookResponse, status_code=201)
async def upload_book(
    file: UploadFile = File(...),
    book_extraction: BookExtractionService = Depends(get_book_extraction_service),
) -> UploadBookResponse:
    """Upload and process a book file.

    * Returns **201 Created** when the book is new (``status="new"``).
    * Returns **200 OK** when the book already exists (``status="exists"``).
      (FastAPI uses the declared ``status_code=201`` for new books; for existing
      books the service signals ``status="exists"`` in the body – no separate
      HTTP status override is needed for API clients that check the body.)

    The response body is always an :class:`~src.response.upload_book_response.UploadBookResponse`.

    **Migration note:** previous clients received a :class:`~src.response.book.BookSummary`
    from this endpoint.  The new response shape is
    ``{book_id, status, message}`` which is lighter and action-oriented.
    Clients that need full book details should follow up with
    ``GET /books/{book_id}``.
    """
    try:
        file_type = FileType.from_filename(file.filename)
    except UnsupportedFormatError as exc:
        raise HTTPException(400, str(exc)) from exc

    temp_path = await save_upload(file)

    try:
        result = await book_extraction.extract_and_persist_metadata(
            temp_path, file_type
        )
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Extraction failed: {exc}") from exc

    # EPUB: extract contents to static dir so the reader can serve chapters
    if file_type == FileType.Epub:
        EpubLoader.extract_to_static(temp_path, result.book_id, EXTRACTED_BOOKS_DIR)

    temp_path.unlink(missing_ok=True)

    return UploadBookResponse(
        book_id=result.book_id,
        status=result.status,
        message=result.message,
    )
