from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional

from src.services.facts_read_service import FactsReadService
from src.core.exceptions import ExtractionNotReadyError
from src.response.section import FactsResponse, HintResponse
from src.response.audit_report import AuditReportResponse
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.api.dependencies.storages import get_audit_report_repo, get_summary_repo
from src.api.dependencies.services import (
    get_facts_read_service,
    get_section_repo,
    get_audit_service,
    get_facts_extraction_service,
)
from src.infrastructure.persistence.section_repo import SectionRepository
from src.services.audit_service import AuditService
from src.services.facts_extraction_service import FactsExtractionService
from src.core.enums import ExtractionStatus
from src.request.summary_request import SummaryRequest

router = APIRouter(prefix="/sections", tags=["sections"])


# POST /sections/{section_id}/extract-facts
@router.post("/{section_id}/extract-facts", status_code=202)
async def extract_facts(
    section_id: str,
    force: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    section_repo: SectionRepository = Depends(get_section_repo),
    extraction_service: FactsExtractionService = Depends(get_facts_extraction_service),
):
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    if section.extraction_status == ExtractionStatus.PENDING:
        raise HTTPException(409, "Extraction already in progress")

    # Mark as PENDING
    section.extraction_status = ExtractionStatus.PENDING
    await section_repo.save(section)
    await section_repo.session.commit()

    background_tasks.add_task(
        extraction_service.extract_facts_by_section, section_id, force
    )
    return {"section_id": section_id, "status": "pending"}


# GET /sections/{section_id}/facts
@router.get("/{section_id}/facts", response_model=FactsResponse)
async def get_facts(
    section_id: str,
    facts_read_service: FactsReadService = Depends(get_facts_read_service),
) -> FactsResponse:

    try:
        return await facts_read_service.get_facts_by_section(section_id)
    except ExtractionNotReadyError as e:
        if "status:" in str(e):
            status = str(e).split("status: ")[-1].rstrip(")")
            raise HTTPException(
                404,
                detail={
                    "extraction_status": status,
                    "message": "No facts extracted yet",
                },
            )
    except ValueError as e:
        raise HTTPException(404, str(e))


# GET /sections/{section_id}/hints
@router.get("/{section_id}/hints", response_model=List[HintResponse])
async def get_hints(
    section_id: str,
    attempt_number: Optional[int] = None,
    max_hints: int = Query(5, le=10),
    section_repo: SectionRepository = Depends(get_section_repo),
    facts_read_service: FactsReadService = Depends(get_facts_read_service),
) -> List[HintResponse]:
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    if section.extraction_status != ExtractionStatus.DONE:
        raise HTTPException(
            400, "No facts extracted for this section – call extract-facts first"
        )

    return await facts_read_service.get_hints(
        section_id=section_id,
        attempt_number=attempt_number,
        max_hints=max_hints,
    )


# POST /sections/{section_id}/evaluations
@router.post("/{section_id}/evaluations", response_model=AuditReportResponse)
async def evaluate_summary(
    section_id: str,
    request: SummaryRequest,
    audit_svc: AuditService = Depends(get_audit_service),
    section_repo: SectionRepository = Depends(get_section_repo),
    summary_repo: SummaryRepository = Depends(get_summary_repo),
) -> AuditReportResponse:
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    if section.extraction_status != ExtractionStatus.DONE:
        raise HTTPException(
            400, "Atomic facts not ready – please wait for extraction to complete"
        )

    report = await audit_svc.evaluate_summary(
        section_id=section_id,
        summary_text=request.summary,
    )

    summary = await summary_repo.find_by_id(report.summary_id)
    attempt_number = summary.attempt_number if summary else 1

    feedback = []
    for v in report.validations:
        fact = await audit_svc.fact_repo.find_by_id(v.atomic_fact_id)
        feedback.append(
            {
                "fact_id": v.atomic_fact_id,
                "point": fact.point if fact else "",
                "status": v.status if hasattr(v.status, "value") else v.status,
                "evidence": v.evidence or "",
                "confidence": v.confidence,
                "improved": v.improved,
            }
        )

    return AuditReportResponse(
        id=report.id,
        score=report.score,
        score_delta=report.score_delta,
        attempt_number=attempt_number,
        fact_feedback=feedback,
    )


# GET /sections/{section_id}/evaluations – history
@router.get("/{section_id}/evaluations")
async def get_evaluation_history(
    section_id: str,
    audit_repo=Depends(get_audit_report_repo),
):
    reports = await audit_repo.get_history_by_section(section_id)
    return [
        {
            "id": r.id,
            "score": r.score,
            "score_delta": r.score_delta,
            "attempt_number": r.summary.attempt_number if r.summary else 1,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in reports
    ]
