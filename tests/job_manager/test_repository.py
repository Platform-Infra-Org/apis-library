"""InMemoryJobRepository contract (the Redis impl is exercised by the e2e/integration path)."""

import pytest

from tashtiot_apis_library.job_manager.models import JobRecord, JobStatus
from tashtiot_apis_library.job_manager.repository import InMemoryJobRepository


def _rec(job_id, target="host-1", status=JobStatus.PENDING):
    return JobRecord(job_id=job_id, target=target, operation="op", params={}, status=status)


@pytest.mark.asyncio
async def test_save_get_update():
    repo = InMemoryJobRepository()
    await repo.save(_rec("a"))
    assert (await repo.get("a")).status is JobStatus.PENDING
    assert await repo.get("missing") is None

    updated = await repo.update("a", status=JobStatus.RUNNING.value, result="out")
    assert updated.status is JobStatus.RUNNING
    assert (await repo.get("a")).result == "out"
    assert await repo.update("missing", status=JobStatus.FAILED.value) is None


@pytest.mark.asyncio
async def test_create_claim_semantics():
    repo = InMemoryJobRepository()
    assert await repo.create(_rec("a", status=JobStatus.PENDING)) is True
    # A live (non-terminal) record owns the id -> claim fails.
    assert await repo.create(_rec("a", status=JobStatus.RUNNING)) is False
    # Once terminal, a re-claim wins and replaces the record.
    await repo.update("a", status=JobStatus.SUCCEEDED.value)
    assert await repo.create(_rec("a", target="host-2", status=JobStatus.PENDING)) is True
    replaced = await repo.get("a")
    assert replaced.status is JobStatus.PENDING
    assert replaced.target == "host-2"


@pytest.mark.asyncio
async def test_list_filters_target_and_status():
    repo = InMemoryJobRepository()
    await repo.save(_rec("a", target="host-1", status=JobStatus.RUNNING))
    await repo.save(_rec("b", target="host-1", status=JobStatus.SUCCEEDED))
    await repo.save(_rec("c", target="host-2", status=JobStatus.RUNNING))

    assert {r.job_id for r in await repo.list(target="host-1")} == {"a", "b"}
    assert {r.job_id for r in await repo.list(status=JobStatus.RUNNING)} == {"a", "c"}
    assert len(await repo.list(limit=2)) == 2
