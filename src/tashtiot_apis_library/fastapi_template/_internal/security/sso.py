"""Outbound SSO authentication via the OAuth2 client_credentials grant.

This is the *client* (token-requesting) counterpart to :mod:`.verifier` (which
*verifies* inbound tokens). A service built on this library uses it to obtain a
bearer token for calling other protected services, with credentials supplied via
the ``AUTH_SSO_*`` settings.

Three pieces, layered like the connectors (model -> client -> high level):

* :class:`TokenResponse` -- the parsed token endpoint response.
* :class:`SSOTokenClient` -- fetches, caches, and refreshes the access token.
* :class:`SSOClientCredentialsAuth` -- an :class:`httpx.Auth` that injects the
  bearer on every request and refreshes it on ``401``.

``client_credentials`` issues no OAuth2 refresh token (RFC 6749 section 4.4.3):
"refresh" here means re-running the grant (re-sending the client credentials) to
mint a new access token when the cached one expires.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict

from ..utils import settings as default_settings
from .errors import AuthConfigError, SSOError

__all__ = [
    "TokenResponse",
    "SSOTokenClient",
    "SSOClientCredentialsAuth",
    "get_sso_token_client",
    "sso_auth",
    "sso_authenticated_api",
]

# Fallback lifetime (seconds) when the token endpoint omits ``expires_in``.
_DEFAULT_TTL_SECONDS = 60


class TokenResponse(BaseModel):
    """Parsed OAuth2 token endpoint response (tolerant of provider extras)."""

    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    scope: Optional[str] = None


class SSOTokenClient:
    """Fetches and caches an access token via the client_credentials grant.

    Built once per settings object (see :func:`get_sso_token_client`) so the token
    cache is shared across callers. Concurrent refreshes are serialised with an
    :class:`asyncio.Lock` so a token expiry does not stampede the provider.
    """

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        missing = [
            name
            for name in ("AUTH_SSO_TOKEN_URL", "AUTH_SSO_CLIENT_ID", "AUTH_SSO_CLIENT_SECRET")
            if not getattr(settings, name, None)
        ]
        if missing:
            raise AuthConfigError(
                "SSO client_credentials is not fully configured; missing: "
                f"{', '.join(missing)}."
            )

        style = (settings.AUTH_SSO_AUTH_STYLE or "post").lower()
        if style not in ("post", "basic"):
            raise AuthConfigError(
                f"AUTH_SSO_AUTH_STYLE must be 'post' or 'basic', got {style!r}."
            )
        self._auth_style = style

        self._token: Optional[str] = None
        self._expires_at: float = 0.0  # time.monotonic() deadline (minus skew)
        self._lock = asyncio.Lock()

    async def get_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid access token, fetching a fresh one when needed."""
        if not force_refresh and self._token and time.monotonic() < self._expires_at:
            return self._token

        async with self._lock:
            # Re-check under the lock: another coroutine may have refreshed already.
            if not force_refresh and self._token and time.monotonic() < self._expires_at:
                return self._token

            token_response = await self._fetch()
            ttl = token_response.expires_in or _DEFAULT_TTL_SECONDS
            skew = self._settings.AUTH_SSO_EXPIRY_SKEW
            self._token = token_response.access_token
            self._expires_at = time.monotonic() + max(ttl - skew, 0)
            logger.debug(
                "Acquired SSO access token (ttl={}s, skew={}s).", ttl, skew
            )
            return self._token

    async def auth_header(self) -> Dict[str, str]:
        """Return an ``Authorization`` header dict for manual attachment."""
        return {"Authorization": f"Bearer {await self.get_token()}"}

    def _request_kwargs(self) -> Dict[str, Any]:
        """Build the form body and (optional) basic auth for the token request."""
        settings = self._settings
        data: Dict[str, str] = {"grant_type": "client_credentials"}
        if settings.AUTH_SSO_SCOPE:
            data["scope"] = settings.AUTH_SSO_SCOPE
        if settings.AUTH_SSO_AUDIENCE:
            data["audience"] = settings.AUTH_SSO_AUDIENCE

        kwargs: Dict[str, Any] = {"data": data}
        if self._auth_style == "basic":
            kwargs["auth"] = (settings.AUTH_SSO_CLIENT_ID, settings.AUTH_SSO_CLIENT_SECRET)
        else:  # "post": credentials travel in the form body.
            data["client_id"] = settings.AUTH_SSO_CLIENT_ID
            data["client_secret"] = settings.AUTH_SSO_CLIENT_SECRET
        return kwargs

    async def _fetch(self) -> TokenResponse:
        settings = self._settings
        # Use the same outbound HTTP wrapper the connectors use.
        from ..database import BaseAPI

        api = BaseAPI(
            settings.AUTH_SSO_TOKEN_URL,
            timeout=settings.AUTH_SSO_TIMEOUT,
            verify=settings.AUTH_SSO_VERIFY_SSL,
        )
        try:
            async with api as client:
                # Post to the absolute URL so the exact token endpoint is hit
                # (an empty relative path would have httpx append a trailing slash).
                response = await client.post(
                    settings.AUTH_SSO_TOKEN_URL, **self._request_kwargs()
                )
        except httpx.HTTPError as exc:
            raise SSOError(f"SSO token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise SSOError(
                f"SSO token endpoint returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        try:
            return TokenResponse.model_validate(response.json())
        except Exception as exc:  # JSON decode or schema mismatch
            raise SSOError(f"Malformed SSO token response: {exc}") from exc


class SSOClientCredentialsAuth(httpx.Auth):
    """httpx auth that injects (and refreshes) an SSO bearer token per request.

    Plug into any async httpx client -- including :class:`BaseAPI` via
    ``BaseAPI(url, auth=...)`` -- to authenticate outbound calls. On a ``401`` it
    forces one token refresh and retries the request once.
    """

    requires_response_body = False

    def __init__(self, token_client: SSOTokenClient) -> None:
        self._token_client = token_client

    def sync_auth_flow(self, request):  # pragma: no cover - library is async-only
        raise RuntimeError(
            "SSOClientCredentialsAuth is async-only; use an httpx.AsyncClient."
        )

    async def async_auth_flow(self, request):
        token = await self._token_client.get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request

        if response.status_code == 401:
            # Token may have been revoked/rotated early; refresh once and retry.
            token = await self._token_client.get_token(force_refresh=True)
            request.headers["Authorization"] = f"Bearer {token}"
            yield request


_token_client_cache: Dict[int, SSOTokenClient] = {}


def get_sso_token_client(settings: Any = None) -> SSOTokenClient:
    """Return a memoized :class:`SSOTokenClient` for the given settings.

    Memoizing keeps the token cache shared across all callers using the same
    settings object. Defaults to the package ``settings``.
    """
    if settings is None:
        settings = default_settings
    cached = _token_client_cache.get(id(settings))
    if cached is None:
        cached = SSOTokenClient(settings)
        _token_client_cache[id(settings)] = cached
    return cached


def sso_auth(settings: Any = None) -> SSOClientCredentialsAuth:
    """Return an :class:`httpx.Auth` backed by the shared SSO token client."""
    return SSOClientCredentialsAuth(get_sso_token_client(settings))


def sso_authenticated_api(base_url: str, *, settings: Any = None, **base_api_kwargs: Any):
    """Return a :class:`BaseAPI` whose every request carries a fresh SSO token.

    The connector-style outbound client (``async with`` it for a reusable
    ``httpx.AsyncClient``) with automatic per-request token injection/refresh::

        async with sso_authenticated_api("https://downstream.example.com") as client:
            resp = await client.get("/protected")   # Authorization added & refreshed

    Extra keyword args pass through to :class:`BaseAPI` (e.g. ``headers``,
    ``timeout``, ``verify``).
    """
    from ..database import BaseAPI

    if settings is None:
        settings = default_settings
    base_api_kwargs.setdefault("timeout", settings.AUTH_SSO_TIMEOUT)
    base_api_kwargs.setdefault("verify", settings.AUTH_SSO_VERIFY_SSL)
    return BaseAPI(base_url, auth=sso_auth(settings), **base_api_kwargs)
