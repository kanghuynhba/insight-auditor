"""Public book ingestion module."""

from src.ingestion._responses import (
    book_detail_response,
    book_summary_response,
    delete_book_response,
)
from src.ingestion._embedding import embed_chunks
from src.ingestion._models import (
    BookDetailModel,
    BookSummaryModel,
    ExtractionResultModel,
    TocNodeModel,
)
from src.ingestion._service import BookIngestion
from src.ingestion._toc import TOCService

__all__ = [
    "BookDetailModel",
    "BookIngestion",
    "BookSummaryModel",
    "ExtractionResultModel",
    "TOCService",
    "TocNodeModel",
    "book_detail_response",
    "book_summary_response",
    "delete_book_response",
    "embed_chunks",
]
