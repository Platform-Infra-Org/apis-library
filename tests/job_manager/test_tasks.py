"""run_job actor body: status transitions written to the repo, under the per-target lock.

The actor coroutine (``run_job.fn.__wrapped__``, the coroutine under dramatiq's async_to_sync) is called directly with its module-level
dependencies monkeypatched -- no broker/worker needed.
"""

import pytest

import tashtiot_apis_library.job_manager.tasks as tasks
from tashtiot_apis_library.job_manager.exceptions import ExecutorError
from tashtiot_apis_library.job_manager.models import JobRecord, JobStatus
from tashtiot_apis_library.job_manager.repository import InMemoryJobRepository

from .conftest import FakeExecutor, FakeRedis


@pytest.fixture
def wire(monkeypatch):
    """Point the actor at an in-memory repo + fake redis; return (repo, set_executor, set_redis)."""
    repo = InMemoryJobRepository()
    redis = FakeRedis()
    monkeypatch.setattr(tasks, "_repo", lambda: repo)
    monkeypatch.setattr(tasks, "create_async_redis", lambda: redis)

    def set_executor(ex):
        monkeypatch.setattr(tasks, "_executor", ex)

    def set_redis(r):
        monkeypatch.setattr(tasks, "create_async_redis", lambda: r)

    return repo, redis, set_executor, set_redis


async def _seed(repo, job_id="j1"):
    await repo.save(JobRecord(job_id=job_id, target="host-1", operation="op", params={}))


@pytest.mark.asyncio
async def test_success_writes_running_then_succeeded(wire):
    repo, redis, set_executor, _ = wire
    set_executor(FakeExecutor(["a", "b", "c"]))
    await _seed(repo)

    await tasks.run_job.fn.__wrapped__(job_id="j1", target="host-1", operation="op", params={})

    record = await repo.get("j1")
    assert record.status is JobStatus.SUCCEEDED
    assert record.result == "a\nb\nc"
    assert record.started_at is not None and record.finished_at is not None
    assert redis.last_lock.released is True


@pytest.mark.asyncio
async def test_failure_writes_failed_with_error_and_reraises(wire):
    repo, _, set_executor, _ = wire
    set_executor(FakeExecutor(raises=ExecutorError("boom")))
    await _seed(repo, "j2")

    with pytest.raises(ExecutorError):
        await tasks.run_job.fn.__wrapped__(job_id="j2", target="host-1", operation="op", params={})
    record = await repo.get("j2")
    assert record.status is JobStatus.FAILED
    assert "boom" in record.error


@pytest.mark.asyncio
async def test_lock_contention_writes_failed(wire):
    repo, _, set_executor, set_redis = wire
    set_executor(FakeExecutor())
    set_redis(FakeRedis(acquirable=False))
    await _seed(repo, "j3")

    await tasks.run_job.fn.__wrapped__(job_id="j3", target="host-1", operation="op", params={})
    record = await repo.get("j3")
    assert record.status is JobStatus.FAILED
    assert "lock" in record.error.lower()


@pytest.mark.asyncio
async def test_cooperative_abort_writes_cancelled(wire, monkeypatch):
    repo, _, set_executor, _ = wire
    set_executor(FakeExecutor(["a", "b"]))
    await _seed(repo, "j4")

    class _Msg:
        message_id = "m4"

    monkeypatch.setattr(tasks.CurrentMessage, "get_current_message", staticmethod(lambda: _Msg()))
    monkeypatch.setattr(tasks, "abort_requested", lambda mid: 1.0)  # abort already requested

    await tasks.run_job.fn.__wrapped__(job_id="j4", target="host-1", operation="op", params={})
    record = await repo.get("j4")
    assert record.status is JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_midstream_abort_writes_cancelled_and_releases_lock(wire, monkeypatch):
    # Abort lands between output chunks: first poll clean, second flagged.
    repo, redis, set_executor, _ = wire
    set_executor(FakeExecutor(["a", "b", "c"]))
    await _seed(repo, "j5")

    class _Msg:
        message_id = "m5"

    polls = iter([False, True])
    monkeypatch.setattr(tasks.CurrentMessage, "get_current_message", staticmethod(lambda: _Msg()))
    monkeypatch.setattr(tasks, "abort_requested", lambda mid: next(polls))

    await tasks.run_job.fn.__wrapped__(job_id="j5", target="host-1", operation="op", params={})
    record = await repo.get("j5")
    assert record.status is JobStatus.CANCELLED
    assert record.finished_at is not None
    assert redis.last_lock.released is True


@pytest.mark.asyncio
async def test_cancelled_error_writes_cancelled_and_reraises(wire):
    # The Abortable/AsyncIO middleware interrupts the actor by cancelling its task.
    import asyncio

    repo, redis, set_executor, _ = wire
    set_executor(FakeExecutor(raises=asyncio.CancelledError()))
    await _seed(repo, "j6")

    with pytest.raises(asyncio.CancelledError):
        await tasks.run_job.fn.__wrapped__(job_id="j6", target="host-1", operation="op", params={})
    record = await repo.get("j6")
    assert record.status is JobStatus.CANCELLED
    assert redis.last_lock.released is True


def test_actor_max_retries_is_zero():
    # Non-idempotent jobs must not be retried by Dramatiq's default of 20.
    assert tasks.run_job.options.get("max_retries") == 0
