"""General-purpose async job manager.

An AWX-like execution layer (Dramatiq + Redis) for operations Ansible can't drive
on any system. Mountable via ``enable_job_manager``; the worker runs separately.
"""

from __future__ import annotations

from .exceptions import (
    ExecutorError,
    JobAlreadyTerminalError,
    JobManagerError,
    JobNotFoundError,
    TargetLockTimeout,
    UnknownOperationError,
)
from .executor import CommandExecutor, Executor
from .locks import target_lock
from .models import (
    JobOperationResponse,
    JobRecord,
    JobRequest,
    JobStatus,
    JobStatusResponse,
    JobSummary,
)
from .repository import InMemoryJobRepository, JobRepository, RedisJobRepository
from .router import create_job_manager_router
from .service import JobManager
from .wiring import enable_job_manager

__all__ = [
    "JobManager",
    "enable_job_manager",
    "create_job_manager_router",
    "JobRepository",
    "RedisJobRepository",
    "InMemoryJobRepository",
    "Executor",
    "CommandExecutor",
    "target_lock",
    "JobRequest",
    "JobRecord",
    "JobSummary",
    "JobStatus",
    "JobStatusResponse",
    "JobOperationResponse",
    "JobManagerError",
    "JobNotFoundError",
    "JobAlreadyTerminalError",
    "UnknownOperationError",
    "ExecutorError",
    "TargetLockTimeout",
]
