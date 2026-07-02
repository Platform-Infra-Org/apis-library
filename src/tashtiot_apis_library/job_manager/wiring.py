"""One-call wiring to mount the job manager onto a ``general_create_app`` instance."""

from __future__ import annotations

from typing import Collection, Optional

from fastapi import FastAPI
from loguru import logger

from ..fastapi_template.utils import settings as app_settings
from .repository import JobRepository, RedisJobRepository
from .router import create_job_manager_router
from .service import JobManager

__all__ = ["enable_job_manager"]


def enable_job_manager(
    app: FastAPI,
    *,
    prefix: str = "",
    repository: Optional[JobRepository] = None,
    manager: Optional[JobManager] = None,
    known_operations: Optional[Collection[str]] = None,
) -> JobManager:
    """Set up the Dramatiq broker (so launch/cancel work), build the service, mount the router.

    API replicas only enqueue + read the repository; the executor runs in the
    separate worker. Pass ``manager``/``repository`` to inject fakes in tests.
    ``known_operations`` rejects unknown operations at launch with 422.
    """
    if manager is None:
        if repository is None:
            from .broker import create_async_redis, setup_broker  # lazy: pulls in Dramatiq

            setup_broker()  # uses settings.REDIS_URL -- the single source of truth
            repository = RedisJobRepository(
                create_async_redis(), record_ttl=app_settings.JM_JOB_TTL
            )
        manager = JobManager(repository, known_operations=known_operations)

    app.include_router(create_job_manager_router(manager), prefix=prefix)
    logger.info("Job manager enabled at {}/jobs", prefix)
    return manager
