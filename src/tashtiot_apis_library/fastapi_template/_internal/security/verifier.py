"""JWT verification logic supporting three configurable modes.

Verification mode is auto-selected from settings:

* **HS256**       -- symmetric, ``AUTH_HS256_SECRET``.
* **LOCAL_PUBKEY** -- offline RS256 against ``AUTH_PUBLIC_KEY_PEM`` / ``AUTH_PUBLIC_KEY_PATH``.
* **JWKS**        -- RS256 against keys fetched (and cached) from ``AUTH_JWKS_URL``, or from the
  ``jwks_uri`` discovered from ``AUTH_OIDC_ISSUER`` (generic OIDC).

Exactly one set of material may be configured; configuring more than one (or
none, while auth is enabled) raises :class:`AuthConfigError` at startup.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

import jwt
from loguru import logger

from .errors import AuthConfigError, TokenError
from .oidc import discover_jwks_uri

__all__ = ["AuthMode", "JWTVerifier", "get_verifier", "verify_token"]


class AuthMode(str, Enum):
    HS256 = "hs256"
    JWKS = "jwks"
    LOCAL_PUBKEY = "local_pubkey"


def _select_mode(settings: Any) -> AuthMode:
    """Pick the verification mode from configured material, failing loudly on
    ambiguity (more than one material set) or absence (none set)."""
    # AUTH_JWKS_URL and AUTH_OIDC_ISSUER both select JWKS mode and are
    # complementary (an explicit URL overrides discovery), so they count as one
    # material group, not two competing ones.
    has_jwks = bool(settings.AUTH_JWKS_URL or settings.AUTH_OIDC_ISSUER)
    has_local = bool(settings.AUTH_PUBLIC_KEY_PEM or settings.AUTH_PUBLIC_KEY_PATH)
    has_hs256 = bool(settings.AUTH_HS256_SECRET)

    configured = [
        name
        for name, present in (
            ("AUTH_JWKS_URL/AUTH_OIDC_ISSUER", has_jwks),
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
            # An explicit JWKS URL wins; otherwise discover it from the issuer.
            jwks_url = settings.AUTH_JWKS_URL or discover_jwks_uri(
                settings.AUTH_OIDC_ISSUER,
                verify_ssl=settings.AUTH_OIDC_VERIFY_SSL,
                timeout=settings.AUTH_OIDC_TIMEOUT,
            )
            self._jwks_client = _build_jwks_client(jwks_url, settings.AUTH_JWKS_CACHE_TTL)

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
        # 'exp' is required by default; opt out via AUTH_REQUIRE_EXP=false to accept
        # non-expiring tokens. A token that *does* carry 'exp' is still validated
        # (PyJWT's verify_exp stays on), so expired tokens remain rejected.
        require = ["exp"] if settings.AUTH_REQUIRE_EXP else []
        options: Dict[str, Any] = {"require": require, "verify_aud": bool(settings.AUTH_AUDIENCE)}
        kwargs: Dict[str, Any] = {"algorithms": self._algorithms, "options": options}
        if settings.AUTH_AUDIENCE:
            kwargs["audience"] = settings.AUTH_AUDIENCE
        # Validate 'iss' against AUTH_ISSUER, defaulting to the OIDC issuer so that
        # configuring AUTH_OIDC_ISSUER enforces the issuer claim out of the box.
        issuer = settings.AUTH_ISSUER or settings.AUTH_OIDC_ISSUER
        if issuer:
            kwargs["issuer"] = issuer
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
        except jwt.MissingRequiredClaimError as exc:
            # Most commonly the required 'exp' claim (e.g. a non-expiring token sent
            # to a verifier that still requires it). Name the claim so the fix is clear.
            raise TokenError(f"Token is missing required '{exc.claim}' claim") from exc
        except jwt.PyJWTError as exc:
            # Bad signature, wrong algorithm, malformed, etc.
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


def verify_token(token: str, *, settings: Any = None) -> Dict[str, Any]:
    """Verify a bearer token and return its claims (standalone server-side check).

    A one-call convenience over :func:`get_verifier`, for checking a token outside
    the request middleware (e.g. background workers, scripts, or routes that
    receive a token by other means). Defaults to the package ``settings``; pass an
    explicit settings object to verify against a different configuration. For SSO,
    point ``AUTH_JWKS_URL`` at the provider's JWKS endpoint and set
    ``AUTH_AUDIENCE`` / ``AUTH_ISSUER`` to match the issued tokens.

    Raises:
        TokenError: with a public-safe message on any verification failure.
    """
    if settings is None:
        from ..utils import settings as default_settings

        settings = default_settings
    return get_verifier(settings).verify(token)
