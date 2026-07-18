"""Tests for GitClient's file-content fetch and ssh_host construction, mocking the HTTP layer with respx."""

import base64

import httpx
import pytest
import respx

from tashtiot_apis_library.connectors.errors import GitError
from tashtiot_apis_library.connectors.git.client import GitClient

BASE_URL = "https://example.com"
PROJECT_KEY = "PROJ"
REPO_SLUG = "repo"
PATH = "consumers/acme/config.yaml"

SSH_BASE_URL = "https://bitbucket.example.com/rest/api/1.0"


@pytest.fixture
def client():
    return GitClient(
        base_url=BASE_URL,
        username_or_email="svc",
        token="token",
        project_key=PROJECT_KEY,
        repo_slug=REPO_SLUG,
        default_ref="master",
        ssh_key_file_path="/etc/.ssh/private_key",
    )


def _client(**kwargs) -> GitClient:
    return GitClient(
        base_url=SSH_BASE_URL,
        username_or_email="svc-account",
        token="token",
        project_key="PROJECT",
        repo_slug="repo",
        **kwargs,
    )


@pytest.mark.asyncio
@respx.mock
async def test_get_file_fetches_content_from_dedicated_raw_endpoint(client):
    browse_route = respx.get(
        f"{BASE_URL}/projects/{PROJECT_KEY}/repos/{REPO_SLUG}/browse/{PATH}"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "path": {
                    "toString": PATH,
                    "components": PATH.split("/"),
                    "name": "config.yaml",
                }
            },
        )
    )
    raw_route = respx.get(f"{BASE_URL}/projects/{PROJECT_KEY}/repos/{REPO_SLUG}/raw/{PATH}").mock(
        return_value=httpx.Response(200, content=b"name: acme\n")
    )

    result = await client.get_file(PATH, ref="master")

    assert browse_route.called
    assert raw_route.called
    # Bitbucket Server's `browse` endpoint doesn't support `raw=1` with
    # octet-stream content negotiation. Returns 406 for non-JSON Accept header.
    # Must use dedicated `raw` endpoint instead.
    assert "raw=1" not in str(browse_route.calls.last.request.url)
    assert base64.b64decode(result.content) == b"name: acme\n"


@pytest.mark.asyncio
@respx.mock
async def test_get_file_raises_on_raw_endpoint_error(client):
    respx.get(f"{BASE_URL}/projects/{PROJECT_KEY}/repos/{REPO_SLUG}/browse/{PATH}").mock(
        return_value=httpx.Response(200, json={"path": {"toString": PATH}})
    )
    respx.get(f"{BASE_URL}/projects/{PROJECT_KEY}/repos/{REPO_SLUG}/raw/{PATH}").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )

    with pytest.raises(GitError) as exc_info:
        await client.get_file(PATH, ref="master")

    assert exc_info.value.status_code == 404


def test_ssh_host_defaults_to_port_7995():
    client = _client()
    assert client.ssh_host == "bitbucket.example.com:7995"


def test_ssh_host_honours_ssh_port_override():
    client = _client(ssh_port=7999)
    assert client.ssh_host == "bitbucket.example.com:7999"
