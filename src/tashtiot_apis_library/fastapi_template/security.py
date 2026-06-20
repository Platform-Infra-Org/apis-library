"""Public outbound SSO helpers for the FastAPI template.

Re-exported from the private ``_internal.security.sso`` module so consumers
import them from a stable public location (mirroring ``errors.py``):

    from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

These are imported straight from ``_internal.security.sso`` (not the
``_internal.security`` package) so pulling them in does **not** drag in the
inbound-JWT machinery (and therefore PyJWT) -- consumers that only mint outbound
tokens stay free of that dependency.
"""

from ._internal.security.sso import (
    SSOClientCredentialsAuth,
    SSOConfig,
    SSOTokenClient,
    StaticBearerAuth,
    TokenResponse,
    get_sso_token_client,
    sso_auth,
    sso_authenticated_api,
)

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
