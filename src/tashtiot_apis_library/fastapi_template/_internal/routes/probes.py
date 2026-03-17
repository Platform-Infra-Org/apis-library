"""Health probe endpoints for the FastAPI Template application."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..utils import settings

health_router = APIRouter()


@health_router.get(settings.PROBE_LIVENESS_PATH)
def liveness_probe() -> JSONResponse:
    return JSONResponse(content={"status": "OK"}, status_code=200)


@health_router.get(settings.PROBE_READINESS_PATH)
def readiness_probe() -> JSONResponse:
    return JSONResponse(content={"status": "OK"}, status_code=200)
