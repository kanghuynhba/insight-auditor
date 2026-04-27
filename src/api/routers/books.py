# api/routers/books.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from src.api.storage import save_upload
from src.response.book import (
    BookUploadResponse,
    BookDetailResponse,
    BookSummary,
    ChapterSummary,
    ChapterDetailResponse,
    SectionResponse,
)
from src.services.book_extraction_service import BookExtractionService
from src.services.chunk_ingestion_service import ChunkIngestionService
from src.infrastructure.loaders.file_type import FileType
from src.core.exceptions import UnsupportedFormatError
from src.api.dependencies.services import (
    get_book_extraction_service,
    get_chunk_ingestion_service,
)
from src.api.dependencies.storages import get_book_repo  # add this dependency
from src.infrastructure.persistence.book_repo import BookRepository

router = APIRouter(prefix="/books", tags=["books"])


@router.post(
    "/upload", response_model=BookUploadResponse
)  # fixed: use BookUploadResponse
async def upload_book(
    file: UploadFile = File(...),
    book_extraction: BookExtractionService = Depends(get_book_extraction_service),
    chunk_ingestion: ChunkIngestionService = Depends(get_chunk_ingestion_service),
):
    """
    1. Validate file type
    2. Extract book structure → Book object
    3. Save book metadata to DB
    4. Chunk + embed + store vectors
    """
    try:
        file_type = FileType.from_filename(file.filename)
    except UnsupportedFormatError as e:
        raise HTTPException(400, str(e))

    temp_path = await save_upload(file)

    book = await book_extraction.extract_and_persist_metadata(temp_path, file_type)
    await chunk_ingestion.ingest_book(book)

    temp_path.unlink()

    return BookUploadResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=file_type.value,
        total_chapters=len(book.chapters),
        chapters=[
            ChapterSummary(
                id=ch.id,
                title=ch.title,
                path_id=ch.path_id,  # fixed: was ch.path.id
                section_count=len(ch.sections),
            )
            for ch in book.chapters
        ],
    )


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    book_repo: BookRepository = Depends(get_book_repo),  # inject repository
):
    book = await book_repo.find_by_id(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return BookDetailResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=book.source_format.value,
        chapters=[
            ChapterDetailResponse(
                id=ch.id,
                title=ch.title,
                path_id=ch.path_id,
                index=ch.index,
                sections=[
                    SectionResponse(
                        id=s.id,
                        title=s.title,
                        path_id=s.path_id,
                        level=s.level,
                        word_count=s.word_count,
                        extraction_status=s.extraction_status.value,
                    )
                    for s in ch.sections
                ],
            )
            for ch in book.chapters
        ],
    )
