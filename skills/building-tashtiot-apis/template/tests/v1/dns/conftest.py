from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from tashtiot_apis_library import AWX
from tashtiot_apis_library.connectors import AWXOperationResponse
from tests.conftest import HS256_SECRET


@pytest.fixture
def awx_calls(monkeypatch):
    """Mock the AWX connector: no network. Records calls; tests can override the fakes."""
    calls = []

    async def fake_launch_job(self, job_template_id, extra_vars=None, **kwargs):
        calls.append({"job_template_id": job_template_id, "extra_vars": extra_vars})
        return AWXOperationResponse(status="successful", status_code=200, job_id=42)

    async def fake_get_job_status(self, job_id, *, include_logs=False):
        return AWXOperationResponse(status="running", status_code=202, job_id=job_id)

    monkeypatch.setattr(AWX, "launch_job", fake_launch_job)
    monkeypatch.setattr(AWX, "get_job_status", fake_get_job_status)
    return calls


@pytest.fixture
def client(awx_calls):
    from app.main import create_app

    return TestClient(create_app())


@pytest.fixture
def auth_headers():
    token = jwt.encode(
        {"sub": "test", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        HS256_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def body():
    return {
        "metadata": {"project": "payments", "environment": "dev"},
        "spec": {"record_name": "api-01", "ip": "10.0.0.15", "dns_zone": "net.com"},
    }
