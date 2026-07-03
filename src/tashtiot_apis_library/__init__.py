"""Tashtiot APIs Library - Unified package for API connectors and FastAPI utilities.

This package consolidates infrastructure connectors (ArgoCD, Git, Vault) and
FastAPI template utilities into a single library.
"""

# Re-export connectors for convenient access
from .connectors import AWX, ArgoCD, Git, Vault
from .connectors.errors import (
    ArgoCDError,
    AWXError,
    ExternalServiceError,
    GitError,
    VaultError,
)

# Re-export FastAPI template
from .fastapi_template import general_create_app
from .fastapi_template.errors import AuthConfigError, SSOError, TokenError
from .schemas import (
    DefaultMetaSpec,
    InfraOperationRequest,
    NameNamespace,
    OperationRequest,
    RequiredInfraOperationRequest,
    ResourceSpec,
)

__all__ = [
    "ArgoCD",
    "Git",
    "Vault",
    "AWX",
    "ExternalServiceError",
    "ArgoCDError",
    "GitError",
    "VaultError",
    "AWXError",
    "AuthConfigError",
    "TokenError",
    "SSOError",
    "general_create_app",
    "OperationRequest",
    "ResourceSpec",
    "DefaultMetaSpec",
    "NameNamespace",
    "InfraOperationRequest",
    "RequiredInfraOperationRequest",
]
