# src/api/routers/books.py
from fastapi import (
    APIRouter,
    Depends,
    Request,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
)
from typing import List
from fastapi.responses import FileResponse

from src.infrastructure.loaders.epub_loader import EpubLoader
from pathlib import Path
from src.response.toc_node_response import TocNodeResponse
from src.api.storage import save_upload
from src.response.book import (
    BookUploadResponse,
    BookDetailResponse,
    BookSummary,
)
from src.services.book_extraction_service import BookExtractionService
from src.services.chunk_ingestion_service import ChunkIngestionService
from src.services.toc_service import TOCService
from src.infrastructure.loaders.file_type import FileType
from src.core.exceptions import UnsupportedFormatError
from src.api.dependencies.services import (
    get_book_extraction_service,
    get_chunk_ingestion_service,
    get_toc_service,
)
from src.api.dependencies.storages import (
    get_book_repo,
)
from src.infrastructure.persistence.book_repo import BookRepository

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookSummary])
async def list_books(
    book_repo: BookRepository = Depends(get_book_repo),
):
    """List all books."""
    books = await book_repo.find_all()
    return [
        BookSummary(
            id=b.id,
            title=b.title,
            author=b.author,
            source_format=b.source_format,
        )
        for b in books
    ]


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    request: Request,
    book_repo: BookRepository = Depends(get_book_repo),
    toc_service: TOCService = Depends(get_toc_service),
):
    book = await book_repo.find_by_id(book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    toc_node = toc_service.to_tree(book.table_of_contents)
    file_url = str(request.url_for("get_book_file", book_id=book_id))

    return BookDetailResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=book.source_format,
        file_url=file_url,
        toc=TocNodeResponse.from_toc_node(toc_node),
    )


# src/api/routers/books.py - Add file serving endpoint
@router.get("/{book_id}/file")
async def get_book_file(
    book_id: str,
    book_repo: BookRepository = Depends(get_book_repo),
):
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


EXTRACTED_BOOKS_DIR = Path("extracted_books")


@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    book_extraction: BookExtractionService = Depends(get_book_extraction_service),
    chunk_ingestion: ChunkIngestionService = Depends(get_chunk_ingestion_service),
):
    """Upload a book."""
    try:
        file_type = FileType.from_filename(file.filename)
    except UnsupportedFormatError as e:
        raise HTTPException(400, str(e))

    temp_path = await save_upload(file)

    book = await book_extraction.extract_and_persist_metadata(temp_path, file_type)

    # Schedule chunk ingestion in background
    # if background_tasks:
    #     background_tasks.add_task(chunk_ingestion.ingest_book, book)

    # temp_path.unlink()
    if file_type == FileType.Epub:
        EpubLoader.extract_to_static(temp_path, book.id, EXTRACTED_BOOKS_DIR)

    return BookUploadResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=file_type.value,
        message="Book uploaded successfully",
    )
