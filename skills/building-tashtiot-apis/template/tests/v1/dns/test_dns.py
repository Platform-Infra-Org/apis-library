import pytest
from app.v1.dns.conf import config

from tashtiot_apis_library import AWX, AWXError

URL = f"{config.API_PREFIX}/"


# --- contract ---------------------------------------------------------------------------------
def test_create_returns_202_with_job_id(client, auth_headers, body, awx_calls):
    r = client.post(URL, json=body, headers=auth_headers)
    assert r.status_code == 202
    assert r.json()["job_id"] == 42
    # Remote Config is off in tests -> the static template id is used.
    assert awx_calls[0]["job_template_id"] == config.AWX_CREATE_DNS_TEMPLATE_ID
    assert awx_calls[0]["extra_vars"]["RECORD_ADDRESS"] == "10.0.0.15"


def test_project_only_metadata_is_accepted(client, auth_headers, body):
    body["metadata"] = {"project": "payments"}
    assert client.post(URL, json=body, headers=auth_headers).status_code == 202


def test_unknown_metadata_keys_are_ignored(client, auth_headers, body):
    body["metadata"]["something_new"] = "x"
    assert client.post(URL, json=body, headers=auth_headers).status_code == 202


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["metadata"].pop("project"),  # project is required
        lambda b: b.pop("metadata"),  # metadata is required
        lambda b: b["spec"].update(ip="not-an-ip"),
        lambda b: b["spec"].update(record_name="way-too-long-record-name"),
    ],
)
def test_invalid_body_is_422(client, auth_headers, body, mutate, awx_calls):
    mutate(body)
    assert client.post(URL, json=body, headers=auth_headers).status_code == 422
    assert awx_calls == []  # nothing reached AWX


# --- auth -------------------------------------------------------------------------------------
def test_missing_token_is_401(client, body):
    assert client.post(URL, json=body).status_code == 401


def test_bad_token_is_401(client, body):
    assert client.post(URL, json=body, headers={"Authorization": "Bearer junk"}).status_code == 401


# --- upstream failures -------------------------------------------------------------------------
def test_awx_failure_is_502(client, auth_headers, body, monkeypatch):
    async def failing_launch(self, **kwargs):
        raise AWXError(status_code=403, detail="forbidden")

    monkeypatch.setattr(AWX, "launch_job", failing_launch)
    r = client.post(URL, json=body, headers=auth_headers)
    assert r.status_code == 502
    assert r.json() == {"detail": "AWX: forbidden"}


# --- status (AWX is the job queue) -------------------------------------------------------------
def test_status_is_http_200_with_job_state_in_body(client, auth_headers):
    r = client.get(f"{config.API_PREFIX}/status/42", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    assert r.json()["status_code"] == 202  # the job's state, not the HTTP status


def test_unknown_job_is_404(client, auth_headers, monkeypatch):
    async def missing(self, job_id, *, include_logs=False):
        raise AWXError(status_code=404, detail="not found")

    monkeypatch.setattr(AWX, "get_job_status", missing)
    assert client.get(f"{config.API_PREFIX}/status/7", headers=auth_headers).status_code == 404
