"""The Dramatiq actor: run one operation under the per-target lock, writing every
status transition to the repository (the sole source of truth)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

import dramatiq
from dramatiq.middleware import CurrentMessage
from dramatiq_abort import Abort, abort_requested
from loguru import logger

from ..fastapi_template.utils import settings as app_settings
from .broker import create_async_redis, setup_broker
from .exceptions import TargetLockTimeout
from .executor import CommandExecutor, Executor
from .locks import target_lock
from .metrics import JOB_DURATION, JOBS_INFLIGHT, JOBS_TOTAL
from .models import JobStatus, _utcnow
from .repository import RedisJobRepository

__all__ = ["run_job", "set_executor"]

setup_broker()  # the actor must register against a set broker

_executor: Optional[Executor] = None


def set_executor(executor: Executor) -> None:
    """Override the worker's executor (call at worker-module import for a custom backend)."""
    global _executor
    _executor = executor


def _executor_instance() -> Executor:
    global _executor
    if _executor is None:
        commands: Dict[str, Any] = {}
        if app_settings.JM_COMMAND_MAP:
            commands = json.loads(app_settings.JM_COMMAND_MAP)
        _executor = CommandExecutor(command_for=commands, shell=app_settings.JM_COMMAND_SHELL)
    return _executor


def _repo() -> RedisJobRepository:
    return RedisJobRepository(create_async_redis(), record_ttl=app_settings.JM_JOB_TTL)


async def _finish(
    repo: Any,
    job_id: str,
    status: JobStatus,
    *,
    metric: Optional[str] = None,
    expected_status: Optional[JobStatus] = None,
    **fields: Any,
) -> None:
    """Write a terminal status to the repo and bump the metric (defaults to the status).

    With ``expected_status`` the write is a CAS: if another write beat us (e.g. the
    success write already landed when a cancel arrives), it is skipped, metric included.
    """
    updated = await repo.update(
        job_id,
        expected_status=expected_status,
        status=status.value,
        finished_at=_utcnow(),
        **fields,
    )
    if updated is None:
        if expected_status is not None:
            logger.info("Skipped '{}' write for job {}: status moved on", status.value, job_id)
            return
        # Record gone (JM_JOB_TTL shorter than the job ran?) -- the outcome is lost.
        logger.warning(
            "Terminal write '{}' for job {} dropped: record missing/expired. "
            "Keep JM_JOB_TTL above the longest job runtime.",
            status.value,
            job_id,
        )
    JOBS_TOTAL.labels(status=metric or status.value).inc()


@dramatiq.actor(
    max_retries=app_settings.JM_MAX_RETRIES, time_limit=app_settings.JM_ACTOR_TIME_LIMIT_MS
)
async def run_job(*, job_id: str, target: str, operation: str, params: Dict[str, Any]) -> None:
    """Execute the job and persist its lifecycle. Status lives only in the repository.

    Tests call the bare coroutine directly via ``run_job.fn.__wrapped__``.
    """
    repo = _repo()
    message = CurrentMessage.get_current_message()
    message_id = message.message_id if message is not None else None

    with logger.contextualize(job_id=job_id):
        # A cancel that landed before we started: bail without running.
        if message_id is not None and abort_requested(message_id):
            await _finish(repo, job_id, JobStatus.CANCELLED)
            return

        JOBS_INFLIGHT.inc()
        start = time.monotonic()
        finished = False
        lines: list[str] = []
        try:
            # Inside the try so a setup failure (e.g. malformed JM_COMMAND_MAP)
            # marks the job failed instead of leaving it pending forever.
            executor = _executor_instance()
            redis = create_async_redis()
            await repo.update(job_id, status=JobStatus.RUNNING.value, started_at=_utcnow())
            async with target_lock(
                redis,
                target,
                timeout=app_settings.JM_TARGET_LOCK_TIMEOUT,
                blocking_timeout=app_settings.JM_TARGET_LOCK_WAIT,
            ):
                logger.info("Job started on target {}", target)
                stream = executor.run(operation, params)
                try:
                    async for chunk in stream:
                        # Cooperative abort: checked between output chunks.
                        if message_id is not None and abort_requested(message_id):
                            raise Abort(message_id)
                        lines.append(chunk)
                finally:
                    aclose = getattr(stream, "aclose", None)
                    if aclose is not None:  # async generators expose aclose(); iterators may not
                        await aclose()
            # Shielded so a cancel landing after the work completed can't kill the
            # success write; `finished` stops the handler re-labelling it cancelled.
            await asyncio.shield(
                _finish(repo, job_id, JobStatus.SUCCEEDED, result="\n".join(lines))
            )
            finished = True
            logger.info("Job succeeded")
        except (Abort, asyncio.CancelledError) as exc:
            # The abort middleware interrupts an async actor by cancelling its task,
            # so we must catch CancelledError too. Shield the terminal write so the
            # cancellation tearing down the task doesn't also kill the status update.
            if not finished:
                logger.warning("Job cancelled")
                # Keep whatever output was captured before the abort. CAS on running:
                # if the success/failure write already landed (a cancel racing the
                # shielded write), this loses cleanly instead of relabelling the job.
                await asyncio.shield(
                    _finish(
                        repo,
                        job_id,
                        JobStatus.CANCELLED,
                        result="\n".join(lines),
                        expected_status=JobStatus.RUNNING,
                    )
                )
            if isinstance(exc, asyncio.CancelledError):
                raise  # never swallow a CancelledError
        except TargetLockTimeout:
            logger.warning("Could not acquire lock for target {} within wait window", target)
            await _finish(
                repo,
                job_id,
                JobStatus.FAILED,
                metric="lock_timeout",
                error="could not acquire target lock",
            )
        except Exception as exc:
            logger.exception("Job failed")
            await _finish(repo, job_id, JobStatus.FAILED, error=str(exc))
            raise  # let Dramatiq log it (max_retries=0 -> no retry)
        finally:
            JOBS_INFLIGHT.dec()
            JOB_DURATION.observe(time.monotonic() - start)
