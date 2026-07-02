"""High-level job manager service (AWX-mirrored). Enqueues via Dramatiq, reads state from the repository."""

from __future__ import annotations

import asyncio
import uuid
from typing import Collection, List, Optional

from loguru import logger

from .exceptions import (
    JobAlreadyTerminalError,
    JobManagerError,
    JobNotFoundError,
    UnknownOperationError,
)
from .models import (
    JobOperationResponse,
    JobRecord,
    JobRequest,
    JobStatus,
    JobStatusResponse,
    _utcnow,
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
        job_id = f"job-{request.idempotency_key}" if request.idempotency_key else uuid.uuid4().hex

        from .tasks import run_job  # lazy: pulls in Dramatiq

        # Build the message first (no I/O) so its message_id lands in the record at
        # claim time -- no post-send update() racing the worker's status writes.
        message = run_job.message(
            job_id=job_id,
            target=request.target,
            operation=request.operation,
            params=request.params,
        )

        # Record exists before the worker can pick the message up. Atomic claim so
        # concurrent duplicate launches can't both enqueue -- exactly one wins create()
        # (a terminal prior record lets the claim succeed and re-run under the same id).
        record = JobRecord(
            job_id=job_id,
            target=request.target,
            operation=request.operation,
            params=request.params,
            status=JobStatus.PENDING,
            message_id=message.message_id,
        )
        if not await self.repository.create(record):
            # Lost the claim: a live (non-terminal) record already owns this id -- reuse it.
            existing = await self.repository.get(job_id)
            if existing is None:
                # Claim refused yet no record exists: repository inconsistency.
                # Don't mask it as a healthy pending job.
                logger.error("Job {} claim lost but record missing", job_id)
                raise JobManagerError(500, f"Job {job_id!r} state is inconsistent; retry launch.")
            logger.info("Idempotent launch: reusing in-flight job {}", job_id)
            return JobOperationResponse(
                status=existing.status.value, status_code=202, job_id=job_id
            )

        try:
            await asyncio.to_thread(run_job.broker.enqueue, message)
        except Exception as exc:
            logger.exception(
                "Enqueue failed for job {} ({} on {})", job_id, request.operation, request.target
            )
            # No phantom pending record if the enqueue itself fails.
            await self.repository.update(
                job_id, status=JobStatus.FAILED.value, error=f"enqueue failed: {exc}"
            )
            raise
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
    ) -> List[JobRecord]:
        # JobRecord is a superset of JobSummary; the router's response_model filters.
        return await self.repository.list(target=target, status=status, limit=limit, offset=offset)

    async def cancel_job(self, job_id: str) -> JobOperationResponse:
        """Request a cooperative abort; the actor writes the terminal ``cancelled`` state."""
        record = await self._require(job_id)
        if record.is_terminal:
            raise JobAlreadyTerminalError(job_id)
        if record.message_id:
            from dramatiq_abort import abort  # lazy: pulls in Dramatiq

            await asyncio.to_thread(abort, record.message_id)
        if record.status == JobStatus.PENDING:
            # Still queued: the Abortable middleware skips the message before the actor
            # runs, so nobody else would ever write the terminal state.
            await self.repository.update(
                job_id, status=JobStatus.CANCELLED.value, finished_at=_utcnow()
            )
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
