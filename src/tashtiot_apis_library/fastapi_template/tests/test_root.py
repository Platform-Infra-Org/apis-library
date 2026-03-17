import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from .._internal import general_create_app

# -------------------------- Tests for root endpoint --------------------------
@pytest.mark.rest
@pytest.mark.asyncio
async def test_root_endpoint():
    app = general_create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data == {"message": "Welcome to MyApp!"}

@pytest.mark.asyncio
async def test_root_endpoint_disabled():
    app = general_create_app(
        enable_root_route=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")

    assert response.status_code == 404

# -------------------------- Tests for openapi.json --------------------------
@pytest.mark.asyncio
async def test_openapi_json_enabled():
    app = general_create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data

# -------------------------- Tests for background tasks --------------------------
@pytest.mark.asyncio
async def test_background_tasks_call_task():
    async_task = AsyncMock()

    app = general_create_app(
        async_background_tasks=[async_task]
    )

    with TestClient(app) as client:

        response = client.get("/")
        assert response.status_code == 200

        async_task.assert_awaited_once()

# ------------------------ Tests for swagger UI ----------------------------------

@pytest.mark.asyncio
async def test_swagger_ui_enabled_docs():
    app = general_create_app(
        enable_swagger_routes=True,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text

@pytest.mark.asyncio
async def test_swagger_ui_enabled_redoc():
    app = general_create_app(
        enable_swagger_routes=True,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/redoc")

    assert response.status_code == 200
    assert "ReDoc" in response.text

@pytest.mark.asyncio
async def test_swagger_ui_disabled_docs():
    app = general_create_app(
        enable_swagger_routes=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/docs")

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_swagger_ui_disabled_redoc():
    app = general_create_app(
        enable_swagger_routes=False,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/redoc")

    assert response.status_code == 404

# ------------------------ Test for metrics endpoint -------------------------------
@pytest.mark.asyncio
async def test_metrics_endpoint_enabled():
    app = general_create_app(
        enable_metrics_route=True,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/metrics")

    assert response.status_code == 200
    assert "python_info" in response.text