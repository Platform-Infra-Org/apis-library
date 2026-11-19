"""HTTP layer: paths, models, status codes, and mapping upstream errors. No business logic."""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from tashtiot_apis_library import AWX, ExternalServiceError
from tashtiot_apis_library.fastapi_template.config_api import RemoteConfigProvider

from .conf import config
from .operations import create_dns, get_dns_status
from .schemas import DNSRecordCreate, DNSRecordResponse


def _bad_gateway(err: ExternalServiceError) -> JSONResponse:
    # The upstream's own code (e.g. Vault 403) would mislead the caller: it is our 502.
    return JSONResponse(status_code=502, content={"detail": f"{err.service_name}: {err.detail}"})


def get_v1_dns_router(awx: AWX, provider: Optional[RemoteConfigProvider] = None) -> APIRouter:
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post(
        "/",
        response_model=DNSRecordResponse,
        status_code=202,
        summary="Create DNS record",
        description="Launches the AWX create-DNS job. Poll GET /status/{job_id} for the result.",
    )
    async def create(record: DNSRecordCreate):
        try:
            return await create_dns(record, awx, provider)
        except ExternalServiceError as err:
            return _bad_gateway(err)

    @router.get(
        "/status/{job_id}",
        response_model=DNSRecordResponse,
        status_code=200,
        summary="DNS job status",
        description="HTTP 200 whenever the job was read; the job state is in `status`/`status_code`.",
    )
    async def status(job_id: int):
        try:
            return await get_dns_status(job_id, awx)
        except ExternalServiceError as err:
            if err.status_code == 404:
                return JSONResponse(status_code=404, content={"detail": "Job not found"})
            return _bad_gateway(err)

    return router
