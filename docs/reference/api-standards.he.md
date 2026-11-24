# תקני API {#api-standards}

כללי החברה לכל API מבוסס HTTP שנבנה על **`tashtiot-apis-library`**. APIs חדשים חייבים לעמוד בהם,
ו-APIs קיימים צריכים להתקרב אליהם בהדרגה. העמוד הזה מפרט את הכללים. ההסברים נמצאים בעמודי
ה[הסבר](../explanation/index.md), והמתכונים צעד אחר צעד נמצאים ב[מדריכי הביצוע](../how-to/index.md).

!!! info "מימוש לדוגמה"
    המאגר **[`example-api`](https://github.com/Platform-Infra-Org/example-api)** הוא API שלם וניתן להרצה שבנוי על הספרייה. העתיקו ממנו את
    **המבנה** ואת **אופן השימוש בספרייה**. במקומות שבהם הוא סותר את העמוד הזה, העמוד הזה קובע (ראו
    [פערים ידועים ב-`example-api`](#known-gaps-in-example-api)).

חדשים בספרייה? התחילו במדריכים למתחילים [האפליקציה הראשונה שלכם](../tutorials/first-app.md)
ו[אבטחת ה-API שלכם](../tutorials/secure-your-api.md).

!!! tip "עבודה עם סוכן קוד מבוסס AI"
    - **עבודה שוטפת על API:** מאגר הספרייה כולל skill עצמאי לסוכנים,
      [`skills/building-tashtiot-apis/`](https://github.com/Platform-Infra-Org/apis-library/tree/master/skills/building-tashtiot-apis).
      הוא כולל את הכללים האלה, מידע עזר על ה-API של הספרייה ו-API תבנית שנבדק, ולכן הוא עובד גם
      בתוך הרשת המבודדת, בלי GitHub ובלי האתר הזה. **שמרו אותו במאגר ה-API שלכם בנתיב
      `.claude/skills/building-tashtiot-apis/`**: כך הוא עובר יחד עם ה-mirror, ונשאר מותאם לגרסת
      הספרייה שהמאגר משתמש בה. רעננו אותו בכל פעם שאתם משדרגים את הספרייה.
    - **עבודה על CI, image ופריסה:** השתמשו במדריך ה-CI הפנימי (וב-skill ה-CI הפנימי, אם יש
      כזה). הם נמצאים בתוך הרשת המבודדת.
    - **שדרוג לגרסה חדשה של הספרייה, או כתיבה מחדש של API על הספרייה:** השתמשו
      ב[פרומפט ההסבה](../how-to/migrate-an-api.md).

---

## סטאק טכנולוגי {#stack}

| תחום | תקן |
|---|---|
| שפה | Python **3.12** (הספרייה עצמה תומכת ב-3.10 ומעלה) |
| Web framework | **FastAPI** + **uvicorn** (ASGI) |
| SDK משותף | **`tashtiot-apis-library`** ([ארכיטקטורה](../explanation/architecture.md)) |
| מודלים / ולידציה | **Pydantic v2**, ו-**pydantic-settings** להגדרות |
| לקוח HTTP | **httpx** (אסינכרוני), תמיד דרך `BaseAPI` של הספרייה |
| לוגים | **Loguru**, מוגדר על ידי הספרייה ([לוגים](../explanation/logging.md)) |
| מנהל חבילות | **uv** (‏`uv.lock` נשמר ב-git, ‏`uv.toml` לעולם לא) |
| בדיקות | **pytest** + `pytest-asyncio` (‏`asyncio_mode = "auto"`) + `respx` |
| CI | ‏Woodpecker (‏`.woodpecker/*.yaml`). ראו [CI](#ci) |
| Image registry | **JFrog Artifactory** (ממנו מושכים את ה-base images, ואליו דוחפים את ה-images שנבנו) |

---

## מבנה הפרויקט {#project-layout}

```
<your-api>/
├── app/
│   ├── main.py            # create_app(): the ONLY wiring point (connectors + routers)
│   ├── global_conf.py     # app-wide BaseSettings -> `global_config`
│   ├── schemas.py         # shared models (e.g. ProjectMetadata)
│   ├── helpers.py         # shared pure helpers (naming conventions, payload parsing)
│   └── v1/
│       └── <resource>/
│           ├── conf.py        # module BaseSettings -> `config` (API_PREFIX, API_TAGS, ids…)
│           ├── schemas.py     # Pydantic request/response models ({metadata, spec})
│           ├── operations.py  # business logic; receives connectors as arguments
│           └── routes.py      # get_<resource>_router(deps) -> APIRouter
├── tests/
│   ├── conftest.py        # hermetic env (shadows a developer .env)
│   └── v1/<resource>/     # conftest.py + test_*.py per module
├── .env.example           # every variable, documented. Committed.
├── .env                   # local values. NEVER committed.
├── pyproject.toml
├── uv.lock                # committed
├── uv.toml                # Artifactory index + creds. NEVER committed.
├── Dockerfile
├── .woodpecker/build.yaml
└── README.md
```

| שכבה | מותר | אסור |
|---|---|---|
| `routes.py` | להגדיר נתיבים, מודלים וקודי סטטוס; לתרגם חריגות לתשובות HTTP | להכיל לוגיקה עסקית; לבנות מחברים |
| `operations.py` | לתזמר מחברים; להחיל כללים עסקיים; לבצע rollback | לייבא `Request`/`Response`; לקרוא משתני סביבה ישירות |
| `schemas.py` | להגדיר מבנה וולידציה | לבצע I/O |
| `conf.py` | להצהיר על הגדרות עם ברירות מחדל ותיאורים | להחזיק סודות אמיתיים כברירות מחדל |

---

## פונקציית יצירת האפליקציה {#application-factory}

‏`general_create_app()` ([מידע עזר ל-API](api/fastapi-app.md)) מספקת את היכולות המובנות האלה:

| יכולת מובנית | נתיב / התנהגות | דגל (ברירת מחדל) |
|---|---|---|
| Middleware ללוגים של בקשות | רושם כל בקשה ותשובה (health/docs/metrics ברמת DEBUG) | `enable_logging_middleware=True` |
| Middleware למדידת זמן | מוסיף את הכותרת `X-Process-Time` (בננו-שניות) | `enable_time_recording_middleware=True` |
| מטפלי חריגות | `HTTPException` → `{"detail": ...}`; ולידציה → 422; כל דבר אחר → 500 `"Internal Server Error"` | `enable_exception_handlers=True` |
| מדדי Prometheus | `GET /metrics` (+ מדד ה-gauge‏ `app_uptime_seconds`) | `enable_metrics_route=True` |
| Swagger / ReDoc | `GET /docs`, `GET /redoc` (קבצים סטטיים מאוחסנים מקומית) | `enable_swagger_routes=True` |
| Probes | `GET /liveness`, `GET /readiness` | `enable_probe_routes=True` |
| נתיב השורש | `GET /` → הודעת פתיחה | `enable_root_route=True` |
| אימות JWT נכנס | Middleware גלובלי ([אימות](#authentication)) | `enable_auth=False` |
| משימות רקע | Coroutines שמופעלות באתחול ומבוטלות בכיבוי | `async_background_tasks=[...]` |

כל keyword אחר (‏`title`, `version`, `description`…) מועבר כמו שהוא ל-`FastAPI()`.

**כללים:**

- ‏`create_app()` בקובץ `app/main.py` היא **נקודת החיווט היחידה**. היא בונה כל מחבר **פעם אחת**,
  בונה את ה-Remote Config במידת הצורך, ומחברת את כל ה-routers.
- **תמיד העבירו `enable_auth=True`.** מתג זמן הריצה `AUTH_ENABLED` קובע אם האימות נאכף בפועל.
- הגדירו `title` ו-`version` (‏`APP_VERSION`, שמוזרק מתגית ה-git בזמן הבנייה).
- משהו שכל API צריך (middleware, נתיב, פונקציית עזר) נכנס לספרייה, לא ל-API אחד
  ([הרחבת תבנית ה-FastAPI](../how-to/extend-the-template.md)).

---

## הגדרות {#configuration}

- כל ההגדרות הן **`BaseSettings` של pydantic-settings**, שנקראות ממשתני סביבה עם `.env` כגיבוי.
  למשתני הסביבה יש עדיפות.
- **`app/global_conf.py`** מחזיק הגדרות שמשותפות לכמה מודולים (כתובות וטוקנים של מחברים,
  `TEAM_NAME`, `CONFIG_API_*`, `API_TITLE`, `APP_VERSION`) ב-singleton‏ `global_config`.
- **`app/v1/<resource>/conf.py`** מחזיק את ההגדרות של מודול אחד, כולל **`API_PREFIX`**
  ו-**`API_TAGS`**, ב-singleton‏ `config`.
- לכל שדה יש `description=`. השתמשו ב-`SettingsConfigDict(env_file=".env", extra="ignore")`.
- להגדרות חובה אין ברירת מחדל, כך שערך חסר מכשיל את האפליקציה כבר באתחול.
- **אל תצהירו מחדש על הגדרות שהספרייה אחראית עליהן** (‏`PORT`, `LOG_LEVEL`, `PROXIED`,
  `PROXY_LISTEN_PATH`, `AUTH_*`, `AUTH_SSO_*`, `CONFIG_REMOTE_*`, נתיבי ה-probes וה-Swagger).
  הרשימה המלאה נמצאת ב[הגדרות](configuration.md).
- כשהאפליקציה מוגשת תחת קידומת נתיב של ingress, הגדירו `PROXIED=true` ו-`PROXY_LISTEN_PATH=/<prefix>`.

**סודות:**

- הסודות מגיעים ממאגר הסודות של הפריסה (Vault או Kubernetes Secrets, שמוזרקים כמשתני סביבה או
  כקבצים מחוברים). **לעולם** אל תשימו אותם ב-git, בברירת מחדל של `conf.py`, ב-`.env.example`,
  בלוגים או ב-image.
- ‏`.env.example` מפרט **כל** משתנה, עם ערך placeholder והערה.
- ‏`.env`, ‏`uv.toml` ומפתחות פרטיים נמצאים ב-git-ignore.

---

## חוזה הבקשה {#request-contract}

### מבנה {#shape}

לגוף הבקשה של כל נתיב כתיבה יש בדיוק שני אובייקטים ברמה העליונה:

```json
{
  "metadata": {
    "project": "payments",
    "space": "net",
    "network": "core",
    "region": "kirya",
    "island": "a1",
    "environment": "prod"
  },
  "spec": {
    "record_name": "api-01",
    "ip": "10.0.0.15",
    "record_type": "A",
    "dns_zone": "net.com"
  }
}
```

| אובייקט | תוכן |
|---|---|
| **`metadata`** | **מי** מבקש ו**לאן** הפעולה מכוונת: `project`, `space`, `network`, `region`, `island` ו-`environment`. |
| **`spec`** | **מה** לעשות: המצב הרצוי, הספציפי למשאב. ה-API שלכם הוא הבעלים שלו ומגדיר אותו. |

### כללי metadata {#metadata-rules}

1. **`project` תמיד מאוכלס** על ידי הקוראים, והוא **חובה**.
2. **`space`, `network`, `region`, `island` ו-`environment` הם אופציונליים.** השתמשו באלה שהפעולה
   שלכם צריכה. יש APIs שלא צריכים אף אחד מהם.
3. **כל API מקבל את האובייקט `metadata`**, גם אם הוא לא משתמש בשום דבר ממנו. שדות שאינם בשימוש
   מתעלמים מהם, ולעולם לא דוחים אותם.
4. API ש**צריך** קואורדינטה אופציונלית אוכף אותה בסכמה או בפעולה שלו ומחזיר 422. היא לא הופכת
   לחובה ברמת הפלטפורמה כולה.
5. מפתחות נוספים לא מוכרים בתוך `metadata` מושמטים (ברירת המחדל של Pydantic,‏ `extra="ignore"`).
   אל תגדירו `extra="forbid"` במודלים של metadata.

### מודלי בסיס {#base-models}

מתוך החבילה הראשית `tashtiot_apis_library` ([סכמות](api/schemas.md)):

| בסיס | הטיפוס של `metadata` | ולידציה |
|---|---|---|
| `InfraOperationRequest` | `InfraMetadata`: **כל** הקואורדינטות אופציונליות | רשימות ערכים מותרים חיות והיררכיית קואורדינטות מה-Config API ([ולידציה דינמית מול הקונפיגורציה](../explanation/dynamic-config-validation.md)). **התחילו מזה.** |
| `RequiredInfraOperationRequest` | `RequiredInfraMetadata`: **כל** הקואורדינטות חובה | אותה ולידציה. השתמשו בו רק אם ה-API שלכם צריך כל קואורדינטה. |
| `OperationRequest` | `MetadataRequest`: סטטי, בלי ולידציה חיה | Legacy. לא לקוד חדש. |

אף אחד מהם לא מגדיר **רק** את `project` כחובה. כל API מגדיר את זה פעם אחת, ב-`app/schemas.py`,
ומשתמש בזה שוב ושוב:

```python
from pydantic import BaseModel, Field
from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata


class ProjectMetadata(InfraMetadata):
    """Platform metadata: project required, every other coordinate optional."""

    project: str = Field(..., description="The platform application submitting the request")


class MetadataRequest(BaseModel):
    metadata: ProjectMetadata = Field(..., description="Platform metadata (project required).")


# app/v1/dns/schemas.py
class DNSRecordCreate(MetadataRequest):
    spec: DNSRecordCreateSpec
```

### מוסכמות לשדות {#field-conventions}

- **בצעו ולידציה בגבול.** השתמשו בשדות עם טיפוסים (‏`IPv4Address`, `Enum`, `constr`, `max_length`)
  וב-`field_validator`s. קלט שגוי נכשל עם **422** לפני שמחבר כלשהו נקרא.
- השתמשו באבני הבניין של הספרייה בתוך `spec` כשהן מתאימות: `ResourceSpec`, `NameNamespace`,
  `DefaultMetaSpec`.
- לשדה ב-`spec` שהערכים המותרים שלו תלויים בקואורדינטות של הבקשה, ראו
  [הגבלת שדה לפי הקונפיגורציה שנפתרה](../how-to/constrain-field-by-config.md).
- לכל שדה יש `description=`.
- **נתיבי קריאה ומחיקה** מזהים משאב באמצעות פרמטרים בנתיב או ב-query. העדיפו פרמטרי query על פני
  גוף בבקשת DELETE, כי יש proxies שזורקים את הגוף של בקשות DELETE.

---

## תשובות וקודי סטטוס {#responses-and-status-codes}

- כל נתיב מצהיר על `response_model=` (או על type annotation להחזרה). מילונים גולמיים משירותים
  חיצוניים לעולם לא מועברים הלאה כמו שהם.
- תוצאות של פעולות יורשות מ-**`OperationResponse`** (‏`status`, `status_code`, `return_code`,
  `stdout`), או מאחת ממחלקות הבת שלה עבור המחברים: `AWXOperationResponse` (+ `job_id`) או
  `ArgoOperationResponse` (+ `app_name`). ראו
  [ארכיטקטורה](../explanation/architecture.md#standardized-responses-and-errors).

| מצב | קוד |
|---|---|
| קריאה סינכרונית הצליחה | `200` |
| יצירה סינכרונית הסתיימה | `201` |
| **העבודה התקבלה ומסתיימת באופן אסינכרוני** (משימת AWX הופעלה, סנכרון ArgoCD התחיל, משימה נכנסה לתור) | **`202`** + מזהה לתשאול ([עבודה ארוכה](#long-running-work)) |
| המחיקה הסתיימה, בלי גוף | `204` |
| הוולידציה נכשלה | `422` (אוטומטי) |
| טוקן חסר, לא תקין או עם audience שגוי | `401` (אוטומטי, מה-middleware) |
| המשאב לא נמצא | `404` |
| התנגשות (כבר קיים, שינוי מקביל) | `409` |
| שירות חיצוני (upstream) (‏AWX, ArgoCD, Vault, Git, …) נכשל | **`502`** |
| שירות חיצוני (upstream) חרג מזמן ההמתנה | `504` |
| באג | `500` (אוטומטי; אף פעם לא מוחזר בכוונה) |

---

## שגיאות {#errors}

- מחברים זורקים מחלקות בת של **`ExternalServiceError`**: `AWXError`, `ArgoCDError`,
  `GitError` ו-`VaultError`. כל אחת נושאת `service_name`, `status_code` ו-`detail`
  ([שגיאות](api/errors.md)).
- ‏`ExternalServiceError` היא `HTTPException` של FastAPI. אם לא תופסים אותה, היא מחזירה ללקוח את
  קוד הסטטוס של **השירות החיצוני**. הנתיבים תופסים אותה ומחזירים **502**:
    ```python
    app_name = build_app_name(cluster, namespace, name, "haproxy")
    try:
        await create_haproxy_operation(git=git, vault=vault, argocd=argocd, payload=payload.spec)
    except ExternalServiceError as err:
        return JSONResponse(
            ArgoOperationResponse(
                app_name=app_name,
                status="Failed",
                status_code=err.status_code,
                stdout=f"{err.service_name}: {err.detail}",
            ).model_dump(),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    ```
- ‏`404` צפוי מהשירות החיצוני (למשל "הסוד עדיין לא קיים") מטופל בפעולה באמצעות בדיקה של
  `exc.status_code == 404`. הוא לא נחשב לכישלון.
- את סוגי שגיאות האימות (‏`AuthConfigError`, `TokenError`, `SSOError`) מייבאים מ-
  `tashtiot_apis_library.fastapi_template.errors` או מהחבילה הראשית, ולעולם לא מ-`_internal`.
- ה-`detail` של שגיאה לעולם לא מכיל stack traces, טוקנים, או גופי תשובה מהשירות החיצוני שעלולים
  להכיל סודות.
- גופי שגיאה משתמשים במבנה `{"detail": "..."}`.
- תשובות 422 ושורות לוג של ולידציה מכילות רק את ה-`loc`, ה-`msg` וה-`type` של כל שגיאה. הספרייה
  מסירה את הערך שנשלח (‏`input`) ואת `ctx`, כך שסיסמה שנדחתה לעולם לא מוחזרת או נרשמת בלוג. גם
  הודעות של validators מותאמים אישית אסור שיכללו את הערך: כתבו
  `"not a valid IPv4 address"`, ולא `f"'{v}' is not a valid IPv4 address"`.

---

## נתיבים וגרסאות {#paths-and-versioning}

- סכמת הנתיבים: **`/api/<api-name>/v<N>/<resource>`**, למשל `/api/example/v1/dns`, שמוגדרת
  כ-`API_PREFIX` בקובץ `conf.py` של המודול.
- שמות משאבים הם שמות עצם ברבים, ופעלי ה-HTTP מבטאים את הפעולה. סטטוס של משימה:
  `GET .../status/{job_id}` או `GET .../status?...`.
- **שינוי שובר משמעו גרסה חדשה.** הוא נכנס ל-`app/v2/<resource>/` לצד `v1`.
  הסרה או שינוי שם של שדה, שינוי טיפוס, או הפיכת שדה אופציונלי לחובה הם שינויים שוברים.
  הוספת שדה אופציונלי אינה שינוי שובר.
- ה-endpoints מקובצים ב-Swagger באמצעות `API_TAGS`, למשל `["v1 - DNS Operations"]`.
- לכל נתיב יש `summary`, ‏`description`, ‏`response_model` וקוד סטטוס מפורש.

### פונקציות ליצירת routers {#router-factories}

כל מודול חושף `get_<resource>_router(<connectors...>) -> APIRouter`. המחברים נלכדים ב-closure
ומועברים במפורש לפעולות. הם לא מוזרקים באמצעות `Depends` של FastAPI, ולעולם לא נבנים מחדש בכל
בקשה.

```python
def get_v1_dns_router(awx_client: AWX, provider=None) -> APIRouter:
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post(
        "/",
        response_model=DNSRecordResponse,
        status_code=202,
        summary="Create DNS Record",
        description="Launches the AWX create-DNS job.",
    )
    async def create(record: DNSRecordCreate) -> DNSRecordResponse:
        return await create_dns(record, awx_client, provider)

    return router
```

---

## כללי async {#async-rules}

למה הכללים האלה קיימים: [אסינכרוניות ולולאת האירועים](../explanation/async.md).

1. Route handlers שמבצעים I/O מוגדרים כ-`async def` וממתינים (`await`) לספריות אסינכרוניות.
2. שום דבר לא חוסם את לולאת האירועים בתוך קוד `async def`:

    | אסור | השתמשו במקום זאת ב- |
    |---|---|
    | `requests.get(...)` | `BaseAPI` / `httpx.AsyncClient` |
    | `time.sleep(n)` | `await asyncio.sleep(n)` |
    | `subprocess.run(...)` | `await asyncio.create_subprocess_exec(...)` |
    | לקוח DB או SDK סינכרוני | הדרייבר האסינכרוני שלו, או `await asyncio.to_thread(fn, ...)` |
    | עבודת CPU כבדה | `await asyncio.to_thread(...)`, או העברתה מחוץ לנתיב הבקשה ([עבודה ארוכה](#long-running-work)) |

3. Handlers רגילים מסוג `def` מיועדים רק לעבודת CPU טריוויאלית (כמו `/whoami`), ולעולם לא כדרך
   לקרוא ל-I/O סינכרוני.
4. קריאות בלתי תלויות רצות במקביל עם `asyncio.gather`.
5. בלי `asyncio.run()` או `loop.run_until_complete()` בתוך האפליקציה.
6. לכל `await` של רשת יש timeout. ברירת המחדל של `BaseAPI` היא 10 שניות, ופונקציות העזר
   `wait_for_*` של המחברים מקבלות timeouts מפורשים.
7. כל משימה שנוצרת עם `asyncio.create_task` נשמרת עם הפניה עד שהיא מסתיימת
   ([למה](../explanation/job-queues.md#in-process-background-tasks-are-not-a-queue)).

---

## מחברים {#connectors}

מתוך החבילה הראשית `tashtiot_apis_library` ([מחברים](api/connectors.md)):

| מחבר | בנייה | המתודות האסינכרוניות העיקריות |
|---|---|---|
| **`AWX`** | `AWX(base_url, token)` | `launch_job`, `launch_workflow_job`, `get_job_status(job_id, include_logs=False)`, `get_workflow_job_status`, `wait_for_job_completion(job_id, timeout=300, poll_interval=5)`, `wait_for_workflow_completion`, `get_job_output(job_id, start_line, page_size)` |
| **`ArgoCD`** | `ArgoCD(base_url, api_key, application_set_timeout)` | `sync`, `create_app`, `delete_app`, `get_app_status`, `wait_for_app_creation`, `wait_for_app_deletion`, `wait_for_update`, `get_app_values`/`modify_values`, `get_app_parameters`/`modify_parameters`, `add_namespace_to_cluster_secret` |
| **`Git`** (‏Bitbucket Server) | `Git(base_url, token, username_or_email, project_key, repo_slug, default_ref="main", ssh_key_file_path=..., ssh_port=7995)` | `add_file`, `modify_file`, `delete_file`, `get_file_content`, `file_exists`, `list_dir`, `list_files_recursive` |
| **`Vault`** | `Vault(base_url, token)` | `read_secret`, `write_secret`, `delete_secret` |
| **`BaseAPI`** (כללי) | `BaseAPI(base_url, headers=None, auth=None, timeout=10.0, verify=False)` | כל קריאה של `httpx.AsyncClient` |

מתכונים: [עבודה עם AWX, ArgoCD ו-Vault](../how-to/use-awx-argocd-vault.md),
[קריאה וכתיבה של קבצים ב-Bitbucket](../how-to/read-write-bitbucket.md).

**כללים:**

1. המחברים נבנים פעם אחת ב-`create_app()` ומוזרקים.
2. כשקיים מחבר, משתמשים בו במקום ב-HTTP גולמי. לשירותים אחרים קוראים דרך `BaseAPI`, או דרך
   `sso_authenticated_api` כשהם דורשים טוקן SSO.
3. ברירת המחדל של `BaseAPI` היא `verify=False`. שירותים עם תעודה תקינה מקבלים `verify=True`, או
   `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` שמצביעים על חבילת ה-CA הארגונית. כיבוי האימות של התעודה
   הוא החלטה מכוונת שמתועדת בהערה.
4. משתמשים בתוצאות של המחברים כפי שהן מוחזרות (מודלי Pydantic / `OperationResponse`s). לא מפענחים
   JSON גולמי ידנית.
5. תוצאה של הפעלת AWX (‏`status="successful"`, `status_code=200`, `job_id`) פירושה שהמשימה
   **נכנסה לתור**, לא שהסתיימה ([AWX הוא כבר תור משימות](../explanation/job-queues.md#awx-is-already-a-job-queue)).
6. אינטגרציה חדשה שיותר מצוות אחד ישתמש בה נוספת לספרייה כמחבר
   ([הוספת מחבר חדש](../how-to/add-a-connector.md), [תרומה לפרויקט](../contributing/index.md)),
   ולא מועתקת בין APIs.

---

## אימות {#authentication}

רקע על התכנון: [תכנון האימות](../explanation/authentication.md).

### נכנס {#inbound}

- מחווט על ידי `general_create_app(enable_auth=True)` ונאכף רק כש-`AUTH_ENABLED=true`. כשהוא כבוי,
  האפליקציה עולה **פתוחה** (לפיתוח בלבד).
- מוגדר **מצב** אימות **אחד** בדיוק. אחרת יצירת האפליקציה נכשלת עם `AuthConfigError`.

    | מצב | הגדרה | שימוש |
    |---|---|---|
    | **JWKS / OIDC (RS256)** | `AUTH_OIDC_ISSUER` (‏discovery) או `AUTH_JWKS_URL` | **Production** ([אבטחת API עם OIDC ו-JWKS](../how-to/secure-with-oidc-jwks.md)) |
    | מפתח ציבורי מקומי (RS256) | `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | אימות offline או ברשת המבודדת (air-gapped) |
    | סוד משותף (HS256) | `AUTH_HS256_SECRET` | בדיקות ופיתוח מקומי בלבד |

- **מה נבדק:** החתימה של הטוקן, תוקפו (‏`AUTH_REQUIRE_EXP=true` כברירת מחדל) וה-audience שלו.
  **ב-Production מגדירים `AUTH_AUDIENCE`** ל-audience של ה-API. ‏`AUTH_ISSUER` הוא בדיקה נוספת
  אופציונלית.
- הטוקן נקרא מ-`Authorization: Bearer <jwt>` (‏`AUTH_HEADER_NAME`). כישלון מחזיר 401
  עם `WWW-Authenticate: Bearer`.
- נתיבים שמוחרגים כברירת מחדל: `/health`, `/metrics`, `/static`, `/docs`, `/redoc`,
  `/openapi.json`, `/.well-known`, `/liveness` ו-`/readiness`. אפשר להוסיף עוד באמצעות
  `AUTH_EXCLUDE_PATHS`. ה-probes נשארים מוחרגים.
- את ה-claims המאומתים קוראים עם `Depends(get_current_claims)` מתוך
  `tashtiot_apis_library.fastapi_template.auth`, לצורכי לוגים וביקורת.
- טוקנים מאומתים מחוץ לבקשה באמצעות `verify_token`
  ([אימות טוקן מחוץ לבקשה](../how-to/verify-a-token.md)).
- כפתור ה-**Authorize** של Swagger מופיע אוטומטית כשהאימות נאכף
  ([הזרקה ל-OpenAPI ול-Swagger](../explanation/openapi-swagger-injection.md)).

!!! important "ההרשאות מטופלות מחוץ ל-APIs"
    בשלב זה, האימות הנכנס הוא **אימות בלבד**: ה-API בודק שה-JWT תקין ושהונפק עבור ה-audience שלו.
    **הרשאות** (איזה קורא רשאי לעשות מה, ועל איזה פרויקט) נאכפות **מחוץ ל-APIs**. ה-APIs **לא**
    מוסיפים בדיקות הרשאה על claims של הטוקן כמו `project`, תפקידים או scopes.

### יוצא (משירות לשירות) {#outbound-service-to-service}

- לשירותי יעד מוגנים קוראים עם `sso_authenticated_api(base_url)` מתוך
  `tashtiot_apis_library.fastapi_template.security`, שמשתמש ב-grant מסוג `client_credentials`
  של OAuth2.
- הוא מוגדר באמצעות `AUTH_SSO_TOKEN_URL`, `AUTH_SSO_CLIENT_ID` ו-`AUTH_SSO_CLIENT_SECRET` (וגם
  `SCOPE`, `AUDIENCE` ו-`AUTH_STYLE` האופציונליים).
- הספרייה שומרת את הטוקנים ב-cache ומחדשת אותם. ה-APIs לא שומרים טוקנים ב-cache בעצמם.
- ב-Keycloak, ה-`aud` של שירות היעד מגיע מ-scope עם Audience mapper (‏`AUTH_SSO_SCOPE`).
- הגדרות חסרות זורקות `AuthConfigError`, שהפעולה תופסת והופכת לתוצאת שגיאה נקייה.
- מתכונים: [קריאה לשירותים אחרים עם SSO](../how-to/call-services-with-sso.md).

### ה-upstream של Remote Config {#remote-config-upstream}

- ‏`CONFIG_REMOTE_AUTH_METHOD`: ‏`sso` (ברירת מחדל, `CONFIG_REMOTE_SSO_*`), ‏`bearer`
  (‏`CONFIG_REMOTE_BEARER_TOKEN`) או `none` (פיתוח מקומי). ראו
  [הפעלת ה-Remote Config API](../how-to/enable-remote-config-api.md#choose-the-outbound-auth).

### טוקנים לפיתוח {#dev-tokens}

- נוצרים עם `gen-auth-material` ([יצירת חומרי אימות לפיתוח](../how-to/generate-auth-material.md),
  [CLI](cli.md)).

---

## Remote Config {#remote-config}

- ערכים ש**משתנים לפי סביבה או קואורדינטה** (מזהי תבניות, endpoints, מכסות) נפתרים דרך
  `enable_remote_config_api` ו-`provider.resolve_infra_config(payload.metadata)`, ולא נכתבים
  hard-coded לכל סביבה ([הפעלת ה-Remote Config API](../how-to/enable-remote-config-api.md)).
- החיווט הוא **opt-in**: הוא מופעל רק כש-`CONFIG_API_URL` מוגדר, ו-`AuthConfigError` נתפסת
  ונרשמת בלוג.
- לכל ערך שנפתר יש ברירת מחדל סטטית ב-`conf.py`, שמשמשת כשהספק מושבת או כשהמפתח חסר:
    ```python
    resolved = await provider.resolve_infra_config(payload.metadata)
    template_id = resolved.get("awx_create_dns_template_id", config.AWX_CREATE_DNS_TEMPLATE_ID)
    ```

---

## עבודה ארוכה {#long-running-work}

מושגים וטבלת ההחלטה: [תורי משימות ועבודה ארוכה](../explanation/job-queues.md).

- עבודה שלא מסתיימת בבירור בתוך זמן בקשה (בערך 5 שניות) **לא ממתינים לה בתוך הבקשה**.
- חוזה ה-API לעבודה כזו:

    ```
    POST   /api/<api>/v1/<resource>                -> 202 {id, status, ...}
    GET    /api/<api>/v1/<resource>/status/{id}    -> 200 {id, status, stdout, ...}
    ```

    הסטטוסים משתמשים באוצר המילים של `OperationResponse`: ‏`pending`/`running` בזמן שהעבודה
    מתבצעת, ו-`successful`, `failed` או `canceled` כשהיא הגיעה למצב סופי.
- נתיב הסטטוס מחזיר **HTTP 200** בכל פעם שהוא הצליח לקרוא את המשימה, כולל משימה שנכשלה. מצב
    המשימה מופיע בגוף (‏`status`, ועבור AWX גם ה-`status_code` הממופה). הוא לעולם לא מועתק לסטטוס
    ה-HTTP. מזהה לא מוכר מחזיר 404, וכישלון של השירות החיצוני מחזיר 502.
- **משימות AWX הן תור המשימות.** API שמפעיל משימות AWX מחזיר את ה-`job_id` של AWX וקורא את
  הסטטוס עם `awx.get_job_status`.
- **אין בספרייה מימוש של תור משימות.** צוות שצריך תור עמיד לעבודה שרצה בתוך ה-API שלו מממש תור
  כזה בעצמו או משתמש בפתרון חיצוני.
- משימות רקע בתוך התהליך מיועדות רק לעבודה קצרה, ברמת best-effort. הסטטוס שלהן מגיע מהמערכות
  החיצוניות, לעולם לא מהזיכרון, וכל משימה נשמרת עם הפניה.
- עבודה תקופתית משתמשת ב-`general_create_app(async_background_tasks=[...])` והיא אידמפוטנטית (עותק
  אחד רץ בכל רפליקה).

---

## ריבוי רפליקות {#multiple-replicas}

כל API רץ כמה רפליקות זהות מאחורי load balancer, ובזמן rolling updates רצות שתי גרסאות זו לצד זו.
למה כל כלל קיים: [APIs מסוג cloud-native וריבוי רפליקות](../explanation/cloud-native.md).

- **Stateless:** אין מקור אמת בזיכרון התהליך או במערכת הקבצים המקומית. כל רפליקה חייבת להיות
  מסוגלת לענות על כל בקשה, ולכן הסטטוס מגיע מהמערכת שאחראית עליו (‏AWX, ArgoCD, Git, Vault) או
  ממאגר משותף.
- cache לכל pod מותר רק כ-cache, כלומר כש-miss גורם לשליפה מחדש.
- **אידמפוטנטי ועמיד ל-race conditions:** בטוח לחזור על פעולות ובטוח להריץ אותן במקביל על שתי
  רפליקות. התנגשויות בין רפליקות נשארות באחריות השירות החיצוני (למשל `add_file` של Git על נתיב
  קיים) ומוחזרות כ-`409`. לא משתמשים ב-`asyncio.Lock` כהגנה בין בקשות.
- **משימות רקע רצות בכל רפליקה.** רק לולאות אידמפוטנטיות נכנסות ל-`async_background_tasks`.
  עבודה שחייבת לרוץ פעם אחת עוברת ל-CronJob של Kubernetes, לתזמון של AWX או לתור עם צרכן יחיד.
- **Disposable:** האפליקציה עולה מהר ונכשלת מהר על הגדרות שגויות. הבקשות קצרות מספיק כדי להסתיים
  בתוך זמן החסד של הכיבוי (30 שניות כברירת מחדל).
- **Probes:** ה-liveness וה-readiness לא תלויים במערכות חיצוניות.
- **תאימות לאחור על פני שחרור אחד**, כי בזמן פריסה הדרגתית pods ישנים וחדשים משרתים יחד. שינויים
  שוברים עוברים לגרסת API חדשה.
- **תהליך uvicorn אחד לכל pod.** מגדילים קנה מידה באמצעות רפליקות.
- הלוגים נכתבים ל-stdout עם מזהי קורלציה. ה-dashboards מאגדים מדדים מכל ה-pods.

---

## פעולות מרובות שלבים {#multi-step-operations}

לפעולות שנוגעות בכמה מערכות (‏Git → Vault → ArgoCD) אין טרנזקציה מבוזרת. הן פועלות לפי הכללים
האלה:

1. השלבים מסודרים כך שהשלב שהכי זול לבטל רץ ראשון, ושום דבר שגלוי למשתמש לא עולה לאוויר עד השלב
   האחרון.
2. לפני שמשנים מצב, שומרים ממנו snapshot (קובץ ה-Git הנוכחי, הסוד הנוכחי ב-Vault).
3. בכישלון, מבצעים פעולות פיצוי לשלבים שהושלמו, בסדר הפוך. לכל פעולת פיצוי יש `try/except` משלה,
   ופעולת פיצוי שנכשלה נרשמת בלוג עם `logger.exception`. לאחר מכן השגיאה המקורית נזרקת מחדש.
4. ה-rollback סימטרי בכל מקום שבו העבודה ממשיכה (בתוך הבקשה, וגם במשימות רקע או במשימות).
5. הפעולות אידמפוטנטיות:
    - **יצירה:** משאב קיים עם אותו spec מחזיר הצלחה או `409` (מתועד).
    - **עדכון:** כתיבות שלא משנות דבר מדולגות (`example-api` משווה YAML עם `yaml_data_equals`).
    - **מחיקה:** "כבר לא קיים" (`404`) נחשב להצלחה.
6. ערכי סודות ריקים מוסרים לפני הכתיבה ל-Vault (‏`filter_secret_payload` ב-
   `example-api`).
7. שמות המשאבים דטרמיניסטיים ונגזרים מהבקשה (למשל
   `{cluster}-{namespace}-{resource}-{name}`).

---

## לוגים ו-observability {#logging-and-observability}

הגדרת הלוגר ומוסכמת הרמות: [לוגים](../explanation/logging.md).

- הלוגים נכתבים עם `from loguru import logger`. הספרייה כבר רושמת את הבקשות והתשובות.
- השתמשו ב-placeholders עצלים: `logger.info("Syncing app {} in {}", app_name, cluster)`.

| רמה | משמשת ל- |
|---|---|
| `debug` | פרטי payload (בלי סודות) |
| `info` | אירועים עסקיים ("launched AWX job 123 for record X") |
| `warning` | פועל, אבל במצב מוחלש |
| `error` / `exception` | כישלונות, כולל stack traces |

- שורות הלוג כוללות מזהי קורלציה: `job_id`, `app_name`, `metadata.project` וה-`sub` של
  הקורא.
- **לעולם לא נרשמים בלוג:** טוקנים, סודות, כותרות `Authorization`, payloads של Vault, או גופי בקשה
  שמכילים `secrets`.
- בלי `print()` בקוד האפליקציה.
- ‏`/metrics` חשוף ל-Prometheus. מדדים עסקיים מוסיפים עם `prometheus_client`.
- ‏`/liveness` ו-`/readiness` נשארים בלי אימות.
- סכמת ה-OpenAPI (‏`/docs`) היא החוזה הציבורי, ולכן ה-summaries, התיאורים והדוגמאות נשמרים
  מדויקים.

---

## בדיקות {#testing}

הגדרות: `asyncio_mode = "auto"`, `pythonpath = ["."]`, `testpaths = ["tests"]`. הריצו עם
`uv run pytest`.

| בדיקה נדרשת | דוגמה ב-`example-api` |
|---|---|
| ולידציה של הסכמה: payloads תקינים ולא תקינים (→ 422), כולל בקשה עם `metadata.project` **בלבד** ובקשה עם מפתחות metadata נוספים | `tests/v1/dns/test_dns_schema.py` |
| נתיבים דרך `TestClient(create_app())` עם bearer תקין | `tests/v1/dns/test_dns_routes.py` |
| אימות: בלי טוקן → 401, טוקן שגוי → 401, טוקן תקין → 200 | `tests/v1/auth_demo/test_auth_demo_routes.py` |
| פעולות: כל מסלול כישלון, ובדיקה שה-rollback מופעל | — |
| גיבוי ל-Remote Config (ספק מושבת או מפתח חסר → ברירת מחדל סטטית) | `tests/v1/dns_config/` |

- **סביבה הרמטית:** קובץ `tests/conftest.py` שבשורש מרוקן את משתני `AUTH_*`/`CONFIG_*`
  האופציונליים. קובצי ה-conftest של המודולים מגדירים את המשתנים הנדרשים **לפני** ייבוא `app.main`.
- **אימות בבדיקות:** ‏HS256 (‏`AUTH_ENABLED=true`, `AUTH_HS256_SECRET=<32+ bytes>`), עם טוקנים
  שנוצרים באמצעות `jwt.encode(...)` או [`gen-auth-material`](../how-to/generate-auth-material.md).
- **בלי קריאות רשת אמיתיות.** עשו mock למתודות של המחברים עם `monkeypatch.setattr(...)` (מתודות
  אסינכרוניות שעושים להן mock מוגדרות כ-`async def`), או עשו mock ל-HTTP עם `respx`.
- הפעולות מקבלות מחברים כארגומנטים, ולכן בודקים אותן ישירות בבדיקות יחידה עם מימושים מזויפים.

---

## אריזה ו-Docker {#packaging-and-docker}

- ‏`uv sync --group dev` מתקין הכול. ‏`uv.lock` נשמר ב-git. מייצרים אותו מחדש עם
  `uv lock` בסביבה עם גישה מלאה ל-Artifactory.
- ‏`uv.toml` (אינדקס ה-Artifactory + פרטי ההתחברות) נמצא בשורש המאגר או ב-`~/.config/uv/uv.toml`,
  ולעולם לא נשמר ב-git.
- ‏`tashtiot-apis-library` מוצמדת לגרסה מינימלית (‏`>=1.1.0`). דריסת נתיב ב-`[tool.uv.sources]`
  מיועדת לפיתוח מקומי של הספרייה בלבד. בדקו את [יומן השינויים](../changelog.md) כשאתם מעלים את
  הגרסה.
- בלי dependency חדש למשהו שהספרייה, הספרייה הסטנדרטית או FastAPI כבר עושים. בלי לקוחות HTTP
  סינכרוניים (‏`requests`).
- Dockerfile (לפי זה של `example-api`):
    - ה-base image המאושר של Python 3.12 מ-JFrog Artifactory
    - העתקת `pyproject.toml`, `uv.lock` ו-`.python-version`, אחר כך הרצת `uv sync --frozen --no-dev`,
      ואחר כך העתקת `app/`
    - ‏`ARG APP_VERSION` / `ENV APP_VERSION` שמוגדרים מתגית ה-git
    - `CMD ["uv","run","--no-sync","-m","app.main","--host","0.0.0.0","--port","5000"]`
    - בלי סודות ב-image

---

## CI {#ci}

ה-CI רץ על **Woodpecker** (‏`.woodpecker/*.yaml` בכל מאגר) **בתוך הרשת המבודדת (air-gapped)**,
כי הוא צריך את ה-JFrog Artifactory וה-SonarQube הפנימיים.

!!! tip "מדריך ה-CI: ה-Confluence הפנימי"
    מדריך ה-CI והמפרט המלא נמצאים ב-**Confluence הפנימי**, שנגיש רק מהרשת המבודדת. הוא מגדיר את
    שלבי ה-pipeline, הסודות הנדרשים, ה-images וספי ה-quality gate. פעלו לפיו כשאתם מקימים או
    משנים pipeline.

### Pipeline {#pipeline}

ה-pipeline של כל API מבצע את הפעולות הבאות:

| שלב | מה הוא בודק או מייצר |
|---|---|
| **בדיקות** | חבילת בדיקות ה-pytest עוברת ([בדיקות](#testing)) |
| **פורמט** | הקוד תואם ל-formatter (הספרייה עצמה משתמשת ב-`ruff format --check`) |
| **Linting** | ה-linter עובר (הספרייה עצמה משתמשת ב-`ruff check`) |
| **SonarQube** | סריקת ה-SonarQube עוברת את ה-quality gate של הפרויקט |
| **בנייה ודחיפה** | ה-Docker image נבנה (‏kaniko) ונדחף ל-**JFrog Artifactory**, עם תגית של גרסת השחרור, שמועברת גם כ-`APP_VERSION` |

### גרסאות ויומן שינויים (git-cliff) {#versioning-and-changelog-git-cliff}

השחרורים מקבלים גרסאות לפי **semver** (תגיות git בפורמט `vMAJOR.MINOR.PATCH`), וגם הגרסה וגם
`CHANGELOG.md` נוצרים על ידי **git-cliff** מתוך `cliff.toml` (ראו את זה של `example-api`, או את
[יומן השינויים](../changelog.md) של הספרייה הזו כדי לראות את התוצאה).

- **הודעת ה-PR היא הטקסט של יומן השינויים, לא ה-commits הבודדים.** כל PR שממוזג נכנס ל-`master`
  כ-commit אחד שנושא את הכותרת והתיאור של ה-PR, ואת זה git-cliff קורא. הודעות ה-commit בתוך
  ה-branch לא משמשות.
- **כותרות PR חייבות להיות conventional commits**, כי הקידומת קובעת גם את הסעיף ביומן השינויים וגם
  את העלאת הגרסה:

    | קידומת כותרת ה-PR | סעיף ביומן השינויים | העלאת גרסה |
    |---|---|---|
    | `feat: ...` | Added | **minor** |
    | `fix: ...` | Fixed | patch |
    | `refactor: ...`, `perf: ...` | Changed | patch |
    | `docs: ...` | Documentation | patch |
    | `revert: ...` | Reverted | patch |
    | `build: ...`, `ci: ...` | Build, CI | patch |
    | `chore: ...`, `style: ...`, `test: ...` | *(לא מופיע)* | — |
    | `feat!: ...` / `fix!: ...` או footer מסוג `BREAKING CHANGE:` | (הסעיף שלו) | **major** |

    תיאור PR שמזכיר `security` מכניס את הרשומה תחת **Security**.

- **כותרת PR שאינה conventional commit נשמטת** מיומן השינויים ולא מעלה את הגרסה
  (‏`filter_unconventional = true`).
- כתבו את כותרת ה-PR כשורת יומן השינויים שהקוראים יראו, למשל
  `feat: add DNS record status endpoint`.
- ‏`CHANGELOG.md` נשמר ב-git ונוצר על ידי git-cliff, ולכן לא עורכים אותו ידנית.
- שינוי API שובר (‏`v<N>` חדש, ראו [נתיבים וגרסאות](#paths-and-versioning)) משוחרר כגרסת
  **major**.

---

## פערים ידועים ב-`example-api` {#known-gaps-in-example-api}

‏`example-api` הוא המימוש לדוגמה עבור **המבנה ואופן השימוש בספרייה**. אל תעתיקו ממנו את הדברים
הבאים:

| ב-`example-api` | התקן |
|---|---|
| ‏`PUT`/`GET /{record_name}` של `dns` הם stubs (‏`print`, כתובת IP קבועה בקוד ו-`job_id=1234`) | פעולות אמיתיות, או שאין נתיב בכלל |
| לגוף הבקשה של `chat` אין `metadata` | כל נתיב כתיבה מקבל `{metadata, spec}` ([חוזה הבקשה](#request-contract)) |
| שימוש ישיר ב-`InfraOperationRequest` (‏`project` אופציונלי) | ‏`ProjectMetadata` עם `project` כחובה ([מודלי בסיס](#base-models)) |
| פעולות שעדיין רצות מחזירות `200`/`201` | ‏`202` + מזהה לתשאול ([תשובות וקודי סטטוס](#responses-and-status-codes)) |
| ‏`asyncio.create_task(...)` בלי לשמור הפניה | המשימות נשמרות עם הפניה ([כללי async](#async-rules)) |
| ‏`requests` מופיע כ-dependency | רק `httpx` אסינכרוני דרך `BaseAPI` |
| ‏`chat_client = BaseAPI(...).client` בשימוש בלי `async with` (לעולם לא נסגר) | ‏`async with BaseAPI(...) as client:`, או סגירת הלקוח ב-lifespan של האפליקציה |
| שלבי הבדיקות וה-Sonar בהערה ב-`.woodpecker/build.yaml` | מדריך ה-[CI](#ci) |
| ה-`Dockerfile` מושך את ה-base image שלו מ-`harbor.app.com` | ה-base images מגיעים מ-JFrog Artifactory |
| ברירות מחדל שנראות כמו סודות ב-`global_conf.py` (‏`AWX_TOKEN="sheker123"`) | סודות הם שדות חובה בלי ברירת מחדל |

---

## רשימת בדיקה לפני מיזוג {#pre-merge-checklist}

**מבנה וחוזה**

- [ ] המודול בנוי לפי `conf.py / schemas.py / operations.py / routes.py`, ומחווט רק ב-`create_app()`.
- [ ] כל נתיב כתיבה מקבל `{metadata, spec}`. ‏`metadata.project` הוא חובה, שאר הקואורדינטות
      אופציונליות, ו-metadata שאינו בשימוש מתקבל וזוכה להתעלמות.
- [ ] הנתיב הוא `/api/<api>/v<N>/<resource>`, ושינויים שוברים עברו לגרסה חדשה.
- [ ] לכל נתיב יש `response_model`, ‏`summary`, ‏`description` וקוד הסטטוס הנכון.

**Async**

- [ ] אין קריאות חוסמות ב-`async def` (‏`requests`, `time.sleep`, לקוחות סינכרוניים, עבודת CPU כבדה).
- [ ] לכל `await` של רשת יש timeout. קריאות בלתי תלויות משתמשות ב-`asyncio.gather`.
- [ ] עבודה ארוכה מחזירה `202` + מזהה ([עבודה ארוכה](#long-running-work)). לכל משימה שנוצרת
      נשמרת הפניה.

**מחברים ושגיאות**

- [ ] המחברים נבנים פעם אחת ומוזרקים. אין HTTP גולמי כשקיים מחבר.
- [ ] ‏`ExternalServiceError` ממופה ל-`502`. אין סודות או stack traces ב-`detail`.
- [ ] זרימות מרובות שלבים שומרות snapshot של המצב, מבצעות פעולות פיצוי בסדר הפוך, רושמות בלוג
      כישלונות של rollback, והן אידמפוטנטיות.
- [ ] בטוח לריבוי רפליקות: אין מצב בזיכרון או בדיסק המקומי, בטוח מול בקשות כפולות מקבילות,
      אין עבודה חד-פעמית ב-`async_background_tasks`, תאימות לאחור עם השחרור הקודם.

**אבטחה**

- [ ] ‏`general_create_app(enable_auth=True)`. הגדרות ה-Production משתמשות ב-JWKS/OIDC ומגדירות
      `AUTH_AUDIENCE`.
- [ ] אין בדיקות הרשאה על claims של הטוקן בתוך ה-API (ההרשאות מטופלות מחוץ ל-APIs).
- [ ] אין סודות ב-git, ב-`.env.example`, בברירות מחדל של `conf.py`, בלוגים או ב-image. אימות
      ה-TLS פעיל, או כבוי עם סיבה מתועדת.

**איכות**

- [ ] ‏`.env.example` ו-`README.md` מעודכנים עבור כל משתנה ונתיב חדשים.
- [ ] הבדיקות מכסות את הסכמה (תקינה, לא תקינה, metadata עם project בלבד), נתיבים עם אימות, ומסלולי
      כישלון ו-rollback. בלי קריאות רשת אמיתיות.
- [ ] ה-CI ירוק (בדיקות, פורמט, linting, ‏SonarQube) לפי מדריך ה-CI ב-Confluence הפנימי ([CI](#ci)).
- [ ] כותרת ה-PR היא conventional commit שנקראת טוב כשורה ביומן השינויים
      ([גרסאות ויומן שינויים](#versioning-and-changelog-git-cliff)).
