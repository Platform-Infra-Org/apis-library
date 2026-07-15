"""Tests for ArgoCD Application lifecycle (create/delete), mocking HTTP with respx."""

import httpx
import pytest
import respx

from tashtiot_apis_library.connectors.argocd.client import ArgoCDClient
from tashtiot_apis_library.connectors.errors import ArgoCDError

BASE_URL = "https://example.com"
API_KEY = "token"
APP_NAME = "consumer-app"


@pytest.fixture
def client():
    return ArgoCDClient(BASE_URL, API_KEY)


APP_MANIFEST = {
    "metadata": {"name": APP_NAME, "namespace": "argocd"},
    "spec": {
        "project": "default",
        "source": {
            "repoURL": "https://example.com/repo.git",
            "targetRevision": "HEAD",
            "path": ".",
        },
        "destination": {"server": "https://kubernetes.default.svc", "namespace": "default"},
    },
}


@pytest.mark.asyncio
@respx.mock
async def test_create_app_posts_manifest_to_applications_endpoint(client):
    route = respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(200, json=APP_MANIFEST)
    )

    result = await client.create_app(APP_MANIFEST, validate=False)

    assert route.called
    request = route.calls.last.request
    assert request.url.params["validate"] == "false"
    assert result.metadata["name"] == APP_NAME


@pytest.mark.asyncio
@respx.mock
async def test_create_app_defaults_validate_true(client):
    route = respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(200, json=APP_MANIFEST)
    )

    await client.create_app(APP_MANIFEST)

    assert route.calls.last.request.url.params["validate"] == "true"


@pytest.mark.asyncio
@respx.mock
async def test_create_app_raises_on_error(client):
    respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(400, json={"message": "invalid spec"})
    )

    with pytest.raises(ArgoCDError) as exc_info:
        await client.create_app(APP_MANIFEST, validate=False)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_calls_delete_with_cascade_and_namespace(client):
    route = respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(200, json={})
    )

    await client.delete_app(APP_NAME, app_namespace="argocd", cascade=False)

    assert route.called
    params = route.calls.last.request.url.params
    assert params["cascade"] == "false"
    assert params["appNamespace"] == "argocd"


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_omits_namespace_when_not_given(client):
    route = respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(200, json={})
    )

    await client.delete_app(APP_NAME)

    params = route.calls.last.request.url.params
    assert "appNamespace" not in params
    assert params["cascade"] == "true"


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_raises_on_error(client):
    respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(403, json={"message": "forbidden"})
    )

    with pytest.raises(ArgoCDError) as exc_info:
        await client.delete_app(APP_NAME)

    assert exc_info.value.status_code == 403
