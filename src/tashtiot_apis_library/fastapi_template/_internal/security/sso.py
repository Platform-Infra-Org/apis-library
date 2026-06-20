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

Downstream audience (``aud``) is provider-specific and decided at the token
endpoint, not at the call site:

* Auth0-style providers honor the ``audience`` request parameter -> set
  ``AUTH_SSO_AUDIENCE`` (sent below in :meth:`SSOTokenClient._request_kwargs`).
* **Keycloak ignores the ``audience`` parameter.** Configure an Audience protocol
  mapper on a Keycloak client scope and request that scope via ``AUTH_SSO_SCOPE``;
  the issued token then carries the right ``aud``. See the README's "Outbound SSO"
  section.
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
    "SSOConfig",
    "TokenResponse",
    "SSOTokenClient",
    "SSOClientCredentialsAuth",
    "StaticBearerAuth",
    "get_sso_token_client",
    "sso_auth",
    "sso_authenticated_api",
]

# Fallback lifetime (seconds) when the token endpoint omits ``expires_in``.
_DEFAULT_TTL_SECONDS = 60


class SSOConfig(BaseModel):
    """Client-side OAuth2 ``client_credentials`` configuration.

    Pass an explicit instance to the SSO helpers (:func:`sso_authenticated_api`,
    :func:`sso_auth`, :class:`SSOTokenClient`) to mint tokens for a specific
    identity/audience **independently of the package settings singleton** -- so a
    single process can talk to several upstreams that each require a different
    audience or even a different SSO. Build one instance per remote and reuse it,
    so its token cache (memoized by object identity) is shared across calls.

    The required fields default to ``None`` rather than being mandatory so a
    partially-configured instance still constructs and is validated by
    :class:`SSOTokenClient` (which raises a clear :class:`AuthConfigError`),
    mirroring the settings-driven path.
    """

    token_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scope: Optional[str] = None
    audience: Optional[str] = None
    auth_style: str = "post"
    verify_ssl: bool = True
    timeout: float = 10.0
    expiry_skew: int = 30

    @classmethod
    def from_settings(cls, settings: Any) -> "SSOConfig":
        """Build an :class:`SSOConfig` from a settings object's ``AUTH_SSO_*`` knobs.

        This is the bridge that keeps the legacy singleton-driven path working: a
        settings object is just one source of an :class:`SSOConfig`.
        """
        return cls(
            token_url=settings.AUTH_SSO_TOKEN_URL,
            client_id=settings.AUTH_SSO_CLIENT_ID,
            client_secret=settings.AUTH_SSO_CLIENT_SECRET,
            scope=settings.AUTH_SSO_SCOPE,
            audience=settings.AUTH_SSO_AUDIENCE,
            auth_style=settings.AUTH_SSO_AUTH_STYLE,
            verify_ssl=settings.AUTH_SSO_VERIFY_SSL,
            timeout=settings.AUTH_SSO_TIMEOUT,
            expiry_skew=settings.AUTH_SSO_EXPIRY_SKEW,
        )


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

    def __init__(self, config: Any) -> None:
        # Dual-accept: an explicit SSOConfig (client-side config) or a settings
        # object exposing AUTH_SSO_* (legacy singleton path). A settings object is
        # validated against its AUTH_SSO_* names so the error message matches the
        # env var, then normalised to an SSOConfig.
        if isinstance(config, SSOConfig):
            missing = [
                name
                for name in ("token_url", "client_id", "client_secret")
                if not getattr(config, name, None)
            ]
            if missing:
                raise AuthConfigError(
                    "SSO client_credentials is not fully configured; missing: "
                    f"{', '.join(missing)}."
                )
        else:
            missing = [
                name
                for name in ("AUTH_SSO_TOKEN_URL", "AUTH_SSO_CLIENT_ID", "AUTH_SSO_CLIENT_SECRET")
                if not getattr(config, name, None)
            ]
            if missing:
                raise AuthConfigError(
                    "SSO client_credentials is not fully configured; missing: "
                    f"{', '.join(missing)}."
                )
            config = SSOConfig.from_settings(config)

        style = (config.auth_style or "post").lower()
        if style not in ("post", "basic"):
            raise AuthConfigError(
                f"AUTH_SSO_AUTH_STYLE must be 'post' or 'basic', got {style!r}."
            )
        self._config = config
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
            skew = self._config.expiry_skew
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
        config = self._config
        data: Dict[str, str] = {"grant_type": "client_credentials"}
        if config.scope:
            data["scope"] = config.scope
        if config.audience:
            data["audience"] = config.audience

        kwargs: Dict[str, Any] = {"data": data}
        if self._auth_style == "basic":
            kwargs["auth"] = (config.client_id, config.client_secret)
        else:  # "post": credentials travel in the form body.
            data["client_id"] = config.client_id
            data["client_secret"] = config.client_secret
        return kwargs

    async def _fetch(self) -> TokenResponse:
        config = self._config
        # Use the same outbound HTTP wrapper the connectors use.
        from ..database import BaseAPI

        api = BaseAPI(
            config.token_url,
            timeout=config.timeout,
            verify=config.verify_ssl,
        )
        logger.debug("Requesting SSO token from {}.", config.token_url)
        try:
            async with api as client:
                # Post to the absolute URL so the exact token endpoint is hit
                # (an empty relative path would have httpx append a trailing slash).
                response = await client.post(
                    config.token_url, **self._request_kwargs()
                )
        except httpx.HTTPError as exc:
            logger.error("SSO token request to {} failed: {}", config.token_url, exc)
            raise SSOError(f"SSO token request failed: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "SSO token endpoint {} returned {}: {}",
                config.token_url,
                response.status_code,
                response.text[:500],
            )
            raise SSOError(
                f"SSO token endpoint returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        try:
            return TokenResponse.model_validate(response.json())
        except Exception as exc:  # JSON decode or schema mismatch
            logger.error("Malformed SSO token response from {}: {}", config.token_url, exc)
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
            logger.info(
                "SSO 401 on {} {}; refreshing token and retrying once.",
                request.method,
                request.url,
            )
            token = await self._token_client.get_token(force_refresh=True)
            request.headers["Authorization"] = f"Bearer {token}"
            yield request


class StaticBearerAuth(httpx.Auth):
    """httpx auth that attaches a fixed bearer token on every request.

    Unlike :class:`SSOClientCredentialsAuth` there is no token endpoint and no
    refresh -- the token is supplied verbatim. Handy for upstreams secured by a
    long-lived service token. Works for both sync and async clients.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


_token_client_cache: Dict[int, SSOTokenClient] = {}


def get_sso_token_client(source: Any = None) -> SSOTokenClient:
    """Return a memoized :class:`SSOTokenClient` for ``source``.

    ``source`` may be an explicit :class:`SSOConfig` (client-side config), a
    settings object exposing ``AUTH_SSO_*`` (legacy singleton path), or ``None``
    to use the package ``settings``. Memoizing by object identity keeps the token
    cache shared across all callers passing the same object -- so build one
    :class:`SSOConfig` per remote and reuse it.
    """
    if source is None:
        source = default_settings
    cached = _token_client_cache.get(id(source))
    if cached is None:
        cached = SSOTokenClient(source)
        _token_client_cache[id(source)] = cached
    return cached


def sso_auth(source: Any = None) -> SSOClientCredentialsAuth:
    """Return an :class:`httpx.Auth` backed by the shared SSO token client.

    ``source`` is an :class:`SSOConfig`, a settings object, or ``None`` (package
    settings) -- see :func:`get_sso_token_client`.
    """
    return SSOClientCredentialsAuth(get_sso_token_client(source))


def sso_authenticated_api(
    base_url: str, *, config: Optional[SSOConfig] = None, settings: Any = None, **base_api_kwargs: Any
):
    """Return a :class:`BaseAPI` whose every request carries a fresh SSO token.

    The connector-style outbound client (``async with`` it for a reusable
    ``httpx.AsyncClient``) with automatic per-request token injection/refresh::

        cfg = SSOConfig(token_url=..., client_id=..., client_secret=..., audience=...)
        async with sso_authenticated_api("https://downstream.example.com", config=cfg) as client:
            resp = await client.get("/protected")   # Authorization added & refreshed

    Pass ``config`` (client-side, preferred) to target a specific identity/audience;
    omit it to fall back to ``settings`` (or the package singleton). Extra keyword
    args pass through to :class:`BaseAPI` (e.g. ``headers``, ``timeout``, ``verify``).
    """
    from ..database import BaseAPI

    # The object handed to the token client (identity drives token-cache sharing).
    source = config if config is not None else (settings if settings is not None else default_settings)
    # A normalised view used only to derive timeout/verify defaults.
    resolved = source if isinstance(source, SSOConfig) else SSOConfig.from_settings(source)
    base_api_kwargs.setdefault("timeout", resolved.timeout)
    base_api_kwargs.setdefault("verify", resolved.verify_ssl)
    return BaseAPI(base_url, auth=sso_auth(source), **base_api_kwargs)
