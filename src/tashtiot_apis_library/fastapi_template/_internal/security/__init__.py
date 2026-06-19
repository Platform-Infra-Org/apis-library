"""Inbound authentication for the FastAPI Template.

Importing this package pulls in PyJWT, so it is imported lazily by the
middleware wiring -- consumers with auth disabled never need PyJWT installed.
"""

from .errors import AuthConfigError, TokenError
from .verifier import AuthMode, JWTVerifier, get_verifier
from .middleware import AuthMiddleware
from .dependency import get_current_claims
from .keygen import (
    derive_public_pem,
    generate_keypair,
    load_keypair,
    mint_token,
)

__all__ = [
    "AuthConfigError",
    "TokenError",
    "AuthMode",
    "JWTVerifier",
    "get_verifier",
    "AuthMiddleware",
    "get_current_claims",
    "generate_keypair",
    "derive_public_pem",
    "load_keypair",
    "mint_token",
]
