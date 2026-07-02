"""Router against a real JobManager wired with the in-memory repo + stub broker."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tashtiot_apis_library.job_manager.models import JobStatus
from tashtiot_apis_library.job_manager.repository import InMemoryJobRepository
from tashtiot_apis_library.job_manager.service import JobManager
from tashtiot_apis_library.job_manager.wiring import enable_job_manager


@pytest.fixture
def client(stub_broker):
    repo = InMemoryJobRepository()
    manager = JobManager(repo)
    app = FastAPI()
    enable_job_manager(app, manager=manager)
    return TestClient(app), repo


def test_create_returns_202_with_location(client):
    c, repo = client
    resp = c.post("/jobs", json={"target": "host-1", "operation": "drain_node", "params": {}})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert resp.headers["Location"].endswith(f"/jobs/{body['job_id']}")


def test_status_record_and_logs(client):
    import asyncio

    c, repo = client
    job_id = c.post("/jobs", json={"target": "host-1", "operation": "op", "params": {}}).json()[
        "job_id"
    ]
    # Simulate the worker progressing the job (repo is loop-agnostic).
    asyncio.run(repo.update(job_id, status=JobStatus.SUCCEEDED.value, result="hello"))

    assert c.get(f"/jobs/{job_id}/status").json() == {"status": "succeeded"}
    assert c.get(f"/jobs/{job_id}").json()["target"] == "host-1"
    assert c.get(f"/jobs/{job_id}/logs").text == "hello"


def test_unknown_404(client):
    c, _ = client
    assert c.get("/jobs/missing").status_code == 404


def test_cancel_accepts(client):
    c, _ = client
    job_id = c.post("/jobs", json={"target": "host-1", "operation": "op", "params": {}}).json()[
        "job_id"
    ]
    assert c.post(f"/jobs/{job_id}/cancel").status_code == 202


def test_list_jobs_filters_to_summary_fields(client):
    import asyncio

    c, repo = client
    ids = [
        c.post("/jobs", json={"target": t, "operation": "op", "params": {"p": 1}}).json()["job_id"]
        for t in ("host-1", "host-1", "host-2")
    ]
    asyncio.run(repo.update(ids[0], status=JobStatus.SUCCEEDED.value, result="secret"))

    rows = c.get("/jobs").json()
    assert {r["job_id"] for r in rows} == set(ids)
    # response_model filters JobRecord down to JobSummary rows.
    assert set(rows[0]) == {"job_id", "target", "operation", "status", "created_at"}

    assert {r["job_id"] for r in c.get("/jobs", params={"target": "host-2"}).json()} == {ids[2]}
    succeeded = c.get("/jobs", params={"status": "succeeded"}).json()
    assert [r["job_id"] for r in succeeded] == [ids[0]]
    assert len(c.get("/jobs", params={"limit": 1}).json()) == 1
