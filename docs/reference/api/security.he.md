# ‏API של אבטחה (SSO יוצא) {#security-api-outbound-sso}

הממשק הציבורי של SSO יוצא. ייבאו את כל מה שכאן מ-
`tashtiot_apis_library.fastapi_template.security`:

```python
from tashtiot_apis_library.fastapi_template.security import (
    sso_authenticated_api,
    sso_auth,
    get_sso_token_client,
    SSOConfig,
    SSOTokenClient,
    SSOClientCredentialsAuth,
    StaticBearerAuth,
    TokenResponse,
)
```

לדוגמאות שימוש, ראו [קריאה לשירותים אחרים עם SSO](../../how-to/call-services-with-sso.md).

## פונקציות עזר ברמה גבוהה {#high-level-helpers}

::: tashtiot_apis_library.fastapi_template._internal.security.sso.sso_authenticated_api

::: tashtiot_apis_library.fastapi_template._internal.security.sso.sso_auth

::: tashtiot_apis_library.fastapi_template._internal.security.sso.get_sso_token_client

## קונפיגורציה ולקוחות {#configuration-clients}

::: tashtiot_apis_library.fastapi_template._internal.security.models.SSOConfig

::: tashtiot_apis_library.fastapi_template._internal.security.sso.SSOTokenClient

## אסטרטגיות אימות של httpx {#httpx-auth-strategies}

::: tashtiot_apis_library.fastapi_template._internal.security.sso.SSOClientCredentialsAuth

::: tashtiot_apis_library.fastapi_template._internal.security.sso.StaticBearerAuth

::: tashtiot_apis_library.fastapi_template._internal.security.models.TokenResponse
