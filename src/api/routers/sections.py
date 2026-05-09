from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Optional

from src.core.exceptions import ExtractionNotReadyError
from src.response.section import SectionDetailResponse
from src.response.audit_report import AuditReportResponse
from src.infrastructure.persistence.summary_repo import SummaryRepository
from src.services.task_service import TaskService
from src.api.dependencies.storages import get_audit_report_repo, get_summary_repo
from src.api.dependencies.services import (
    get_section_repo,
    get_audit_service,
    get_task_service,
    get_facts_extraction_service,
)
from src.infrastructure.persistence.section_repo import SectionRepository
from src.services.audit_service import AuditService
from src.services.facts_extraction_service import FactsExtractionService
from src.core.enums import ExtractionStatus
from src.request.summary_request import SummaryRequest

router = APIRouter(prefix="/sections", tags=["sections"])


# GET /sections/{section_id}
@router.get("/{section_id}", response_model=SectionDetailResponse)
async def get_section(
    section_id: str,
    section_repo: SectionRepository = Depends(get_section_repo),
):
    section = await section_repo.find_by_id(section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    return SectionDetailResponse(
        id=section.id,
        word_count=section.word_count,
        raw_text=section.raw_text,
        extraction_status=(
            section.extraction_status.value
            if hasattr(section.extraction_status, "value")
            else section.extraction_status
        ),
    )


# # POST /sections/{section_id}/extract-facts
# @router.post("/{section_id}/extract-facts")
# async def extract_facts(
#     section_id: str,
#     force: bool = Query(False),
#     background_tasks: BackgroundTasks = None,
#     section_repo: SectionRepository = Depends(get_section_repo),
#     extraction_service: FactsExtractionService = Depends(get_facts_extraction_service),
#     task_service: TaskService = Depends(get_task_service),
# ):
#     section = await section_repo.find_by_id(section_id)
#     if not section:
#         raise HTTPException(404, "Section not found")

#     # Fast path: already done and not forced
#     if section.extraction_status == ExtractionStatus.DONE and not force:
#         return await extraction_service.get_facts_for_section(section_id)

#     # Prevent concurrent extractions
#     if section.extraction_status == ExtractionStatus.PENDING:
#         raise HTTPException(409, "Extraction already in progress")

#     # Mark section as PENDING (optimistic lock)
#     section.extraction_status = ExtractionStatus.PENDING
#     await section_repo.save(section)
#     await section_repo.session.commit()

#     # Create a PENDING task via TaskService
#     task = await task_service.create(
#         task_type="fact_extraction",
#         resource_type="section",
#         resource_id=section_id,
#         payload={"force": force},
#     )

#     # Enqueue background job: extraction_svc will update task status
#     background_tasks.add_task(
#         extraction_service.extract_facts_by_section,
#         section_id=section_id,
#         force=force,
#         task_id=task.id,
#     )

#     return {
#         "task_id": task.id,
#         "status_url": f"/tasks/{task.id}",
#         "extraction_status": "pending",
#     }


# # GET /sections/{section_id}/facts
# @router.get("/{section_id}/facts")
# async def get_facts(
#     section_id: str,
#     extraction_service: FactsExtractionService = Depends(get_facts_extraction_service),
# ):
#     try:
#         return await extraction_service.get_facts_for_section(section_id)
#     except ExtractionNotReadyError as e:
#         if "status:" in str(e):
#             status = str(e).split("status: ")[-1].rstrip(")")
#             raise HTTPException(
#                 404,
#                 detail={
#                     "extraction_status": status,
#                     "message": "No facts extracted yet",
#                 },
#             )
#     except ValueError as e:
#         raise HTTPException(404, str(e))


# # GET /sections/{section_id}/hints
# @router.get("/{section_id}/hints")
# async def get_hints(
#     section_id: str,
#     attempt_number: Optional[int] = None,
#     max_hints: int = Query(5, le=10),
#     section_repo: SectionRepository = Depends(get_section_repo),
#     extraction_service: FactsExtractionService = Depends(get_facts_extraction_service),
# ):
#     section = await section_repo.find_by_id(section_id)
#     if not section:
#         raise HTTPException(404, "Section not found")

#     if section.extraction_status != ExtractionStatus.DONE:
#         raise HTTPException(
#             400, "No facts extracted for this section – call extract-facts first"
#         )

#     hints = await extraction_service.generate_hints(
#         section_id=section_id,
#         attempt_number=attempt_number,
#         max_hints=max_hints,
#     )
#     return {"hints": hints}


# # POST /sections/{section_id}/evaluations
# @router.post("/{section_id}/evaluations", response_model=AuditReportResponse)
# async def evaluate_summary(
#     section_id: str,
#     request: SummaryRequest,
#     audit_svc: AuditService = Depends(get_audit_service),
#     section_repo: SectionRepository = Depends(get_section_repo),
#     summary_repo: SummaryRepository = Depends(get_summary_repo),
# ):
#     section = await section_repo.find_by_id(section_id)
#     if not section:
#         raise HTTPException(404, "Section not found")

#     if section.extraction_status != ExtractionStatus.DONE:
#         raise HTTPException(
#             400, "Atomic facts not ready – please wait for extraction to complete"
#         )

#     report = await audit_svc.evaluate_summary(
#         section_id=section_id,
#         summary_text=request.summary,
#     )

#     summary = await summary_repo.find_by_id(report.summary_id)
#     attempt_number = summary.attempt_number if summary else 1

#     feedback = []
#     for v in report.validations:
#         fact = await audit_svc.fact_repo.find_by_id(v.atomic_fact_id)
#         feedback.append(
#             {
#                 "fact_id": v.atomic_fact_id,
#                 "point": fact.point if fact else "",
#                 "rank": fact.rank if hasattr(fact, "rank") else 3,
#                 "status": v.status if hasattr(v.status, "value") else v.status,
#                 "evidence": v.evidence or "",
#                 "confidence": v.confidence,
#                 "improved": v.improved,
#             }
#         )

#     return AuditReportResponse(
#         id=report.id,
#         score=report.score,
#         score_delta=report.score_delta,
#         attempt_number=attempt_number,
#         fact_feedback=feedback,
#     )


# # GET /sections/{section_id}/evaluations – history
# @router.get("/{section_id}/evaluations")
# async def get_evaluation_history(
#     section_id: str,
#     audit_repo=Depends(get_audit_report_repo),
# ):
#     reports = await audit_repo.get_history_by_section(section_id)
#     return [
#         {
#             "id": r.id,
#             "score": r.score,
#             "score_delta": r.score_delta,
#             "attempt_number": r.summary.attempt_number if r.summary else 1,
#             "generated_at": r.generated_at.isoformat() if r.generated_at else None,
#         }
#         for r in reports
#     ]
