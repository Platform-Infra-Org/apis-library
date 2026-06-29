# Connectors API

The four infrastructure connectors. Each is a three-layer stack — a high-level **service** users
instantiate, a low-level **client**, and **Pydantic models** for requests/responses (see
[Architecture](../../explanation/architecture.md)). Import the services from the top-level package:

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault
```

The clients and models are available from each connector's subpackage, e.g.
`from tashtiot_apis_library.connectors.awx import AWXClient, AWXJob`.

See [Drive AWX, ArgoCD & Vault](../../how-to/use-awx-argocd-vault.md) and
[Read & write Bitbucket files](../../how-to/read-write-bitbucket.md) for task-oriented usage.

## Services

::: tashtiot_apis_library.connectors.awx.service.AWX

::: tashtiot_apis_library.connectors.argocd.service.ArgoCD

::: tashtiot_apis_library.connectors.argocd.service.evaluate_argo_result

::: tashtiot_apis_library.connectors.git.service.Git

::: tashtiot_apis_library.connectors.vault.service.Vault

## Low-level clients

The HTTP layer each service composes. Use these directly only if you need raw access below the
service helpers.

::: tashtiot_apis_library.connectors.awx.client.AWXClient

::: tashtiot_apis_library.connectors.argocd.client.ArgoCDClient

::: tashtiot_apis_library.connectors.git.client.GitClient

::: tashtiot_apis_library.connectors.vault.client.VaultClient

## Standardized responses

The base response model returned by service operations (connector-specific subclasses are in the
per-connector models below).

::: tashtiot_apis_library.connectors.response_schemas.OperationResponse

## Models

The request/response Pydantic models for each connector.

### AWX

::: tashtiot_apis_library.connectors.awx.models

### ArgoCD

::: tashtiot_apis_library.connectors.argocd.models

### Git (Bitbucket Server)

::: tashtiot_apis_library.connectors.git.models

### Vault

::: tashtiot_apis_library.connectors.vault.models
