"""JWT verification logic supporting three configurable modes.

Verification mode is auto-selected from settings:

* **HS256**       -- symmetric, ``AUTH_HS256_SECRET``.
* **LOCAL_PUBKEY** -- offline RS256 against ``AUTH_PUBLIC_KEY_PEM`` / ``AUTH_PUBLIC_KEY_PATH``.
* **JWKS**        -- RS256 against keys fetched (and cached) from ``AUTH_JWKS_URL``.

Exactly one set of material may be configured; configuring more than one (or
none, while auth is enabled) raises :class:`AuthConfigError` at startup.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

import jwt
from loguru import logger

from .errors import AuthConfigError, TokenError

__all__ = ["AuthMode", "JWTVerifier", "get_verifier"]


class AuthMode(str, Enum):
    HS256 = "hs256"
    JWKS = "jwks"
    LOCAL_PUBKEY = "local_pubkey"


def _select_mode(settings: Any) -> AuthMode:
    """Pick the verification mode from configured material, failing loudly on
    ambiguity (more than one material set) or absence (none set)."""
    has_jwks = bool(settings.AUTH_JWKS_URL)
    has_local = bool(settings.AUTH_PUBLIC_KEY_PEM or settings.AUTH_PUBLIC_KEY_PATH)
    has_hs256 = bool(settings.AUTH_HS256_SECRET)

    configured = [
        name
        for name, present in (
            ("AUTH_JWKS_URL", has_jwks),
            ("AUTH_PUBLIC_KEY_PEM/AUTH_PUBLIC_KEY_PATH", has_local),
            ("AUTH_HS256_SECRET", has_hs256),
        )
        if present
    ]

    if len(configured) > 1:
        raise AuthConfigError(
            "Ambiguous authentication configuration: more than one verification "
            f"material is set ({', '.join(configured)}). Configure exactly one."
        )
    if not configured:
        raise AuthConfigError(
            "Authentication is enabled but no verification material is configured. "
            "Set one of AUTH_JWKS_URL, AUTH_PUBLIC_KEY_PEM, AUTH_PUBLIC_KEY_PATH, "
            "or AUTH_HS256_SECRET."
        )

    if has_jwks:
        return AuthMode.JWKS
    if has_local:
        return AuthMode.LOCAL_PUBKEY
    return AuthMode.HS256


def _build_jwks_client(url: str, cache_ttl: int) -> "jwt.PyJWKClient":
    """Construct a PyJWKClient, tolerating PyJWT versions without ``lifespan``."""
    try:
        return jwt.PyJWKClient(url, cache_keys=True, lifespan=cache_ttl)
    except TypeError:
        # Older PyJWT without lifespan/cache_keys kwargs.
        return jwt.PyJWKClient(url)


class JWTVerifier:
    """Verifies bearer tokens according to the configured mode.

    Built once at application startup so misconfiguration raises immediately.
    """

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._mode = _select_mode(settings)
        self._algorithms = self._resolve_algorithms()
        self._jwks_client: Optional["jwt.PyJWKClient"] = None
        self._local_key: Optional[str] = None

        if self._mode is AuthMode.LOCAL_PUBKEY:
            self._local_key = self._load_local_key()
        elif self._mode is AuthMode.JWKS:
            self._jwks_client = _build_jwks_client(
                settings.AUTH_JWKS_URL, settings.AUTH_JWKS_CACHE_TTL
            )

        logger.debug(
            "JWTVerifier initialised in {} mode (algorithms={}).",
            self._mode.value,
            self._algorithms,
        )

    @property
    def mode(self) -> AuthMode:
        return self._mode

    def _resolve_algorithms(self) -> List[str]:
        if self._mode is AuthMode.HS256:
            return ["HS256"]
        return list(self._settings.AUTH_ALGORITHMS)

    def _load_local_key(self) -> str:
        settings = self._settings
        if settings.AUTH_PUBLIC_KEY_PEM:
            return settings.AUTH_PUBLIC_KEY_PEM
        try:
            with open(settings.AUTH_PUBLIC_KEY_PATH, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise AuthConfigError(
                f"Unable to read AUTH_PUBLIC_KEY_PATH ({settings.AUTH_PUBLIC_KEY_PATH!r}): {exc}"
            ) from exc

    def _decode_kwargs(self) -> Dict[str, Any]:
        settings = self._settings
        options: Dict[str, Any] = {"require": ["exp"], "verify_aud": bool(settings.AUTH_AUDIENCE)}
        kwargs: Dict[str, Any] = {"algorithms": self._algorithms, "options": options}
        if settings.AUTH_AUDIENCE:
            kwargs["audience"] = settings.AUTH_AUDIENCE
        if settings.AUTH_ISSUER:
            kwargs["issuer"] = settings.AUTH_ISSUER
        return kwargs

    def _signing_key(self, token: str) -> Any:
        """Resolve the key/secret used to verify ``token`` for the active mode."""
        if self._mode is AuthMode.HS256:
            return self._settings.AUTH_HS256_SECRET
        if self._mode is AuthMode.LOCAL_PUBKEY:
            return self._local_key
        # JWKS: look up the signing key by the token's `kid`.
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> Dict[str, Any]:
        """Verify signature and standard claims; return the decoded claims.

        Raises:
            TokenError: with a public-safe message on any verification failure.
        """
        try:
            key = self._signing_key(token)
        except jwt.PyJWKClientError as exc:
            logger.warning("JWKS key resolution failed: {}", exc)
            raise TokenError("Unable to verify token") from exc
        except jwt.PyJWTError as exc:
            raise TokenError("Invalid token") from exc

        try:
            return jwt.decode(token, key, **self._decode_kwargs())
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("Token has expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenError("Invalid token audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenError("Invalid token issuer") from exc
        except jwt.PyJWTError as exc:
            # Bad signature, wrong algorithm, missing exp, malformed, etc.
            # Do not disclose specifics (e.g. allowed algorithms) to the client.
            raise TokenError("Invalid token") from exc


_verifier_cache: Dict[int, JWTVerifier] = {}


def get_verifier(settings: Any) -> JWTVerifier:
    """Return a memoized verifier for the given settings instance.

    Building it here (at app creation) surfaces :class:`AuthConfigError` before
    the first request rather than on it.
    """
    cached = _verifier_cache.get(id(settings))
    if cached is None:
        cached = JWTVerifier(settings)
        _verifier_cache[id(settings)] = cached
    return cached
