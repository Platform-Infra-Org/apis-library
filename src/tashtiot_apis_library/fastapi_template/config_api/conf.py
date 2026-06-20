"""Package-side configuration for the Remote Config provider's outbound auth.

The provider itself lives in the library, so the knobs governing **how it
authenticates to its upstream** live here too -- but the method is selectable.
Unlike the generic, now client-side SSO (:class:`SSOConfig`), these are read from
the environment via ``CONFIG_REMOTE_*`` so a deployment can pick SSO, a static
bearer, or no auth without code changes.
"""
from typing import Any, Dict, Optional, Tuple

import httpx
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:  # Python 3.8+ stdlib; fall back gracefully for very old runtimes.
    from typing import Literal
except ImportError:  # pragma: no cover
    Literal = None  # type: ignore

from .._internal.security.errors import AuthConfigError
from .._internal.security.sso import SSOConfig, StaticBearerAuth, sso_auth


class ConfigRemoteSettings(BaseSettings):
    """Outbound auth configuration for the upstream Config API.

    ``CONFIG_REMOTE_AUTH_METHOD`` selects the strategy:

    * ``"sso"`` -- OAuth2 ``client_credentials`` bearer minted from the
      ``CONFIG_REMOTE_SSO_*`` knobs (client-side :class:`SSOConfig`).
    * ``"bearer"`` -- a fixed ``CONFIG_REMOTE_BEARER_TOKEN``.
    * ``"none"`` -- no auth (plain HTTP; e.g. in-cluster / mesh-secured / local dev).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    CONFIG_REMOTE_AUTH_METHOD: str = Field(
        default="sso",
        description="Outbound auth method for the upstream Config API: 'sso', 'bearer', or 'none'.",
        examples=["sso", "bearer", "none"],
    )

    # --- method == "bearer" ---
    CONFIG_REMOTE_BEARER_TOKEN: Optional[str] = Field(
        default=None,
        description="Static bearer token sent on every upstream request when method is 'bearer'.",
    )

    # --- method == "sso" (OAuth2 client_credentials) ---
    CONFIG_REMOTE_SSO_TOKEN_URL: Optional[str] = Field(
        default=None, description="OAuth2 token endpoint for the config-remote client_credentials grant."
    )
    CONFIG_REMOTE_SSO_CLIENT_ID: Optional[str] = Field(
        default=None, description="OAuth2 client id for the config-remote grant."
    )
    CONFIG_REMOTE_SSO_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="OAuth2 client secret for the config-remote grant."
    )
    CONFIG_REMOTE_SSO_SCOPE: Optional[str] = Field(
        default=None, description="Space-separated scopes (Keycloak: carries the downstream 'aud')."
    )
    CONFIG_REMOTE_SSO_AUDIENCE: Optional[str] = Field(
        default=None, description="'audience' token-request parameter (Auth0-style; Keycloak ignores it)."
    )
    CONFIG_REMOTE_SSO_AUTH_STYLE: str = Field(
        default="post", description="How credentials are sent to the token endpoint: 'post' or 'basic'."
    )
    CONFIG_REMOTE_SSO_VERIFY_SSL: bool = Field(
        default=True, description="Verify the TLS certificate of the token endpoint."
    )
    CONFIG_REMOTE_SSO_TIMEOUT: float = Field(
        default=10.0, description="Timeout (seconds) for token endpoint requests."
    )
    CONFIG_REMOTE_SSO_EXPIRY_SKEW: int = Field(
        default=30, description="Refresh the cached access token this many seconds before expiry."
    )

    def sso_config(self) -> SSOConfig:
        """Build the client-side :class:`SSOConfig` from the ``CONFIG_REMOTE_SSO_*`` knobs."""
        return SSOConfig(
            token_url=self.CONFIG_REMOTE_SSO_TOKEN_URL,
            client_id=self.CONFIG_REMOTE_SSO_CLIENT_ID,
            client_secret=self.CONFIG_REMOTE_SSO_CLIENT_SECRET,
            scope=self.CONFIG_REMOTE_SSO_SCOPE,
            audience=self.CONFIG_REMOTE_SSO_AUDIENCE,
            auth_style=self.CONFIG_REMOTE_SSO_AUTH_STYLE,
            verify_ssl=self.CONFIG_REMOTE_SSO_VERIFY_SSL,
            timeout=self.CONFIG_REMOTE_SSO_TIMEOUT,
            expiry_skew=self.CONFIG_REMOTE_SSO_EXPIRY_SKEW,
        )

    def resolve_auth(self) -> Tuple[Optional[httpx.Auth], Dict[str, Any]]:
        """Resolve ``(auth, base_api_kwargs)`` for the configured method.

        ``base_api_kwargs`` carries any ``timeout``/``verify`` defaults that should
        flow into the provider's outbound client. Raises :class:`AuthConfigError`
        when the chosen method is missing its required configuration.
        """
        method = (self.CONFIG_REMOTE_AUTH_METHOD or "sso").lower()
        logger.debug("Config-remote outbound auth method resolved: {}.", method)

        if method == "none":
            return None, {}

        if method == "bearer":
            if not self.CONFIG_REMOTE_BEARER_TOKEN:
                raise AuthConfigError(
                    "CONFIG_REMOTE_AUTH_METHOD='bearer' requires CONFIG_REMOTE_BEARER_TOKEN."
                )
            return StaticBearerAuth(self.CONFIG_REMOTE_BEARER_TOKEN), {}

        if method == "sso":
            cfg = self.sso_config()
            # sso_auth -> SSOTokenClient validates required fields, raising
            # AuthConfigError (mentioning the missing SSOConfig fields) if unset.
            auth = sso_auth(cfg)
            return auth, {"timeout": cfg.timeout, "verify": cfg.verify_ssl}

        raise AuthConfigError(
            f"CONFIG_REMOTE_AUTH_METHOD must be 'sso', 'bearer', or 'none', got {method!r}."
        )
