"""OIDC discovery for inbound JWT verification.

The `.verifier` JWKS mode needs the provider's ``jwks_uri`` to fetch signing
keys. Rather than make every operator look that URL up, this resolves it from the
issuer's well-known document (OpenID Connect Discovery / RFC 8414), so configuring
``AUTH_OIDC_ISSUER`` alone is enough to verify tokens against any standards-
compliant OIDC provider.

Discovery is a single blocking request performed once at verifier construction
(i.e. app startup), so a broken issuer fails the app loudly rather than on the
first request — matching the rest of the auth fail-fast behaviour.
"""

from __future__ import annotations

import httpx
from loguru import logger

from .errors import AuthConfigError

__all__ = ["OIDC_DISCOVERY_PATH", "discover_jwks_uri"]

# Standard discovery path appended to the issuer (OIDC Discovery / RFC 8414).
OIDC_DISCOVERY_PATH = "/.well-known/openid-configuration"


def discover_jwks_uri(issuer: str, *, verify_ssl: bool = True, timeout: float = 10.0) -> str:
    """Return the provider's ``jwks_uri`` from its OIDC discovery document.

    Args:
        issuer: The OIDC issuer base URL (a trailing slash is tolerated).
        verify_ssl: Verify the discovery endpoint's TLS certificate.
        timeout: Per-request timeout in seconds.

    Raises:
        AuthConfigError: if the discovery document cannot be fetched or does not
            advertise a ``jwks_uri``.
    """
    well_known = issuer.rstrip("/") + OIDC_DISCOVERY_PATH
    try:
        response = httpx.get(well_known, timeout=timeout, verify=verify_ssl)
        response.raise_for_status()
        document = response.json()
    except httpx.HTTPError as exc:
        logger.error("OIDC discovery failed for issuer {!r}: {}", issuer, exc)
        raise AuthConfigError(f"OIDC discovery failed for issuer {issuer!r}: {exc}") from exc

    jwks_uri = document.get("jwks_uri")
    if not jwks_uri:
        logger.warning("OIDC discovery document at {} has no 'jwks_uri'.", well_known)
        raise AuthConfigError(f"OIDC discovery document at {well_known} has no 'jwks_uri'.")
    logger.debug("OIDC discovery for {} resolved jwks_uri={}.", issuer, jwks_uri)
    return jwks_uri
