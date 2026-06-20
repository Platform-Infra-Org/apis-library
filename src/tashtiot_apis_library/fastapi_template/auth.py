"""Public inbound-JWT auth helpers for the FastAPI template.

The stable public home for inbound JWT verification and dev key/token minting
(mirroring ``security.py`` for outbound SSO and ``errors.py`` for auth errors)::

    from tashtiot_apis_library.fastapi_template.auth import get_current_claims, verify_token

``get_current_claims`` is imported eagerly -- its module deliberately does not
import PyJWT. The verifier/keygen names are served lazily via ``__getattr__`` so
importing this module does **not** drag in PyJWT / cryptography unless those
specific symbols are actually used.
"""

from ._internal.security.dependency import get_current_claims

__all__ = [
    "get_current_claims",
    "JWTVerifier",
    "verify_token",
    "AuthMode",
    "generate_keypair",
    "mint_token",
    "load_keypair",
    "derive_public_pem",
]

# Names served from the verifier module (inbound JWT verification).
_VERIFIER_EXPORTS = frozenset({"JWTVerifier", "verify_token", "AuthMode"})

# Names served from the keygen module (the signing-side companion to JWTVerifier).
_KEYGEN_EXPORTS = frozenset(
    {"generate_keypair", "mint_token", "load_keypair", "derive_public_pem"}
)


def __getattr__(name: str):
    # Lazy export: importing these pulls in PyJWT / cryptography, so only load
    # them on demand and keep auth deps out of the always-imported path.
    if name in _VERIFIER_EXPORTS:
        from ._internal.security import verifier

        return getattr(verifier, name)
    if name in _KEYGEN_EXPORTS:
        from ._internal.security import keygen

        return getattr(keygen, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
