# תכנון האימות {#authentication-design}

לספרייה יש שני נושאי אימות נפרדים שקל לבלבל ביניהם, ולכן הם נמצאים במודולים ציבוריים נפרדים:

- **נכנס** (`fastapi_template.auth`): *אימות* של bearer tokens בבקשות שהשירות הזה מקבל.
- **יוצא** (`fastapi_template.security`): *השגת* bearer tokens כדי לקרוא לשירותים אחרים.

העמוד הזה מסביר את התכנון שמאחורי שניהם.

## נכנס: נאכף ב-middleware, לא ב-dependencies {#inbound-enforced-by-middleware-not-dependencies}

האימות הנכנס נאכף על ידי `AuthMiddleware`, ולא על ידי dependencies של FastAPI בכל נתיב. ה-middleware
מחלץ `Bearer <token>` מה-header שהוגדר, מאמת אותו, ושומר את ה-claims ב-`request.state.user`;
הנתיבים קוראים אותם דרך `Depends(get_current_claims)`. כשעושים את זה ב-middleware, **כל** נתיב מוגן
כברירת מחדל (חוץ מרשימת החרגות מפורשת), במקום להסתמך על כך שכל נתיב יזכור להוסיף dependency.

השלכה אחת: מכיוון שסכמת ה-OpenAPI לא הייתה נושאת מידע אבטחה בדרך אחרת, הספרייה מזריקה סכמת
`BearerAuth` גלובלית, כדי ש-Swagger יציג כפתור **Authorize** כשהאימות פעיל.

## השער הכפול {#the-dual-gate}

האימות מופעל רק כש**שני** התנאים מתקיימים:

- **דגל הקוד** `enable_auth=True` מועבר ל-`general_create_app`, וגם
- **המתג בזמן ריצה** `AUTH_ENABLED=true` מוגדר בסביבה.

שני שערים הופכים את זה לבלתי אפשרי לשחרר בטעות קוד עם אימות פעיל שרץ עם אימות כבוי (או להפך) על
ידי שינוי של רק אחד מהם. פריסה יכולה גם לכבות את האימות בזמן ריצה בלי שינוי קוד.

## מצבי אימות {#verification-modes}

ה-verifier **בוחר אוטומטית מצב אחד בדיוק** לפי החומר שהוגדר, וזורק `AuthConfigError` בעלייה אם
לא הוגדר אף אחד או שהוגדר יותר מאחד (נכשל מהר, ולא בבקשה הראשונה):

| חומר | מצב |
|---|---|
| `AUTH_HS256_SECRET` | **HS256**: סוד משותף סימטרי |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | **LOCAL_PUBKEY**: ‏RS256 אופליין מול מפתח ציבורי |
| `AUTH_JWKS_URL` *או* `AUTH_OIDC_ISSUER` | **JWKS**: ‏RS256 מול מפתחות שנשלפים מ-endpoint של JWKS |

### ‏OIDC discovery {#oidc-discovery}

עבור כל ספק OIDC שעומד בתקן אפשר להגדיר רק את `AUTH_OIDC_ISSUER`: בעלייה, הספרייה שולפת את
`/.well-known/openid-configuration` של ה-issuer, מגלה את ה-`jwks_uri` שלו, ומאמתת במצב JWKS.
ה-issuer הופך גם לברירת המחדל של ה-claim ‏`iss` הצפוי. ‏`AUTH_JWKS_URL` מפורש תמיד גובר על
ה-discovery. (‏`AUTH_JWKS_URL` ו-`AUTH_OIDC_ISSUER` נחשבים לקבוצת חומר אחת, לא לשתי קבוצות
מתחרות.)

### טוקנים בלי תפוגה {#non-expiring-tokens}

ה-verifier דורש claim ‏`exp` כברירת מחדל. הגדירו `AUTH_REQUIRE_EXP=false` כדי לקבל טוקנים שהונפקו
בלעדיו (למשל טוקנים לפיתוח מ-[`gen-auth-material`](../how-to/generate-auth-material.md)). טוקן
ש*כן* נושא `exp` עדיין עובר ולידציה, כך שטוקנים שפג תוקפם נדחים בכל מקרה.

## יוצא: client_credentials, שמור במטמון ומתרענן {#outbound-client_credentials-cached-and-refreshed}

‏SSO יוצא משתמש ב-grant ‏**`client_credentials`** של OAuth2. לקוח הטוקנים שולף טוקן, שומר אותו
במטמון, מרענן אותו זמן קצר לפני התפוגה (`AUTH_SSO_EXPIRY_SKEW`), מסדר רענונים מקבילים בתור עם
lock, וה-`httpx.Auth` מנסה שוב פעם אחת כשמתקבל `401`. שימו לב ש-`client_credentials` לא מנפיק
refresh token (‏RFC 6749 §4.4.3): "רענון" פירושו הרצה מחדש של ה-grant.

אימות בצד השרת של טוקנים שהונפקו על ידי ה-SSO משתמש שוב ב**מצב JWKS**: הפנו את `AUTH_JWKS_URL`
ל-endpoint של ה-JWKS של הספק. כך הצד הנכנס והצד היוצא נפגשים ב-JWKS.

## למה PyJWT נטען בעצלות {#why-pyjwt-is-lazy}

צריך את PyJWT ואת cryptography רק כשבאמת מאמתים או מנפיקים טוקנים. המודול הציבורי `auth` מגיש את
שמות ה-verifier וה-keygen שלו דרך `__getattr__` ברמת המודול, וה-`__init__` של החבילה
`_internal/security` ריק, ולכן **ייבוא של החבילה, או אפליקציה עם אימות כבוי, אף פעם לא מייבא את
PyJWT.** צרכנים שרק מנפיקים טוקנים יוצאים מייבאים מ-`security`, שמושך את קוד ה-SSO אבל לא את מנגנון
ה-JWT הנכנס. משלמים על פיצ'ר רק כשמשתמשים בו.

## ראו גם {#see-also}

- [אבטחת ה-API שלכם](../tutorials/secure-your-api.md): הצד הנכנס, בצורה מעשית.
- [אבטחת API עם OIDC ו-JWKS](../how-to/secure-with-oidc-jwks.md): המסלול הנכנס בסביבת ייצור מול ה-SSO של הפלטפורמה.
- [קריאה לשירותים אחרים עם SSO](../how-to/call-services-with-sso.md): הצד היוצא.
- [קונפיגורציה](../reference/configuration.md): כל משתנה `AUTH_*` / `AUTH_SSO_*`.
