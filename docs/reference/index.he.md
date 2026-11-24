# מידע עזר

מידע העזר **מכוון למידע**: העובדות היבשות והמוסמכות. הוא מתאר את המנגנון בלי ללמד או לשכנע.
חפשו כאן כשצריך לוודא שם, ערך ברירת מחדל או חתימה.

- **[תקני API](api-standards.md)**: הכללים של החברה לכל API שנבנה על הספרייה: חוזה ה-
  `{metadata, spec}`, קודי סטטוס, כללי async, אימות, בדיקות, ורשימת בדיקה לפני מיזוג.
- **[קונפיגורציה](configuration.md)**: כל משתני הסביבה שתבנית FastAPI קוראת, עם ערכי ברירת המחדל:
  הגדרות ליבה, אימות נכנס (`AUTH_*`), SSO יוצא (`AUTH_SSO_*`) ו-Remote Config (`CONFIG_REMOTE_*`).
- **[CLI ‏(`gen-auth-material`)](cli.md)**: טבלת האפשרויות המלאה של מחולל המפתחות והטוקנים.

## תיעוד ה-API

נוצר אוטומטית מה-docstrings של החבילה:

- **[מחברים](api/connectors.md)**: `AWX`, `ArgoCD`, `Git`, `Vault` ומודלי התשובה שלהם.
- **[אפליקציית FastAPI](api/fastapi-app.md)**: `general_create_app`, `BaseAPI`, `settings`.
- **[אימות (JWT נכנס)](api/auth.md)**: `get_current_claims`, `verify_token`, `JWTVerifier`, יצירת
  מפתחות.
- **[אבטחה (SSO יוצא)](api/security.md)**: `sso_authenticated_api`, `SSOConfig`, `StaticBearerAuth`.
- **[Remote Config API](api/config-api.md)**: `enable_remote_config_api`, `RemoteConfigProvider`.
- **[שגיאות](api/errors.md)**: סוגי החריגות של המחברים ושל האימות.
- **[סכמות](api/schemas.md)**: מודלים משותפים של בקשות ותשובות.
