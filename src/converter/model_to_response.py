# src/converter/model_to_response.py
"""Converters: service models  →  response DTOs.

Rules
-----
* These functions are the *only* place that imports from both ``src/model/``
  and ``src/response/``.
* Routers call these converters; they never build response DTOs directly from
  entities.
* All functions are pure and stateless.
"""

from __future__ import annotations

from typing import Dict, List

from src.model.audit_models import AuditReportModel
from src.model.book_models import BookDetailModel, BookSummaryModel
from src.model.extraction_models import ExtractionJobModel, ExtractionStatusModel
from src.model.section_models import FactsModel
from src.model.toc_node_model import TocNodeModel
from src.response.atomic_fact import AtomicFactResponse
from src.response.audit_report import AuditReportResponse, FactFeedback
from src.response.book import BookDetailResponse, BookSummary
from src.response.section import FactsResponse, HintResponse
from src.response.toc_node_response import TocNodeResponse

# ---------------------------------------------------------------------------
# Book response converters
# ---------------------------------------------------------------------------


def book_summary_model_to_response(model: BookSummaryModel) -> BookSummary:
    """Convert a :class:`~src.model.book_models.BookSummaryModel` to the
    existing :class:`~src.response.book.BookSummary` response DTO.

    Args:
        model: The immutable service model.

    Returns:
        A :class:`BookSummary` ready for serialisation.
    """
    return BookSummary(
        id=model.id,
        title=model.title,
        author=model.author,
        source_format=model.source_format,
    )


def book_detail_model_to_response(model: BookDetailModel) -> BookDetailResponse:
    """Convert a :class:`~src.model.book_models.BookDetailModel` to a
    :class:`~src.response.book.BookDetailResponse`.

    Args:
        model: The immutable detail model (includes TOC).

    Returns:
        A :class:`BookDetailResponse` ready for serialisation.
    """
    return BookDetailResponse(
        id=model.id,
        title=model.title,
        author=model.author,
        source_format=model.source_format,
        file_url=model.file_url,
        toc=toc_node_model_to_response(model.toc),
    )


# ---------------------------------------------------------------------------
# TOC response converters
# ---------------------------------------------------------------------------


def toc_node_model_to_response(model: TocNodeModel) -> TocNodeResponse:
    """Recursively convert a :class:`~src.model.toc_node_model.TocNodeModel`
    to a :class:`~src.response.toc_node_response.TocNodeResponse`.

    Args:
        model: The root (or any subtree root) TOC model.

    Returns:
        A :class:`TocNodeResponse` with recursively converted children.
    """
    return TocNodeResponse(
        id=model.id,
        title=model.title,
        level=model.level,
        order=model.order,
        section_id=model.section_id,
        href=model.href,
        children=[toc_node_model_to_response(child) for child in model.children],
    )


# ---------------------------------------------------------------------------
# Facts response converters
# ---------------------------------------------------------------------------


def facts_model_to_response(model: FactsModel) -> FactsResponse:
    """Convert a :class:`~src.model.section_models.FactsModel` to a
    :class:`~src.response.section.FactsResponse`.

    Args:
        model: The service model containing facts and hints.

    Returns:
        A :class:`FactsResponse` ready for serialisation.
    """
    return FactsResponse(
        section_id=model.section_id,
        extraction_status=model.extraction_status,
        facts=[
            AtomicFactResponse(
                id=f.id,
                point=f.point,
                rank=f.rank,
                reason=f.reason,
                questions=f.questions,
                chunk_id=f.chunk_id,
                start_char=f.start_char,
                end_char=f.end_char,
            )
            for f in model.facts
        ],
    )


def hints_to_response(hints: List[str]) -> List[HintResponse]:
    """Wrap a plain list of hint strings into :class:`HintResponse` objects.

    Args:
        hints: Strings returned by
               :meth:`~src.services.facts_read_service.FactsReadService.get_hints`.

    Returns:
        A list of :class:`HintResponse` DTOs.
    """
    return [HintResponse(hint=h) for h in hints]


# ---------------------------------------------------------------------------
# Extraction job response converters
# ---------------------------------------------------------------------------


def extraction_job_model_to_response(model: ExtractionJobModel) -> Dict:
    """Convert an :class:`~src.model.extraction_models.ExtractionJobModel` to a
    plain dict that routers return as a JSON body for HTTP 202 Accepted.

    Args:
        model: The service model.

    Returns:
        A serialisable dict.
    """
    return {
        "job_id": model.job_id,
        "section_id": model.section_id,
        "status": model.status,
        "created_at": model.created_at.isoformat(),
        **({"message": model.message} if model.message else {}),
    }


def extraction_status_model_to_response(model: ExtractionStatusModel) -> Dict:
    """Convert an :class:`~src.model.extraction_models.ExtractionStatusModel` to a
    plain dict suitable for an HTTP response body.

    Args:
        model: The service model.

    Returns:
        A serialisable dict.
    """
    result: Dict = {
        "job_id": model.job_id,
        "status": model.status,
    }
    if model.progress is not None:
        result["progress"] = model.progress
    if model.result_summary is not None:
        result["result_summary"] = model.result_summary
    if model.error is not None:
        result["error"] = model.error
    if model.completed_at is not None:
        result["completed_at"] = model.completed_at.isoformat()
    return result


# ---------------------------------------------------------------------------
# Audit report response converters
# ---------------------------------------------------------------------------


def audit_report_model_to_response(model: AuditReportModel) -> AuditReportResponse:
    """Convert an :class:`~src.model.audit_models.AuditReportModel` to an
    :class:`~src.response.audit_report.AuditReportResponse`.

    Args:
        model: The service model.

    Returns:
        An :class:`AuditReportResponse` ready for serialisation.
    """
    return AuditReportResponse(
        id=model.id,
        score=model.score,
        score_delta=model.score_delta,
        attempt_number=model.attempt_number,
        fact_feedback=[
            FactFeedback(
                fact_id=fb.fact_id,
                point=fb.point,
                rank=fb.rank,
                status=fb.status,
                evidence=fb.evidence,
                confidence=fb.confidence,
                improved=fb.improved,
            )
            for fb in model.fact_feedback
        ],
    )
