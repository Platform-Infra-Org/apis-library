"""Router registration for the FastAPI Template application."""

from fastapi import FastAPI

from .metrics import metrics_router
from .probes import health_router
from .swagger import router as swagger_router


def add_routers(
    app: FastAPI,
    *,
    enable_swagger: bool = True,
    enable_metrics: bool = True,
    enable_probe: bool = True,
) -> None:
    """Attach optional routers to the application."""

    if enable_swagger:
        app.include_router(swagger_router, include_in_schema=False)

    if enable_metrics:
        app.include_router(metrics_router, include_in_schema=False)

    if enable_probe:
        app.include_router(health_router, include_in_schema=False)
