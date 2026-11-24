# ארכיטקטורה {#architecture}

העמוד הזה מסביר איך החבילה מאורגנת ולמה.

## שני ארגזי כלים עצמאיים, חבילה אחת {#two-independent-toolsets-one-package}

הספרייה כוללת שני ארגזי כלים עצמאיים ברובם תחת הפצה אחת:

1. **מחברי תשתית** (`connectors/`): לקוחות אסינכרוניים ל-ArgoCD, ‏AWX, ‏Bitbucket Server
   ו-Vault.
2. **תבנית FastAPI** (`fastapi_template/`): פונקציית יצירת האפליקציה `general_create_app` וה-middleware,
   המטריקות, ה-probes, האימות ויכולת ה-Remote Config שלה.

הם ארוזים יחד מטעמי נוחות, אבל צרכן יכול להשתמש בכל אחד מהם לבד. כיוון התלות היחיד ביניהם: המחברים
תלויים ב-`fastapi_template.utils.BaseAPI` (עטיפת ה-HTTP היוצא המשותפת), ולכן **תבנית ה-FastAPI היא
תלות של המחברים, ולא להפך.**

## דפוס המחבר בשלוש שכבות {#the-three-layer-connector-pattern}

כל מחבר תחת `connectors/<name>/` מפוצל לשלושה מודולים בדיוק, ומחברים חדשים חייבים לפעול באותה
צורה (ראו [הוספת מחבר חדש](../how-to/add-a-connector.md)):

| שכבה | קובץ | אחריות |
|---|---|---|
| **מודלים** | `models.py` | מבני בקשה ותשובה ב-Pydantic. ‏aliases ל-JSON ב-camelCase; סובלנות לשדות לא מוכרים. |
| **לקוח** | `client.py` | ‏HTTP ברמה נמוכה דרך `BaseAPI`. ממיר קודי סטטוס של שגיאה לחריגות מוגדרות טיפוס; מחזיר מודלים מפוענחים, אף פעם לא dicts גולמיים. |
| **שירות** | `service.py` | המחלקה ברמה הגבוהה שמשתמשים יוצרים (`AWX`, `Git`, …). **מרכיבה** את הלקוח ומוסיפה תזמור: תשאול, `wait_for_*`, ניסיונות חוזרים. |

הוספת יכולת פירושה לגעת בשכבות מלמטה למעלה: מודל (אם יש מבנים חדשים) ← מתודה בלקוח ← מתודה
בשירות.

אזור ה-SSO היוצא בתבנית ה-FastAPI פועל לפי אותה הפרדה בין מודלים ללוגיקה: מודלי הנתונים שלו
ב-Pydantic (`SSOConfig`, `TokenResponse`) נמצאים לידו ב-`_internal/security/models.py`, ואילו
מחלקות הלקוח והאימות נשארות ב-`_internal/security/sso.py`.

### תשובות ושגיאות אחידות {#standardized-responses-and-errors}

מתודות השירות מחזירות תת-מחלקות של `OperationResponse` (`status`, `status_code`, `return_code`,
`stdout`) ולא את ה-payloads הגולמיים של ה-API: ‏`AWXOperationResponse` מוסיפה `job_id`,
ו-`ArgoOperationResponse` מוסיפה `app_name`. השגיאות הן היררכיה מקבילה: ‏
`ExternalServiceError(HTTPException)` עם תת-מחלקה לכל מחבר (`ArgoCDError`, `GitError`, `VaultError`,
`AWXError`). מכיוון שהן יורשות מ-`fastapi.HTTPException`, זריקה של אחת מהן בתוך נתיב מגיעה ישירות
ללקוח כתשובת HTTP.

## הממשק הציבורי לעומת `_internal` {#the-public-surface-vs-_internal}

תבנית ה-FastAPI שומרת בכוונה על ממשק ציבורי מצומצם; כל מה שתחת `_internal/` הוא מימוש פרטי.
המודולים הציבוריים מאורגנים **לפי תחום**, וכל אחד מהם הוא בית יציב לייבוא:

| מודול | תחום |
|---|---|
| `fastapi_template` | `general_create_app` (+ `enable_remote_config_api` שנטען בעצלות) |
| `fastapi_template.utils` | כלי תשתית: `BaseAPI`, `settings` |
| `fastapi_template.auth` | ‏JWT נכנס: `get_current_claims`, `JWTVerifier`, `verify_token`, `AuthMode`, ‏keygen |
| `fastapi_template.security` | ‏SSO יוצא: `sso_authenticated_api`, `SSOConfig`, `StaticBearerAuth`, … |
| `fastapi_template.errors` | טיפוסי שגיאות האימות |

המודולים הציבוריים האלה הם חזיתות דקות שמייצאות מחדש את מה שב-`_internal`. ההפרדה הזו מאפשרת
לתלויות הכבדות להיטען בעצלות (ראו [תכנון האימות](authentication.md) ו[לוגים](logging.md)), ונותנת
לצרכנים API קטן שמבטא את הכוונה שלו, לייבא ממנו.

## ייבוא בתוך החבילה {#imports-within-the-package}

הקוד הפנימי משתמש ב**ייבוא יחסי** (`from .client import ...`, `from ..errors import ...`,
`from ...fastapi_template.utils import BaseAPI`). נמנעים מייבוא מוחלט של החבילה מתוך עצמה, כי שם
ההפצה נכתב מחדש בזמן ה-build, וייבוא מוחלט כזה היה שביר.
