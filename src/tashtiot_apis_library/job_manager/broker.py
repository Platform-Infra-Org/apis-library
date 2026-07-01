"""Dramatiq broker + abort middleware setup, and the Redis clients the job manager uses.

Imports ``dramatiq``/``redis`` lazily so the package stays importable without the
``[job-manager]`` extra. ``setup_broker`` is idempotent and must run on both the
API side (so ``send``/``abort`` work) and the worker side.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from ..fastapi_template.utils import settings

__all__ = ["setup_broker", "create_async_redis"]

_broker: Any = None


def setup_broker(url: Optional[str] = None) -> Any:
    """Create the Redis broker + ``Abortable`` middleware and set it globally (once)."""
    global _broker
    if _broker is not None:
        return _broker

    import dramatiq
    import redis
    from dramatiq.brokers.redis import RedisBroker
    from dramatiq.middleware.asyncio import AsyncIO
    from dramatiq_abort import Abortable
    from dramatiq_abort.backends import RedisBackend as AbortRedisBackend

    url = url or settings.REDIS_URL
    broker = RedisBroker(url=url)
    broker.add_middleware(AsyncIO())  # required to run async actors
    broker.add_middleware(
        Abortable(
            backend=AbortRedisBackend(client=redis.from_url(url)), abort_ttl=settings.JM_ABORT_TTL
        )
    )
    dramatiq.set_broker(broker)
    _broker = broker
    return broker


@lru_cache(maxsize=1)
def create_async_redis() -> Any:
    """Async Redis client for the record store and the per-target lock."""
    import redis.asyncio as aioredis

    return aioredis.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )
