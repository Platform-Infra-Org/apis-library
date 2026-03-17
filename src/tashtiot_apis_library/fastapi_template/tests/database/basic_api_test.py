# tests/test_base_api.py
import pytest
import httpx
import respx
from ..._internal.database.basic_api import BaseAPI  # adjust import path if needed

# --------------------------- tests for BaseAPI ---------------------------

# --------------------------- ctx manager tests ---------------------------

@pytest.mark.asyncio
async def test_base_api_context_manager_creates_client():
    api = BaseAPI(base_url="https://example.com")

    async with api as client:
        assert isinstance(client, httpx.AsyncClient)
        assert client.base_url == httpx.URL("https://example.com")

    assert api._client is None

# --------------------------- property tests ---------------------------

@pytest.mark.asyncio
async def test_base_api_property_returns_temp_client():
    api = BaseAPI(base_url="https://example.com")
    temp_client = api.client
    assert isinstance(temp_client, httpx.AsyncClient)
    assert temp_client.base_url == httpx.URL("https://example.com")
    assert api._client is None

# --------------------------- request method tests ---------------------------

@pytest.mark.asyncio
async def test_base_api_performs_get_request():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/test").respond(200, json={"message": "ok"})
        async with api as client:
            response = await client.get("/test")
            assert response.status_code == 200
            assert response.json() == {"message": "ok"}
            assert route.called

@pytest.mark.asyncio
async def test_base_api_performs_post_request():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.post("/submit", json={"data": "test"}).respond(201, json={"status": "created"})
        async with api as client:
            response = await client.post("/submit", json={"data": "test"})
            assert response.status_code == 201
            assert response.json() == {"status": "created"}
            assert route.called

@pytest.mark.asyncio
async def test_base_api_performs_put_request():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.put("/update", json={"data": "new"}).respond(200, json={"status": "updated"})
        async with api as client:
            response = await client.put("/update", json={"data": "new"})
            assert response.status_code == 200
            assert response.json() == {"status": "updated"}
            assert route.called

@pytest.mark.asyncio
async def test_base_api_performs_delete_request():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.delete("/remove").respond(204)
        async with api as client:
            response = await client.delete("/remove")
            assert response.status_code == 204
            assert route.called

@pytest.mark.asyncio
async def test_base_api_file_upload():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.post("/upload").respond(200, json={"uploaded": True})
        async with api as client:
            files = {"file": ("test.txt", b"hello world")}
            response = await client.post("/upload", files=files)
            assert response.status_code == 200
            assert response.json() == {"uploaded": True}
            assert route.called

@pytest.mark.asyncio
async def test_base_api_file_download():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/download").respond(200, content=b"file content")
        async with api as client:
            response = await client.get("/download")
            assert response.status_code == 200
            assert response.content == b"file content"
            assert route.called

@pytest.mark.asyncio
async def test_base_api_custom_params():
    api = BaseAPI(base_url="https://example.com")
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/search").respond(200, json={"results": []})
        async with api as client:
            response = await client.get("/search", params={"q": "test"})
            assert response.status_code == 200
            assert response.json() == {"results": []}
            assert route.called
            assert route.calls[0].request.url.params["q"] == "test"

@pytest.mark.asyncio
async def test_base_api_custom_headers():
    api = BaseAPI(base_url="https://example.com", headers={"X-Test": "value"})
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/headers").respond(200)
        async with api as client:
            await client.get("/headers")
            # Verify headers sent
            assert route.calls[0].request.headers["X-Test"] == "value"

@pytest.mark.asyncio
async def test_base_api_auth_basic():
    api = BaseAPI(base_url="https://example.com", auth=("user", "pass"))
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/auth").respond(200)
        async with api as client:
            await client.get("/auth")
            auth_header = route.calls[0].request.headers.get("Authorization")
            assert auth_header is not None
            assert "Basic " in auth_header

@pytest.mark.asyncio
async def test_base_api_timeout():
    api = BaseAPI(base_url="https://example.com", timeout=0.01)
    with respx.mock(base_url="https://example.com") as mock:
        route = mock.get("/slow").respond(200, text="ok")
        async with api as client:
            # Simulate a delay in the response by using a transport with sleep if needed
            # For simplicity, we just check the timeout attribute
            assert client.timeout.read == 0.01
            response = await client.get("/slow")
            assert response.status_code == 200
            assert response.text == "ok"
            assert route.called
