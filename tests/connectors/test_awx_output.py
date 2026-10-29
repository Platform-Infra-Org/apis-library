"""Incremental output contract, using AWX HTTP responses without a real AWX."""

import pytest
import respx

from tashtiot_apis_library import AWX
from tashtiot_apis_library.connectors.errors import AWXError

BASE = "https://awx.test"


def job(status="running", processed=False):
    return {"id": 42, "name": "linux", "status": status, "event_processing_finished": processed}


def event(start, end, text):
    return {"id": end + 1, "start_line": start, "end_line": end, "stdout": text}


@pytest.mark.asyncio
@respx.mock
async def test_incremental_output_and_final_drain():
    awx = AWX(BASE, "secret")
    status = respx.get(f"{BASE}/api/v2/jobs/42/")
    events = respx.get(f"{BASE}/api/v2/jobs/42/job_events/")
    status.respond(200, json=job())
    events.respond(200, json={"results": [event(0, 1, "TASK [packages]")], "next": None})
    first = await awx.get_job_output(42)
    assert first.stdout == "TASK [packages]"
    assert first.next_line == 1
    assert not first.finished
    # A terminal status alone does not mean the output is fully available.
    status.respond(200, json=job("successful"))
    events.respond(200, json={"results": [], "next": None})
    assert not (await awx.get_job_output(42, start_line=1)).finished
    status.respond(200, json=job("successful", True))
    events.respond(200, json={"results": [event(1, 2, "PLAY RECAP")], "next": "/next"})
    second = await awx.get_job_output(42, start_line=1)
    assert second.stdout == "PLAY RECAP"
    assert second.has_more and not second.finished
    assert events.calls.last.request.url.params["start_line__gte"] == "1"
    events.respond(200, json={"results": [], "next": None})
    final = await awx.get_job_output(42, start_line=second.next_line)
    assert final.finished and final.stdout == "" and final.next_line == 2
    await awx.client.api.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["failed", "error", "canceled"])
@respx.mock
async def test_terminal_failure_keeps_output(state):
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(200, json=job(state, True))
    respx.get(f"{BASE}/api/v2/jobs/42/job_events/").respond(
        200, json={"results": [event(0, 1, "fatal: failure")], "next": None}
    )
    result = await awx.get_job_output(42)
    assert result.finished and result.status == state
    assert result.stdout == "fatal: failure"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_gap_does_not_skip_late_output():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(200, json=job("successful", True))
    respx.get(f"{BASE}/api/v2/jobs/42/job_events/").respond(
        200, json={"results": [event(0, 1, "first"), event(2, 3, "late")], "next": None}
    )
    result = await awx.get_job_output(42)
    assert result.next_line == 1 and result.stdout == "first"
    assert result.has_more and not result.finished
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_output_http_error():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(200, json=job())
    respx.get(f"{BASE}/api/v2/jobs/42/job_events/").respond(502, text="Bad gateway")
    with pytest.raises(AWXError) as exc:
        await awx.get_job_output(42)
    assert exc.value.status_code == 502
    await awx.client.api.aclose()


@pytest.mark.asyncio
async def test_invalid_cursor():
    awx = AWX(BASE, "secret")
    with pytest.raises(ValueError):
        await awx.get_job_output(42, start_line=-1)
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_empty_events_cannot_block_cursor_and_query_is_bounded():
    import httpx

    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(200, json=job())

    def respond(request):
        params = request.url.params
        assert params["start_line__gte"] == "0"
        assert params["end_line__gt"] == "0"
        assert params["page_size"] == "1"
        assert params["order_by"] == "start_line,id"
        assert params["no_truncate"] == "true"
        # AWX filters out zero-line events before pagination.
        return httpx.Response(200, json={"results": [event(0, 1, "output")], "next": None})

    respx.get(f"{BASE}/api/v2/jobs/42/job_events/").mock(side_effect=respond)
    result = await awx.get_job_output(42, page_size=1)
    assert result.next_line == 1 and result.stdout == "output"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_missing_processing_metadata_does_not_claim_finished():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(
        200, json={"id": 42, "name": "linux", "status": "successful"}
    )
    respx.get(f"{BASE}/api/v2/jobs/42/job_events/").respond(200, json={"results": [], "next": None})
    assert not (await awx.get_job_output(42)).finished
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_late_gap_is_filled_on_next_poll():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(200, json=job())
    route = respx.get(f"{BASE}/api/v2/jobs/42/job_events/")
    route.respond(200, json={"results": [event(1, 2, "second")], "next": None})
    first = await awx.get_job_output(42)
    assert first.next_line == 0 and first.stdout == ""
    route.respond(
        200, json={"results": [event(0, 1, "first"), event(1, 2, "second")], "next": None}
    )
    second = await awx.get_job_output(42, start_line=first.next_line)
    assert second.next_line == 2 and second.stdout == "first\nsecond"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("page_size", [0, 1001])
async def test_invalid_page_size(page_size):
    awx = AWX(BASE, "secret")
    with pytest.raises(ValueError):
        await awx.get_job_output(42, page_size=page_size)
    await awx.client.api.aclose()
