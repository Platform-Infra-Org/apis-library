from ._internal.database import BaseAPI
from ._internal.utils import settings
from ._internal.security.dependency import get_current_claims

__all__ = [
    "BaseAPI",
    "settings",
    "get_current_claims",
    "JWTVerifier",
    "generate_keypair",
    "mint_token",
    "load_keypair",
    "derive_public_pem",
]

# Names served from the keygen module (the signing-side companion to JWTVerifier).
_KEYGEN_EXPORTS = frozenset(
    {"generate_keypair", "mint_token", "load_keypair", "derive_public_pem"}
)


def __getattr__(name: str):
    # Lazy export: importing these pulls in PyJWT / cryptography, so only load
    # them on demand and keep auth deps out of the always-imported path.
    if name == "JWTVerifier":
        from ._internal.security.verifier import JWTVerifier

        return JWTVerifier
    if name in _KEYGEN_EXPORTS:
        from ._internal.security import keygen

        return getattr(keygen, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
