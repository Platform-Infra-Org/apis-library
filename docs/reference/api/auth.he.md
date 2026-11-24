# ‏API של אימות (JWT נכנס) {#auth-api-inbound-jwt}

הממשק הציבורי של אימות JWT נכנס. ייבאו את כל מה שכאן מ-`tashtiot_apis_library.fastapi_template.auth`:

```python
from tashtiot_apis_library.fastapi_template.auth import (
    get_current_claims,
    verify_token,
    JWTVerifier,
    AuthMode,
    generate_keypair,
    mint_token,
    load_keypair,
    derive_public_pem,
)
```

לדוגמאות שימוש, ראו [אבטחת ה-API שלך](../../tutorials/secure-your-api.md) ו-
[אימות טוקן מחוץ לבקשה](../../how-to/verify-a-token.md).

## get_current_claims {#get_current_claims}

::: tashtiot_apis_library.fastapi_template._internal.security.dependency.get_current_claims

## verify_token {#verify_token}

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.verify_token

## JWTVerifier {#jwtverifier}

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.JWTVerifier

## AuthMode {#authmode}

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.AuthMode

## יצירת מפתחות וטוקנים {#key-token-generation}

הצד החותם שמשלים את המאמת (ראו את ה-[CLI](../cli.md) לעטיפת שורת הפקודה).

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.generate_keypair

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.mint_token

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.load_keypair

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.derive_public_pem

## אבני בניין ברמה נמוכה {#lower-level-building-blocks}

רכיבי המימוש שמאחורי שני המתגים. בדרך כלל לא משתמשים בהם ישירות, כי `general_create_app(enable_auth=True)`
מחברת אותם, אבל הם מתועדים כאן לשם השלמות.

### AuthMiddleware {#authmiddleware}

ה-middleware שאוכף אימות bearer על כל בקשה שלא הוחרגה.

::: tashtiot_apis_library.fastapi_template._internal.security.middleware.AuthMiddleware

### get_verifier {#get_verifier}

מחזירה `JWTVerifier` (ראו למעלה) שמור במטמון עבור ההגדרות הנתונות. הוא נבנה בעליית האפליקציה, כך
שקונפיגורציה שגויה נכשלת מיד.

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.get_verifier

### discover_jwks_uri {#discover_jwks_uri}

מאתרת את ה-`jwks_uri` של ספק מתוך מסמך ה-discovery של OIDC שלו. עליה נשען `AUTH_OIDC_ISSUER`.

::: tashtiot_apis_library.fastapi_template._internal.security.oidc.discover_jwks_uri
