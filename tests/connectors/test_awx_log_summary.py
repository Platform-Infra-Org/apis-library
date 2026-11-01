"""Status summaries modeled after the Linux API examples."""

import httpx
import pytest
import respx

from tashtiot_apis_library import AWX
from tashtiot_apis_library.connectors.awx._log_summary import filter_ansible_logs

BASE = "https://awx.test"
RAW = """\x1b[31mPLAY [Linux setup]\x1b[0m
TASK [Install monitoring]
fatal: [server-01]: FAILED! => {"msg": "Package not found", "invocation": {"password": "hidden-body"}}
PLAY RECAP *********************************************************************
server-01 : ok=3 changed=1 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
"""


def node(node_id, job_id, name, status, kind="job"):
    return {
        "id": node_id,
        "job": job_id,
        "summary_fields": {"job": {"name": name, "status": status, "type": kind}},
    }


@pytest.mark.asyncio
@respx.mock
async def test_job_summary_preserves_response_and_hides_verbose_body():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(
        200, json={"id": 42, "name": "Install Linux", "status": "failed"}
    )
    stdout = respx.get(f"{BASE}/api/v2/jobs/42/stdout/").respond(200, text=RAW)
    result = await awx.get_job_status(42, include_logs=True)
    assert result.stdout.startswith("[✗] Install Linux: failed")
    assert "Package not found" in result.stdout
    assert "hidden-body" not in result.stdout
    assert stdout.calls.last.request.url.params["format"] == "txt"
    assert result.model_dump().keys() == {
        "status",
        "status_code",
        "return_code",
        "stdout",
        "job_id",
    }
    original = await awx.get_job_status(42)
    assert original.stdout == "" and result.status_code == original.status_code
    assert stdout.call_count == 1
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_workflow_pagination_child_failures_and_nested_workflow():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(
        200, json={"id": 500, "name": "Machine", "status": "failed"}
    )

    def pages(request):
        if request.url.params["page"] == "1":
            return httpx.Response(
                200,
                json={
                    "next": "https://untrusted.test/page2",
                    "results": [
                        node(1, 501, "Create VM", "successful"),
                        node(2, 502, "Sync project", "successful", "project_update"),
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "next": None,
                "results": [
                    node(3, 503, "Linux setup", "failed"),
                    node(4, 504, "Nested", "running", "workflow_job"),
                    {"id": 5, "job": None},
                ],
            },
        )

    respx.get(f"{BASE}/api/v2/workflow_jobs/500/workflow_nodes/").mock(side_effect=pages)
    respx.get(f"{BASE}/api/v2/workflow_jobs/504/workflow_nodes/").respond(
        200, json={"results": [node(6, 505, "Monitoring", "running")], "next": None}
    )
    failed_stdout = respx.get(f"{BASE}/api/v2/jobs/503/stdout/").respond(200, text=RAW)
    result = await awx.get_workflow_job_status(500, include_logs=True)
    assert "[✓] Create VM: successful" in result.stdout
    assert "[✗] Linux setup: failed" in result.stdout
    assert "Package not found" in result.stdout
    assert "[…] Monitoring: running" in result.stdout
    assert "Sync project" not in result.stdout
    assert failed_stdout.call_count == 1
    assert result.status == "failed"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_optional_log_failure_does_not_replace_job_status():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(
        200, json={"id": 42, "name": "Install Linux", "status": "failed"}
    )
    respx.get(f"{BASE}/api/v2/jobs/42/stdout/").respond(403, json={"detail": "Forbidden"})
    result = await awx.get_job_status(42, include_logs=True)
    assert result.status == "failed" and "output unavailable" in result.stdout
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_success_only_includes_recap_and_running_has_neutral_icon():
    awx = AWX(BASE, "secret")
    status = respx.get(f"{BASE}/api/v2/jobs/42/")
    status.respond(200, json={"id": 42, "name": "Linux", "status": "successful"})
    respx.get(f"{BASE}/api/v2/jobs/42/stdout/").respond(200, text=RAW)
    result = await awx.get_job_status(42, include_logs=True)
    assert "PLAY RECAP" in result.stdout and "TASK" not in result.stdout
    status.respond(200, json={"id": 42, "name": "Linux", "status": "running"})
    assert (await awx.get_job_status(42, include_logs=True)).stdout == "[…] Linux: running"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_nested_cycle_is_bounded():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(
        200, json={"id": 500, "name": "Machine", "status": "running"}
    )
    route = respx.get(f"{BASE}/api/v2/workflow_jobs/500/workflow_nodes/").respond(
        200, json={"results": [node(1, 500, "Cycle", "running", "workflow_job")]}
    )
    result = await awx.get_workflow_job_status(500, include_logs=True)
    assert "limit reached" in result.stdout and route.call_count == 1
    await awx.client.api.aclose()


def test_filter_recovers_after_structured_blocks_and_is_bounded():
    raw = """TASK [First]
{
  "password": "hidden-body"
}
TASK [Second]
ok: [server-01] => {"msg": "ready", "data": "hidden-body"}
"""
    text = filter_ansible_logs(raw)
    assert "TASK [Second]" in text and "ready" in text and "hidden-body" not in text
    assert "\x1b" not in filter_ansible_logs(RAW)
    text = filter_ansible_logs("\n".join(f"TASK [{i}] " + "x" * 500 for i in range(200)))
    assert len(text) <= 10_000 and "truncated" in text
    assert "TASK [199]" in text and "TASK [0]" not in text


@pytest.mark.asyncio
@respx.mock
async def test_workflow_log_error_is_visible_without_changing_primary_status():
    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(
        200, json={"id": 500, "name": "Machine", "status": "successful"}
    )
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/workflow_nodes/").respond(502, text="Bad gateway")
    result = await awx.get_workflow_job_status(500, include_logs=True)
    assert result.status == "successful" and result.status_code == 200
    assert result.stdout == "[AWX workflow nodes unavailable]"
    await awx.client.api.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_primary_status_error_still_raises():
    from tashtiot_apis_library.connectors.errors import AWXError

    awx = AWX(BASE, "secret")
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(403, json={"detail": "Forbidden"})
    with pytest.raises(AWXError):
        await awx.get_workflow_job_status(500, include_logs=True)
    await awx.client.api.aclose()
