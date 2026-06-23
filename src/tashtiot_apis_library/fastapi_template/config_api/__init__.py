"""Remote Config capability: a thin, authenticated proxy to an upstream Config API.

Resolves hierarchical infrastructure config / naming / project-registry by
forwarding allocation coordinates to an upstream Config API (same routes) over
HTTP. Bundles the dynamic ``InfraMetadata`` coordinate schemas (whose validators
and OpenAPI enum dropdowns track live ``LIVE_ALLOWED_*`` allowlists), the
background allowlist poller, and a one-call wiring helper.

Outbound auth to the upstream is package-side but selectable via the
``CONFIG_REMOTE_*`` settings ([`ConfigRemoteSettings`][ConfigRemoteSettings]): SSO
``client_credentials``, a static bearer, or none.
"""

from .conf import ConfigRemoteSettings
from .errors import install_coordinate_validation_error_handler
from .models import (
    LIVE_ALLOWED_ENVIRONMENTS,
    LIVE_ALLOWED_ISLANDS,
    LIVE_ALLOWED_NETWORKS,
    LIVE_ALLOWED_PROJECTS,
    LIVE_ALLOWED_REGIONS,
    LIVE_ALLOWED_SPACES,
    AllProjectsResponse,
    ConfigResolutionResponse,
    CoordinateCatalogResponse,
    InfraMetadata,
    NamingConventionResponse,
    RequiredInfraMetadata,
)
from .openapi import make_config_openapi
from .provider import RemoteConfigProvider
from .wiring import enable_remote_config_api

__all__ = [
    "enable_remote_config_api",
    "RemoteConfigProvider",
    "ConfigRemoteSettings",
    "make_config_openapi",
    "install_coordinate_validation_error_handler",
    "InfraMetadata",
    "RequiredInfraMetadata",
    "ConfigResolutionResponse",
    "NamingConventionResponse",
    "AllProjectsResponse",
    "CoordinateCatalogResponse",
    "LIVE_ALLOWED_NETWORKS",
    "LIVE_ALLOWED_REGIONS",
    "LIVE_ALLOWED_ISLANDS",
    "LIVE_ALLOWED_ENVIRONMENTS",
    "LIVE_ALLOWED_SPACES",
    "LIVE_ALLOWED_PROJECTS",
]
