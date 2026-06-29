"""Core application wiring for the FastAPI Template package."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Coroutine, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .middlewares import add_middlewares
from .routes import add_routers
from .utils import logger_config, settings

__all__ = ["general_create_app", "settings", "logger_config"]


def general_create_app(
    *,
    async_background_tasks: List[Callable[[], Coroutine]] = None,
    enable_logging_middleware: bool = True,
    enable_time_recording_middleware: bool = True,
    enable_root_route: bool = True,
    enable_exception_handlers: bool = True,
    enable_uptime_background_task: bool = True,
    enable_metrics_route: bool = True,
    enable_swagger_routes: bool = True,
    enable_probe_routes: bool = True,
    enable_auth: bool = False,
    **fastapi_kwargs: Any,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        # Launch each background task as a fire-and-forget coroutine on startup
        # and cancel any still running on shutdown. The task list is read from
        # ``app.state`` (not the captured argument) so capabilities wired *after*
        # construction -- e.g. ``enable_remote_config_api`` -- can append their
        # own background tasks before the lifespan starts.
        registered = getattr(_app.state, "async_background_tasks", [])
        tasks = [asyncio.create_task(task()) for task in registered]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            # Wait for cancellation to unwind so each task runs its cleanup
            # before shutdown completes. return_exceptions swallows the
            # expected CancelledError (and any teardown errors).
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        **fastapi_kwargs,
        docs_url=None,
        redoc_url=None,
        openapi_url=settings.OPENAPI_JSON_URL,
        root_path=settings.PROXY_LISTEN_PATH,
        lifespan=lifespan,
    )

    # Seed the mutable background-task registry the lifespan reads at startup.
    app.state.async_background_tasks = list(async_background_tasks or [])

    static_dir = Path(__file__).parent.parent / "static"

    app.mount(
        "/static",
        StaticFiles(directory=static_dir),
        name="static",
    )

    app.openapi_version = settings.OPENAPI_VERSION

    add_routers(
        app,
        enable_metrics=enable_metrics_route,
        enable_swagger=enable_swagger_routes,
        enable_probe=enable_probe_routes,
    )

    add_middlewares(
        app,
        enable_request_logging=enable_logging_middleware,
        enable_request_timing=enable_time_recording_middleware,
        enable_exception_handlers=enable_exception_handlers,
        enable_auth=enable_auth,
    )

    # Same dual-gate as the auth middleware: only advertise bearer auth in the
    # OpenAPI schema (Swagger's Authorize tab) when auth is actually enforced.
    if enable_auth and settings.AUTH_ENABLED:
        from .openapi import install_bearer_security_scheme

        install_bearer_security_scheme(app)

    @app.get(settings.SWAGGER_OPENAPI_JSON_URL, include_in_schema=False)
    async def get_openapi():
        return app.openapi()

    if enable_root_route:

        @app.get("/", response_model=dict, status_code=200)
        def read_root():
            return {"message": f"Welcome to {settings.APP_NAME}!"}

    return app
