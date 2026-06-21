# Connectors API

The four infrastructure connector services and their standardized response models. Import the
services from the top-level package:

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault
```

See [Drive AWX, ArgoCD & Vault](../../how-to/use-awx-argocd-vault.md) and
[Read & write Bitbucket files](../../how-to/read-write-bitbucket.md) for task-oriented usage.

## AWX

::: tashtiot_apis_library.connectors.awx.service.AWX

## ArgoCD

::: tashtiot_apis_library.connectors.argocd.service.ArgoCD

## Git (Bitbucket Server)

::: tashtiot_apis_library.connectors.git.service.Git

## Vault

::: tashtiot_apis_library.connectors.vault.service.Vault

## Response models

::: tashtiot_apis_library.connectors.response_schemas.OperationResponse

::: tashtiot_apis_library.connectors.awx.models.AWXOperationResponse

::: tashtiot_apis_library.connectors.argocd.models.ArgoOperationResponse
