"""Typed exceptions for the job manager (extend ``ExternalServiceError``, like the connectors)."""

from __future__ import annotations

from ..connectors.errors import ExternalServiceError

__all__ = [
    "JobManagerError",
    "JobNotFoundError",
    "JobAlreadyTerminalError",
    "UnknownOperationError",
    "ExecutorError",
    "TargetLockTimeout",
]


class JobManagerError(ExternalServiceError):
    """Base error for the job manager."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(service_name="JobManager", status_code=status_code, detail=detail)


class JobNotFoundError(JobManagerError):
    def __init__(self, job_id: str) -> None:
        super().__init__(status_code=404, detail=f"Job {job_id!r} not found.")


class JobAlreadyTerminalError(JobManagerError):
    def __init__(self, job_id: str) -> None:
        super().__init__(status_code=409, detail=f"Job {job_id!r} is already in a terminal state.")


class UnknownOperationError(JobManagerError):
    """Launch rejected: the operation isn't in the configured catalog (fast-fail at 422)."""

    def __init__(self, operation: str) -> None:
        super().__init__(status_code=422, detail=f"Unknown operation {operation!r}.")


class ExecutorError(JobManagerError):
    """Raised by an executor on a failed operation."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=502, detail=detail)


class TargetLockTimeout(JobManagerError):
    def __init__(self, target: str) -> None:
        super().__init__(status_code=503, detail=f"Timed out acquiring lock for target {target!r}.")
