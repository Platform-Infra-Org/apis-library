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
    │   └── routes/          # Built-in routes
    ├── static/              # Static files (Swagger UI)
    └── utils.py             # Public utility exports (BaseAPI and settings for now)
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
| `auth` | tuple | `None` | Basic auth (username, password) |
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
