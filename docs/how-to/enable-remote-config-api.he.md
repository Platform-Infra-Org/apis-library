# הפעלת Remote Config API {#enable-the-remote-config-api}

`enable_remote_config_api` מחבר לאפליקציה שלכם **proxy דק ומאומת ל-Config API חיצוני (upstream)**.
השירות החיצוני (upstream) מחשב קונפיגורציית תשתית היררכית, מוסכמות שמות ורישום פרויקטים מתוך קבוצה
של *קואורדינטות הקצאה* (`space`, `network`, `region`, `island`, `environment`, `project`); היכולת
הזו מעבירה את הקואורדינטות האלה ב-HTTP, שומרת את התוצאה במטמון בזיכרון, ומסנכרנת את הרשימות
הנפתחות ב-Swagger ואת הולידציה של הבקשות שלכם עם רשימות הערכים המותרים החיות של ה-upstream.

## חיבור היכולת {#wire-it-up}

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template import enable_remote_config_api

app = general_create_app()

provider = enable_remote_config_api(
    app,
    base_url="https://config-api.example.com",  # where the upstream lives
    remote_prefix="/api/v1",  # upstream prefix serving /projects, /config, /naming, /coordinates
    coordinate_paths=[
        "/config",
        "/naming",
    ],  # your routes whose coordinate params get enum dropdowns
)
```

## הגדרת נתיבים מול ה-provider {#define-routes-against-the-provider}

ה-`RemoteConfigProvider` שמוחזר חושף את `resolve_infra_config`, `resolve_naming_convention`,
`get_all_projects`, `get_coordinate_catalog` ו-`get_coordinate_tree` (כולן נשמרות במטמון למשך
`cache_ttl` שניות, ברירת מחדל 60):

```python
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.config_api import (
    RequiredInfraMetadata,
    CoordinateCatalogResponse,
    CoordinateTreeResponse,
)


@app.get("/config")
async def get_config(meta: RequiredInfraMetadata = Depends()):
    return await provider.resolve_infra_config(meta)


@app.get("/coordinates", response_model=CoordinateCatalogResponse)
async def get_coordinates():
    # Discovery: the valid values per coordinate level plus the project list.
    return await provider.get_coordinate_catalog()


@app.get("/coordinates/tree", response_model=CoordinateTreeResponse)
async def get_coordinates_tree():
    # Same values, shaped as the nested config hierarchy.
    return await provider.get_coordinate_tree()
```

כל נתיב שמופיע ב-`coordinate_paths` מקבל רשימות `enum` נפתחות חיות שמוזרקות לשדות הקואורדינטות
שלו, **בין אם הם מגיעים כפרמטרים של query/path** (מודל `Depends()`, כמו למעלה) **ובין אם בתוך גוף
בקשה ב-JSON** (המודל כפרמטר גוף רגיל). במודל גוף, ה-enums נכתבים על סכמת הרכיב שאליה הוא מפנה, כך
שמודל שמשותף לכמה נתיבים מעוטר פעם אחת. הזרקת ה-enums מתאימה לפי שם השדה, ולכן תנו לשדה את שם
הקואורדינטה שלו (`region`, `island`, …).

`get_coordinate_catalog` מעביר את הבקשה לנתיב `/coordinates` של ה-upstream ומחזיר dict במבנה של
[`CoordinateCatalogResponse`](../reference/api/config-api.md#models-allowlists): הקבוצה הממוינת של
הערכים עבור כל אחד מ-`space` / `network` / `region` / `island` / `environment`, ובנוסף
`projects`. ‏upstream שעוד לא אוכלס מחזיר רשימות ריקות (`200` תקין, לא `404`).

`get_coordinate_tree` מעביר את הבקשה לנתיב `/coordinates/tree` של ה-upstream ומחזיר dict במבנה של
[`CoordinateTreeResponse`](../reference/api/config-api.md#models-allowlists): היררכיה מקוננת
(`coordinates`: space → network → region → island → רשימת env ממוינת) ובנוסף רשימת `projects`
שטוחה. ‏upstream שעוד לא אוכלס מחזיר `{"coordinates": {}, "projects": []}`.

## מה היכולת מגדירה {#what-it-sets-up}

- `RemoteConfigProvider` (מוחזר) לחישוב קונפיגורציה / שמות / פרויקטים.
- **אכלוס בעלייה + poller ברקע** (נרשם ב-lifespan של `general_create_app`). רשימות הערכים המותרים
  נשלפות **פעם אחת בעלייה, ללא קשר ל-`enable_polling`**; כש-polling מופעל, הן מתרעננות לאחר מכן כל
  `poll_interval` שניות, ומעדכנות תוך כדי ריצה גם את ה-validators של Pydantic וגם את רשימות `enum`
  הנפתחות ב-OpenAPI. העבירו `enable_polling=False` לקבלת snapshot חד-פעמי (אכלוס בלבד, בלי ריענון).
- handler של `pydantic.ValidationError → 422`, כך שקואורדינטה מחוץ לרשימת הערכים המותרים שלה מחזירה
  את אותו מבנה כמו כל פרמטר query לא תקין אחר.
- **ולידציה היררכית.** מעבר לרשימות הערכים המותרים השטוחות לכל רמה, מודלי הקואורדינטות אוכפים גם
  את **עץ הקואורדינטות** החי (`/coordinates/tree`): ילד חייב להיות תחת ההורה שנבחר. למשל, `island`
  תקין רק בתוך ה-`region` שנבחר. זו שגיאת `422` בזמן השליחה, ולא רשימה נפתחת ב-Swagger (‏OpenAPI
  לא יכול לבטא enums תלויים); חשפו את `/coordinates/tree` אם ממשק קצה צריך בחירות מדורגות. הבדיקה
  מתירנית עד שהעץ מאוכלס, וגם עבור בחירות חלקיות (שבהן הושמטו קואורדינטות).

## אכלוס חד-פעמי ואז ריענון {#seeded-once-then-refreshed}

רשימות הערכים המותרים ועץ הקואורדינטות נשלפים **פעם אחת בעלייה, גם עם `enable_polling=False`**,
כך שהולידציה והרשימות הנפתחות עובדות מול ה-snapshot הזה; ה-polling רק שומר עליהם עדכניים לאחר מכן.
שתי הסתייגויות:

- לפני שהשליפה הראשונה מסתיימת (חלון קצר בעלייה), רשימות הערכים המותרים ריקות, ולכן
  הולידציה מתירנית (מקבלת כל ערך) ולא מוזרקות רשימות נפתחות. זה מכוון
  (`InfraMetadata` לא חוסם כשרשימת הערכים המותרים ריקה).
- אם האפליקציה **לא** נבנית על ידי `general_create_app` (אף אחד לא מפעיל את המשימה הרשומה), האכלוס
  אף פעם לא רץ אוטומטית. הפעילו אותו בעצמכם:

  ```python
  await provider.crawl_and_sync_keys(app)  # populate the allowlists + tree once
  ```

## התאמת נתיבים עם `coordinate_paths` {#matching-routes-with-coordinate_paths}

כל רשומה ב-`coordinate_paths` היא **מחרוזת regex**, שמותאמת עם `re.fullmatch` מול כל נתיב.
נתיב רגיל הוא פשוט regex מילולי שמתאים רק לעצמו (כך ש-`["/config", "/naming"]` עובד בדיוק כמו
שהייתם מצפים), אבל אפשר גם להתאים **משפחה של נתיבים** ברשומה אחת:

```python
coordinate_paths = [r"/api/v\d+/infra/(config|naming)"]  # one entry, many/versioned routes
```

מכיוון שזו התאמה של הנתיב המלא, השתמשו ב-`.*` להתאמות חלקיות (`r"/api/v1/infra/.*"`); עשו escape
לתווים מיוחדים של regex (`.`, `+`, …) אם אתם צריכים אותם כפשוטם (נדיר בנתיבים); פרמטרי נתיב של
FastAPI כמו `{id}` מותאמים כפשוטם. regex לא תקין מעלה חריגה בזמן החיבור.

מעבר לזה, הזרקת ה-enums **מתאימה לפי שם ומוסיפה בלבד**: נתיב מותאם שמצהיר רק על חלק מהקואורדינטות
מקבל רשימות נפתחות רק עבורן. אין כלל של "כל השש חובה" ואין שגיאה, ופרמטרים שאינם קואורדינטות לא
משתנים. הצד השני של זה הוא שטעויות נכשלות בשקט: תבנית שלא מתאימה לאף נתיב, או שדה ששמו שונה משם
הקואורדינטה שלו, פשוט לא מקבלים רשימה נפתחת (בלי אזהרה). תנו לשדות הקואורדינטות את שם הקואורדינטה
שלהם (`region`, `island`, …).

## הגשת ערך ישן כשה-upstream נכשל {#serve-stale-on-upstream-failure}

כברירת מחדל, upstream שלא ניתן להגיע אליו או שמחזיר `5xx` מתורגם ל-`502` (החוזה המחמיר, שנכשל
לסגור). העבירו `serve_stale_on_error=True` כדי לחזור במקום זאת ל**ערך האחרון שנשלף בהצלחה עבור
המפתח הזה** (last-known-good) כשה-upstream לא זמין:

```python
provider = enable_remote_config_api(app, ..., serve_stale_on_error=True)
```

הערות:

- כל שגיאה של ה-upstream *חוץ* מ-`404` גורמת לחזרה לערך הישן: שרת שלא ניתן להגיע אליו, `5xx` או
  `4xx` (כולם ממופים ל-`502` פנימית). `404` אינו שגיאה: הוא אומר "אין עדיין ערך" ומחזיר את ברירת
  המחדל הריקה.
- מאגר ה-last-known-good **לא מוגבל** (אף פעם לא פג תוקף), ונפרד מהמטמון של `cache_ttl`, כך
  שמפתח שנשלף פעם אחת נשאר זמין להגשה לאורך תקלה בכל אורך.
- למפתח שאף פעם לא נשלף בהצלחה אין ערך לחזור אליו, ולכן הבקשה הראשונה שלו בזמן תקלה עדיין מחזירה
  `502`.

## בחירת האימות היוצא {#choose-the-outbound-auth}

האימות מול ה-upstream **ניתן לבחירה דרך משתני הסביבה `CONFIG_REMOTE_*`**:
`CONFIG_REMOTE_AUTH_METHOD` בוחר `sso` (‏OAuth2 `client_credentials`), `bearer` (טוקן סטטי) או
`none`. ראו את [טבלת ההגדרות של Remote Config](../reference/configuration.md#remote-config-api-outbound-to-the-upstream).

בשיטת ברירת המחדל `sso`, ספק הקונפיגורציה מנפיק את הטוקן שלו עם אותו מנגנון `client_credentials`
כמו כל [קריאת SSO יוצאת](call-services-with-sso.md). כדי להגדיר אותו, **בקשו מצוות ה-SSO client**
והזינו את ה-id/secret שלו ב-`CONFIG_REMOTE_SSO_CLIENT_ID` /
`CONFIG_REMOTE_SSO_CLIENT_SECRET`. אם ה-Config API החיצוני בודק את ה-audience שלו, בקשו גם את
**ה-client scope האופציונלי שנושא את ה-audience של הפלטפורמה**. ה-scope הזה **אמור כבר להתקיים
ב-SSO**, כך שצריך רק להעניק אותו ל-client. הגדירו את `CONFIG_REMOTE_SSO_SCOPE` לשמו. (ספקים בסגנון
Auth0 יכולים במקום זאת לשלוח את ה-audience כפרמטר דרך `CONFIG_REMOTE_SSO_AUDIENCE`.) אותו דפוס
לאבטחת ה-API *שלכם* מתואר ב[אבטחת API עם OIDC ו-JWKS](secure-with-oidc-jwks.md).

כדי לעקוף את ההגדרות לגמרי (בדיקות / פתח מילוט), העבירו `httpx.Auth` מפורש:

```python
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth

provider = enable_remote_config_api(app, ..., auth=StaticBearerAuth("token"))
```

!!! note "תלות שנטענת בעצלות"
    Remote Config משתמש ב-[`aiocache`](https://pypi.org/project/aiocache/) למטמון שבזיכרון.
    מכיוון שגם המטמון וגם `enable_remote_config_api` מיובאים בעצלות, אפליקציות שלא קוראות לה אף
    פעם לא צריכות את `aiocache`.

## ראו גם {#see-also}

- [מידע עזר על ה-API: ‏Remote Config API](../reference/api/config-api.md)
- [מידע עזר על ההגדרות](../reference/configuration.md)
- [הגבלת שדה לפי קונפיגורציה](constrain-field-by-config.md): ולידציה של שדה מול הקונפיגורציה
  שחושבה עבור הקואורדינטות של הבקשה.
- [ולידציה דינמית של קונפיגורציה](../explanation/dynamic-config-validation.md): איפה כל בדיקה נמצאת
  ולמה.
- [הזרקה ל-OpenAPI ול-Swagger](../explanation/openapi-swagger-injection.md): איך רשימות ה-enum
  הנפתחות החיות מגיעות ל-Swagger.
