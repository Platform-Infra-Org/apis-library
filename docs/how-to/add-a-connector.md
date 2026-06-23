# Add a new connector

This guide is for contributors extending the library with a new infrastructure connector. Connectors
follow a strict **three-layer pattern** so they stay consistent and portable; new ones must match it.

## The three layers

Create a package under `src/tashtiot_apis_library/connectors/<name>/` with exactly three modules:

```
connectors/<name>/
  models.py     # Pydantic request/response models
  client.py     # low-level HTTP
  service.py    # high-level class users instantiate
```

### 1. `models.py` — shapes

Pydantic models for requests and responses. Use `Field(alias="...")` for camelCase JSON keys and
`model_config = ConfigDict(extra="allow")` to tolerate unknown fields. Connector-specific response
subclasses of `OperationResponse` live here too (e.g. add a `job_id`).

### 2. `client.py` — low-level HTTP

Builds its `httpx.AsyncClient` via `BaseAPI(...).client`, converts HTTP error status codes into your
typed exception, and returns parsed Pydantic models — **never raw dicts**.

```python
from ...fastapi_template.utils import BaseAPI   # relative import — see below
from ..errors import MyServiceError
from .models import MyModel
```

### 3. `service.py` — high-level orchestration

The class users instantiate (e.g. `MyService`). It **composes** the client (does not inherit it) and
adds orchestration — polling, `wait_for_*_completion`, retries. Service methods generally return
standardized `OperationResponse` subclasses rather than raw API models.

## Conventions to follow

- **Relative imports only.** Within the package use `from ..errors import ...`,
  `from .models import ...`, `from ...fastapi_template.utils import BaseAPI`. Absolute self-imports
  (`from tashtiot_apis_library...`) are incorrect here — they break portability (the package name is
  rewritten at build time).
- **Typed errors.** Add `MyServiceError(ExternalServiceError)` to `connectors/errors.py`; the client
  raises it on `status_code >= 400`. Because `ExternalServiceError` extends `fastapi.HTTPException`,
  raising one inside a route surfaces directly as an HTTP response.
- **Standard logging.** `from loguru import logger`; INFO for user-facing operations, DEBUG for
  internal reads/polling, ERROR before raising on external failures. See
  [Logging](../explanation/logging.md).
- **Export it.** Add the service and error to the relevant `__init__.py` and to the top-level
  `tashtiot_apis_library/__init__.py` `__all__`.

Adding a capability to an existing connector is the same idea bottom-up: model (if new shapes) →
client method → service method.

## See also

- [Architecture: the three-layer connector pattern](../explanation/architecture.md)
- [Connectors API reference](../reference/api/connectors.md)
