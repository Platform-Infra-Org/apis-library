"""JobManager against the in-memory repo + the stub broker (no Redis)."""

import dramatiq_abort
import pytest

from tashtiot_apis_library.job_manager.exceptions import (
    JobAlreadyTerminalError,
    JobNotFoundError,
    UnknownOperationError,
)
from tashtiot_apis_library.job_manager.models import JobRequest, JobStatus
from tashtiot_apis_library.job_manager.repository import InMemoryJobRepository
from tashtiot_apis_library.job_manager.service import JobManager


@pytest.fixture
def manager(repo: InMemoryJobRepository) -> JobManager:
    return JobManager(repo)


def _req(**kw):
    return JobRequest(target="host-1", operation="drain_node", params={"node": "n1"}, **kw)


@pytest.mark.asyncio
async def test_launch_creates_pending_record_and_enqueues(manager, stub_broker):
    resp = await manager.launch_job(_req())

    assert resp.status == JobStatus.PENDING.value
    assert resp.status_code == 202
    record = await manager.repository.get(resp.job_id)
    assert record.status is JobStatus.PENDING
    assert record.target == "host-1"
    assert record.message_id is not None  # set from the enqueued Dramatiq message


@pytest.mark.asyncio
async def test_status_and_logs_read_from_repository(manager, stub_broker):
    resp = await manager.launch_job(_req())
    # Simulate the worker progressing the job.
    await manager.repository.update(resp.job_id, status=JobStatus.SUCCEEDED.value, result="done")
    assert (await manager.get_job_status(resp.job_id)).status is JobStatus.SUCCEEDED
    assert await manager.get_logs(resp.job_id) == "done"


@pytest.mark.asyncio
async def test_get_unknown_raises(manager):
    with pytest.raises(JobNotFoundError):
        await manager.get_job("nope")


@pytest.mark.asyncio
async def test_unknown_operation_rejected_at_launch(repo, stub_broker):
    mgr = JobManager(repo, known_operations={"drain_node"})
    with pytest.raises(UnknownOperationError):
        await mgr.launch_job(JobRequest(target="h", operation="bogus", params={}))


@pytest.mark.asyncio
async def test_idempotency_reuses_inflight(manager, stub_broker):
    first = await manager.launch_job(_req(idempotency_key="abc"))
    await manager.repository.update(first.job_id, status=JobStatus.RUNNING.value)
    second = await manager.launch_job(_req(idempotency_key="abc"))
    assert second.job_id == first.job_id
    assert second.status == JobStatus.RUNNING.value


@pytest.mark.asyncio
async def test_concurrent_idempotent_launches_enqueue_once(manager, stub_broker):
    # Two identical requests racing: exactly one wins the atomic claim; the loser
    # reuses the same job without a second enqueue.
    import asyncio

    a, b = await asyncio.gather(
        manager.launch_job(_req(idempotency_key="dup")),
        manager.launch_job(_req(idempotency_key="dup")),
    )
    assert a.job_id == b.job_id
    assert stub_broker.queues["default"].qsize() == 1


@pytest.mark.asyncio
async def test_relaunch_after_terminal_reuses_id_and_enqueues_again(manager, stub_broker):
    first = await manager.launch_job(_req(idempotency_key="re"))
    await manager.repository.update(first.job_id, status=JobStatus.SUCCEEDED.value)
    stub_broker.flush_all()  # drop the first message so we can count the second

    second = await manager.launch_job(_req(idempotency_key="re"))
    assert second.job_id == first.job_id
    assert second.status == JobStatus.PENDING.value
    assert stub_broker.queues["default"].qsize() == 1  # terminal prior -> re-enqueued


@pytest.mark.asyncio
async def test_concurrent_relaunch_after_terminal_enqueues_once(manager, stub_broker):
    import asyncio

    first = await manager.launch_job(_req(idempotency_key="rdup"))
    await manager.repository.update(first.job_id, status=JobStatus.SUCCEEDED.value)
    stub_broker.flush_all()  # drop the first message

    a, b = await asyncio.gather(
        manager.launch_job(_req(idempotency_key="rdup")),
        manager.launch_job(_req(idempotency_key="rdup")),
    )
    assert a.job_id == b.job_id
    assert stub_broker.queues["default"].qsize() == 1  # exactly one wins the claim


@pytest.mark.asyncio
async def test_enqueue_failure_marks_failed_and_reraises(manager, stub_broker, monkeypatch):
    from tashtiot_apis_library.job_manager.tasks import run_job

    def boom(*_a, **_k):
        raise RuntimeError("broker down")

    monkeypatch.setattr(run_job.broker, "enqueue", boom)

    with pytest.raises(RuntimeError):
        await manager.launch_job(_req(idempotency_key="failenq"))

    record = await manager.repository.get("job-failenq")
    assert record.status is JobStatus.FAILED
    assert "enqueue failed" in record.error


@pytest.mark.asyncio
async def test_cancel_requests_abort(manager, stub_broker, monkeypatch):
    calls = []
    monkeypatch.setattr(dramatiq_abort, "abort", lambda mid, **kw: calls.append(mid))

    resp = await manager.launch_job(_req())
    record = await manager.repository.get(resp.job_id)

    out = await manager.cancel_job(resp.job_id)
    assert out.status == JobStatus.CANCELLED.value
    assert calls == [record.message_id]  # cancel maps job_id -> message_id and aborts

    # Still-queued job: cancel_job itself writes the terminal state (the actor
    # never runs -- Abortable skips the message before it starts).
    record = await manager.repository.get(resp.job_id)
    assert record.status is JobStatus.CANCELLED
    assert record.finished_at is not None


@pytest.mark.asyncio
async def test_cancel_running_leaves_terminal_write_to_actor(manager, stub_broker, monkeypatch):
    monkeypatch.setattr(dramatiq_abort, "abort", lambda mid, **kw: None)
    resp = await manager.launch_job(_req())
    await manager.repository.update(resp.job_id, status=JobStatus.RUNNING.value)

    await manager.cancel_job(resp.job_id)
    record = await manager.repository.get(resp.job_id)
    assert record.status is JobStatus.RUNNING  # actor's shielded write owns the transition


@pytest.mark.asyncio
async def test_cancel_terminal_raises(manager, stub_broker):
    resp = await manager.launch_job(_req())
    await manager.repository.update(resp.job_id, status=JobStatus.SUCCEEDED.value)
    with pytest.raises(JobAlreadyTerminalError):
        await manager.cancel_job(resp.job_id)


@pytest.mark.asyncio
async def test_wait_returns_terminal_record(manager, stub_broker):
    resp = await manager.launch_job(_req())
    await manager.repository.update(resp.job_id, status=JobStatus.SUCCEEDED.value)
    record = await manager.wait_for_job_completion(resp.job_id, timeout=1, poll_interval=1)
    assert record.status is JobStatus.SUCCEEDED
