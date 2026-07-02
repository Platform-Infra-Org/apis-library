"""Repository contract: InMemory impl + RedisJobRepository over a dict-backed fake."""

import json

import pytest

from tashtiot_apis_library.job_manager.models import JobRecord, JobStatus
from tashtiot_apis_library.job_manager.repository import (
    InMemoryJobRepository,
    RedisJobRepository,
)


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


# ---------------------------------------------------------------------------
# RedisJobRepository against a dict-backed fake that mirrors the redis commands
# the repo uses. `eval` re-implements the two Lua scripts' contracts in Python,
# so these tests pin the *calling convention* (key/ARGV order); the Lua itself
# is exercised end-to-end against real Redis (see docs/how-to/run-a-job.md).
# ---------------------------------------------------------------------------
class FakeAsyncRedis:
    def __init__(self):
        self.kv = {}
        self.z = {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None):
        self.kv[key] = value

    async def zadd(self, name, mapping):
        self.z.setdefault(name, {}).update(mapping)

    async def expire(self, name, ttl):
        pass

    async def zrevrange(self, name, start, end):
        members = sorted(self.z.get(name, {}).items(), key=lambda kv: kv[1], reverse=True)
        ids = [m for m, _ in members]
        return ids[start : None if end == -1 else end + 1]

    async def mget(self, keys):
        return [self.kv.get(k) for k in keys]

    async def zrem(self, name, *members):
        for m in members:
            self.z.get(name, {}).pop(m, None)

    async def eval(self, script, numkeys, *args):
        keys, argv = args[:numkeys], [str(a) for a in args[numkeys:]]
        cur = self.kv.get(keys[0])
        if "ZADD" in script:  # _CLAIM_LUA: record JSON, ttl, score, *terminal
            if cur is not None and json.loads(cur)["status"] not in argv[3:]:
                return 0
            self.kv[keys[0]] = argv[0]
            self.z.setdefault(keys[1], {})[json.loads(argv[0])["job_id"]] = float(argv[2])
            return 1
        # _CAS_LUA: record JSON, ttl, expected status
        if cur is None or json.loads(cur)["status"] != argv[2]:
            return 0
        self.kv[keys[0]] = argv[0]
        return 1


@pytest.fixture
def redis_repo():
    fake = FakeAsyncRedis()
    return RedisJobRepository(fake, record_ttl=60), fake


@pytest.mark.asyncio
async def test_redis_create_claims_and_indexes(redis_repo):
    repo, fake = redis_repo
    assert await repo.create(_rec("a")) is True
    assert (await repo.get("a")).status is JobStatus.PENDING
    assert [r.job_id for r in await repo.list()] == ["a"]  # indexed atomically with the claim

    assert await repo.create(_rec("a", status=JobStatus.RUNNING)) is False  # live record owns it
    await repo.update("a", status=JobStatus.FAILED.value)
    assert await repo.create(_rec("a", target="host-2")) is True  # terminal -> reclaim
    assert (await repo.get("a")).target == "host-2"


@pytest.mark.asyncio
async def test_redis_update_cas_guards_status(redis_repo):
    repo, fake = redis_repo
    await repo.create(_rec("a"))
    # CAS win: record still pending.
    assert (
        await repo.update("a", expected_status=JobStatus.PENDING, status=JobStatus.CANCELLED.value)
    ) is not None
    # CAS lose: status moved on; nothing written.
    lost = await repo.update("a", expected_status=JobStatus.PENDING, status=JobStatus.FAILED.value)
    assert lost is None
    assert (await repo.get("a")).status is JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_redis_list_pages_and_drops_stale_ids(redis_repo):
    repo, fake = redis_repo
    for i in range(5):
        rec = _rec(f"j{i}")
        rec.created_at = rec.created_at.replace(microsecond=i)
        await repo.create(rec)

    page = await repo.list(limit=2, offset=1)  # newest-first slice
    assert [r.job_id for r in page] == ["j3", "j2"]

    del fake.kv[repo._rec_key("j4")]  # record expired; index entry now stale
    listed = await repo.list(target="host-1")  # filtered path scans everything
    assert {r.job_id for r in listed} == {"j0", "j1", "j2", "j3"}
    assert "j4" not in fake.z[repo._index]  # stale id pruned from the index
