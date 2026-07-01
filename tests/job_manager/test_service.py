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
async def test_cancel_requests_abort(manager, stub_broker, monkeypatch):
    calls = []
    monkeypatch.setattr(dramatiq_abort, "abort", lambda mid, **kw: calls.append(mid))

    resp = await manager.launch_job(_req())
    record = await manager.repository.get(resp.job_id)

    out = await manager.cancel_job(resp.job_id)
    assert out.status == JobStatus.CANCELLED.value
    assert calls == [record.message_id]  # cancel maps job_id -> message_id and aborts


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
