"""Pydantic models for the job manager (request, status, stored record, responses)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..connectors.response_schemas import OperationResponse

__all__ = [
    "JobStatus",
    "JobRequest",
    "JobRecord",
    "JobSummary",
    "JobStatusResponse",
    "JobOperationResponse",
]


class JobStatus(str, Enum):
    """Job status vocabulary. The JobRepository is the sole source of truth."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobRequest(BaseModel):
    """Request to run an operation against a target (also the per-target serialization key)."""

    model_config = ConfigDict(extra="allow")

    target: str = Field(
        ..., description="Resource the operation targets; per-target serialization key."
    )
    operation: str = Field(..., description="Named operation to run, e.g. 'drain_node'.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters.")
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Optional caller key to dedupe launches; same key reuses the in-flight job.",
    )


class JobRecord(BaseModel):
    """The stored job state -- written by the actor, read by the routes."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    target: str
    operation: str
    params: Dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    message_id: Optional[str] = Field(default=None, description="Dramatiq message id (for cancel).")
    error: Optional[str] = None
    result: Optional[str] = Field(default=None, description="Captured stdout, set on success.")
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


class JobSummary(BaseModel):
    """Lightweight list row."""

    job_id: str
    target: str
    operation: str
    status: JobStatus
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Cheap-poll payload for ``GET /jobs/{id}/status``."""

    status: JobStatus


class JobOperationResponse(OperationResponse):
    """AWX-mirrored operation response (adds the string ``job_id``)."""

    job_id: str = Field(..., description="Job id.")
