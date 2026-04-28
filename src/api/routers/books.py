# api/routers/books.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from src.api.storage import save_upload
from src.response.book import (
    BookUploadResponse,
    BookDetailResponse,
    BookSummary,
    TocNodeResponse,  # new
)
from src.services.book_extraction_service import BookExtractionService
from src.services.chunk_ingestion_service import ChunkIngestionService
from src.infrastructure.loaders.file_type import FileType
from src.core.exceptions import UnsupportedFormatError
from src.api.dependencies.services import (
    get_book_extraction_service,
    get_chunk_ingestion_service,
)
from src.api.dependencies.storages import get_book_repo
from src.infrastructure.persistence.book_repo import BookRepository
from src.core.table_of_content import TableOfContent

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookSummary])
async def list_books(
    book_repo: BookRepository = Depends(get_book_repo),
):
    books = await book_repo.find_all()
    return [
        BookSummary(
            id=b.id,
            title=b.title,
            author=b.author,
            source_format=b.source_format.value,
            total_chapters=len([t for t in b.toc if t.level == 1]),  # top-level count
        )
        for b in books
    ]


@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    book_extraction: BookExtractionService = Depends(get_book_extraction_service),
    chunk_ingestion: ChunkIngestionService = Depends(get_chunk_ingestion_service),
):
    try:
        file_type = FileType.from_filename(file.filename)
    except UnsupportedFormatError as e:
        raise HTTPException(400, str(e))

    temp_path = await save_upload(file)

    book = await book_extraction.extract_and_persist_metadata(temp_path, file_type)
    await chunk_ingestion.ingest_book(book)

    temp_path.unlink()

    # Build top-level TOC nodes for response
    top_level_toc = [t for t in book.toc if t.parent_id is None]
    # order by 'order' field
    top_level_toc.sort(key=lambda t: t.order)

    return BookUploadResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=file_type.value,
        total_chapters=len(top_level_toc),
        toc=[
            {
                "id": t.id,
                "title": t.title,
                "level": t.level,
                "section_id": t.section_id,
                "order": t.order,
            }
            for t in top_level_toc
        ],
    )


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    book_repo: BookRepository = Depends(get_book_repo),
):
    book = await book_repo.find_by_id(book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    # Build a tree from flat TOC list
    toc_map = {t.id: t for t in book.toc}
    children_map: dict[str, list[TableOfContent]] = {}
    for t in book.toc:
        parent_id = t.parent_id
        if parent_id is None:
            continue
        children_map.setdefault(parent_id, []).append(t)

    # Sort children by order
    for parent in children_map:
        children_map[parent].sort(key=lambda c: c.order)

    def build_tree(node: TableOfContent) -> dict:
        return {
            "id": node.id,
            "title": node.title,
            "level": node.level,
            "section_id": node.section_id,
            "order": node.order,
            "children": [build_tree(child) for child in children_map.get(node.id, [])],
        }

    # Root nodes are those with parent_id None
    roots = [t for t in book.toc if t.parent_id is None]
    roots.sort(key=lambda r: r.order)
    toc_tree = [build_tree(root) for root in roots]

    return BookDetailResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=book.source_format.value,
        toc=toc_tree,
    )
