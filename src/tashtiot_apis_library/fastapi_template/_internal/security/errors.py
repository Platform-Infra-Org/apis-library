"""Auth-related error types for the FastAPI Template security layer."""

from __future__ import annotations


class AuthConfigError(RuntimeError):
    """Raised at startup when authentication is enabled but the verification
    material is missing or ambiguous. Surfacing this during app creation makes
    misconfiguration fail fast instead of on the first request."""


class TokenError(Exception):
    """Internal token-level failure (missing, malformed, expired, bad signature,
    or failing claim validation).

    Carries a public-safe ``detail`` string for the 401 response body. Raw PyJWT
    exception text is never propagated to clients.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
