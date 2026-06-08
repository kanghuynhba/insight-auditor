"""Generic processing job status router."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.wiring import get_job_service
from src.jobs import JobService
from src.response.job import ProcessingJobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobResponse])
async def list_jobs(
    status: Optional[str] = Query(None),
    queue_name: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    jobs: JobService = Depends(get_job_service),
) -> list[ProcessingJobResponse]:
    matching_jobs = await jobs.list_jobs(
        status=status,
        queue_name=queue_name,
        job_type=job_type,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
    )
    return [ProcessingJobResponse.from_job(job) for job in matching_jobs]


@router.get("/{job_id}", response_model=ProcessingJobResponse)
async def get_job(
    job_id: str,
    jobs: JobService = Depends(get_job_service),
) -> ProcessingJobResponse:
    job = await jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return ProcessingJobResponse.from_job(job)
