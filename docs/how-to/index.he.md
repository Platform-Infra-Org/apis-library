# מדריכי ביצוע {#how-to-guides}

מדריכי הביצוע **מכוונים למשימה**: כל אחד הוא מתכון ממוקד להשגת מטרה מסוימת, בהנחה שאתם כבר יודעים
בערך מה אתם רוצים. אם אתם חדשים, התחילו דווקא ב[מדריכים למתחילים](../tutorials/index.md).

## מחברים {#connectors}

- **[קריאה וכתיבה של קבצים ב-Bitbucket](read-write-bitbucket.md)**: שימוש במחבר `Git` כדי לקרוא,
  להוסיף, לשנות ולמחוק קבצים במאגר Bitbucket Server.
- **[עבודה עם AWX, ArgoCD ו-Vault](use-awx-argocd-vault.md)**: הפעלת משימות AWX והמתנה להן, סנכרון
  אפליקציות ArgoCD, וקריאה וכתיבה של סודות ב-Vault.
- **[הוספת מחבר חדש](add-a-connector.md)**: הרחבת הספרייה בשירות משלכם לפי דפוס שלוש השכבות.

## אימות {#authentication}

- **[אבטחת API עם OIDC ו-JWKS](secure-with-oidc-jwks.md)**: אימות טוקנים של ה-SSO של הפלטפורמה
  במצב JWKS: מה לבקש מצוות ה-SSO, איך להגדיר את האימות הנכנס, ואיך הקוראים מקבלים טוקן.
- **[אימות טוקן מחוץ לבקשה](verify-a-token.md)**: בדיקת JWT ב-worker או בסקריפט.
- **[קריאה לשירותים אחרים עם SSO](call-services-with-sso.md)**: צירוף טוקני OAuth2 של
  `client_credentials`, שמתחדשים אוטומטית, לקריאות יוצאות.
- **[יצירת חומרי אימות לפיתוח](generate-auth-material.md)**: יצירת מפתחות וטוקנים עם ה-CLI
  `gen-auth-material`.

## APIs {#apis}

- **[הסבת API לגרסה הנוכחית](migrate-an-api.md)**: פרומפט לסוכן AI שמשדרג API מגרסה ישנה של
  הספרייה, או כותב אותו מחדש על הספרייה ולפי תקני ה-API.

## יכולות {#capabilities}

- **[הפעלת Remote Config API](enable-remote-config-api.md)**: חיבור proxy מאומת ל-Config API חיצוני,
  עם רשימות בחירה חיות ב-Swagger.
- **[הגבלת שדה לפי קונפיגורציה](constrain-field-by-config.md)**: אימות שדה בבקשה מול ערכים שמוגדרים
  בקצה הקואורדינטות של הבקשה (תלות בצד האפליקציה).
