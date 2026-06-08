"""Response mapping for book ingestion routes."""

from src.ingestion._models import (
    BookDetailModel,
    BookSummaryModel,
    TocNodeModel,
)
from src.response.book import BookDetailResponse, BookSummary, DeleteBookResponse
from src.response.toc_node_response import TocNodeResponse
from src.store import DeleteBookResultModel


def book_summary_response(model: BookSummaryModel) -> BookSummary:
    return BookSummary(
        id=model.id,
        title=model.title,
        author=model.author,
        source_format=model.source_format,
        upload_status=model.upload_status,
    )


def book_detail_response(model: BookDetailModel) -> BookDetailResponse:
    return BookDetailResponse(
        id=model.id,
        title=model.title,
        author=model.author,
        source_format=model.source_format,
        upload_status=model.upload_status,
        file_url=model.file_url,
        toc=toc_response(model.toc),
    )


def delete_book_response(model: DeleteBookResultModel) -> DeleteBookResponse:
    return DeleteBookResponse(
        book_id=model.book_id,
        deleted_sections=model.deleted_sections,
        deleted_summaries=model.deleted_summaries,
        deleted_reports=model.deleted_reports,
        deleted_facts=model.deleted_facts,
    )


def toc_response(model: TocNodeModel) -> TocNodeResponse:
    return TocNodeResponse(
        id=model.id,
        title=model.title,
        level=model.level,
        order=model.order,
        section_id=model.section_id,
        href=model.href,
        children=[toc_response(child) for child in model.children],
    )
