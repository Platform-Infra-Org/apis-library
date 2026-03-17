"""Tashtiot APIs Library - Unified package for API connectors and FastAPI utilities.

This package consolidates infrastructure connectors (ArgoCD, Git, Vault) and
FastAPI template utilities into a single library.
"""

# Re-export connectors for convenient access
from .connectors import ArgoCD, Git, Vault, AWX
from .connectors.errors import (
    ExternalServiceError,
    ArgoCDError,
    GitError,
    VaultError,
)

from .schemas import OperationRequest, ResourceSpec, DefaultMetaSpec, NameNamespace
# Re-export FastAPI template
from .fastapi_template import general_create_app

__version__ = "0.1.0"

__all__ = [
    "ArgoCD",
    "Git",
    "Vault",
    "AWX",
    "ExternalServiceError",
    "ArgoCDError",
    "GitError",
    "VaultError",
    "general_create_app",
    "OperationRequest",
    "ResourceSpec",
    "DefaultMetaSpec",
    "NameNamespace",
]
