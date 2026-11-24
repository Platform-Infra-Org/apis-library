# ספריית ה-APIs של תשתיות {#tashtiot-apis-library}

חבילת Python אחת שמאגדת שני ארגזי כלים, כמעט בלתי תלויים זה בזה, לבניית שירותים מוכנים לייצור:

1. **מחברים לתשתיות**: לקוחות אסינכרוניים ל-**AWX** (Ansible Tower), ל-**ArgoCD**, ל-**Bitbucket
   Server** ("Git") ול-**HashiCorp Vault**. כל מחבר מאמת את התשובות, מחזיר מודלים טיפוסיים של
   Pydantic, ומעלה חריגות טיפוסיות.
2. **תבנית FastAPI**: פונקציית יצירת אפליקציה לשימוש חוזר (`general_create_app`), עם middleware
   מובנה, מטריקות Prometheus, בדיקות בריאות (probes), Swagger שמתארח בשירות עצמו, לוגים מובנים עם
   Loguru, אימות JWT נכנס, SSO יוצא, ויכולת Remote Config API.

מתקינים את החבילה עם `pip install` ומייבאים מה-namespace הראשי `tashtiot_apis_library`. אין כאן
אפליקציה "להריץ": הספרייה היא המוצר.

```bash
pip install tashtiot-apis-library
```

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault, general_create_app
```

## איך התיעוד מאורגן {#how-this-documentation-is-organised}

התיעוד בנוי לפי שיטת [Diátaxis](https://diataxis.fr/): ארבעה חלקים, וכל אחד עונה על צורך אחר.
התחילו בחלק שמתאים למה שאתם מנסים לעשות:

<div class="grid cards" markdown>

- :material-school: **[מדריכים למתחילים](tutorials/index.md)**

    מכוונים ללמידה. שיעורים מעשיים שלוקחים אתכם מאפס לאפליקציה עובדת ומאובטחת.

- :material-wrench: **[מדריכי ביצוע](how-to/index.md)**

    מכוונים למשימה. מתכונים ממוקדים למטרה מסוימת: קריאת קובץ מ-Bitbucket, קריאה לשירות עם SSO,
    הפעלת Remote Config API.

- :material-book-open-variant: **[מידע עזר](reference/index.md)**

    מכוון למידע. העובדות היבשות: כל משתני הסביבה, הדגלים של ה-CLI, ותיעוד API שנוצר אוטומטית לכל
    רכיב ציבורי.

- :material-lightbulb: **[הסברים](explanation/index.md)**

    מכוונים להבנה. ה"למה": הארכיטקטורה, תכנון האימות, ואיך הלוגים עובדים.

</div>

עובדים **על** הספרייה ולא רק משתמשים בה? ראו **[תרומה לפרויקט](contributing/index.md)** להגדרת
סביבת הפיתוח, לכלים ולמוסכמות.

## במבט מהיר {#at-a-glance}

| רוצים… | לכו אל |
|---|---|
| לבנות API של החברה בדרך הסטנדרטית | [מידע עזר: תקני API](reference/api-standards.md) |
| להרים שירות FastAPI תוך דקות | [מדריך: האפליקציה הראשונה שלך](tutorials/first-app.md) |
| להגן על endpoints עם אימות JWT bearer | [מדריך: אבטחת ה-API שלך](tutorials/secure-your-api.md) |
| לעבוד מול ArgoCD / AWX / Vault / Bitbucket | [מדריך ביצוע: מחברים](how-to/use-awx-argocd-vault.md) |
| לאמת קריאות יוצאות לשירותים אחרים | [מדריך ביצוע: קריאה לשירותים עם SSO](how-to/call-services-with-sso.md) |
| לחפש משתנה סביבה | [מידע עזר: קונפיגורציה](reference/configuration.md) |
| להבין את דפוס המחברים | [הסבר: ארכיטקטורה](explanation/architecture.md) |

!!! note "דרישות"
    Python ≥ 3.10. החבילה תלויה ב-FastAPI, httpx, Pydantic v2, Loguru ו-PyJWT. תלויות האימות
    והמטמון הכבדות נטענות רק כשצריך, כך שיכולות שלא משתמשים בהן לא עולות דבר בזמן הייבוא.
