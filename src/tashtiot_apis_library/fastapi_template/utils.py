from ._internal.database import BaseAPI
from ._internal.utils import settings
from ._internal.security.dependency import get_current_claims

__all__ = [
    "BaseAPI",
    "settings",
    "get_current_claims",
    "JWTVerifier",
]


def __getattr__(name: str):
    # Lazy export: importing JWTVerifier pulls in PyJWT, so only load it on
    # demand and keep PyJWT optional for consumers with auth disabled.
    if name == "JWTVerifier":
        from ._internal.security.verifier import JWTVerifier

        return JWTVerifier
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
