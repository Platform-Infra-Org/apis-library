"""Tests for the high-level ArgoCD service wrapper's create_app/delete_app."""

from unittest.mock import AsyncMock

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


@pytest.mark.asyncio
@respx.mock
async def test_create_app_does_not_wait_by_default(argocd, monkeypatch):
    respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(200, json=APP_MANIFEST)
    )
    waiter = AsyncMock()
    monkeypatch.setattr(argocd, "wait_for_app_creation", waiter)

    await argocd.create_app(APP_MANIFEST, validate=False)

    waiter.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_create_app_waits_when_requested(argocd, monkeypatch):
    respx.post(f"{BASE_URL}/api/v1/applications").mock(
        return_value=httpx.Response(200, json=APP_MANIFEST)
    )
    waiter = AsyncMock()
    monkeypatch.setattr(argocd, "wait_for_app_creation", waiter)

    await argocd.create_app(APP_MANIFEST, validate=False, wait=True)

    waiter.assert_awaited_once_with(APP_NAME)


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_does_not_wait_by_default(argocd, monkeypatch):
    respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(200, json={})
    )
    waiter = AsyncMock()
    monkeypatch.setattr(argocd, "wait_for_app_deletion", waiter)

    await argocd.delete_app(APP_NAME)

    waiter.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_delete_app_waits_when_requested(argocd, monkeypatch):
    respx.delete(f"{BASE_URL}/api/v1/applications/{APP_NAME}").mock(
        return_value=httpx.Response(200, json={})
    )
    waiter = AsyncMock()
    monkeypatch.setattr(argocd, "wait_for_app_deletion", waiter)

    await argocd.delete_app(APP_NAME, wait=True)

    waiter.assert_awaited_once_with(APP_NAME)
