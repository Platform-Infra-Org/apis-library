"""Pydantic models for AWX (Ansible Workflow Engine) operations and responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..response_schemas import OperationResponse

__all__ = [
    "AWXJobStatus",
    "AWXJob",
    "AWXWorkflowJob",
    "AWXLaunchJobRequest",
    "AWXLaunchWorkflowRequest",
    "AWXOperationResponse",
]


class AWXOperationResponse(OperationResponse):
    """Response schema for AWX/AWX operations.

    Extends OperationResponse with AWX-specific job_id field.
    """

    job_id: int = Field(..., description="AWX job ID")


class AWXJobStatus(str, Enum):
    """Status enumeration for AWX jobs."""

    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    ERROR = "error"
    CANCELED = "canceled"


class AWXJob(BaseModel):
    """Represents a single AWX job."""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    status: AWXJobStatus
    job_type: Optional[str] = Field(default=None, alias="type")
    url: Optional[str] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    finished: Optional[datetime] = None
    elapsed: Optional[float] = None
    job_explanation: Optional[str] = Field(default=None, alias="job_explanation")
    result_stdout: Optional[str] = Field(default=None, alias="result_stdout")
    job_template_id: Optional[int] = Field(default=None, alias="job_template")
    inventory: Optional[int] = None
    project: Optional[int] = None
    playbook: Optional[str] = None
    credential: Optional[int] = None
    limit: Optional[str] = None
    extra_vars: Optional[str] = Field(default=None, alias="extra_vars")


class AWXWorkflowJob(BaseModel):
    """Represents a workflow job (collection of jobs)."""

    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    status: AWXJobStatus
    url: Optional[str] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    finished: Optional[datetime] = None
    elapsed: Optional[float] = None
    workflow_job_template_id: Optional[int] = Field(default=None, alias="workflow_job_template")
    extra_vars: Optional[str] = Field(default=None, alias="extra_vars")
    workflow_nodes: List[Dict[str, Any]] = Field(default_factory=list)


class AWXLaunchJobRequest(BaseModel):
    """Request payload for launching a job."""

    model_config = ConfigDict(extra="allow")

    inventory: Optional[int] = None
    credential: Optional[int] = None
    limit: Optional[str] = None
    extra_vars: Optional[str] = Field(default=None, alias="extra_vars")
    job_tags: Optional[str] = Field(default=None, alias="job_tags")
    skip_tags: Optional[str] = Field(default=None, alias="skip_tags")
    diff_mode: Optional[bool] = Field(default=None, alias="diff_mode")
    verbosity: Optional[int] = None


class AWXLaunchWorkflowRequest(BaseModel):
    """Request payload for launching a workflow."""

    model_config = ConfigDict(extra="allow")

    extra_vars: Optional[str] = Field(default=None, alias="extra_vars")
    inventory: Optional[int] = None
    limit: Optional[str] = None
