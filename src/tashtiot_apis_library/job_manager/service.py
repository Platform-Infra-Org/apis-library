"""High-level job manager service (AWX-mirrored). Enqueues via Dramatiq, reads state from the repository."""

from __future__ import annotations

import asyncio
import uuid
from typing import Collection, List, Optional

from loguru import logger

from .exceptions import JobAlreadyTerminalError, JobNotFoundError, UnknownOperationError
from .models import (
    JobOperationResponse,
    JobRecord,
    JobRequest,
    JobStatus,
    JobStatusResponse,
    JobSummary,
)
from .repository import JobRepository

__all__ = ["JobManager"]


class JobManager:
    """Sibling of :class:`AWX`: launch/poll/cancel jobs on any target via Dramatiq + Redis."""

    def __init__(
        self,
        repository: JobRepository,
        *,
        known_operations: Optional[Collection[str]] = None,
    ) -> None:
        self.repository = repository
        self.known_operations = set(known_operations) if known_operations is not None else None

    async def launch_job(self, request: JobRequest) -> JobOperationResponse:
        """Create the ``pending`` record, then enqueue. Returns ``202``-shaped."""
        if self.known_operations is not None and request.operation not in self.known_operations:
            raise UnknownOperationError(request.operation)

        # Idempotency: a stable id lets a replay reuse a still-running job.
        if request.idempotency_key:
            job_id = f"job-{request.idempotency_key}"
            existing = await self.repository.get(job_id)
            if existing is not None and not existing.is_terminal:
                logger.info("Idempotent launch: reusing in-flight job {}", job_id)
                return JobOperationResponse(
                    status=existing.status.value, status_code=202, job_id=job_id
                )
        else:
            job_id = uuid.uuid4().hex

        # Record exists before the worker can pick the message up.
        record = JobRecord(
            job_id=job_id,
            target=request.target,
            operation=request.operation,
            params=request.params,
            status=JobStatus.PENDING,
        )
        await self.repository.save(record)

        from .tasks import run_job  # lazy: pulls in Dramatiq

        message = await asyncio.to_thread(
            run_job.send,
            job_id=job_id,
            target=request.target,
            operation=request.operation,
            params=request.params,
        )
        await self.repository.update(job_id, message_id=message.message_id)
        logger.info("Enqueued job {} for target {}", job_id, request.target)
        return JobOperationResponse(status=JobStatus.PENDING.value, status_code=202, job_id=job_id)

    async def _require(self, job_id: str) -> JobRecord:
        record = await self.repository.get(job_id)
        if record is None:
            raise JobNotFoundError(job_id)
        return record

    async def get_job(self, job_id: str) -> JobRecord:
        return await self._require(job_id)

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        return JobStatusResponse(status=(await self._require(job_id)).status)

    async def list_jobs(
        self,
        *,
        target: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobSummary]:
        records = await self.repository.list(
            target=target, status=status, limit=limit, offset=offset
        )
        return [
            JobSummary(
                job_id=r.job_id,
                target=r.target,
                operation=r.operation,
                status=r.status,
                created_at=r.created_at,
            )
            for r in records
        ]

    async def cancel_job(self, job_id: str) -> JobOperationResponse:
        """Request a cooperative abort; the actor writes the terminal ``cancelled`` state."""
        record = await self._require(job_id)
        if record.is_terminal:
            raise JobAlreadyTerminalError(job_id)
        if record.message_id:
            from dramatiq_abort import abort  # lazy: pulls in Dramatiq

            await asyncio.to_thread(abort, record.message_id)
        logger.info("Requested abort for job {}", job_id)
        return JobOperationResponse(
            status=JobStatus.CANCELLED.value, status_code=202, job_id=job_id
        )

    async def get_logs(self, job_id: str) -> str:
        """Captured stdout = the record's ``result`` (set by the actor on success)."""
        record = await self._require(job_id)
        return record.result or ""

    async def wait_for_job_completion(
        self, job_id: str, timeout: int = 300, poll_interval: int = 5
    ) -> JobRecord:
        """Poll the repository until the job reaches a terminal status (mirrors ``AWX``)."""
        logger.info("Waiting for job {} to complete (timeout={}s)", job_id, timeout)
        elapsed = 0
        while elapsed < timeout:
            record = await self._require(job_id)
            if record.is_terminal:
                logger.info("Job {} completed with status {}", job_id, record.status.value)
                return record
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
