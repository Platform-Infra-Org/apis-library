"""Per-target distributed mutex over ``redis.asyncio``'s native ``Lock``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from .exceptions import TargetLockTimeout

__all__ = ["target_lock"]


@asynccontextmanager
async def target_lock(
    redis: Any,
    target: str,
    *,
    timeout: float = 600.0,
    blocking_timeout: float = 30.0,
    key_prefix: str = "jm",
) -> AsyncIterator[None]:
    """Hold the per-target lock for the duration of the ``with`` block.

    ``timeout`` is the lock's auto-expiry (a crashed holder can't wedge the
    target forever); ``blocking_timeout`` is how long we wait to acquire before
    raising :class:`TargetLockTimeout`.
    """
    lock = redis.lock(
        f"{key_prefix}:lock:{target}", timeout=timeout, blocking_timeout=blocking_timeout
    )
    acquired = await lock.acquire()
    if not acquired:
        raise TargetLockTimeout(target)
    try:
        yield
    finally:
        # Lock may have already expired (long op) -> release can raise; ignore.
        try:
            await lock.release()
        except Exception:  # noqa: BLE001 - best-effort release
            pass
