from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, Field

from tashtiot_apis_library.connectors import AWXOperationResponse

from ...schemas import MetadataRequest


class DNSRecordCreateSpec(BaseModel):
    record_name: str = Field(
        ..., max_length=15, pattern=r"^[a-z0-9-]+$", description="Record name (lowercase)."
    )
    record_type: Literal["A"] = Field(default="A", description="DNS record type.")
    ip: IPv4Address = Field(..., description="Target IPv4 address.")
    dns_zone: str = Field(..., description="DNS zone, for example net.com.")


class DNSRecordCreate(MetadataRequest):
    spec: DNSRecordCreateSpec = Field(..., description="The record to create.")


class DNSRecordResponse(AWXOperationResponse):
    """`job_id` is polled via GET .../status/{job_id}; `status`/`status_code` carry the job state."""
