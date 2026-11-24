# קריאה לשירותים אחרים עם SSO {#call-other-services-with-sso}

כשהשירות שלכם צריך לקרוא לשירות מוגן **אחר**, השתמשו בפונקציות העזר של ה-SSO היוצא. הן מקבלות
טוקן bearer דרך ה-grant של OAuth2 **`client_credentials`**, שומרות אותו במטמון, מרעננות אותו לפני
שפג תוקפו, ומנסות שוב פעם אחת כשמתקבל `401`.

פונקציות העזר האלה נמצאות ב-`tashtiot_apis_library.fastapi_template.security`, בכוונה בנפרד
ממנגנון ה-JWT הנכנס, כך שצרכן שמשתמש רק בצד הלקוח אף פעם לא מושך את PyJWT.

## המקרה הפשוט: מבוסס הגדרות {#the-simple-case-settings-driven}

הגדירו את משתני הסביבה `AUTH_SSO_*` (ראו [הגדרות](../reference/configuration.md)) והשתמשו
ב-`sso_authenticated_api`. כל בקשה שעוברת דרך הלקוח שמוחזר נושאת טוקן עדכני:

```python
from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

async with sso_authenticated_api("https://downstream.example.com") as client:
    resp = await client.get("/protected")  # Authorization: Bearer <auto-managed>
```

## כמה שירותים חיצוניים עם זהויות שונות {#several-upstreams-with-different-identities}

כדי לקרוא לכמה שירותים חיצוניים (upstream) שכל אחד מהם צריך זהות או audience שונים, באופן בלתי
תלוי ב-singleton של `AUTH_SSO_*`, העבירו `SSOConfig` מפורש. בנו **אחד לכל שירות מרוחק והשתמשו בו
שוב**, כדי שמטמון הטוקנים שלו יהיה משותף:

```python
from tashtiot_apis_library.fastapi_template.security import SSOConfig, sso_authenticated_api

billing = SSOConfig(
    token_url="https://idp/oauth/token",
    client_id="my-svc",
    client_secret="…",
    audience="https://billing.example.com",
)

async with sso_authenticated_api("https://billing.example.com", config=billing) as client:
    resp = await client.get("/invoices")
```

## טוקן קבוע וארוך-טווח {#a-fixed-long-lived-token}

עבור upstream שמאובטח בטוקן שירות סטטי (בלי endpoint לטוקנים), השתמשו ב-`StaticBearerAuth` עם
כל לקוח שמקבל `httpx.Auth`, כולל ה-`BaseAPI` של הספרייה:

```python
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

async with BaseAPI("https://downstream.example.com", auth=StaticBearerAuth("token")) as client:
    resp = await client.get("/protected")
```

## רק הטוקן הגולמי {#just-the-raw-token}

```python
from tashtiot_apis_library.fastapi_template.security import get_sso_token_client

token = await get_sso_token_client().get_token()
headers = await get_sso_token_client().auth_header()  # {"Authorization": "Bearer …"}
```

## הגדרת ה-audience של שירות היעד (`aud`) {#setting-the-downstream-audience-aud}

האופן שבו ה-claim ‏`aud` של שירות היעד מאוכלס **תלוי בספק**: הוא נקבע כשהטוקן מונפק
ב-endpoint הטוקנים, ולא במקום שבו מתבצעת הקריאה:

- **ספקים בסגנון Auth0** מכבדים פרמטר בבקשה: הגדירו את `AUTH_SSO_AUDIENCE`, והוא יישלח כשדה הטופס
  `audience`; ה-IdP מטביע אותו ב-`aud`.
- **Keycloak מתעלם מהפרמטר `audience`.** הגדירו protocol mapper מסוג **Audience** על client scope,
  ואז בקשו את ה-scope הזה דרך `AUTH_SSO_SCOPE`, כדי שהטוקן שמונפק יישא את ה-`aud` הנכון. השירות
  המקבל מאמת אותו לאחר מכן דרך ה-`AUTH_AUDIENCE` הנכנס שלו.

!!! note "אין refresh token"
    `client_credentials` לא מנפיק refresh token של OAuth2 ‏(RFC 6749 §4.4.3). "ריענון" כאן פירושו
    הרצה מחדש של ה-grant כדי להנפיק access token חדש כשהטוקן שבמטמון מתקרב לפקיעת תוקפו.

## ראו גם {#see-also}

- [מידע עזר על ה-API: ‏security](../reference/api/security.md)
- [הגדרות: SSO יוצא](../reference/configuration.md#outbound-sso-client-side)
- [אימות טוקן (הצד הנכנס)](verify-a-token.md)
- [אבטחת API עם OIDC ו-JWKS](secure-with-oidc-jwks.md): הצד הנכנס המקביל, שעבורו מונפקים הטוקנים
  האלה.
