"""Sections router – thin HTTP layer.

Each handler:
1. Validates the request.
2. Calls one service method that returns a service model (or raises a domain exception).
3. Converts the service model to a response DTO.
4. Returns the HTTP response.

No business logic lives here.

Primary API paths
-----------------
* ``GET /sections/{section_id}``
* ``GET /sections/{section_id}/facts``
* ``POST /sections/{section_id}/facts/extraction``
* ``POST /sections/{section_id}/summaries``
* ``GET /sections/{section_id}/audit_reports``
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.wiring import get_audit_gateway, get_extraction, get_job_service
from src.audit import AuditGateway, audit_report_response, hints_response
from src.domain import ExtractionStatus
from src.domain.exceptions import ExtractionNotReadyError
from src.extraction import FactExtraction, facts_response
from src.jobs import JobService
from src.request.write_summary_request import WriteSummaryRequest
from src.response.atomic_fact import AtomicFactResponse
from src.response.audit_report import AuditReportResponse, SummarySubmissionResponse
from src.response.extract_fact_response import (
    ExtractFactResponse,
    FactExtractionJobResponse,
)
from src.response.section import HintResponse, SectionResponse

router = APIRouter(prefix="/sections", tags=["sections"])


def _legacy_extraction_status(job_status: str) -> str:
    return {
        "queued": "pending",
        "running": "running",
        "succeeded": "completed",
        "failed": "failed",
        "cancelled": "failed",
    }.get(job_status, job_status)


# ---------------------------------------------------------------------------
# GET /sections/{section_id}
# ---------------------------------------------------------------------------


@router.get("/{section_id}", response_model=SectionResponse)
async def get_section(
    section_id: str,
    extraction: FactExtraction = Depends(get_extraction),
) -> SectionResponse:
    section = await extraction.store.get_section(section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    return SectionResponse(
        id=section.id,
        book_id=section.book_id,
        title=section.title,
        level=section.level,
        order=section.order,
        href=section.href,
        raw_text=section.raw_text,
        extraction_status=(
            section.extraction_status.value
            if hasattr(section.extraction_status, "value")
            else str(section.extraction_status)
        ),
        word_count=section.word_count,
    )


# ---------------------------------------------------------------------------
# POST /sections/{section_id}/facts/extraction
# ---------------------------------------------------------------------------


@router.post(
    "/{section_id}/facts/extraction",
    response_model=FactExtractionJobResponse,
    status_code=202,
)
async def extract_facts(
    section_id: str,
    force: bool = Query(False),
    extraction: FactExtraction = Depends(get_extraction),
    jobs: JobService = Depends(get_job_service),
) -> FactExtractionJobResponse:
    """Enqueue an async fact-extraction job for the given section.

    Returns HTTP 202 Accepted with a ``job_id`` and ``status="pending"``
    so the client can track progress.

    Raises:
        404: When the section is not found.
    """
    section = await extraction.store.get_section(section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    section.extraction_status = ExtractionStatus.PENDING
    await extraction.store.save_section(section)
    job = await jobs.enqueue_extract_facts(section_id, force=force)

    return FactExtractionJobResponse(extraction_job_id=job.id, status=job.status)


@router.post(
    "/{section_id}/extract-facts", response_model=ExtractFactResponse, status_code=202
)
async def extract_facts_legacy(
    section_id: str,
    force: bool = Query(False),
    extraction: FactExtraction = Depends(get_extraction),
    jobs: JobService = Depends(get_job_service),
) -> ExtractFactResponse:
    """Backward-compatible alias for old clients."""
    section = await extraction.store.get_section(section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    section.extraction_status = ExtractionStatus.PENDING
    await extraction.store.save_section(section)
    job = await jobs.enqueue_extract_facts(section_id, force=force)
    return ExtractFactResponse(
        job_id=job.id,
        section_id=section_id,
        status=_legacy_extraction_status(job.status),
        created_at=job.created_at,
        message=job.message,
    )


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/facts
# ---------------------------------------------------------------------------


@router.get("/{section_id}/facts", response_model=List[AtomicFactResponse])
async def get_facts(
    section_id: str,
    extraction: FactExtraction = Depends(get_extraction),
) -> List[AtomicFactResponse]:
    """Return the extracted atomic facts for a section.

    Raises:
        404: When the section is not found or extraction is not yet complete.
    """
    try:
        facts_model = await extraction.get_facts(section_id)
    except ExtractionNotReadyError as exc:
        raise HTTPException(
            404,
            detail={
                "extraction_status": exc.status,
                "message": exc.message,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    return facts_response(facts_model).facts


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/hints
# ---------------------------------------------------------------------------


@router.get("/{section_id}/hints", response_model=List[HintResponse])
async def get_hints(
    section_id: str,
    attempt_number: Optional[int] = None,
    max_hints: int = Query(5, le=10),
    audit: AuditGateway = Depends(get_audit_gateway),
) -> List[HintResponse]:
    """Return study hints (one question per top-ranked fact).

    Raises:
        404: When the section is not found.
        400: When facts have not been extracted yet.
    """
    try:
        hint_strings = await audit.hints(
            section_id=section_id,
            attempt_number=attempt_number,
            max_hints=max_hints,
        )
    except KeyError as exc:
        raise HTTPException(404, "Section not found")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return hints_response(hint_strings)


# ---------------------------------------------------------------------------
# POST /sections/{section_id}/summaries
# ---------------------------------------------------------------------------


@router.post("/{section_id}/summaries", response_model=SummarySubmissionResponse)
async def submit_summary(
    section_id: str,
    request: WriteSummaryRequest,
    audit: AuditGateway = Depends(get_audit_gateway),
) -> SummarySubmissionResponse:
    """Evaluate a user-written summary against the section's atomic facts.

    **Breaking change:** request body field renamed ``summary`` → ``summary_text``.

    Raises:
        404: When the section is not found.
        400: When facts have not been extracted yet, or the summary is too short.
    """
    try:
        report_model = await audit.evaluate(
            section_id=section_id,
            summary_text=request.summary_text,
        )
    except KeyError as exc:
        raise HTTPException(404, "Section not found")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return SummarySubmissionResponse(
        summary_id=report_model.summary_id,
        audit_report_id=report_model.id,
    )


@router.post("/{section_id}/evaluations", response_model=AuditReportResponse)
async def evaluate_summary(
    section_id: str,
    request: WriteSummaryRequest,
    audit: AuditGateway = Depends(get_audit_gateway),
) -> AuditReportResponse:
    """Backward-compatible alias returning the full audit report."""
    try:
        report_model = await audit.evaluate(
            section_id=section_id,
            summary_text=request.summary_text,
        )
    except KeyError as exc:
        raise HTTPException(404, "Section not found") from exc
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return audit_report_response(report_model)


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/audit_reports
# ---------------------------------------------------------------------------


@router.get("/{section_id}/audit_reports", response_model=List[AuditReportResponse])
async def get_section_audit_reports(
    section_id: str,
    audit: AuditGateway = Depends(get_audit_gateway),
) -> List[AuditReportResponse]:
    models = await audit.history(section_id)
    return [audit_report_response(model) for model in models]


@router.get("/{section_id}/evaluations")
async def get_evaluation_history(
    section_id: str,
    audit: AuditGateway = Depends(get_audit_gateway),
):
    """Backward-compatible alias for old evaluation history clients."""
    models = await audit.history(section_id)
    return [
        {
            "id": m.id,
            "score": m.score,
            "score_delta": m.score_delta,
            "attempt_number": m.attempt_number,
        }
        for m in models
    ]
