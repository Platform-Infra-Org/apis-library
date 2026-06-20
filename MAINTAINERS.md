# Developer Guide For The Junior Platform Developer

Welcome to the **tashtiot_apis_library** package! This guide will help you understand the codebase structure and how to maintain and extend it effectively.

---

## Table of Contents

1. [Project Structure Overview](#project-structure-overview)
2. [Modular Python Code & Relative Imports](#modular-python-code--relative-imports)
3. [Connectors Architecture](#connectors-architecture)
4. [FastAPI Template Components](#fastapi-template-components)

---

## Project Structure Overview

```
tashtiot_apis_library/
├── __init__.py              # Root exports (ArgoCD, Git, Vault, AWX, general_create_app)
├── connectors/              # Infrastructure clients
│   ├── argocd/              # ArgoCD connector
│   ├── awx/                 # AWX connector
│   ├── git/                 # Bitbucket connector
│   ├── vault/               # HashiCorp Vault connector
│   ├── errors.py            # Common error hierarchy
│   └── response_schemas.py  # Shared response models
└── fastapi_template/        # FastAPI application factory
    ├── _internal/           # Implementation details
    │   ├── middlewares/     # Request/response middleware
    │   ├── utils/           # Settings & logging
    │   ├── metrics/         # Metrics
    │   ├── database/        # BaseAPI client
    │   ├── security/        # Auth: verifier, oidc discovery, middleware, keygen, SSO client
    │   ├── openapi.py       # Swagger "Authorize" tab injection
    │   └── routes/          # Built-in routes
    ├── config_api/          # Remote Config capability (upstream Config API proxy)
    ├── static/              # Static files (Swagger UI)
    ├── errors.py            # Public auth error types (AuthConfigError, TokenError, SSOError)
    ├── security.py          # Public outbound SSO helpers (PyJWT-free import path)
    └── utils.py             # Public utility exports (BaseAPI, settings, auth helpers)
```

---

## Modular Python Code & Relative Imports

### What Are Relative Imports?

Relative imports use dots (`.`) to navigate the package hierarchy. They're essential for maintaining a modular, self-contained package.

```python
# Absolute import (external package)
from pydantic import BaseModel

# Relative imports (within our package)
from .models import ArgoApplication      # Same directory
from ..errors import ArgoCDError         # Parent directory
from ...fastapi_template.utils import BaseAPI  # Up 3 levels, down into fastapi_template
```

### The Dot System

| Syntax | Meaning | Example |
|--------|---------|---------|
| `.module` | Same directory | `from .client import ArgoCDClient` |
| `..module` | Parent directory | `from ..errors import ArgoCDError` |
| `...module` | Grandparent directory | Rare, but possible |

### Why Relative Imports Matter

1. **Portability** - The package works regardless of where it's installed
2. **Refactoring Safety** - Renaming the top-level package doesn't break internal imports
3. **Clear Dependencies** - You can see the relationship between modules at a glance

### Real Example from Our Codebase

From `connectors/argocd/service.py`:

```python
# Go up one level (..) to connectors/, then import errors
from ..errors import ArgoCDError

# Same directory (argocd/) - import the client layer
from .client import ArgoCDClient

# Same directory - import data models
from .models import ArgoApplication, ArgoApplicationSpec
```

### Common Mistakes to Avoid

```python
# ❌ Wrong: Absolute path to internal module
from tashtiot_apis_library.connectors.argocd.models import ArgoApplication

# ✅ Correct: Relative import
from .models import ArgoApplication
```

---

## Connectors Architecture

### The Service → Client → Models Pattern

Every connector follows a **three-layer architecture**:

```
┌─────────────────────────────────────────────────────┐
│                    service.py                       │
│  High-level business logic (e.g., wait_for_update)  │
│  Users interact with this layer                     │
└────────────────────────┬────────────────────────────┘
                         │ uses
                         ▼
┌─────────────────────────────────────────────────────┐
│                    client.py                        │
│  Low-level HTTP calls (GET, POST, PATCH)            │
│  Handles response parsing and error conversion      │
└────────────────────────┬────────────────────────────┘
                         │ uses
                         ▼
┌─────────────────────────────────────────────────────┐
│                    models.py                        │
│  Pydantic models for request/response validation    │
│  Type safety and data serialization                 │
└─────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### 1. `models.py` - Data Layer

Defines **Pydantic models** for typed data validation:

```python
# From connectors/argocd/models.py
from pydantic import BaseModel, Field

class ArgoApplicationStatus(BaseModel):
    """Aggregated status information for an Argo CD application."""
    sync: Optional[ArgoSyncInfo] = None
    health: Optional[ArgoHealthInfo] = None
    reconciled_at: Optional[str] = Field(default=None, alias="reconciledAt")
```

**Key Points:**
- Use `Field(alias="..."` for JSON keys that differ from Python conventions
- Use `model_config = ConfigDict(extra="allow")` to ignore unexpected fields
- Models are self-documenting with docstrings

#### 2. `client.py` - HTTP Layer

Handles raw HTTP calls using `BaseAPI`:

```python
# From connectors/argocd/client.py
from tashtiot_apis_library.fastapi_template.utils import BaseAPI
from ..errors import ArgoCDError
from .models import ArgoApplication

class ArgoCDClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        headers = {"Authorization": f"Bearer {api_key}"}
        self.client = BaseAPI(base_url, headers=headers).client

    async def get_app(self, app_name: str) -> ArgoApplication:
        response = await self.api.get(f"/api/v1/applications/{app_name}")
        response_json = response.json()
        
        # Convert HTTP errors to typed exceptions
        if response.status_code >= 400:
            raise ArgoCDError(response.status_code, response_json.get("message"))
        
        # Parse response into typed model
        return ArgoApplication.model_validate(response_json)
```

**Key Points:**
- Always use `BaseAPI` for HTTP calls (it handles timeouts, headers, etc.)
- Convert HTTP errors to typed exceptions (e.g., `ArgoCDError`)
- Return parsed Pydantic models, not raw dictionaries

#### 3. `service.py` - Business Logic Layer

Provides high-level operations users actually need:

```python
# From connectors/argocd/service.py
class ArgoCD:
    """Convenience wrapper for high-level Argo CD interactions."""

    def __init__(self, base_url: str, api_key: str, application_set_timeout: int) -> None:
        self.client = ArgoCDClient(base_url, api_key)  # Compose the client layer
        self.application_set_timeout = application_set_timeout

    async def wait_for_update(self, app_name: str) -> ArgoApplication:
        """Wait until the ArgoCD Application shows a new update."""
        current = await self.client.get_app(app_name)
        # ... polling logic ...
        return updated_app

    async def sync(self, app_name: str) -> None:
        """Trigger a sync operation."""
        await self.client.sync_app(app_name)
```

**Key Points:**
- The Service class **composes** the Client class (not inherits)
- Provides meaningful method names (`wait_for_update` vs raw `get_app`)
- Contains business logic like polling, retries, and orchestration

### Error Hierarchy

All connectors use a shared error system from `connectors/errors.py`:

```python
ExternalServiceError          # Base class for all connector errors
├── ArgoCDError               # ArgoCD-specific errors
├── GitError                  # Git/Bitbucket errors
├── VaultError                # Vault errors
└── AWXError                  # AWX (Ansible Tower) errors
```

Each error includes `status_code` and `detail` for consistent error handling.

### Adding a New Connector

1. Create a new directory: `connectors/myservice/`
2. Create the three files:
   - `models.py` - Pydantic models for the API
   - `client.py` - Low-level HTTP calls using `BaseAPI`
   - `service.py` - High-level business logic
3. Add `__init__.py` to export the main class
4. Add a new error class in `connectors/errors.py`
5. Export from `connectors/__init__.py`

### Adding a Capability to an Existing Connector

When you need to add a new method to an existing connector (e.g., adding `delete_app` to ArgoCD):

#### Step 1: Add Models (if needed)

If the new capability uses new data structures, add them to `models.py`:

```python
# connectors/argocd/models.py
class ArgoDeleteResponse(BaseModel):
    """Response from deleting an ArgoCD application."""
    deleted: bool
    app_name: str
```

#### Step 2: Add Client Method

Add the low-level HTTP call to `client.py`:

```python
# connectors/argocd/client.py
async def delete_app(self, app_name: str) -> None:
    """Delete an application from ArgoCD."""
    uri = f"/api/v1/applications/{app_name}"
    response = await self.client.delete(uri)
    _handle_response(response.json(), response.status_code)
```

#### Step 3: Add Service Method

Expose the capability in `service.py` with business logic:

```python
# connectors/argocd/service.py
async def delete_application(self, app_name: str, wait: bool = True) -> None:
    """Delete an ArgoCD application and optionally wait for deletion."""
    logger.info(f"Deleting application {app_name}")
    await self.client.delete_app(app_name)
    
    if wait:
        await self.wait_for_app_deletion(app_name)
```

#### Step 4: Update Exports (if adding new models)

If you added new models, export them in `__init__.py`:

```python
# connectors/argocd/__init__.py
from .models import ArgoDeleteResponse  # Add to existing imports
```

#### Key Questions to Ask

- **Does this need a client method?** If it's a new HTTP endpoint, yes.
- **Does this need new models?** If the request/response has a new structure, yes.
- **What business logic is needed?** Retries, waiting, validation, error handling?

---

## FastAPI Template Components

### `general_create_app()` - The Application Factory

```python
from tashtiot_apis_library import general_create_app

app = general_create_app(
    enable_logging_middleware=True,        # Log all requests/responses
    enable_time_recording_middleware=True, # Add processing time header
    enable_exception_handlers=True,        # Use standard error responses
    enable_metrics_route=True,             # Prometheus metrics at /metrics
    enable_swagger_routes=True,            # Swagger UI at /docs
    enable_probe_routes=True,              # Health checks at /healthz
    enable_auth=False,                     # Inbound JWT auth (also needs AUTH_ENABLED=true)
)
```

### Middlewares

Middlewares wrap every request/response cycle. They're defined in `_internal/middlewares/`:

#### TimeRequestsMiddleware

Records how long each request takes:

```python
class TimeRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.perf_counter_ns()
        response = await call_next(request)
        process_time = time.perf_counter_ns() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
```

#### LogRequestsMiddleware

Logs incoming requests and outgoing responses:

```python
class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Log incoming request
        logger.info(f"{request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Log response with timing
        process_time = response.headers.get("X-Process-Time")
        logger.info(f"{request.method} {request.url.path} {response.status_code} {process_time}")
        
        return response
```

**Note:** Paths in `LOG_REQUEST_EXCLUDE_PATHS` (like `/metrics`, `/healthz`) are logged at DEBUG level to reduce noise.

#### Exception Handlers

Standardizes error responses across the application:

| Exception Type | HTTP Code | Response |
|---------------|-----------|----------|
| `HTTPException` | varies | `{"detail": "..."}` |
| `RequestValidationError` | 422 | `{"detail": [...errors...]}` |
| Any other `Exception` | 500 | `{"detail": "Internal Server Error"}` |

All exceptions are logged with full traceback for debugging.

### Global Logger Format

The logging system uses **Loguru** with a consistent format:

```
2026-01-12 18:30:45.123 | INFO     | app.services.user:create:42 - User created successfully
```

Format breakdown:
```
{timestamp} | {level} | {module}:{function}:{line} - {message}
```

The logger is configured in `_internal/utils/logger.py`:

```python
def base_formatter(record: dict) -> str:
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level:<8}</level> | "
        f"<cyan>{location}</cyan> - "
        "<level>{message}</level>\n"
    )
```

**Key Features:**
- Automatically extracts module/function/line from call site
- Exception traces show project-relevant frames, not library internals
- Uvicorn logs are redirected through the same formatter

### BaseAPI - HTTP Client Wrapper

`BaseAPI` is a reusable async HTTP client wrapper around `httpx`:

```python
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

class MyServiceAPI:
    def __init__(self, base_url: str, token: str) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        self.api = BaseAPI(base_url, headers=headers).client

    async def get_data(self) -> dict:
        response = await self.api.get("/data")
        return response.json()
```

**BaseAPI Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | str | required | API base URL |
| `headers` | dict | `{}` | Default headers for all requests |
| `auth` | tuple \| `httpx.Auth` | `None` | Basic auth `(username, password)`, or any `httpx.Auth` (e.g. the SSO bearer auth) |
| `timeout` | float | `10.0` | Request timeout in seconds |
| `verify` | bool | `False` | Verify SSL certificates |

**Context Manager Usage (for connection reuse):**

```python
async with BaseAPI(base_url, headers=headers) as client:
    response1 = await client.get("/endpoint1")
    response2 = await client.get("/endpoint2")
    # Connection is reused for both requests
```

---

## Security Module (`_internal/security/`)

The security package handles **both directions** of authentication. Everything is configured from
`AUTH_*` / `AUTH_SSO_*` settings (`_internal/utils/config.py`) and re-exported lazily from
`fastapi_template/utils.py` (importing `JWTVerifier`, the SSO client, or keygen pulls in PyJWT /
cryptography / httpx-auth only on demand). The error types are exposed publicly via
`fastapi_template/errors.py` (and the top-level package), mirroring `connectors/errors.py` — never
import them from `_internal`.

| File | Responsibility |
|------|----------------|
| `errors.py` | `AuthConfigError` (startup misconfig), `TokenError` (inbound verify failure), `SSOError` (outbound token-acquisition failure) |
| `verifier.py` | `JWTVerifier` (HS256 / local-pubkey / JWKS), `get_verifier` (memoized), `verify_token()` convenience |
| `oidc.py` | `discover_jwks_uri()` — resolves a provider's `jwks_uri` from `<issuer>/.well-known/openid-configuration` (backs `AUTH_OIDC_ISSUER`) |
| `middleware.py` | `AuthMiddleware` — enforces bearer auth on every non-excluded request |
| `dependency.py` | `get_current_claims` — FastAPI dependency returning the verified claims |
| `keygen.py` | RSA keypair + dev-token generation; backs the `gen-auth-material` CLI |
| `sso.py` | Outbound OAuth2 `client_credentials` token client + httpx auth |
| (`../openapi.py`) | Injects the bearer security scheme so Swagger shows the **Authorize** tab |

### Inbound verification (server side)

`AuthMiddleware` extracts `Authorization: Bearer <token>`, verifies it via `JWTVerifier`, and stores
the claims on `request.state.user`. It is wired in **only** under a dual-gate — the code flag
`enable_auth=True` **and** the runtime switch `AUTH_ENABLED=true` — so the master switch can disable
auth without a code change. The verifier auto-selects its mode from whichever single material is
configured (`AUTH_HS256_SECRET` | `AUTH_JWKS_URL`/`AUTH_OIDC_ISSUER` | `AUTH_PUBLIC_KEY_PEM`/`PATH`)
and raises `AuthConfigError` at startup if zero or more than one is set. `AUTH_JWKS_URL` and
`AUTH_OIDC_ISSUER` both select JWKS mode and count as **one** material group: an explicit URL wins,
otherwise `oidc.py`'s `discover_jwks_uri` resolves the `jwks_uri` from the issuer's well-known
document at startup (and the issuer becomes the default expected `iss`).

By default the verifier **requires an `exp` claim** (`_decode_kwargs` sets `require=["exp"]`). Set
`AUTH_REQUIRE_EXP=false` to accept non-expiring tokens (e.g. a forever `gen-auth-material` token).
Relaxing the *requirement* does not stop validating an `exp` that is present, so expired tokens are
still rejected; a token lacking `exp` under the default surfaces as
`TokenError("Token is missing required 'exp' claim")`.

```python
# Verify a token anywhere (workers, scripts) — same code path as the middleware:
from tashtiot_apis_library.fastapi_template.utils import verify_token
claims = verify_token(token)        # raises TokenError on failure
```

Under the same dual-gate, `_internal/openapi.py` wraps `app.openapi` to add a global `BearerAuth`
security scheme — that's what makes Swagger's **Authorize** tab appear. It lives outside the
`security/` package so it doesn't force the PyJWT import.

### Outbound SSO client (client side)

`sso.py` implements the OAuth2 `client_credentials` grant for calling *other* services. Layers,
mirroring the connector pattern:

- **`SSOConfig`** — client-side config (token URL, credentials, scope, audience, …). Pass an explicit
  instance to talk to several upstreams that each need a different identity/audience **independently
  of the settings singleton**; `SSOConfig.from_settings(settings)` bridges the legacy `AUTH_SSO_*`
  path. The SSO helpers dual-accept an `SSOConfig`, a settings object, or `None` (package settings).
- **`TokenResponse`** — Pydantic model of the token endpoint response.
- **`SSOTokenClient`** — fetches, caches, and refreshes the access token (guarded by an
  `asyncio.Lock`); `get_token()` / `auth_header()`. `get_sso_token_client(source)` memoizes it by the
  object's identity, so build one `SSOConfig` per remote and reuse it to share the token cache.
- **`SSOClientCredentialsAuth(httpx.Auth)`** — injects the bearer on every request and, on a `401`,
  forces one refresh and retries.
- **`StaticBearerAuth(httpx.Auth)`** — attaches a fixed, long-lived bearer token (no token endpoint,
  no refresh) for upstreams secured by a service token.

These outbound helpers are re-exported from the public **`fastapi_template/security.py`** module
(`from ...fastapi_template.security import sso_authenticated_api, SSOConfig, StaticBearerAuth, …`),
which imports straight from `_internal.security.sso` so consumers that only mint outbound tokens
don't drag in the inbound-JWT machinery (PyJWT). They are also re-exported lazily from
`fastapi_template/utils.py`.

The headline helper plugs that auth into `BaseAPI` (whose `auth=` now accepts any `httpx.Auth`), so
you get a connector-style client with **automatic per-request token refresh**:

```python
from tashtiot_apis_library.fastapi_template.utils import sso_authenticated_api

async with sso_authenticated_api("https://downstream.example.com") as client:
    resp = await client.get("/protected")   # bearer added & refreshed automatically
```

> `client_credentials` issues **no** OAuth2 refresh token (RFC 6749 §4.4.3) — "refresh" means
> re-running the grant with the standing client secret.

### Generating dev key material

`keygen.py` is the signing-side companion to `JWTVerifier`, exposed both as importable functions
(`generate_keypair`, `mint_token`, `load_keypair`, `derive_public_pem`) and the `gen-auth-material`
console script (registered in `pyproject.toml` `[project.scripts]`). Useful for exercising
local-pubkey auth locally.

`mint_token`'s `expires_minutes` defaults to `None`, which **omits the `exp` claim** entirely (a
non-expiring token); pass an `int` for a normally-expiring one. Because the verifier requires `exp`
by default, a forever token is only accepted when the service sets `AUTH_REQUIRE_EXP=false` — the
CLI prints that hint in its `.env` config block when minting a non-expiring token.

---

## Remote Config Capability (`config_api/`)

A self-contained, **opt-in** capability that turns the app into a thin authenticated proxy to an
upstream Config API. It is wired by one call, `enable_remote_config_api(app, …)`, and is imported
**lazily** from `fastapi_template/__init__.py` so apps that don't use it never pull in its
dependency (`aiocache`). Files:

| File | Responsibility |
|------|----------------|
| `wiring.py` | `enable_remote_config_api(app, …)` — builds the provider, installs the dynamic-enum OpenAPI patcher + the coordinate-validation→422 handler, and registers the background poller. Returns the `RemoteConfigProvider`. |
| `provider.py` | `RemoteConfigProvider` — forwards coordinates to the upstream's `/config`, `/naming`, `/projects` routes (auth via an injected `httpx.Auth`), caches results (`aiocache` MEMORY, `cache_ttl`s), and runs `crawl_and_sync_keys` / `start_periodic_polling`. Upstream transport/≥400 errors → `502`; `404` → empty result. |
| `schemas.py` | `InfraMetadata` / `RequiredInfraMetadata` coordinate models, the response models, and the mutable module-level `LIVE_ALLOWED_*` allowlists that drive **both** the field validators and the OpenAPI enums. Validators are permissive when their allowlist is empty (pre-poll). |
| `conf.py` | `ConfigRemoteSettings` — `CONFIG_REMOTE_*` env config selecting the outbound auth method (`sso` / `bearer` / `none`); `resolve_auth()` returns `(httpx.Auth, base_api_kwargs)`. |
| `openapi.py` | `make_config_openapi(app, …)` — **wraps** the existing `app.openapi` (preserving the bearer-auth scheme) to inject the live allowlists as `enum` dropdowns on the config/naming coordinate query params. |
| `errors.py` | `install_coordinate_validation_error_handler(app)` — re-emits a `pydantic.ValidationError` from a depended-on coordinate model as FastAPI's standard 422 (instead of an uncaught 500). |

**Background-task wiring note.** `general_create_app` now seeds a *mutable* registry
`app.state.async_background_tasks` (read by the lifespan at startup) rather than capturing the
constructor argument. That's what lets `enable_remote_config_api` — called *after* the app is built —
append its allowlist poller and still have the lifespan launch it. If the app wasn't built by
`general_create_app`, the poller is registered but warns that it won't auto-start.

---

## Quick Reference

### Import Patterns

```python
# Top-level exports (recommended for external use)
from tashtiot_apis_library import ArgoCD, Git, Vault, general_create_app

# Specific connector imports
from tashtiot_apis_library.connectors import ArgoCD, Git, Vault
from tashtiot_apis_library.connectors.errors import ExternalServiceError, ArgoCDError

# FastAPI utilities
from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings

# Inbound-auth utilities (lazy-loaded)
from tashtiot_apis_library.fastapi_template.utils import (
    get_current_claims,        # FastAPI dependency for verified claims
    verify_token,              # standalone server-side token check
    JWTVerifier,               # inbound verifier (HS256 / local-pubkey / JWKS, incl. OIDC discovery)
    generate_keypair, mint_token,  # dev key/token generation
)

# Outbound SSO helpers — public, PyJWT-free import path (also on .utils)
from tashtiot_apis_library.fastapi_template.security import (
    sso_authenticated_api,     # outbound SSO client (auto-refresh bearer)
    get_sso_token_client,      # outbound SSO token provider
    SSOConfig,                 # explicit per-remote client_credentials config
    StaticBearerAuth,          # fixed long-lived bearer auth
)

# Remote Config capability (lazy — pulls in aiocache only when used)
from tashtiot_apis_library.fastapi_template import enable_remote_config_api
from tashtiot_apis_library.fastapi_template.config_api import (
    RemoteConfigProvider, RequiredInfraMetadata, InfraMetadata,
)

# Auth error types — import from fastapi_template.errors (mirrors connectors/errors.py).
# Deliberately NOT part of the top-level package's public export.
from tashtiot_apis_library.fastapi_template.errors import (
    AuthConfigError, TokenError, SSOError,
)
```

### Creating a New Feature Checklist

- [ ] Follow the Service → Client → Models pattern
- [ ] Use relative imports within the package
- [ ] Create typed Pydantic models for all data structures
- [ ] Convert external errors to typed exceptions
- [ ] Use `BaseAPI` for HTTP calls
- [ ] Add logging using `from loguru import logger`
- [ ] Export new classes from `__init__.py`
- [ ] Write tests in the corresponding `tests/` directory

---

## Adding a New Feature to FastAPI Template

When extending the FastAPI template with new functionality:

### Adding a New Middleware

1. **Create the middleware file** in `_internal/middlewares/`:

```python
# _internal/middlewares/my_middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from loguru import logger

class MyCustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pre-request logic
        logger.debug(f"Before request: {request.url.path}")
        
        response = await call_next(request)
        
        # Post-response logic
        logger.debug(f"After response: {response.status_code}")
        
        return response
```

2. **Register in middlewares/__init__.py**:

```python
# _internal/middlewares/__init__.py
from .my_middleware import MyCustomMiddleware

def add_middlewares(app, *, enable_my_middleware: bool = True, ...):
    if enable_my_middleware:
        app.add_middleware(MyCustomMiddleware)
```

3. **Add parameter to general_create_app()**:

```python
# _internal/__init__.py
def general_create_app(
    *,
    enable_my_middleware: bool = True,  # Add new parameter
    ...
):
    add_middlewares(app, enable_my_middleware=enable_my_middleware, ...)
```

### Adding a New Route

1. **Create the route file** in `_internal/routes/`:

```python
# _internal/routes/my_route.py
from fastapi import APIRouter

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

@router.get("/status")
async def get_status():
    return {"status": "ok"}
```

2. **Register in routes/__init__.py**:

```python
# _internal/routes/__init__.py
from .my_route import router as my_router

def add_routers(app, *, enable_my_route: bool = True, ...):
    if enable_my_route:
        app.include_router(my_router)
```

### Adding a New Utility

For reusable utilities, add them to `_internal/utils/` or `_internal/database/`:

1. Create your utility file
2. Export from `_internal/utils/__init__.py`
3. Re-export from `fastapi_template/utils.py` for public access

### Testing Your Changes

```bash
# Run the template tests
pytest tashtiot_apis_library/fastapi_template/tests/

# Test with a sample app
python -c "from tashtiot_apis_library import general_create_app; app = general_create_app(); print('OK')"
```

---

## Need Help?

- Check existing connectors for patterns to follow
- Look at tests for usage examples
- Ask the team for code reviews on new features

Happy coding! 🚀
