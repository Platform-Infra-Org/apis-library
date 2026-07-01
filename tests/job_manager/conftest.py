"""Test setup: a Dramatiq StubBroker (set before any actor import) + fakes.

Setting the stub broker at import time and pinning ``broker._broker`` makes
``setup_broker()`` a no-op, so the ``run_job`` actor registers on the stub and
``.send()`` / ``abort()`` work in-memory with no Redis.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

import dramatiq
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import CurrentMessage
from dramatiq_abort import Abortable
from dramatiq_abort.backends import StubBackend

_stub = StubBroker()
_stub.add_middleware(CurrentMessage())
_stub.add_middleware(Abortable(backend=StubBackend()))
_stub.emit_after("process_boot")
dramatiq.set_broker(_stub)

import tashtiot_apis_library.job_manager.broker as _broker_mod  # noqa: E402

_broker_mod._broker = _stub

import pytest  # noqa: E402

from tashtiot_apis_library.job_manager.repository import InMemoryJobRepository  # noqa: E402


@pytest.fixture
def repo() -> InMemoryJobRepository:
    return InMemoryJobRepository()


@pytest.fixture
def stub_broker() -> StubBroker:
    yield _stub
    _stub.flush_all()


class FakeExecutor:
    """Yields canned chunks, or raises to simulate a failed operation."""

    def __init__(
        self, chunks: Optional[List[str]] = None, raises: Optional[Exception] = None
    ) -> None:
        self.chunks = chunks if chunks is not None else ["line-1", "line-2"]
        self.raises = raises

    async def run(self, operation: str, params: Dict[str, Any]) -> AsyncIterator[str]:
        if self.raises is not None:
            raise self.raises
        for chunk in self.chunks:
            yield chunk


class FakeLock:
    def __init__(self, acquirable: bool) -> None:
        self.acquirable = acquirable
        self.released = False

    async def acquire(self) -> bool:
        return self.acquirable

    async def release(self) -> None:
        self.released = True


class FakeRedis:
    """Minimal stand-in for the per-target lock's redis client."""

    def __init__(self, acquirable: bool = True) -> None:
        self.acquirable = acquirable
        self.last_lock: Optional[FakeLock] = None

    def lock(self, name: str, **_: Any) -> FakeLock:
        self.last_lock = FakeLock(self.acquirable)
        return self.last_lock
