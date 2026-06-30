"""Job record store -- the sole source of truth for status/result/history.

Dramatiq is fire-and-forget (no status), so the actor writes every transition
here and the routes read only from here. Redis-backed by default (TTL'd,
ephemeral); an in-memory impl backs the tests. A durable store can be dropped in
behind the same Protocol without touching the routes.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable

from .models import JobRecord, JobStatus

__all__ = ["JobRepository", "RedisJobRepository", "InMemoryJobRepository"]


@runtime_checkable
class JobRepository(Protocol):
    async def save(self, record: JobRecord) -> None: ...

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

    ponytail: ``list`` scans the index and filters target/status in Python -- fine
    at the retained-job volume (bounded by TTL); swap for per-field indexes if it grows.
    """

    def __init__(self, redis: Any, *, record_ttl: int = 86400, key_prefix: str = "jm") -> None:
        self.redis = redis
        self.record_ttl = record_ttl
        self.p = key_prefix

    def _rec_key(self, job_id: str) -> str:
        return f"{self.p}:job:{job_id}"

    @property
    def _index(self) -> str:
        return f"{self.p}:jobs"

    async def save(self, record: JobRecord) -> None:
        await self.redis.set(
            self._rec_key(record.job_id), record.model_dump_json(), ex=self.record_ttl
        )
        await self.redis.zadd(self._index, {record.job_id: record.created_at.timestamp()})
        await self.redis.expire(self._index, self.record_ttl * 2)

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
        job_ids = await self.redis.zrevrange(self._index, 0, -1)
        out: List[JobRecord] = []
        for jid in job_ids:
            jid = jid.decode() if isinstance(jid, bytes) else jid
            record = await self.get(jid)
            if record is None:
                await self.redis.zrem(self._index, jid)  # expired -> drop stale index entry
                continue
            if target is not None and record.target != target:
                continue
            if status is not None and record.status != status:
                continue
            out.append(record)
        return out[offset : offset + limit]


class InMemoryJobRepository:
    """Process-local repo for unit tests (no Redis)."""

    def __init__(self) -> None:
        self._records: dict[str, JobRecord] = {}

    async def save(self, record: JobRecord) -> None:
        self._records[record.job_id] = record.model_copy(deep=True)

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
