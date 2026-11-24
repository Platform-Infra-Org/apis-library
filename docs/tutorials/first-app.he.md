# האפליקציה הראשונה שלך {#your-first-app}

במדריך הזה תבנו ותריצו שירות FastAPI בעזרת פונקציית יצירת האפליקציה של הספרייה, ואז תסיירו
ביכולות שהיא מחברת עבורכם מראש. צריך Python ≥ 3.10 וכחמש דקות.

## 1. התקנה {#1-install}

```bash
pip install tashtiot-apis-library
# uvicorn comes as a dependency; install nothing else for this tutorial
```

## 2. יצירת האפליקציה {#2-create-the-app}

הפונקציה `general_create_app()` מחזירה מופע `FastAPI` מוגדר במלואו. צרו קובץ בשם `main.py`:

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import settings

app = general_create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
```

זו כל האפליקציה. ‏`general_create_app()` כבר רשמה middleware ללוגים ולמדידת זמנים, handler
לחריגות, נתיב שורש, endpoint למטריקות Prometheus, בדיקות בריאות (probes) ו-Swagger UI שמתארח
בשירות עצמו.

## 3. הרצה {#3-run-it}

```bash
python main.py
# or: uvicorn main:app --port 8000
```

כשהאפליקציה עולה, תראו פלט מובנה של Loguru ב-stdout.

## 4. מה קיבלתם {#4-explore-what-you-got}

כשהשרת רץ, פתחו את הכתובות האלה בדפדפן או עם `curl`:

| URL | מה זה |
|---|---|
| `http://localhost:8000/` | נתיב השורש המובנה |
| `http://localhost:8000/docs` | ‏Swagger UI (מוגש מקבצים סטטיים שמגיעים עם החבילה) |
| `http://localhost:8000/redoc` | ‏ReDoc |
| `http://localhost:8000/metrics` | מטריקות בפורמט Prometheus |
| `http://localhost:8000/health/live` | ‏probe של liveness (מוכן ל-Kubernetes) |
| `http://localhost:8000/health/ready` | ‏probe של readiness |

כל בקשה נרשמת בלוג עם ה-method, הנתיב וזמן העיבוד שלה.

## 5. הוספת נתיב משלכם {#5-add-your-own-route}

ה-`app` שמוחזר הוא מופע `FastAPI` רגיל, כך שמוסיפים נתיבים בדרך המוכרת:

```python
@app.get("/hello")
def hello():
    return {"message": "hello from tashtiot-apis-library"}
```

הפעילו מחדש וגלשו אל `http://localhost:8000/hello`. הנתיב מופיע ב-`/docs` אוטומטית.

## 6. קונפיגורציה דרך הסביבה {#6-configure-via-environment}

כל רכיב מובנה ניתן להגדרה דרך משתני סביבה (או קובץ `.env`). למשל, כדי לשנות את הפורט ואת רמת
הלוגים:

```env
PORT=9000
LOG_LEVEL=DEBUG
APP_NAME=MyFirstApp
```

הרשימה המלאה נמצאת ב[מידע העזר על הקונפיגורציה](../reference/configuration.md).

## הצעדים הבאים {#next-steps}

- **[אבטחת ה-API שלך](secure-your-api.md)**: הוספת אימות JWT bearer.
- **[מדריכי ביצוע](../how-to/index.md)**: חיבור ל-ArgoCD/AWX/Vault, קריאה לשירותים עם SSO, ועוד.
- **[ארכיטקטורה](../explanation/architecture.md)**: הבנת המבנה של פונקציית יצירת האפליקציה ושל
  המחברים.
