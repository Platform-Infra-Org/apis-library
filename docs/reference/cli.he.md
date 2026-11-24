# ‏CLI: ‏`gen-auth-material` {#cli-gen-auth-material}

סקריפט קונסול (רשום בשם `gen-auth-material`, ואפשר להריץ אותו גם כ-
`python -m tashtiot_apis_library.fastapi_template._internal.security.keygen`) שיוצר זוג מפתחות RSA
ו-JWT חתום, כדי לתרגל אימות נכנס במצב מפתח ציבורי מקומי.

לשימוש מכוון משימה, ראו [יצירת חומרי אימות לפיתוח](../how-to/generate-auth-material.md).

## התנהגות {#behaviour}

כברירת מחדל הפקודה כותבת את `jwt_private.pem` ואת `jwt_public.pem` לתיקייה הנוכחית ומדפיסה JWT
חתום. לטוקן שנוצר **אין claim של `exp`** והוא לעולם לא פג; המאמת דורש `exp` כברירת מחדל, ולכן
השירות המאמת חייב להגדיר `AUTH_REQUIRE_EXP=false` כדי לקבל אותו (ה-CLI מדפיס את הרמז הזה). העבירו
`--expires-minutes N` כדי ליצור במקום זאת טוקן שפג כרגיל.

## אפשרויות {#options}

| אפשרות | תיאור | ברירת מחדל |
|--------|-------------|---------|
| `--sub` | נושא הטוקן (ה-claim ‏`sub`) | `local-dev` |
| `--aud` | קהל היעד (`aud`); הגדירו כך שיתאים ל-`AUTH_AUDIENCE` | `None` |
| `--iss` | המנפיק (`iss`); הגדירו כך שיתאים ל-`AUTH_ISSUER` | `None` |
| `--algorithm` | אלגוריתם החתימה | `RS256` |
| `--kid` | מזהה המפתח שנכתב ב-header של ה-JWT | `local-dev-key` |
| `--expires-minutes` | אורך חיי הטוקן בדקות; השמיטו לקבלת טוקן שלא פג (בלי `exp`) | `None` (לא פג לעולם) |
| `--key-size` | גודל מפתח ה-RSA בביטים | `2048` |
| `--out-dir` | התיקייה לקבצי ה-`.pem` | `.` |
| `--private-name` | שם הקובץ של המפתח הפרטי | `jwt_private.pem` |
| `--public-name` | שם הקובץ של המפתח הציבורי | `jwt_public.pem` |
| `--no-write` | הדפסה בלבד; לא כותב קבצי מפתח | `false` |
| `--private-key` | נתיב ל-PEM קיים של מפתח פרטי לחתימה (מדלג על יצירת מפתחות) | `None` |
| `--public-key` | נתיב ל-PEM קיים של מפתח ציבורי (נגזר מ-`--private-key` אם לא מועבר) | `None` |
