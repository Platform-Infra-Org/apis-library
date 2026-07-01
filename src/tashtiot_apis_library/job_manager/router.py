"""HTTP routes for the job manager (resource-oriented, AWX-like)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from .models import (
    JobOperationResponse,
    JobRecord,
    JobRequest,
    JobStatus,
    JobStatusResponse,
    JobSummary,
)
from .service import JobManager

__all__ = ["create_job_manager_router"]


def create_job_manager_router(manager: JobManager) -> APIRouter:
    router = APIRouter(tags=["jobs"])

    @router.post("/jobs", response_model=JobOperationResponse, status_code=status.HTTP_202_ACCEPTED)
    async def create_job(request: JobRequest, http_request: Request, response: Response):
        result = await manager.launch_job(request)
        response.headers["Location"] = str(http_request.url_for("get_job", job_id=result.job_id))
        return result

    @router.get("/jobs", response_model=List[JobSummary])
    async def list_jobs(
        status: Optional[JobStatus] = Query(default=None),
        target: Optional[str] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        return await manager.list_jobs(target=target, status=status, limit=limit, offset=offset)

    @router.get("/jobs/{job_id}", response_model=JobRecord, name="get_job")
    async def get_job(job_id: str):
        return await manager.get_job(job_id)

    @router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
    async def get_job_status(job_id: str):
        return await manager.get_job_status(job_id)

    @router.get("/jobs/{job_id}/logs", response_class=PlainTextResponse)
    async def get_job_logs(job_id: str):
        # Captured stdout = the record's result, available once the job is terminal.
        return await manager.get_logs(job_id)

    @router.post(
        "/jobs/{job_id}/cancel",
        response_model=JobOperationResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def cancel_job(job_id: str):
        return await manager.cancel_job(job_id)

    return router
