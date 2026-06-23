# Drive AWX, ArgoCD & Vault

Recipes for the remaining three connectors. All methods are async; construct each client with its
base URL and a token.

## AWX — launch a job and await it

```python
from tashtiot_apis_library import AWX

awx = AWX(base_url="https://awx.example.com", token="token")

# Launch a job template; returns an AWXOperationResponse (carries job_id)
response = await awx.launch_job(job_template_id=1, extra_vars={"env": "prod"})

# Block until it finishes, then inspect the standardized result
result = await awx.wait_for_job_completion(response.job_id)
if result.status == "successful":
    print(f"Job {result.job_id} finished!")
```

`launch_workflow_job` / `wait_for_workflow_completion` do the same for workflow job templates, and
`get_job_status(job_id)` polls a single status.

!!! tip "Standardized responses"
    Service methods return `OperationResponse` subclasses, not raw API payloads. The base carries
    `status`, `status_code`, `return_code`, and `stdout`; `AWXOperationResponse` adds `job_id` and
    `ArgoOperationResponse` adds `app_name`. See the [Schemas reference](../reference/api/schemas.md).

## ArgoCD — sync an app and wait for it

```python
from tashtiot_apis_library import ArgoCD

argo = ArgoCD(
    base_url="https://argo.example.com",
    api_key="token",
    application_set_timeout=30,   # seconds to wait for sync/delete
)

await argo.sync("my-app")
app = await argo.wait_for_update("my-app")        # ArgoApplication once healthy/synced
status = await argo.get_app_status("my-app")      # ArgoOperationResponse
```

Other helpers include `wait_for_app_creation`, `wait_for_app_deletion`, `get_app_values`,
`modify_values`, `get_app_parameters`, and `modify_parameters`.

## Vault — read and write secrets

```python
from tashtiot_apis_library import Vault

vault = Vault(base_url="https://vault.example.com", token="token")

secret = await vault.read_secret("secret/data/myapp")     # VaultSecret (.data, .metadata)
await vault.write_secret("secret/data/myapp", {"api_key": "value"})
await vault.delete_secret("secret/data/myapp")
```

`write_secret` accepts a plain mapping, a `VaultSecretPayload`, or any Pydantic model (it is dumped
to a dict, dropping `None`s).

## Errors

Each connector raises its own typed error on `4xx`/`5xx` — `AWXError`, `ArgoCDError`, `VaultError` —
all subclasses of `ExternalServiceError(HTTPException)`. Import them from
`tashtiot_apis_library.connectors.errors`.

## See also

- [Connectors API reference](../reference/api/connectors.md)
- [Read & write Bitbucket files](read-write-bitbucket.md)
