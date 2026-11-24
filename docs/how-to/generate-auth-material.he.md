# יצירת חומרי אימות לפיתוח {#generate-dev-auth-material}

החבילה מתקינה סקריפט קונסול בשם `gen-auth-material` שיוצר זוג מפתחות RSA ו-JWT חתום, כדי לתרגל
אימות נכנס במצב **מפתח ציבורי מקומי**. זה הצד החותם שמשלים את המאמת, והוא שימושי לפיתוח מקומי
ולבדיקות, כשלא רוצים להרים ספק זהויות אמיתי.

## מתכונים נפוצים {#common-recipes}

```bash
# Write jwt_private.pem + jwt_public.pem, print a non-expiring token
gen-auth-material

# Mint a token that expires in 30 minutes instead
gen-auth-material --expires-minutes 30

# Print a keypair + token, write nothing to disk
gen-auth-material --no-write

# Set claims to match the verifier's AUTH_AUDIENCE / AUTH_ISSUER
gen-auth-material --sub svc --aud my-api --iss https://idp/

# Reuse existing keys, mint a fresh token
gen-auth-material --private-key jwt_private.pem
```

אפשר גם להריץ אותו כמודול:
`python -m tashtiot_apis_library.fastapi_template._internal.security.keygen`.

## שימוש בפלט {#using-the-output}

הפנו שירות מאמת למפתח הציבורי שנוצר:

```env
AUTH_ENABLED=true
AUTH_PUBLIC_KEY_PATH=jwt_public.pem
AUTH_REQUIRE_EXP=false        # only needed for the default non-expiring token
```

אחר כך שלחו את הטוקן שהודפס בתור `Authorization: Bearer <token>`. המדריך
[אבטחת ה-API שלך](../tutorials/secure-your-api.md) עובר על זה מקצה לקצה.

!!! warning "כברירת מחדל הטוקן לא פג"
    בלי `--expires-minutes`, לטוקן שנוצר **אין claim של `exp`** והוא לעולם לא פג. המאמת דורש `exp`
    כברירת מחדל, ולכן השירות המאמת חייב להגדיר `AUTH_REQUIRE_EXP=false` כדי לקבל אותו (ה-CLI מדפיס
    את הרמז הזה).

## רשימת הדגלים המלאה {#full-flag-list}

טבלת האפשרויות המלאה נמצאת ב[מידע העזר על ה-CLI](../reference/cli.md).
