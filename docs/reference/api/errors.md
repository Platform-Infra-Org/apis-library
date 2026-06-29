# Errors API

Two families of typed exceptions.

## Connector errors

Raised by the connector clients on `status_code >= 400`. The base `ExternalServiceError` extends
`fastapi.HTTPException`, so raising one inside a FastAPI route surfaces directly as an HTTP response.
Import from `tashtiot_apis_library.connectors.errors` (or the base/subclasses from the top-level
package):

```python
from tashtiot_apis_library.connectors.errors import (
    ExternalServiceError, ArgoCDError, GitError, VaultError, AWXError,
)
```

::: tashtiot_apis_library.connectors.errors.ExternalServiceError

::: tashtiot_apis_library.connectors.errors.ArgoCDError

::: tashtiot_apis_library.connectors.errors.GitError

::: tashtiot_apis_library.connectors.errors.VaultError

::: tashtiot_apis_library.connectors.errors.AWXError

## Auth errors

Raised by the inbound/outbound auth machinery. Import from
`tashtiot_apis_library.fastapi_template.errors` (also available at the top-level package):

```python
from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError
```

::: tashtiot_apis_library.fastapi_template._internal.security.errors.AuthConfigError

::: tashtiot_apis_library.fastapi_template._internal.security.errors.TokenError

::: tashtiot_apis_library.fastapi_template._internal.security.errors.SSOError
