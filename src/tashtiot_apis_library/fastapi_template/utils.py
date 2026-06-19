from ._internal.database import BaseAPI
from ._internal.utils import settings
from ._internal.security.dependency import get_current_claims

__all__ = [
    "BaseAPI",
    "settings",
    "get_current_claims",
    "JWTVerifier",
    "verify_token",
    "generate_keypair",
    "mint_token",
    "load_keypair",
    "derive_public_pem",
    "get_sso_token_client",
    "sso_auth",
    "sso_authenticated_api",
]

# Names served from the keygen module (the signing-side companion to JWTVerifier).
_KEYGEN_EXPORTS = frozenset(
    {"generate_keypair", "mint_token", "load_keypair", "derive_public_pem"}
)

# Names served from the SSO module (outbound client_credentials token client).
_SSO_EXPORTS = frozenset(
    {"get_sso_token_client", "sso_auth", "sso_authenticated_api"}
)


def __getattr__(name: str):
    # Lazy export: importing these pulls in PyJWT / cryptography / httpx auth, so
    # only load them on demand and keep auth deps out of the always-imported path.
    if name == "JWTVerifier":
        from ._internal.security.verifier import JWTVerifier

        return JWTVerifier
    if name == "verify_token":
        from ._internal.security.verifier import verify_token

        return verify_token
    if name in _KEYGEN_EXPORTS:
        from ._internal.security import keygen

        return getattr(keygen, name)
    if name in _SSO_EXPORTS:
        from ._internal.security import sso

        return getattr(sso, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
