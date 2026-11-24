# אבטחת ה-API שלך {#secure-your-api}

במדריך הזה תוסיפו **אימות JWT נכנס** לאפליקציה מ[האפליקציה הראשונה שלך](first-app.md): תיצרו מפתח
וטוקן לפיתוח, תפעילו את האימות, תגנו על נתיב, ותקראו לו עם bearer token דרך Swagger. נשתמש במצב
**מפתח ציבורי מקומי**, כי הוא לא דורש ספק זהויות חיצוני, ולכן הוא מושלם ללמידה.

## 1. יצירת חומרי מפתח לפיתוח {#1-generate-dev-key-material}

החבילה מתקינה את הפקודה `gen-auth-material`. הריצו אותה כדי ליצור זוג מפתחות RSA וטוקן חתום:

```bash
gen-auth-material
```

הפקודה כותבת את `jwt_private.pem` ואת `jwt_public.pem` לתיקייה הנוכחית, ומדפיסה JWT ורמז. כברירת
מחדל לטוקן **אין claim של `exp`** והוא לעולם לא פג, וזה נוח למדריך.

!!! note "טוקנים שלא פגים"
    מכיוון שלטוקן שנוצר אין `exp`, צריך להורות למאמת לקבל אותו. נעשה את זה בהמשך עם
    `AUTH_REQUIRE_EXP=false`. כדי ליצור במקום זאת טוקן שפג כרגיל, העבירו `--expires-minutes 30`.
    ראו את [מידע העזר על ה-CLI](../reference/cli.md).

## 2. הפעלת האימות {#2-turn-auth-on}

האימות **מוגן בשני מתגים**: הוא פעיל רק כשגם מעבירים `enable_auth=True` בקוד **וגם** מגדירים
`AUTH_ENABLED=true` בסביבה. כך אי אפשר לשחרר קוד שאמור לרוץ עם אימות ורץ בשקט בלעדיו (או להפך).

עדכנו את `main.py`:

```python
from fastapi import Depends
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.auth import get_current_claims

app = general_create_app(enable_auth=True)  # gate 1: the code flag


@app.get("/me")
def me(claims: dict = Depends(get_current_claims)):
    return claims
```

‏`get_current_claims` הוא dependency של FastAPI שמחזיר את ה-claims המאומתים של ה-JWT (ה-middleware
של האימות שם אותם ב-`request.state.user`), או מעלה `401` אם הבקשה לא אומתה.

## 3. הפניית המאמת למפתח הציבורי {#3-point-the-verifier-at-your-public-key}

צרו קובץ `.env` ליד `main.py`:

```env
AUTH_ENABLED=true                 # gate 2: the runtime switch
AUTH_PUBLIC_KEY_PATH=jwt_public.pem
AUTH_REQUIRE_EXP=false            # accept the non-expiring dev token from step 1
```

המאמת בוחר את המצב שלו אוטומטית לפי החומר שהגדרתם. כאן קובץ מפתח ציבורי בוחר אימות **RS256**
לא מקוון. (הגדירו חומר אחד בדיוק; ראו [תכנון האימות](../explanation/authentication.md).)

## 4. הרצה וניסיון {#4-run-and-try-it}

```bash
python main.py
```

קראו לנתיב המוגן **בלי** טוקן, ותקבלו `401`:

```bash
curl -i http://localhost:8000/me
# HTTP/1.1 401 Unauthorized
```

עכשיו העבירו את הטוקן שהודפס בשלב 1:

```bash
TOKEN="<paste the token from gen-auth-material>"
curl -s http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# {"sub": "local-dev", ...}
```

## 5. שימוש בכפתור Authorize של Swagger {#5-use-the-swagger-authorize-button}

מכיוון שהאימות פעיל, ב-Swagger UI מופיע כפתור **Authorize**. פתחו את
`http://localhost:8000/docs`, לחצו על **Authorize**, הדביקו את הטוקן, והשתמשו ב-**Try it out** על
`/me`. הבקשה נושאת עכשיו את ה-bearer token שלכם.

## מה למדתם {#what-you-learned}

- האימות **מוגן בשני מתגים** (`enable_auth=True` + `AUTH_ENABLED=true`).
- המאמת בוחר את המצב שלו לפי החומר שהוגדר (כאן, מפתח ציבורי מקומי).
- נתיבים קוראים את הזהות המאומתת דרך `Depends(get_current_claims)`.

## הצעדים הבאים {#next-steps}

- **[אבטחת API עם OIDC ו-JWKS](../how-to/secure-with-oidc-jwks.md)**: הדרך לייצור: אימות טוקנים של
  ה-SSO של הפלטפורמה ומה צריך להגדיר ב-SSO.
- **[אימות טוקן מחוץ לבקשה](../how-to/verify-a-token.md)**: ל-workers ולסקריפטים.
- **[קריאה לשירותים אחרים עם SSO](../how-to/call-services-with-sso.md)**: הצד היוצא.
- **[תכנון האימות](../explanation/authentication.md)**: מצבי האימות (HS256 / JWKS / OIDC
  discovery) ולמה הם קיימים.
- **[מידע עזר על הקונפיגורציה](../reference/configuration.md)**: כל משתנה `AUTH_*`.
