"""Public interface for the connectors subpackage.

This module provides async clients for ArgoCD, Git providers, HashiCorp Vault,
and AWX (Ansible Workflow Engine).
"""

from .argocd import ArgoCD
from .argocd.models import ArgoOperationResponse
from .awx import AWX
from .awx.models import AWXOperationResponse
from .errors import (
    ArgoCDError,
    AWXError,
    ExternalServiceError,
    GitError,
    VaultError,
)
from .git import Git
from .response_schemas import OperationResponse
from .vault import Vault

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
    "OperationResponse",
    "AWXOperationResponse",
    "ArgoOperationResponse",
]
