# Architecture

This page explains how the package is organised and why.

## Two independent toolsets, one package

The library ships two largely independent toolsets under one distribution:

1. **Infrastructure connectors** (`connectors/`) — async clients for ArgoCD, AWX, Bitbucket Server,
   and Vault.
2. **FastAPI template** (`fastapi_template/`) — the `general_create_app` application factory and its
   middleware, metrics, probes, auth, and Remote Config capability.

They're bundled together for convenience, but a consumer can use either alone. The one dependency
direction between them: connectors depend on `fastapi_template.utils.BaseAPI` (the shared outbound
HTTP wrapper), so **the FastAPI template is a dependency of the connectors, not the reverse.**

## The three-layer connector pattern

Every connector under `connectors/<name>/` is split into exactly three modules, and new ones must
follow suit (see [Add a new connector](../how-to/add-a-connector.md)):

| Layer | File | Responsibility |
|---|---|---|
| **Models** | `models.py` | Pydantic request/response shapes. Aliases for camelCase JSON; tolerate unknown fields. |
| **Client** | `client.py` | Low-level HTTP via `BaseAPI`. Converts error status codes into typed exceptions; returns parsed models, never raw dicts. |
| **Service** | `service.py` | The high-level class users instantiate (`AWX`, `Git`, …). **Composes** the client and adds orchestration: polling, `wait_for_*`, retries. |

Adding a capability means touching the layers bottom-up: model (if new shapes) → client method →
service method.

### Standardized responses and errors

Service methods return `OperationResponse` subclasses (`status`, `status_code`, `return_code`,
`stdout`) rather than raw API payloads — `AWXOperationResponse` adds `job_id`, `ArgoOperationResponse`
adds `app_name`. Errors are a parallel hierarchy: `ExternalServiceError(HTTPException)` subclassed per
connector (`ArgoCDError`, `GitError`, `VaultError`, `AWXError`). Because they extend
`fastapi.HTTPException`, raising one inside a route surfaces directly as an HTTP response.

## The public surface vs `_internal`

The FastAPI template keeps a deliberately narrow public surface; everything under `_internal/` is
private implementation. The public modules are organised **by concern**, each a stable import home:

| Module | Concern |
|---|---|
| `fastapi_template` | `general_create_app` (+ lazy `enable_remote_config_api`) |
| `fastapi_template.utils` | infra utilities — `BaseAPI`, `settings` |
| `fastapi_template.auth` | inbound JWT — `get_current_claims`, `JWTVerifier`, `verify_token`, `AuthMode`, keygen |
| `fastapi_template.security` | outbound SSO — `sso_authenticated_api`, `SSOConfig`, `StaticBearerAuth`, … |
| `fastapi_template.errors` | the auth error types |

These public modules are thin re-export facades over `_internal`. This split lets the heavy
dependencies stay lazy (see [Authentication design](authentication.md) and [Logging](logging.md)) and
gives consumers a small, intention-revealing API to import from.

## Imports within the package

Internal code uses **relative imports** (`from .client import ...`, `from ..errors import ...`,
`from ...fastapi_template.utils import BaseAPI`). Absolute self-imports are avoided because the
distribution name is rewritten at build time — an absolute self-import would be fragile.
