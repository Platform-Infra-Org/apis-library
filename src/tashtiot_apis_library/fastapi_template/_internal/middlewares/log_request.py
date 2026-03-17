"""Middleware for logging incoming HTTP requests."""
import re

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils import settings


class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        log_level = "INFO"

        if any(
            request.url.path.startswith(prefix) or re.match(prefix, request.url.path)
            for prefix in settings.LOG_REQUEST_EXCLUDE_PATHS
        ):
            log_level = "DEBUG"

        logger.log(log_level, f"{request.method} {request.url.path}", extra={"location": "Request"})

        response = await call_next(request)

        process_time = response.headers.get(settings.PROCESS_TIME_HEADER) or ""

        logger.log(
            log_level,
            f"{request.method} {request.url.path} {response.status_code} {process_time}", extra={"location": "Response"}
        )

        return response
