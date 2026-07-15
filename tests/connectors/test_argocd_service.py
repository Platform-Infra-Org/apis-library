"""Tests for the high-level ArgoCD service wrapper's create_app/delete_app."""

import httpx
import pytest
import respx

from tashtiot_apis_library.connectors.argocd.service import ArgoCD

BASE_URL = "https://example.com"
API_KEY = "token"
APP_NAME = "consumer-app"


@pytest.fixture
def argocd():
    return ArgoCD(BASE_URL, API_KEY, application_set_timeout=5)


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
async def test_create_app_delegates_to_client(argocd):
    route = respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(200, json=APP_MANIFEST)
    )

    result = await argocd.create_app(APP_MANIFEST, validate=False)

    assert route.called
    assert result.metadata["name"] == APP_NAME


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_delegates_to_client(argocd):
    route = respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(200, json={})
    )

    await argocd.delete_app(APP_NAME, app_namespace="argocd")

    assert route.called
    assert route.calls.last.request.url.params["appNamespace"] == "argocd"
