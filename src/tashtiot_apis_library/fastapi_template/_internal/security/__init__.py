"""Inbound authentication for the FastAPI Template.

Importing this package pulls in PyJWT, so it is imported lazily by the
middleware wiring -- consumers with auth disabled never need PyJWT installed.
"""

from .errors import AuthConfigError, SSOError, TokenError
from .verifier import AuthMode, JWTVerifier, get_verifier, verify_token
from .middleware import AuthMiddleware
from .dependency import get_current_claims
from .keygen import (
    derive_public_pem,
    generate_keypair,
    load_keypair,
    mint_token,
)
from .sso import (
    SSOClientCredentialsAuth,
    SSOTokenClient,
    TokenResponse,
    get_sso_token_client,
    sso_auth,
    sso_authenticated_api,
)

__all__ = [
    "AuthConfigError",
    "TokenError",
    "SSOError",
    "AuthMode",
    "JWTVerifier",
    "get_verifier",
    "verify_token",
    "AuthMiddleware",
    "get_current_claims",
    "generate_keypair",
    "derive_public_pem",
    "load_keypair",
    "mint_token",
    "TokenResponse",
    "SSOTokenClient",
    "SSOClientCredentialsAuth",
    "get_sso_token_client",
    "sso_auth",
    "sso_authenticated_api",
]
