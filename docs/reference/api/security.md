# Security API (outbound SSO)

The public outbound-SSO surface. Import everything here from
`tashtiot_apis_library.fastapi_template.security`:

```python
from tashtiot_apis_library.fastapi_template.security import (
    sso_authenticated_api, sso_auth, get_sso_token_client,
    SSOConfig, SSOTokenClient, SSOClientCredentialsAuth, StaticBearerAuth, TokenResponse,
)
```

See [Call other services with SSO](../../how-to/call-services-with-sso.md) for usage.

## High-level helpers

::: tashtiot_apis_library.fastapi_template._internal.security.sso.sso_authenticated_api

::: tashtiot_apis_library.fastapi_template._internal.security.sso.sso_auth

::: tashtiot_apis_library.fastapi_template._internal.security.sso.get_sso_token_client

## Configuration & clients

::: tashtiot_apis_library.fastapi_template._internal.security.sso.SSOConfig

::: tashtiot_apis_library.fastapi_template._internal.security.sso.SSOTokenClient

## httpx auth strategies

::: tashtiot_apis_library.fastapi_template._internal.security.sso.SSOClientCredentialsAuth

::: tashtiot_apis_library.fastapi_template._internal.security.sso.StaticBearerAuth

::: tashtiot_apis_library.fastapi_template._internal.security.sso.TokenResponse
