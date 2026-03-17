"""Core application wiring for the FastAPI Template package."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Coroutine, List
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

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
    **fastapi_kwargs: Any,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        **fastapi_kwargs,
        docs_url=None,
        redoc_url=None,
        openapi_url=settings.OPENAPI_JSON_URL,
        root_path=settings.PROXY_LISTEN_PATH,
    )

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
    )

    @app.get(settings.SWAGGER_OPENAPI_JSON_URL, include_in_schema=False)
    async def get_openapi():
        return app.openapi()

    if enable_root_route:
        @app.get("/", response_model=dict, status_code=200)
        def read_root():
            return {"message": f"Welcome to {settings.APP_NAME}!"}

    return app
