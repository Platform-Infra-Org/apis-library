# ‏API של השגיאות {#errors-api}

שתי משפחות של חריגות טיפוסיות.

## שגיאות של מחברים {#connector-errors}

ה-clients של המחברים מעלים אותן כש-`status_code >= 400`. מחלקת הבסיס `ExternalServiceError` יורשת
מ-`fastapi.HTTPException`, כך שהעלאה שלה בתוך נתיב FastAPI הופכת ישירות לתשובת HTTP. ייבאו מ-
`tashtiot_apis_library.connectors.errors` (או את הבסיס ואת תת-המחלקות מהחבילה הראשית):

```python
from tashtiot_apis_library.connectors.errors import (
    ExternalServiceError,
    ArgoCDError,
    GitError,
    VaultError,
    AWXError,
)
```

::: tashtiot_apis_library.connectors.errors.ExternalServiceError

::: tashtiot_apis_library.connectors.errors.ArgoCDError

::: tashtiot_apis_library.connectors.errors.GitError

::: tashtiot_apis_library.connectors.errors.VaultError

::: tashtiot_apis_library.connectors.errors.AWXError

## שגיאות אימות {#auth-errors}

מנגנון האימות הנכנס/היוצא מעלה אותן. ייבאו מ-`tashtiot_apis_library.fastapi_template.errors`
(זמינות גם מהחבילה הראשית):

```python
from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError
```

::: tashtiot_apis_library.fastapi_template._internal.security.errors.AuthConfigError

::: tashtiot_apis_library.fastapi_template._internal.security.errors.TokenError

::: tashtiot_apis_library.fastapi_template._internal.security.errors.SSOError
