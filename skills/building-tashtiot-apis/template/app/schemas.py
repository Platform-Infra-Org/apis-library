"""The request contract shared by every write route: {"metadata": {...}, "spec": {...}}."""

from pydantic import BaseModel, Field

from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata


class ProjectMetadata(InfraMetadata):
    """Platform metadata: `project` is required; space/network/region/island/environment are
    optional. Unknown extra keys are ignored (never set extra="forbid" here)."""

    project: str = Field(..., description="The platform application submitting the request")


class MetadataRequest(BaseModel):
    """Base for every write request. APIs that don't use metadata still accept it."""

    metadata: ProjectMetadata = Field(..., description="Platform metadata (project required).")
