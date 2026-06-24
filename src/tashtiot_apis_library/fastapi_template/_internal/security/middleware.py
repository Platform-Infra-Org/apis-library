"""Global authentication middleware for the FastAPI Template application."""

from __future__ import annotations

import re
from typing import List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils import settings
from .errors import TokenError
from .verifier import JWTVerifier


def _build_exclude_paths(cfg) -> List[str]:
    """Collect path prefixes that bypass authentication.

    Combines ``AUTH_EXCLUDE_PATHS`` with the resolved probe/swagger/openapi paths
    so the excludes track any overridden settings. De-duplicated, order-stable.
    """
    paths = list(cfg.AUTH_EXCLUDE_PATHS)
    paths.extend(
        [
            cfg.PROBE_LIVENESS_PATH,
            cfg.PROBE_READINESS_PATH,
            cfg.SWAGGER_STATIC_FILES,
            cfg.OPENAPI_JSON_URL,
            cfg.SWAGGER_OPENAPI_JSON_URL,
        ]
    )
    return list(dict.fromkeys(path for path in paths if path))


class AuthMiddleware(BaseHTTPMiddleware):
    """Rejects unauthenticated requests to protected paths with a 401.

    Returns a ``JSONResponse`` directly (rather than raising) because Starlette's
    exception handlers do not catch exceptions raised inside ``BaseHTTPMiddleware``.
    The body shape ``{"detail": ...}`` matches the project's HTTP exception handler.
    """

    def __init__(self, app, verifier: JWTVerifier) -> None:
        super().__init__(app)
        self._verifier = verifier
        self._exclude = _build_exclude_paths(settings)

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(prefix) or re.match(prefix, path) for prefix in self._exclude)

    @staticmethod
    def _extract_bearer(header: Optional[str]) -> Optional[str]:
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            return None
        return parts[1]

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if self._is_excluded(path):
            return await call_next(request)

        token = self._extract_bearer(request.headers.get(settings.AUTH_HEADER_NAME))
        if token is None:
            logger.info(
                f"Auth rejected {request.method} {path}: missing bearer token",
                extra={"location": "Auth"},
            )
            return self._unauthorized("Not authenticated")

        try:
            claims = self._verifier.verify(token)
        except TokenError as exc:
            logger.info(
                f"Auth rejected {request.method} {path}: {exc.detail}",
                extra={"location": "Auth"},
            )
            return self._unauthorized(exc.detail)

        request.state.user = claims
        return await call_next(request)
