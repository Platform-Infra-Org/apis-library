"""Tests for the async AWX service, mocking the HTTP layer with respx."""

import httpx
import pytest
import respx

from tashtiot_apis_library.connectors.awx.service import AWX
from tashtiot_apis_library.connectors.errors import AWXError

BASE_URL = "https://example.com"
TOKEN = "token"


@pytest.fixture
def awx():
    return AWX(BASE_URL, TOKEN)


@pytest.mark.asyncio
@respx.mock
async def test_launch_job(awx):
    route = respx.post(f"{BASE_URL}/api/v2/job_templates/1/launch/").mock(
        return_value=httpx.Response(
            200, json={"id": 123, "name": "demo", "status": "successful", "result_stdout": "done"}
        )
    )
    response = await awx.launch_job(1, {"key": "value"})

    assert route.called
    assert response.status == "successful"
    assert response.status_code == 200
    assert response.job_id == 123
    assert response.stdout == "done"


@pytest.mark.asyncio
@respx.mock
async def test_launch_job_failure_raises(awx):
    respx.post(f"{BASE_URL}/api/v2/job_templates/1/launch/").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    with pytest.raises(AWXError) as exc:
        await awx.launch_job(1, {"key": "value"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_get_job_status(awx):
    respx.get(f"{BASE_URL}/api/v2/jobs/1/").mock(
        return_value=httpx.Response(
            200, json={"id": 1, "name": "demo", "status": "successful", "result_stdout": "log"}
        )
    )
    response = await awx.get_job_status(1)

    assert response.status == "successful"
    assert response.status_code == 200
    assert response.job_id == 1
    assert response.stdout == "log"


@pytest.mark.asyncio
@respx.mock
async def test_get_job_status_failure_raises(awx):
    respx.get(f"{BASE_URL}/api/v2/jobs/1/").mock(
        return_value=httpx.Response(404, json={"detail": "missing"})
    )
    with pytest.raises(AWXError) as exc:
        await awx.get_job_status(1)
    assert exc.value.status_code == 404
