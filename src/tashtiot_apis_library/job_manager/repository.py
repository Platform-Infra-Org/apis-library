"""Job record store -- the sole source of truth for status/result/history.

Dramatiq is fire-and-forget (no status), so the actor writes every transition
here and the routes read only from here. Redis-backed by default (TTL'd,
ephemeral); an in-memory impl backs the tests. A durable store can be dropped in
behind the same Protocol without touching the routes.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from .models import JobRecord, JobStatus

__all__ = ["JobRepository", "RedisJobRepository", "InMemoryJobRepository"]

# Atomic claim: set the record iff the key is absent or the prior record is terminal
# (ARGV[3..] are the terminal status values). Returns 1 on claim, 0 if a live one exists.
# cjson is built into Redis's Lua runtime since 2.6, so no server-side modules needed.
_CLAIM_LUA = """
local cur = redis.call('GET', KEYS[1])
if cur then
  local status = cjson.decode(cur)['status']
  local terminal = false
  for i = 3, #ARGV do
    if status == ARGV[i] then terminal = true end
  end
  if not terminal then return 0 end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""

_TERMINAL_VALUES = [
    JobStatus.SUCCEEDED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
]


class JobRepository(Protocol):
    async def save(self, record: JobRecord) -> None: ...

    async def create(self, record: JobRecord) -> bool:
        """Atomic claim: succeeds iff the id is absent OR the existing record is terminal."""
        ...

    async def get(self, job_id: str) -> Optional[JobRecord]: ...

    async def update(self, job_id: str, **fields: Any) -> Optional[JobRecord]: ...

    async def list(
        self,
        *,
        target: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobRecord]: ...


class RedisJobRepository:
    """Records as JSON keys with TTL; a sorted-set index keyed by created time.

    ponytail: ``list`` is a full index scan + one ``mget``, filtered in Python --
    fine at the TTL-bounded volume; swap for per-field indexes if it grows.
    """

    _index = "jm:jobs"

    def __init__(self, redis: Any, *, record_ttl: int = 86400) -> None:
        self.redis = redis
        self.record_ttl = record_ttl

    def _rec_key(self, job_id: str) -> str:
        return f"jm:job:{job_id}"

    async def save(self, record: JobRecord) -> None:
        await self.redis.set(
            self._rec_key(record.job_id), record.model_dump_json(), ex=self.record_ttl
        )
        await self.redis.zadd(self._index, {record.job_id: record.created_at.timestamp()})
        await self.redis.expire(self._index, self.record_ttl * 2)

    async def create(self, record: JobRecord) -> bool:
        """Atomic claim (Lua): win iff the id is absent or the prior record is terminal."""
        won = await self.redis.eval(
            _CLAIM_LUA,
            1,
            self._rec_key(record.job_id),
            record.model_dump_json(),
            self.record_ttl,
            *_TERMINAL_VALUES,
        )
        if won:
            await self.redis.zadd(self._index, {record.job_id: record.created_at.timestamp()})
            await self.redis.expire(self._index, self.record_ttl * 2)
        return bool(won)

    async def get(self, job_id: str) -> Optional[JobRecord]:
        raw = await self.redis.get(self._rec_key(job_id))
        return JobRecord.model_validate_json(raw) if raw is not None else None

    async def update(self, job_id: str, **fields: Any) -> Optional[JobRecord]:
        record = await self.get(job_id)
        if record is None:
            return None
        # Re-validate the merged data so e.g. a status passed as a string coerces
        # back to the JobStatus enum (model_copy(update=) would skip validation).
        updated = JobRecord.model_validate({**record.model_dump(), **fields})
        await self.save(updated)
        return updated

    async def list(
        self,
        *,
        target: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobRecord]:
        # (ids come back as str: the client is created with decode_responses=True)
        if target is None and status is None:
            # No filters: let the index do the paging (a stale id may shorten the page).
            ids = await self.redis.zrevrange(self._index, offset, offset + limit - 1)
            offset = 0  # already applied by the slice
        else:
            # ponytail: filtered listing = full index scan + one mget, bounded by the
            # record TTL; add per-field indexes only if retained volume outgrows it.
            ids = await self.redis.zrevrange(self._index, 0, -1)
        if not ids:
            return []
        raws = await self.redis.mget([self._rec_key(j) for j in ids])
        out: List[JobRecord] = []
        stale: List[str] = []
        for jid, raw in zip(ids, raws, strict=True):
            if raw is None:
                stale.append(jid)
                continue
            record = JobRecord.model_validate_json(raw)
            if target is not None and record.target != target:
                continue
            if status is not None and record.status != status:
                continue
            out.append(record)
        if stale:
            await self.redis.zrem(self._index, *stale)
        return out[offset : offset + limit]


class InMemoryJobRepository:
    """Process-local repo for unit tests (no Redis)."""

    def __init__(self) -> None:
        self._records: dict[str, JobRecord] = {}

    async def save(self, record: JobRecord) -> None:
        self._records[record.job_id] = record.model_copy(deep=True)

    async def create(self, record: JobRecord) -> bool:
        existing = self._records.get(record.job_id)
        if existing is not None and not existing.is_terminal:
            return False  # a live record owns this id
        self._records[record.job_id] = record.model_copy(deep=True)
        return True

    async def get(self, job_id: str) -> Optional[JobRecord]:
        record = self._records.get(job_id)
        return record.model_copy(deep=True) if record else None

    async def update(self, job_id: str, **fields: Any) -> Optional[JobRecord]:
        record = self._records.get(job_id)
        if record is None:
            return None
        updated = JobRecord.model_validate({**record.model_dump(), **fields})
        self._records[job_id] = updated
        return updated.model_copy(deep=True)

    async def list(
        self,
        *,
        target: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobRecord]:
        records = sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)
        if target is not None:
            records = [r for r in records if r.target == target]
        if status is not None:
            records = [r for r in records if r.status == status]
        return [r.model_copy(deep=True) for r in records[offset : offset + limit]]
