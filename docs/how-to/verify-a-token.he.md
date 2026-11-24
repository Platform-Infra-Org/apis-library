# אימות טוקן מחוץ לבקשה {#verify-a-token-outside-a-request}

[ה-middleware של האימות](../tutorials/secure-your-api.md) מאמת טוקנים של בקשות HTTP נכנסות
אוטומטית. כשצריך לאמת טוקן **מחוץ** לזרימת הבקשה, ב-worker ברקע, ב-CLI או בנתיב שמקבל את הטוקן
בדרך אחרת, השתמשו בפונקציית העזר העצמאית `verify_token`.

```python
from tashtiot_apis_library.fastapi_template.auth import verify_token
from tashtiot_apis_library.fastapi_template.errors import TokenError

try:
    claims = verify_token(token)  # returns the decoded claims dict
except TokenError as exc:
    ...  # invalid signature, expired, wrong audience, etc.
```

‏`verify_token` משתמשת באותה קונפיגורציה כמו ה-middleware (היא קוראת את ה-`settings` של החבילה), כך
שהיא מכבדת את חומרי האימות ואת בדיקות ה-claims שהגדרתם דרך משתני הסביבה `AUTH_*`; ראו
[קונפיגורציה](../reference/configuration.md).

## אימות מול קונפיגורציה אחרת {#verify-against-a-different-configuration}

העבירו אובייקט הגדרות מפורש כדי לאמת מול קונפיגורציה שונה מברירת המחדל של החבילה. זה שימושי כש-
worker אחד מאמת טוקנים מכמה מנפיקים:

```python
claims = verify_token(token, settings=other_settings)
```

## אימות בצד השרת של טוקנים שהנפיק ה-SSO {#server-side-verification-of-sso-issued-tokens}

כדי לאמת טוקנים שהנפיק ספק SSO (הצד [היוצא](call-services-with-sso.md) מנפיק טוקנים שהשירות
*הזה* מקבל), השתמשו ב**מצב JWKS**: הפנו את `AUTH_JWKS_URL` ל-endpoint של ה-JWKS של הספק, והגדירו
את `AUTH_AUDIENCE` / `AUTH_ISSUER` כך שיתאימו לטוקנים שהונפקו. אחר כך אפשר להגן על נתיבים עם
ה-middleware (`enable_auth=True`) או לבדוק טוקן ישירות עם `verify_token`.

!!! warning "טוקנים שלא פגים"
    המאמת דורש claim של `exp` כברירת מחדל. כדי לקבל טוקן שנוצר בלעדיו (למשל טוקן פיתוח מ-
    [`gen-auth-material`](generate-auth-material.md)), הגדירו `AUTH_REQUIRE_EXP=false` בשירות
    המאמת. טוקן *שכן* נושא `exp` עדיין נבדק, כך שטוקנים שפגו עדיין נדחים.

## ראו גם {#see-also}

- [מידע עזר על ה-API: ‏auth](../reference/api/auth.md)
- [תכנון האימות](../explanation/authentication.md)
