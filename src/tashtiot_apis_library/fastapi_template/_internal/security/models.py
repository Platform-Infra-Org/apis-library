"""Pydantic data models for outbound SSO.

Co-located models for the SSO client (mirroring the connector ``models``/``client``
split). The client/auth logic that uses them lives in :mod:`.sso`; cross-references
to those symbols are written as explicit paths here because they live in a sibling
module this one cannot import (it would be circular).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class SSOConfig(BaseModel):
    """Client-side OAuth2 ``client_credentials`` configuration.

    Pass an explicit instance to the SSO helpers ([`sso_authenticated_api`][tashtiot_apis_library.fastapi_template._internal.security.sso.sso_authenticated_api],
    [`sso_auth`][tashtiot_apis_library.fastapi_template._internal.security.sso.sso_auth],
    [`SSOTokenClient`][tashtiot_apis_library.fastapi_template._internal.security.sso.SSOTokenClient]) to mint tokens for a specific
    identity/audience **independently of the package settings singleton** -- so a
    single process can talk to several upstreams that each require a different
    audience or even a different SSO. Build one instance per remote and reuse it,
    so its token cache (memoized by object identity) is shared across calls.

    The required fields default to ``None`` rather than being mandatory so a
    partially-configured instance still constructs and is validated by
    [`SSOTokenClient`][tashtiot_apis_library.fastapi_template._internal.security.sso.SSOTokenClient] (which raises a clear [`AuthConfigError`][tashtiot_apis_library.fastapi_template._internal.security.errors.AuthConfigError]),
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
        """Build an [`SSOConfig`][SSOConfig] from a settings object's ``AUTH_SSO_*`` knobs.

        This is the bridge that keeps the legacy singleton-driven path working: a
        settings object is just one source of an [`SSOConfig`][SSOConfig].
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
