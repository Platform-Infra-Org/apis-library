# קונפיגורציה {#configuration}

תבנית FastAPI מוגדרת כולה דרך משתני סביבה (שנטענים מסביבת התהליך או מקובץ `.env` בעזרת
`pydantic-settings`). העמוד הזה מפרט כל משתנה עם ברירת המחדל שלו.

## הגדרות ליבה {#core-settings}

| משתנה | תיאור | ברירת מחדל |
|----------|-------------|---------|
| `PORT` | הפורט של האפליקציה | `8000` |
| `LOG_LEVEL` | רמת הלוגים (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`) | `INFO` |
| `APP_NAME` | שם האפליקציה | `MyApp` |
| `DEBUG` | מצב debug של FastAPI | `false` |

דוגמה ל-`.env`:

```env
PORT=8000
LOG_LEVEL=INFO
APP_NAME=MyFastAPIApp
```

## אימות נכנס (צד השרת) {#inbound-authentication-server-side}

פעיל רק כש-`general_create_app(enable_auth=True)` **וגם** `AUTH_ENABLED=true`. הגדירו חומר אימות
אחד בדיוק (סוד HS256, ‏JWKS/OIDC, או מפתח ציבורי מקומי).

| משתנה | תיאור | ברירת מחדל |
|----------|-------------|---------|
| `AUTH_ENABLED` | המתג הראשי בזמן ריצה לאימות JWT נכנס | `false` |
| `AUTH_HEADER_NAME` | ה-header שנושא את ה-bearer token | `Authorization` |
| `AUTH_HS256_SECRET` | סוד משותף ← בוחר מצב HS256 | `None` |
| `AUTH_JWKS_URL` | ‏endpoint של JWKS/OIDC ← בוחר מצב JWKS | `None` |
| `AUTH_OIDC_ISSUER` | כתובת הבסיס של מנפיק ה-OIDC ← בוחר מצב JWKS דרך discovery; גם ערך ברירת המחדל הצפוי של `iss` | `None` |
| `AUTH_OIDC_VERIFY_SSL` | אימות TLS בשליפת מסמך ה-discovery של OIDC | `true` |
| `AUTH_OIDC_TIMEOUT` | ‏timeout (בשניות) לבקשת ה-discovery החד-פעמית של OIDC בעליית השירות | `10.0` |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | מפתח ציבורי (מוטמע או קובץ) ← בוחר מצב RS256 לא מקוון | `None` |
| `AUTH_ALGORITHMS` | אלגוריתמי חתימה מותרים (מצב HS256 כופה `["HS256"]`) | `["RS256"]` |
| `AUTH_REQUIRE_EXP` | דרישת claim של `exp`; הגדירו `false` כדי לקבל טוקנים שלא פגים | `true` |
| `AUTH_AUDIENCE` | ה-claim הצפוי של `aud` (לא נבדק כשלא מוגדר) | `None` |
| `AUTH_ISSUER` | ה-claim הצפוי של `iss` (לא נבדק כשלא מוגדר) | `None` |
| `AUTH_JWKS_CACHE_TTL` | כמה שניות לשמור במטמון את מפתחות ה-JWKS שנשלפו | `3600` |
| `AUTH_EXCLUDE_PATHS` | קידומות נתיבים שעוקפות את האימות | health/metrics/docs/… |

!!! warning "חומר אימות אחד בדיוק"
    הגדרה של אפס חומרים (כשהאימות מופעל) או של יותר מאחד מעלה `AuthConfigError` בעליית השירות, כך
    שקונפיגורציה שגויה נכשלת מיד ולא בבקשה הראשונה.

## ‏SSO יוצא (צד הלקוח) {#outbound-sso-client-side}

בשימוש של `sso_authenticated_api` / `get_sso_token_client`. שלושת הראשונים חובה.

| משתנה | תיאור | ברירת מחדל |
|----------|-------------|---------|
| `AUTH_SSO_TOKEN_URL` | ‏endpoint הטוקנים של OAuth2 | `None` |
| `AUTH_SSO_CLIENT_ID` | ה-client id של OAuth2 | `None` |
| `AUTH_SSO_CLIENT_SECRET` | ה-client secret של OAuth2 | `None` |
| `AUTH_SSO_SCOPE` | ‏scopes מופרדים ברווחים (לא נשלח כשלא מוגדר) | `None` |
| `AUTH_SSO_AUDIENCE` | הפרמטר `audience` בבקשת הטוקן (למשל Auth0) | `None` |
| `AUTH_SSO_AUTH_STYLE` | אופן העברת פרטי ההזדהות: `post` (בגוף הבקשה) או `basic` (‏HTTP Basic) | `post` |
| `AUTH_SSO_VERIFY_SSL` | אימות תעודת ה-TLS של endpoint הטוקנים | `true` |
| `AUTH_SSO_TIMEOUT` | ‏timeout לבקשת הטוקן (בשניות) | `10.0` |
| `AUTH_SSO_EXPIRY_SKEW` | חידוש הטוקן כך וכך שניות לפני שהוא פג | `30` |

ראו [קריאה לשירותים אחרים עם SSO](../how-to/call-services-with-sso.md) כדי להבין איך נקבע ה-`aud`
של השירות היעד (זה תלוי בספק).

## ‏Remote Config API (יוצא אל השירות החיצוני) {#remote-config-api-outbound-to-the-upstream}

נקרא על ידי `enable_remote_config_api` כדי להזדהות מול ה-Config API החיצוני (upstream).
‏`CONFIG_REMOTE_AUTH_METHOD` בוחר את האסטרטגיה; רק ההגדרות של השיטה שנבחרה הן חובה.

| משתנה | תיאור | ברירת מחדל |
|----------|-------------|---------|
| `CONFIG_REMOTE_AUTH_METHOD` | אסטרטגיית האימות היוצא: `sso`, `bearer` או `none` | `sso` |
| `CONFIG_REMOTE_BEARER_TOKEN` | ‏bearer token סטטי (חובה כשהשיטה היא `bearer`) | `None` |
| `CONFIG_REMOTE_SSO_TOKEN_URL` | ‏endpoint הטוקנים של OAuth2 (שיטה `sso`) | `None` |
| `CONFIG_REMOTE_SSO_CLIENT_ID` | ה-client id של OAuth2 (שיטה `sso`) | `None` |
| `CONFIG_REMOTE_SSO_CLIENT_SECRET` | ה-client secret של OAuth2 (שיטה `sso`) | `None` |
| `CONFIG_REMOTE_SSO_SCOPE` | ‏scopes מופרדים ברווחים (ב-Keycloak: נושא את ה-`aud` של השירות היעד) | `None` |
| `CONFIG_REMOTE_SSO_AUDIENCE` | הפרמטר `audience` בבקשת הטוקן (בסגנון Auth0; ‏Keycloak מתעלם ממנו) | `None` |
| `CONFIG_REMOTE_SSO_AUTH_STYLE` | אופן העברת פרטי ההזדהות: `post` או `basic` | `post` |
| `CONFIG_REMOTE_SSO_VERIFY_SSL` | אימות תעודת ה-TLS של endpoint הטוקנים | `true` |
| `CONFIG_REMOTE_SSO_TIMEOUT` | ‏timeout לבקשת הטוקן (בשניות) | `10.0` |
| `CONFIG_REMOTE_SSO_EXPIRY_SKEW` | חידוש הטוקן כך וכך שניות לפני שהוא פג | `30` |
