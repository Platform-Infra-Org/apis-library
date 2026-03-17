"""Middleware for recording request processing time."""

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils import settings


class TimeRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start_time = time.perf_counter_ns()

        response = await call_next(request)

        process_time = time.perf_counter_ns() - start_time
        response.headers[settings.PROCESS_TIME_HEADER] = str(process_time)

        return response
