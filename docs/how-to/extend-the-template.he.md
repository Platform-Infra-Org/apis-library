# הרחבת תבנית FastAPI {#extend-the-fastapi-template}

‏`general_create_app()` מחזירה מופע `FastAPI` רגיל, כך שבתור **צרכנים** אפשר להוסיף לו נתיבים
ו-middleware משלכם ישירות, בלי שום שינוי בספרייה:

```python
app = general_create_app()


@app.get("/custom")
def custom():
    return {"ok": True}
```

המדריך הזה מיועד ל**תורמים** שמוסיפים לתבנית רכיב *מובנה*, כזה שמגיע מאחורי דגל `enable_*`
בפונקציית יצירת האפליקציה. הפונקציה מחברת כל רכיב מובנה דרך פונקציות רישום קטנות תחת
`_internal/`, שמופעלות או מכובות לפי ארגומנט מילת מפתח.

## הוספת middleware מובנה {#add-a-built-in-middleware}

1. צרו אותו תחת `_internal/middlewares/`:

   ```python
   # _internal/middlewares/my_middleware.py
   from fastapi import Request
   from loguru import logger
   from starlette.middleware.base import BaseHTTPMiddleware


   class MyMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request: Request, call_next):
           logger.debug("before {}", request.url.path)
           response = await call_next(request)
           return response
   ```

2. רשמו אותו ב-`add_middlewares` (`_internal/middlewares/__init__.py`) מאחורי דגל:

   ```python
   def add_middlewares(app, *, enable_my_middleware: bool = True, ...):
       if enable_my_middleware:
           app.add_middleware(MyMiddleware)
   ```

   שימו לב לסדר: Starlette מפעיל middleware בסדר LIFO, ולכן האימות, הלוגים ומדידת הזמנים נרשמים
   בסדר מסוים. הוסיפו את שלכם במקום המתאים לו בשרשרת.

3. העבירו את הדגל דרך `general_create_app` (`_internal/__init__.py`), והעבירו אותו הלאה ל-
   `add_middlewares(app, enable_my_middleware=enable_my_middleware, ...)`.

## הוספת נתיב מובנה {#add-a-built-in-route}

1. צרו router תחת `_internal/routes/`:

   ```python
   # _internal/routes/my_route.py
   from fastapi import APIRouter

   router = APIRouter(prefix="/my-feature", tags=["My Feature"])


   @router.get("/status")
   async def status():
       return {"status": "ok"}
   ```

2. רשמו אותו ב-`add_routers` (`_internal/routes/__init__.py`) מאחורי דגל:

   ```python
   def add_routers(app, *, enable_my_route: bool = True, ...):
       if enable_my_route:
           app.include_router(router)   # add include_in_schema=False to hide from /docs
   ```

3. העבירו דגל `enable_my_route` דרך `general_create_app`.

## הוספת כלי משותף {#add-a-shared-utility}

שימו רכיבים פנימיים לשימוש חוזר תחת `_internal/utils/` (או `_internal/database/` עבור HTTP). כדי
להפוך כלי ל**ציבורי**, ייצאו אותו מחדש מהמודול הציבורי המתאים: `fastapi_template/utils.py`
(תשתית), `auth.py` (‏JWT נכנס), `security.py` (‏SSO יוצא) או `errors.py`, והוסיפו אותו ל-`__all__`
של אותו מודול. השאירו תלויות כבדות בטעינה עצלה במקומות שבהם המודולים הקיימים עושים זאת (ראו
[ארכיטקטורה](../explanation/architecture.md)).

## רשימת בדיקה {#checklist}

- קוד חדש משתמש ב**ייבוא יחסי** וכותב לוגים דרך `from loguru import logger`
  ב[רמות הסטנדרטיות](../explanation/logging.md).
- אפשר **לכבות** כל רכיב מובנה דרך דגל `enable_*` (עם ברירת מחדל הגיונית).
- סמלים ציבוריים נכנסים לממשק הציבורי המצומצם; המימוש נשאר תחת `_internal/`.
- נוספו בדיקות תחת `tests/fastapi_template/`.

## ראו גם {#see-also}

- [הוספת מחבר חדש](add-a-connector.md)
- [ארכיטקטורה](../explanation/architecture.md)
- [תהליך הפיתוח](../contributing/development.md)
