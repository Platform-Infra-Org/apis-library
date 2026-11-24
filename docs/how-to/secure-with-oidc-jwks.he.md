# אבטחת API עם OIDC ו-JWKS {#secure-an-api-with-oidc-jwks}

כדי להגן על השירות שלכם באמצעות טוקנים שמונפקים על ידי **ה-SSO של הפלטפורמה**, אמתו טוקני bearer
נכנסים ב**מצב JWKS**: המאמת שולף את מפתחות החתימה מסוג RS256 של הספק מה-endpoint של ה-JWKS שלו
(לפי ה-`kid` שלהם) ומאמת כל בקשה מולם. זו הדרך הסטנדרטית לכל ספק OIDC, והיא לא דורשת סוד משותף או
קובץ מפתח בצד שלכם, בניגוד למצב המפתח הציבורי המקומי שבו משתמש המדריך למתחילים
[אבטחת ה-API שלכם](../tutorials/secure-your-api.md).

שני צדדים צריכים להתאים זה לזה: **ה-SSO** (מנפיק טוקנים עם ה-audience הנכון), ו**ה-API שלכם**
(מאמת את החתימה, את `iss` ואת `aud`). הקוראים מקבלים את הטוקנים שלהם דרך ה-grant של OAuth2
`client_credentials`.

## 1. מה לבקש מצוות ה-SSO {#1-what-to-request-from-the-sso-team}

את חומרי האימות ואת ה-audience לא מייצרים בעצמכם. בקשו מצוות ה-SSO:

- **client** (‏client id + secret) עבור כל *קורא* שיפנה ל-API שלכם. הקוראים משתמשים בו עם
  ה-grant `client_credentials` (ראו שלב 3). קוראים אנושיים שעובדים דרך ממשק משתמש משתמשים בזרימה
  משלהם; זה מיועד לקריאות **שירות-לשירות**.
- **audience** (שנקרא גם API identifier) עבור השירות *שלכם*: הערך שה-SSO מטביע ב-claim ‏`aud`
  של הטוקנים שהוא מנפיק, והערך שה-API שלכם בודק. סכמו על מחרוזת אחת (למשל
  `https://my-api.platform.example`).
- **ה-client scope שנושא את ה-audience של הפלטפורמה.** בספקים בסגנון Keycloak, ה-`aud` נקבע על
  ידי protocol mapper מסוג **Audience** שמחובר ל-**client scope**. ה-scope הזה של הפלטפורמה אמור
  **כבר להתקיים ב-SSO**; צריך רק להעניק אותו לקוראים או שהם יבקשו אותו, כדי שהטוקנים שלהם יישאו את
  ה-audience שלכם. (בספקים בסגנון Auth0, ה-audience הוא במקום זאת פרמטר בבקשה; ראו שלב 3.)
- **כתובת ה-URL של ה-issuer** (עבור OIDC discovery) *או* ישירות את **כתובת ה-endpoint של ה-JWKS**.

## 2. הגדרת ה-API שלכם (אימות נכנס) {#2-configure-your-api-inbound-verification}

הפעילו את האימות הנכנס. הוא **מוגן בשני שערים**: חייבים להגדיר גם את הדגל בקוד וגם את המתג בזמן
ריצה:

```python
from tashtiot_apis_library import general_create_app

app = general_create_app(enable_auth=True)  # gate 1: the code flag
```

הפנו את המאמת ל-SSO בסביבה שלכם (`.env` או משתני הסביבה של התהליך). העדיפו **OIDC discovery**:
תנו לו את ה-issuer, והוא ישלוף את `/.well-known/openid-configuration` בעלייה כדי למצוא את
ה-`jwks_uri`:

```env
AUTH_ENABLED=true                                        # gate 2: the runtime switch
AUTH_OIDC_ISSUER=https://sso.platform.example/realms/platform
AUTH_AUDIENCE=https://my-api.platform.example            # must equal the audience the SSO assigned you
```

או דלגו על ה-discovery וציינו ישירות את ה-endpoint של ה-JWKS (השתמשו באחד **או** בשני, לא בשניהם):

```env
AUTH_ENABLED=true
AUTH_JWKS_URL=https://sso.platform.example/realms/platform/protocol/openid-connect/certs
AUTH_AUDIENCE=https://my-api.platform.example
AUTH_ISSUER=https://sso.platform.example/realms/platform  # expected iss (OIDC discovery sets this for you)
```

!!! warning "הגדירו את `AUTH_AUDIENCE`, אחרת ה-audience לא נבדק"
    ה-audience נבדק **רק כש-`AUTH_AUDIENCE` מוגדר**. אם לא תגדירו אותו, כל טוקן עם חתימה תקינה
    מה-issuer יתקבל, בלי קשר למי הוא הונפק. כך טוקן שנועד לשירות אחר יעבור. תמיד הגדירו אותו
    ל-audience שהוקצה לכם.

עם `enable_auth=True` + `AUTH_ENABLED=true`, ה-`AuthMiddleware` מגן על **כל** נתיב (חוץ
מ[רשימת ההחרגות](../reference/configuration.md#inbound-authentication-server-side): probes, docs,
`/.well-known`, …). נתיבים קוראים את הזהות המאומתת דרך `Depends(get_current_claims)`; טוקן חסר או
לא תקין מקבל `401`. ראו את [טבלת `AUTH_*` הנכנסת](../reference/configuration.md#inbound-authentication-server-side)
המלאה לכל אפשרות (`AUTH_ISSUER`, `AUTH_ALGORITHMS`, `AUTH_JWKS_CACHE_TTL`, `AUTH_REQUIRE_EXP`, …).

## 3. איך קורא מקבל טוקן (`client_credentials`) {#3-how-a-caller-obtains-a-token-client_credentials}

קורא מחליף את ה-client id/secret שלו בטוקן ב-endpoint הטוקנים של ה-SSO, ואז שולח אותו
כ-`Authorization: Bearer <token>`. ה-`aud` של הטוקן שהונפק **חייב להתאים ל-`AUTH_AUDIENCE`
שלכם**, ולכן הקורא צריך לגרום ל-SSO להטביע אותו:

- **בסגנון Keycloak:** בקשו את **ה-client scope** של הפלטפורמה (שלב 1), כדי שה-Audience mapper
  יוסיף את ה-`aud` שלכם. עם פונקציות העזר של הספרייה, הגדירו את `AUTH_SSO_SCOPE` ל-scope הזה.
- **בסגנון Auth0:** הספק מכבד פרמטר בקשה בשם `audience`. הגדירו את `AUTH_SSO_AUDIENCE`
  ל-audience שלכם, וה-IdP יטביע אותו.

אם הקורא הוא בעצמו שירות שבנוי על הספרייה הזו, הוא לא צריך לממש את ה-grant ידנית: פונקציות העזר
היוצאות שולפות, שומרות במטמון ומרעננות את הטוקן אוטומטית:

```python
from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

async with sso_authenticated_api("https://my-api.platform.example") as client:
    resp = await client.get("/protected")  # Authorization: Bearer <auto-managed>
```

ראו **[קריאה לשירותים אחרים עם SSO](call-services-with-sso.md)** להגדרה היוצאת המלאה
(משתני `AUTH_SSO_*`, ‏`SSOConfig` לכל upstream, ואיך ה-`aud` של שירות היעד מאוכלס).

## אימות טוקן מחוץ לבקשה {#verify-a-token-outside-a-request}

workers, כלי CLI או נתיבים שמקבלים טוקן בדרכים אחרות יכולים לאמת אותו ישירות עם אותה קונפיגורציית
JWKS. ראו [אימות טוקן מחוץ לבקשה](verify-a-token.md).

## ראו גם {#see-also}

- [קריאה לשירותים אחרים עם SSO](call-services-with-sso.md): צד הקורא / הצד היוצא.
- [אימות טוקן מחוץ לבקשה](verify-a-token.md): הבדיקה הנכנסת מחוץ למסלול הבקשה.
- [תכנון האימות](../explanation/authentication.md): למה יש מצבים ואיך בוחרים ביניהם.
- [מידע עזר על ההגדרות](../reference/configuration.md): כל משתנה `AUTH_*` / `AUTH_SSO_*`.
