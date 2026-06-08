"""Fact extraction job status compatibility router."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.wiring import get_job_service
from src.jobs import JOB_EXTRACT_FACTS, JobService
from src.response.extract_fact_response import ExtractFactResponse

router = APIRouter(prefix="/facts/extraction", tags=["facts"])


@router.get("/{job_id}", response_model=ExtractFactResponse)
async def get_extraction_job(
    job_id: str,
    jobs: JobService = Depends(get_job_service),
) -> ExtractFactResponse:
    job = await jobs.get_job(job_id)
    if not job or job.job_type != JOB_EXTRACT_FACTS:
        raise HTTPException(404, "Extraction job not found")
    status_map = {
        "queued": "pending",
        "running": "running",
        "succeeded": "completed",
        "failed": "failed",
        "cancelled": "failed",
    }
    return ExtractFactResponse(
        job_id=job.id,
        section_id=job.resource_id,
        status=status_map.get(job.status, "pending"),
        created_at=job.created_at,
        message=job.message,
    )
