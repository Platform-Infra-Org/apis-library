"""Photo-derived Linux API functions -> real library -> mocked AWX HTTP.

A minimal FastAPI route additionally verifies JSON and transport status. These
routes are a test harness, not a reconstruction of the private API's router.
"""

import importlib.util
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tashtiot_apis_library import AWX
from tashtiot_apis_library.connectors.awx.models import AWXOperationResponse
from tashtiot_apis_library.connectors.errors import AWXError

MODULE_PATH = Path(__file__).resolve().parents[2] / "examples/linux_api/operation_linux.py"
spec = importlib.util.spec_from_file_location("example_operation_linux", MODULE_PATH)
operation_linux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operation_linux)
BASE = "https://awx.test"
RAW = """PLAY [Configure Linux]
TASK [Install agent]
fatal: [server-01]: FAILED! => {"msg": "Package unavailable", "invocation": {"password": "not-for-display"}}
PLAY RECAP ************************************************************
server-01 : ok=3 changed=1 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
"""


@pytest_asyncio.fixture
async def awx():
    instance = AWX(BASE, "test-token")
    try:
        yield instance
    finally:
        await instance.client.api.aclose()


def mock_workflow(state):
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(
        200, json={"id": 500, "name": "New machine", "status": state}
    )
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/workflow_nodes/").respond(
        200,
        json={
            "next": None,
            "results": [
                {
                    "id": 1,
                    "job": 501,
                    "summary_fields": {
                        "job": {
                            "name": "Create VM",
                            "status": "successful",
                            "type": "job",
                        }
                    },
                },
                {
                    "id": 2,
                    "job": 502,
                    "summary_fields": {
                        "job": {
                            "name": "Configure Linux",
                            "status": state,
                            "type": "job",
                        }
                    },
                },
            ],
        },
    )
    respx.get(f"{BASE}/api/v2/jobs/502/stdout/").respond(200, text=RAW)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,code",
    [
        ("pending", 202),
        ("waiting", 202),
        ("running", 202),
        ("successful", 200),
        ("failed", 500),
        ("error", 500),
        ("canceled", 500),
    ],
)
@respx.mock
async def test_machine_status_preserves_existing_contract_through_http(awx, state, code):
    mock_workflow(state)
    original = await awx.get_workflow_job_status(500)
    app = FastAPI()

    @app.get("/machine/status/{workflow_job_id}", response_model=AWXOperationResponse)
    async def status(workflow_job_id: int):
        result = await operation_linux.get_machine_status(awx, workflow_job_id)
        return JSONResponse(status_code=result.status_code, content=result.model_dump(mode="json"))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://linux-api"
    ) as client:
        response = await client.get("/machine/status/500")
    assert response.status_code == code
    body = response.json()
    assert body.keys() == original.model_dump().keys()
    assert {key: value for key, value in body.items() if key != "stdout"} == original.model_dump(
        exclude={"stdout"}
    )
    assert "[✓] Create VM: successful" in body["stdout"]
    assert f"Configure Linux: {state}" in body["stdout"]
    if state in {"failed", "error", "canceled"}:
        # Even HTTP 500 retains the real playbook failure in the response body.
        assert "Package unavailable" in body["stdout"]
        assert "not-for-display" not in body["stdout"]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["successful", "failed"])
@respx.mock
async def test_ssh_status_uses_the_same_library_and_retains_response(awx, state):
    respx.get(f"{BASE}/api/v2/jobs/42/").respond(
        200, json={"id": 42, "name": "Configure SSH keys", "status": state}
    )
    respx.get(f"{BASE}/api/v2/jobs/42/stdout/").respond(200, text=RAW)
    original = await awx.get_job_status(42)
    result = await operation_linux.get_ssh_keys_job_status(awx, 42)
    assert isinstance(result, AWXOperationResponse)
    assert result.model_dump(exclude={"stdout"}) == original.model_dump(exclude={"stdout"})
    assert "Configure SSH keys" in result.stdout
    assert "PLAY RECAP" in result.stdout
    if state == "failed":
        assert "Package unavailable" in result.stdout


@pytest.mark.asyncio
@respx.mock
async def test_log_failure_does_not_change_existing_operation_result(awx):
    mock_workflow("successful")
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/workflow_nodes/").respond(
        403, json={"detail": "Forbidden"}
    )
    result = await operation_linux.get_machine_status(awx, 500)
    assert result.status == "successful" and result.status_code == 200
    assert "unavailable" in result.stdout


@pytest.mark.asyncio
@respx.mock
async def test_primary_status_errors_still_propagate_from_operation(awx):
    respx.get(f"{BASE}/api/v2/workflow_jobs/500/").respond(403, json={"detail": "Forbidden"})
    with pytest.raises(AWXError) as error:
        await operation_linux.get_machine_status(awx, 500)
    assert error.value.status_code == 403
