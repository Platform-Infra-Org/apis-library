"""Business logic. Connectors arrive as arguments; nothing here builds clients or reads env vars."""

from typing import Optional

from loguru import logger

from tashtiot_apis_library import AWX
from tashtiot_apis_library.fastapi_template.config_api import RemoteConfigProvider

from .conf import config
from .schemas import DNSRecordCreate, DNSRecordResponse


async def _template_id(provider: Optional[RemoteConfigProvider], record: DNSRecordCreate) -> int:
    if provider is None:
        return config.AWX_CREATE_DNS_TEMPLATE_ID
    resolved = await provider.resolve_infra_config(record.metadata)  # keyed on the coordinates
    return resolved.get("awx_create_dns_template_id", config.AWX_CREATE_DNS_TEMPLATE_ID)


async def create_dns(
    record: DNSRecordCreate, awx: AWX, provider: Optional[RemoteConfigProvider] = None
) -> DNSRecordResponse:
    template_id = await _template_id(provider, record)
    job = await awx.launch_job(
        job_template_id=template_id,
        extra_vars={
            "RECORD_TYPE": record.spec.record_type,
            "RECORD_NAME": record.spec.record_name,
            "RECORD_ADDRESS": str(record.spec.ip),
            "DNS_ZONE": record.spec.dns_zone,
        },
    )
    logger.info(
        "Launched AWX job {} for DNS record {} (project={})",
        job.job_id,
        record.spec.record_name,
        record.metadata.project,
    )
    return DNSRecordResponse(**job.model_dump())


async def get_dns_status(job_id: int, awx: AWX) -> DNSRecordResponse:
    job = await awx.get_job_status(job_id)
    return DNSRecordResponse(**job.model_dump())
