from __future__ import annotations

import re
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
)

from .fastapi_template.config_api import InfraMetadata, RequiredInfraMetadata

__all__ = [
    "OperationRequest",
    "ResourceSpec",
    "DefaultMetaSpec",
    "NameNamespace",
]

# CPU and memory regex validators, number then unit (examples: cpu: 100m, memory: 10Mi)
_CPU_RE = re.compile(r"^\d+(\.\d+)?m?$")
_MEM_RE = re.compile(r"^\d+(\.\d+)?(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K)?$")


class CpuAndMemory(BaseModel):
    cpu: Optional[str] = Field(default=None, description="CPU spec")
    memory: Optional[str] = Field(default=None, description="Memory spec")

    @field_validator("cpu")
    @classmethod
    def _validate_cpu(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _CPU_RE.fullmatch(v):
            raise ValueError("CPU must use m suffix (e.g., 100m)")
        return v

    @field_validator("memory")
    @classmethod
    def _validate_memory(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MEM_RE.fullmatch(v):
            raise ValueError("Memory must use appropriate suffix (e.g., 100Mi)")
        return v


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limits: Optional[CpuAndMemory] = Field(default=None, description="Resource limits.")
    requests: Optional[CpuAndMemory] = Field(default=None, description="Resource requests.")


class PaasLabels(BaseModel):
    operational_purpose: StrictStr = Field(
        ...,
        description="Purpose label for operational monitoring.",
    )

    operational: bool = Field(
        ...,
        description="Operational PaaS label.",
    )

    critical: bool = Field(
        ...,
        description="Critical PaaS label.",
    )


class MetadataRequest(BaseModel):
    project: str = Field(..., description="Project name of the component owners.")

    network: str = Field(..., description="Network segment of the component.")

    region: str = Field(..., description="Region of the component.")

    space: str = Field(..., description="Space of the component.")

    environment: str = Field(..., description="Environment of the component.")

    island: Optional[str] = Field(default=None, description="Island of the component")


class OperationRequest(BaseModel):
    metadata: MetadataRequest = Field(..., description="Metadata of every operation request.")


class InfraOperationRequest(BaseModel):
    """Operation request whose ``metadata`` is the dynamic [`InfraMetadata`][tashtiot_apis_library.fastapi_template.config_api.InfraMetadata]
    coordinate model — validated against the live allowlists + coordinate tree, all
    coordinates optional. Use when the request's coordinates should track the infra config."""

    metadata: InfraMetadata = Field(
        ...,
        description="Metadata of every operation request, updated dynamically from the infrastructure config.",
    )


class RequiredInfraOperationRequest(BaseModel):
    """Strict variant of [`InfraOperationRequest`][tashtiot_apis_library.InfraOperationRequest] whose
    ``metadata`` uses [`RequiredInfraMetadata`][tashtiot_apis_library.fastapi_template.config_api.RequiredInfraMetadata]
    — every coordinate is mandatory (a missing one yields a 422)."""

    metadata: RequiredInfraMetadata = Field(
        ...,
        description="Metadata of every operation request, updated dynamically from the infrastructure config. Strictly required fields.",
    )


class NameNamespace(BaseModel):
    namespace: StrictStr = Field(
        ...,
        description="K8s namespace for the resource.",
    )

    name: StrictStr = Field(
        ...,
        description="Name of the service.",
    )


class DefaultMetaSpec(NameNamespace):
    paasLabels: PaasLabels = Field(
        ...,
        description="Pass labels.",
    )
