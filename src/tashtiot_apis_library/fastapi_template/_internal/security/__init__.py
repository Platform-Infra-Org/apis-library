"""Inbound authentication for the FastAPI Template.

Importing this package pulls in PyJWT, so it is imported lazily by the
middleware wiring -- consumers with auth disabled never need PyJWT installed.
"""

from .errors import AuthConfigError, TokenError
from .verifier import AuthMode, JWTVerifier, get_verifier
from .middleware import AuthMiddleware
from .dependency import get_current_claims

__all__ = [
    "AuthConfigError",
    "TokenError",
    "AuthMode",
    "JWTVerifier",
    "get_verifier",
    "AuthMiddleware",
    "get_current_claims",
]
