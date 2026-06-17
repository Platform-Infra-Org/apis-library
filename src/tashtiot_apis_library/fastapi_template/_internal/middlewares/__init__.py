"""Middleware configuration for the FastAPI Template application."""

from fastapi import FastAPI
from loguru import logger

from ..utils import settings
from .exception import handlers
from .log_request import LogRequestsMiddleware
from .time_request import TimeRequestsMiddleware


def add_middlewares(
    app: FastAPI,
    *,
    enable_request_logging: bool = True,
    enable_request_timing: bool = True,
    enable_exception_handlers: bool = True,
    enable_auth: bool = False,
) -> None:
    """Register optional middlewares and exception handlers.

    Authentication is registered first so that, under Starlette's LIFO middleware
    ordering, it ends up innermost: requests flow logging -> timing -> auth ->
    route, ensuring even rejected (401) requests are logged and timed.
    """

    # Dual-gate: require both the code flag and the runtime master switch.
    if enable_auth and settings.AUTH_ENABLED:
        # Local import keeps PyJWT optional for consumers with auth disabled.
        from ..security import AuthMiddleware, get_verifier

        verifier = get_verifier(settings)  # raises AuthConfigError on misconfig
        app.add_middleware(AuthMiddleware, verifier=verifier)
    elif enable_auth and not settings.AUTH_ENABLED:
        logger.debug(
            "enable_auth=True but AUTH_ENABLED is false; auth middleware not registered."
        )

    if enable_request_timing:
        app.add_middleware(TimeRequestsMiddleware)

    if enable_request_logging:
        app.add_middleware(LogRequestsMiddleware)

    if enable_exception_handlers:
        for handler in handlers:
            app.add_exception_handler(handler.exception_class, handler.handler)
