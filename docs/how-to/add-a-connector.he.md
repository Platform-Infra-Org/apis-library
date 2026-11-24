# הוספת מחבר חדש {#add-a-new-connector}

המדריך הזה מיועד לתורמים שמרחיבים את הספרייה במחבר תשתית חדש. מחברים בנויים לפי **דפוס שלוש
שכבות** מחייב, כדי שיישארו עקביים וניידים, ומחברים חדשים חייבים להתאים לו.

## שלוש השכבות {#the-three-layers}

צרו חבילה תחת `src/tashtiot_apis_library/connectors/<name>/` עם שלושה מודולים בדיוק:

```
connectors/<name>/
  models.py     # Pydantic request/response models
  client.py     # low-level HTTP
  service.py    # high-level class users instantiate
```

### 1. ‏`models.py`: המבנים {#1-modelspy-shapes}

מודלים של Pydantic לבקשות ולתשובות. השתמשו ב-`Field(alias="...")` למפתחות JSON ב-camelCase,
וב-`model_config = ConfigDict(extra="allow")` כדי לסבול שדות לא מוכרים. תת-מחלקות של
`OperationResponse` שמיוחדות למחבר נמצאות גם הן כאן (למשל, כדי להוסיף `job_id`).

### 2. ‏`client.py`: ‏HTTP ברמה נמוכה {#2-clientpy-low-level-http}

בונה את ה-`httpx.AsyncClient` שלו דרך `BaseAPI(...).client`, ממיר קודי סטטוס של שגיאות HTTP
לחריגה הטיפוסית שלכם, ומחזיר מודלים מפוענחים של Pydantic, **אף פעם לא dicts גולמיים**.

```python
from ...fastapi_template.utils import BaseAPI  # relative import — see below
from ..errors import MyServiceError
from .models import MyModel
```

### 3. ‏`service.py`: תזמור ברמה גבוהה {#3-servicepy-high-level-orchestration}

המחלקה שהמשתמשים יוצרים (למשל `MyService`). היא **מרכיבה** את ה-client (לא יורשת ממנו) ומוסיפה
תזמור: תשאול, `wait_for_*_completion`, ניסיונות חוזרים. מתודות של ה-service מחזירות בדרך כלל
תת-מחלקות סטנדרטיות של `OperationResponse` ולא את המודלים הגולמיים של ה-API.

## מוסכמות שצריך לשמור עליהן {#conventions-to-follow}

- **רק ייבוא יחסי.** בתוך החבילה השתמשו ב-`from ..errors import ...`,
  `from .models import ...`, `from ...fastapi_template.utils import BaseAPI`. ייבוא עצמי מוחלט
  (`from tashtiot_apis_library...`) שגוי כאן, כי הוא פוגע בניידות (שם החבילה נכתב מחדש בזמן
  הבנייה).
- **שגיאות טיפוסיות.** הוסיפו `MyServiceError(ExternalServiceError)` ל-`connectors/errors.py`;
  ה-client מעלה אותה כש-`status_code >= 400`. מכיוון ש-`ExternalServiceError` יורשת מ-
  `fastapi.HTTPException`, העלאה שלה בתוך נתיב הופכת ישירות לתשובת HTTP.
- **לוגים סטנדרטיים.** ‏`from loguru import logger`; ‏INFO לפעולות שהמשתמש רואה, DEBUG לקריאות
  פנימיות ולתשאול, ERROR לפני העלאת חריגה על כשל חיצוני. ראו [לוגים](../explanation/logging.md).
- **ייצאו אותו.** הוסיפו את ה-service ואת השגיאה ל-`__init__.py` הרלוונטי ול-`__all__` של
  `tashtiot_apis_library/__init__.py` הראשי.

הוספת יכולת למחבר קיים היא אותו רעיון, מלמטה למעלה: מודל (אם יש מבנים חדשים) ← מתודה ב-client ←
מתודה ב-service.

## ראו גם {#see-also}

- [ארכיטקטורה: דפוס המחברים בשלוש שכבות](../explanation/architecture.md)
- [מידע עזר על ה-API של המחברים](../reference/api/connectors.md)
