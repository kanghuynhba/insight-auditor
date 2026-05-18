"""Sections router – thin HTTP layer.

Each handler:
1. Validates the request.
2. Calls one service method that returns a service model (or raises a domain exception).
3. Converts the service model to a response DTO.
4. Returns the HTTP response.

No business logic lives here.

Breaking changes from previous version
---------------------------------------
* ``POST /sections/{section_id}/evaluations`` now accepts a
  :class:`~src.request.write_summary_request.WriteSummaryRequest` body
  (``summary_text`` field) instead of the old ``SummaryRequest``
  (``summary`` field).  Clients must rename the JSON key.
* ``POST /sections/{section_id}/extract-facts`` now returns an
  :class:`~src.response.extract_fact_response.ExtractFactResponse` body
  instead of a raw dict.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from src.api.dependencies.services import (
    get_audit_service,
    get_facts_extraction_service,
    get_facts_read_service,
    get_section_repo,
)
from src.converter.model_to_response import (
    audit_report_model_to_response,
    facts_model_to_response,
    hints_to_response,
)
from src.core.enums import ExtractionStatus
from src.core.exceptions import ExtractionNotReadyError
from src.infrastructure.persistence.section_repo import SectionRepository
from src.request.write_summary_request import WriteSummaryRequest
from src.response.audit_report import AuditReportResponse
from src.response.extract_fact_response import ExtractFactResponse
from src.response.section import FactsResponse, HintResponse
from src.services.audit_service import AuditService
from src.services.facts_extraction_service import FactsExtractionService
from src.services.facts_read_service import FactsReadService

router = APIRouter(prefix="/sections", tags=["sections"])


# ---------------------------------------------------------------------------
# POST /sections/{section_id}/extract-facts
# ---------------------------------------------------------------------------


@router.post(
    "/{section_id}/extract-facts", response_model=ExtractFactResponse, status_code=202
)
async def extract_facts(
    section_id: str,
    force: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    section_repo: SectionRepository = Depends(get_section_repo),
    extraction_service: FactsExtractionService = Depends(get_facts_extraction_service),
) -> ExtractFactResponse:
    """Enqueue an async fact-extraction job for the given section.

    Returns HTTP 202 Accepted with a ``job_id`` and ``status="pending"``
    so the client can track progress.

    Raises:
        404: When the section is not found.
        409: When extraction is already in progress for this section.
    """
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    if section.extraction_status == ExtractionStatus.PENDING:
        raise HTTPException(409, "Extraction already in progress for this section")

    job_dict = await extraction_service.start_extraction(
        section_id=section_id,
        force=force,
        background_tasks=background_tasks,
    )

    return ExtractFactResponse(
        job_id=job_dict["job_id"],
        section_id=job_dict["section_id"],
        status=job_dict["status"],
        created_at=job_dict["created_at"],
        message=job_dict.get("message"),
    )


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/facts
# ---------------------------------------------------------------------------


@router.get("/{section_id}/facts", response_model=FactsResponse)
async def get_facts(
    section_id: str,
    facts_read_service: FactsReadService = Depends(get_facts_read_service),
) -> FactsResponse:
    """Return the extracted atomic facts for a section.

    Raises:
        404: When the section is not found or extraction is not yet complete.
    """
    try:
        facts_model = await facts_read_service.get_facts_by_section(section_id)
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

    return facts_model_to_response(facts_model)


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/hints
# ---------------------------------------------------------------------------


@router.get("/{section_id}/hints", response_model=List[HintResponse])
async def get_hints(
    section_id: str,
    attempt_number: Optional[int] = None,
    max_hints: int = Query(5, le=10),
    section_repo: SectionRepository = Depends(get_section_repo),
    facts_read_service: FactsReadService = Depends(get_facts_read_service),
) -> List[HintResponse]:
    """Return study hints (one question per top-ranked fact).

    Raises:
        404: When the section is not found.
        400: When facts have not been extracted yet.
    """
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    if section.extraction_status != ExtractionStatus.DONE:
        raise HTTPException(
            400, "No facts extracted for this section – call extract-facts first"
        )

    hint_strings = await facts_read_service.get_hints(
        section_id=section_id,
        attempt_number=attempt_number,
        max_hints=max_hints,
    )
    return hints_to_response(hint_strings)


# ---------------------------------------------------------------------------
# POST /sections/{section_id}/evaluations
# ---------------------------------------------------------------------------


@router.post("/{section_id}/evaluations", response_model=AuditReportResponse)
async def evaluate_summary(
    section_id: str,
    request: WriteSummaryRequest,
    audit_svc: AuditService = Depends(get_audit_service),
    section_repo: SectionRepository = Depends(get_section_repo),
) -> AuditReportResponse:
    """Evaluate a user-written summary against the section's atomic facts.

    **Breaking change:** request body field renamed ``summary`` → ``summary_text``.

    Raises:
        404: When the section is not found.
        400: When facts have not been extracted yet, or the summary is too short.
    """
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    if section.extraction_status != ExtractionStatus.DONE:
        raise HTTPException(
            400, "Atomic facts not ready – please wait for extraction to complete"
        )

    try:
        report_model = await audit_svc.evaluate_summary(
            section_id=section_id,
            summary_text=request.summary_text,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return audit_report_model_to_response(report_model)


# ---------------------------------------------------------------------------
# GET /sections/{section_id}/evaluations
# ---------------------------------------------------------------------------


@router.get("/{section_id}/evaluations")
async def get_evaluation_history(
    section_id: str,
    audit_svc: AuditService = Depends(get_audit_service),
):
    """Return past evaluation reports for a section (newest last).

    The response shape mirrors the existing API so existing clients are
    unaffected.
    """
    models = await audit_svc.get_history_by_section(section_id)
    return [
        {
            "id": m.id,
            "score": m.score,
            "score_delta": m.score_delta,
            "attempt_number": m.attempt_number,
        }
        for m in models
    ]
