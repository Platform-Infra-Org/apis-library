# ‏API של אפליקציית FastAPI {#fastapi-app-api}

פונקציית יצירת האפליקציה וכלי התשתית המשותפים.

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings
```

## general_create_app {#general_create_app}

::: tashtiot_apis_library.fastapi_template._internal.general_create_app

## BaseAPI {#baseapi}

עטיפת לקוח ה-HTTP היוצא שהמחברים בנויים עליה. מקבלת `httpx.Auth` דרך `auth=`, כך שאפשר לשלב אותה
עם [פונקציות העזר של SSO](security.md).

::: tashtiot_apis_library.fastapi_template._internal.database.basic_api.BaseAPI

## הגדרות {#settings}

‏`settings` הוא מופע של `ApplicationSettings`. השדות שלו הם משתני הסביבה שמתועדים
ב[מידע העזר על הקונפיגורציה](../configuration.md).

::: tashtiot_apis_library.fastapi_template._internal.utils.config.ApplicationSettings
