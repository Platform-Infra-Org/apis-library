"""Tests for outbound SSO (OAuth2 client_credentials) auth and the standalone
server-side token check. The IdP token endpoint and downstream API are mocked
with respx; no network is touched."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
import respx

from tashtiot_apis_library.fastapi_template.utils import settings
from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, SSOError, TokenError
from tashtiot_apis_library.fastapi_template.auth import verify_token
from tashtiot_apis_library.fastapi_template.security import (
    SSOClientCredentialsAuth,
    SSOConfig,
    SSOTokenClient,
    get_sso_token_client,
    sso_auth,
    sso_authenticated_api,
)
# White-box access to private module state (caches) -- no public re-export by design.
from tashtiot_apis_library.fastapi_template._internal.security import sso as sso_mod
from tashtiot_apis_library.fastapi_template._internal.security import verifier as verifier_mod

TOKEN_URL = "https://idp.example.com/oauth/token"
DOWNSTREAM = "https://downstream.example.com"


@pytest.fixture(autouse=True)
def _reset_sso_settings(monkeypatch):
    """Configure SSO settings and clear the shared caches around each test."""
    sso_mod._token_client_cache.clear()
    verifier_mod._verifier_cache.clear()
    for name, value in {
        "AUTH_SSO_TOKEN_URL": TOKEN_URL,
        "AUTH_SSO_CLIENT_ID": "svc",
        "AUTH_SSO_CLIENT_SECRET": "s3cret",
        "AUTH_SSO_SCOPE": None,
        "AUTH_SSO_AUDIENCE": None,
        "AUTH_SSO_AUTH_STYLE": "post",
        "AUTH_SSO_VERIFY_SSL": True,
        "AUTH_SSO_TIMEOUT": 10.0,
        "AUTH_SSO_EXPIRY_SKEW": 30,
        # For the server-side verify_token tests.
        "AUTH_ENABLED": False,
        "AUTH_HS256_SECRET": None,
        "AUTH_JWKS_URL": None,
        "AUTH_PUBLIC_KEY_PEM": None,
        "AUTH_PUBLIC_KEY_PATH": None,
        "AUTH_AUDIENCE": None,
        "AUTH_ISSUER": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    yield
    sso_mod._token_client_cache.clear()
    verifier_mod._verifier_cache.clear()


def _token_route(access_token="tok-abc", expires_in=3600):
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": access_token, "token_type": "Bearer", "expires_in": expires_in},
        )
    )


# --------------------------------------------------------------------------- #
# SSOTokenClient — fetch / cache / refresh
# --------------------------------------------------------------------------- #


def test_missing_config_raises(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SSO_CLIENT_SECRET", None)
    with pytest.raises(AuthConfigError, match="AUTH_SSO_CLIENT_SECRET"):
        SSOTokenClient(settings)


def test_invalid_auth_style_raises(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SSO_AUTH_STYLE", "weird")
    with pytest.raises(AuthConfigError, match="AUTH_SSO_AUTH_STYLE"):
        SSOTokenClient(settings)


@pytest.mark.asyncio
@respx.mock
async def test_get_token_fetches_and_caches():
    route = _token_route(access_token="tok-1")
    client = SSOTokenClient(settings)

    assert await client.get_token() == "tok-1"
    assert await client.get_token() == "tok-1"  # served from cache
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_token_refreshes_when_expired():
    route = _token_route()
    client = SSOTokenClient(settings)

    await client.get_token()
    client._expires_at = 0.0  # force the cache to look expired
    await client.get_token()

    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_force_refresh_bypasses_cache():
    route = _token_route()
    client = SSOTokenClient(settings)

    await client.get_token()
    await client.get_token(force_refresh=True)
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_post_style_sends_credentials_in_body():
    route = _token_route()
    client = SSOTokenClient(settings)
    await client.get_token()

    request = route.calls.last.request
    body = parse_qs(request.content.decode())
    assert body["grant_type"] == ["client_credentials"]
    assert body["client_id"] == ["svc"]
    assert body["client_secret"] == ["s3cret"]
    assert "Authorization" not in request.headers


@pytest.mark.asyncio
@respx.mock
async def test_basic_style_sends_credentials_in_header(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SSO_AUTH_STYLE", "basic")
    route = _token_route()
    client = SSOTokenClient(settings)
    await client.get_token()

    request = route.calls.last.request
    assert request.headers["Authorization"].startswith("Basic ")
    body = parse_qs(request.content.decode())
    assert "client_secret" not in body  # not duplicated into the body


@pytest.mark.asyncio
@respx.mock
async def test_scope_and_audience_included(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SSO_SCOPE", "api.read api.write")
    monkeypatch.setattr(settings, "AUTH_SSO_AUDIENCE", "https://api.example.com")
    route = _token_route()
    await SSOTokenClient(settings).get_token()

    body = parse_qs(route.calls.last.request.content.decode())
    assert body["scope"] == ["api.read api.write"]
    assert body["audience"] == ["https://api.example.com"]


@pytest.mark.asyncio
@respx.mock
async def test_non_2xx_raises_sso_error():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, text="nope"))
    with pytest.raises(SSOError, match="401"):
        await SSOTokenClient(settings).get_token()


@pytest.mark.asyncio
@respx.mock
async def test_malformed_response_raises_sso_error():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"no_token": True}))
    with pytest.raises(SSOError, match="Malformed"):
        await SSOTokenClient(settings).get_token()


def test_get_sso_token_client_is_memoized():
    assert get_sso_token_client(settings) is get_sso_token_client(settings)


# --------------------------------------------------------------------------- #
# SSOClientCredentialsAuth — per-request injection + 401 refresh/retry
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@respx.mock
async def test_auth_injects_bearer_on_request():
    _token_route(access_token="tok-xyz")
    api_route = respx.get(f"{DOWNSTREAM}/protected").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    async with httpx.AsyncClient(auth=sso_auth(settings)) as client:
        resp = await client.get(f"{DOWNSTREAM}/protected")

    assert resp.status_code == 200
    assert api_route.calls.last.request.headers["Authorization"] == "Bearer tok-xyz"


@pytest.mark.asyncio
@respx.mock
async def test_auth_refreshes_once_on_401():
    token_route = _token_route()
    api_route = respx.get(f"{DOWNSTREAM}/protected").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": True})]
    )

    auth = SSOClientCredentialsAuth(SSOTokenClient(settings))
    async with httpx.AsyncClient(auth=auth) as client:
        resp = await client.get(f"{DOWNSTREAM}/protected")

    assert resp.status_code == 200
    assert api_route.call_count == 2          # original + retry
    assert token_route.call_count == 2        # initial fetch + forced refresh


@pytest.mark.asyncio
@respx.mock
async def test_sso_authenticated_api_carries_bearer():
    _token_route(access_token="tok-baseapi")
    api_route = respx.get(f"{DOWNSTREAM}/data").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    async with sso_authenticated_api(DOWNSTREAM, settings=settings) as client:
        resp = await client.get("/data")

    assert resp.status_code == 200
    assert api_route.calls.last.request.headers["Authorization"] == "Bearer tok-baseapi"


# --------------------------------------------------------------------------- #
# Server side — verify_token convenience
# --------------------------------------------------------------------------- #


def _hs256(secret, **extra):
    claims = {"sub": "svc", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    claims.update(extra)
    return jwt.encode(claims, secret, algorithm="HS256")


def test_verify_token_accepts_valid(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", "shared-secret")
    claims = verify_token(_hs256("shared-secret"))
    assert claims["sub"] == "svc"


def test_verify_token_rejects_invalid(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_HS256_SECRET", "shared-secret")
    with pytest.raises(TokenError):
        verify_token(_hs256("wrong-secret"))


# --------------------------------------------------------------------------- #
# Client-side SSOConfig — config passed in, not read from the settings singleton
# --------------------------------------------------------------------------- #

ALT_TOKEN_URL = "https://other-idp.example.com/oauth/token"


def test_sso_config_from_settings_maps_auth_sso_fields():
    cfg = SSOConfig.from_settings(settings)
    assert cfg.token_url == TOKEN_URL
    assert cfg.client_id == "svc"
    assert cfg.client_secret == "s3cret"
    assert cfg.auth_style == "post"


def test_sso_token_client_accepts_explicit_config():
    cfg = SSOConfig(token_url=ALT_TOKEN_URL, client_id="c", client_secret="s")
    client = SSOTokenClient(cfg)
    assert client._config.token_url == ALT_TOKEN_URL


def test_sso_config_missing_field_raises():
    with pytest.raises(AuthConfigError, match="client_secret"):
        SSOTokenClient(SSOConfig(token_url=ALT_TOKEN_URL, client_id="c"))


@pytest.mark.asyncio
@respx.mock
async def test_sso_authenticated_api_uses_explicit_config_not_singleton():
    # The singleton points at TOKEN_URL; the explicit config points elsewhere.
    alt_route = respx.post(ALT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "alt-tok", "expires_in": 3600})
    )
    api_route = respx.get(f"{DOWNSTREAM}/data").mock(return_value=httpx.Response(200, json={"ok": True}))

    cfg = SSOConfig(token_url=ALT_TOKEN_URL, client_id="alt", client_secret="alt-secret")
    async with sso_authenticated_api(DOWNSTREAM, config=cfg) as client:
        resp = await client.get("/data")

    assert resp.status_code == 200
    assert alt_route.called  # token minted from the config's endpoint, not the singleton
    assert api_route.calls.last.request.headers["Authorization"] == "Bearer alt-tok"


@pytest.mark.asyncio
@respx.mock
async def test_distinct_configs_have_independent_token_caches():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-default", "expires_in": 3600})
    )
    respx.post(ALT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-alt", "expires_in": 3600})
    )

    cfg_a = SSOConfig(token_url=TOKEN_URL, client_id="a", client_secret="s")
    cfg_b = SSOConfig(token_url=ALT_TOKEN_URL, client_id="b", client_secret="s")

    # Memoized per object identity -> different clients, different tokens.
    assert get_sso_token_client(cfg_a) is get_sso_token_client(cfg_a)
    assert get_sso_token_client(cfg_a) is not get_sso_token_client(cfg_b)
    assert await get_sso_token_client(cfg_a).get_token() == "tok-default"
    assert await get_sso_token_client(cfg_b).get_token() == "tok-alt"
