"""Reusable FastAPI dependency for reading the authenticated identity.

Routes that want the verified JWT claims can declare:

    from tashtiot_apis_library.fastapi_template.auth import get_current_claims

    @app.get("/me")
    def me(claims: dict = Depends(get_current_claims)):
        return claims

This module intentionally does not import PyJWT -- it only reads the claims that
`AuthMiddleware` placed on ``request.state.user``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, Request

__all__ = ["get_current_claims"]


def get_current_claims(request: Request) -> Dict[str, Any]:
    """Return the verified JWT claims for the current request.

    Raises:
        HTTPException: 401 if no authenticated identity is present (e.g. the
            auth middleware is not enabled or the path is excluded).
    """
    claims = getattr(request.state, "user", None)
    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims
