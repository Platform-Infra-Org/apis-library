# ‏OpenAPI, ‏Swagger והזרקה דינמית של enum {#openapi-swagger-and-dynamic-enum-injection}

היכולת של Remote Config גורמת ל-Swagger להציג **רשימות נפתחות חיות** של ערכי הקואורדינטות
המותרים: ערכים שמשתנים בזמן ריצה כשה-poller מרענן אותם. העמוד הזה מסביר איך זה עובד, ומתחיל מהיסודות
של OpenAPI ו-Swagger, כי המנגנון הוא "תיקון של הסכמה שנוצרה", ולא פיצ'ר של FastAPI.

## ‏OpenAPI לעומת Swagger UI {#openapi-vs-swagger-ui}

שני דברים שונים שאנשים נוטים לבלבל ביניהם:

- **‏OpenAPI** הוא *מסמך*: תיאור JSON (או YAML) של ה-API שלכם: הנתיבים שלו, הפרמטרים וגוף הבקשה
  של כל מתודה, וכל מבנה שמתואר עם **JSON Schema**. זה פשוט מידע.
- **‏Swagger UI** הוא *מציג*: אפליקציית JavaScript שקוראת מסמך OpenAPI ומציירת את התיעוד
  האינטראקטיבי (טופסי "Try it out", רשימות נפתחות, קטלוג ה-"Schemas" בתחתית). הוא לא יודע כלום על
  קוד ה-Python שלכם; הוא מכיר רק את ה-JSON.

‏FastAPI בוחן את הנתיבים ואת מודלי ה-Pydantic שלכם, בונה את מילון ה-OpenAPI עם `get_openapi(...)`,
ושומר אותו במטמון על האפליקציה:

- ‏`app.openapi()`: הפונקציה שמחזירה את המסמך.
- ‏`app.openapi_schema`: המטמון. הגדירו אותו ל-`None`, והקריאה הבאה ל-`app.openapi()` תבנה אותו
  מחדש.
- ‏`/openapi.json` מחזיר את `app.openapi()`; ‏Swagger UI ב-`/docs` שולף אותו ומציג אותו.

## המבנה שחשוב {#the-shape-that-matters}

```jsonc
{
  "paths": { "/config": { "get": {
      "parameters": [ { "name": "region", "in": "query",
                        "schema": { "type": "string" } } ],       // query/path params, inline
      "requestBody": { "content": { "application/json": {
                        "schema": { "$ref": "#/components/schemas/DNSRecordCreate" } } } } } } },
  "components": { "schemas": {                                     // every model, once, by name
      "DNSRecordCreate": { "properties": { "metadata": { "$ref": "#/components/schemas/InfraMetadata" } } },
      "InfraMetadata":   { "properties": { "region": { "anyOf": [{"type":"string"},{"type":"null"}] } } } } }
}
```

- **‏`enum`** הוא מה ש-Swagger הופך ל**רשימה נפתחה**. בלי `enum` מקבלים תיבת טקסט חופשי.
- **פרמטרים של query ושל path** נכתבים **inline** תחת ה-`parameters` של כל פעולה.
- **גופי בקשה (ומודלי תשובה)** *לא* נכתבים inline: הסכמה היא **`$ref`** לרשומה המשותפת היחידה
  ב-`components.schemas`, ומודלים מקוננים זה בזה באמצעות `$ref`.
- שדות **אופציונליים או nullable** מוצגים כ-`{"anyOf": [{"type":"string"}, {"type":"null"}]}`:
  הטיפוס string נמצא ב*ענף*, לא ברמה העליונה.

## למה אנחנו מעבדים את המסמך בדיעבד {#why-we-post-process-the-document}

ערכי הקואורדינטות התקפים הם דינמיים (ה-poller מרענן את `LIVE_ALLOWED_*` בזמן ריצה). ‏`Enum` או
`Literal` רגילים של Pydantic מוקפאים בזמן ה-import, ולכן הם לא יכולים לעקוב אחריהם. במקום זאת,
הספרייה **מתקנת את מסמך ה-OpenAPI שנוצר** בכל פעם שהוא נבנה, וכותבת לתוכו את הערכים הנוכחיים של
רשימת הערכים המותרים בתור `enum`. זו ההזרקה.

## המנגנון (`make_config_openapi`) {#the-mechanism-make_config_openapi}

‏`enable_remote_config_api` מתקין אותו: `app.openapi = make_config_openapi(app, coordinate_paths)`.

- **עוטפים, לא מחליפים.** הוא שומר את ה-`app.openapi` הקודם וקורא לו. זה חשוב כי
  ‏`general_create_app` כבר עטף את `app.openapi` כדי להוסיף את סכמת ה-Bearer של "Authorize"; עטיפה
  מצטברת (`enum wrapper → bearer wrapper → FastAPI`), והחלפה הייתה מעלימה את כפתור ה-Authorize.
- **ערכים חיים דרך הפניה.** הוא שומר את קבוצות `LIVE_ALLOWED_*`; ה-poller משנה אותן במקום, כך
  שההפניות השמורות תמיד רואות את הערכים הנוכחיים.
- **התאמת נתיבים עם regex.** כל רשומה ב-`coordinate_paths` היא regex שמותאם ב-`fullmatch` מול כל
  נתיב.
- **‏`_inject`** מתאים לפי שם: רק שדות *שנקראים* על שם קואורדינטה (`space`/`network`/…) מקבלים
  `enum`, ורק כשרשימת הערכים המותרים הזו לא ריקה. הוא מציב את ה-enum **בתוך ענף ה-string של
  `anyOf`** בשדות Optional (שם מחפש ה-renderer של המודלים ב-Swagger), וברמה העליונה בשדות שטוחים.
- **רקורסיה.** בגופי בקשה הוא יורד דרך רכיבי `$ref` מקוננים (כך ש-`DNSRecordCreate → metadata:
  InfraMetadata → region` עובד), עם קבוצת "כבר ביקרנו" שמגינה מפני מעגלים.
- **רענון.** ה-poller מאפס את `app.openapi_schema` ל-None בכל מחזור, כך שהבקשה הבאה ל-
  `/openapi.json` בונה ומתקנת מחדש עם הערכים העדכניים, בלי הפעלה מחדש.
- **לוג.** שורת INFO אחת מציינת את הנתיבים שקיבלו ערכים (פעם אחת לכל שינוי), והיא משמשת גם כבדיקה
  של "האם ה-`coordinate_paths` שלי הותאמו?".

## למה פרמטרי query וגופי בקשה מתנהגים אחרת (הנקודה העדינה) {#why-query-params-and-bodies-behave-differently-the-subtle-bit}

‏OpenAPI מייצג את שני סוגי הקלט בצורה שונה, וזה ניכר ב-Swagger:

- **מודל של גוף בקשה או של תשובה** הוא אובייקט יחיד ב-`components.schemas`, שמפנים אליו עם
  `$ref`. טופס גוף הבקשה של "Try it out" **וגם** אזור ה-"Schemas" בתחתית מציגים את אותו אובייקט.
  מתקנים אותו פעם אחת, ושניהם מציגים את ה-enums.
- **פרמטרי query** הם **עותקים inline** של כל שדה ברשימת ה-`parameters` של הפעולה: אין רכיב
  משותף ל"אוסף של פרמטרי query". תיקון העותק ה-inline גורם לרשימה הנפתחת לעבוד, אבל הרכיב העצמאי
  `InfraMetadata` (שקיים כי מודלי תשובה מפנים אליו עם `$ref`) הוא אובייקט *אחר*, שהפרמטרים לא מצביעים
  עליו.

לכן, כשמשתמשים בפרמטרי query, המזריק מתקן את הפרמטרים ה-inline (הרשימה הנפתחת עובדת), ובנוסף מתקן
את **הרכיב המשותף** של המודלים הדינמיים (`InfraMetadata` / `RequiredInfraMetadata`) כדי שגם אזור
ה-"Schemas" יציג את האפשרויות. המעבר על הרכיבים מוגבל **לפי שם**: ל-`MetadataRequest` הסטטי יש
אותם שמות שדות, אבל הוא בכוונה לא דינמי, ולכן לא נוגעים בו.

## הסתייגויות {#caveats}

- **התאמה לפי שם, ורק הוספה.** כדי לקבל רשימה נפתחת, שדה חייב *להיקרא* על שם קואורדינטה; נתיב
  עם שגיאת הקלדה, שדה שאינו קואורדינטה או רשימת ערכים מותרים ריקה פשוט לא מניבים כלום (ומכאן לוג
  ה-INFO).
- **‏`coordinate_paths` מותאם ב-`fullmatch`.** השתמשו ב-`.*` להתאמות חלקיות; רשומה שלא מתאימה לשום
  נתיב פשוט לא עושה כלום, בשקט.
- **רכיבים משותפים.** תיקון של רכיב (מודלי גוף בקשה ותשובה, והמעבר על המודלים הדינמיים לפי שם)
  מציג את ה-enums בכל מקום שמפנה לרכיב הזה עם `$ref`: מקור אמת אחד, לא ספציפי לנתיב.

## ראו גם {#see-also}

- [הפעלת ה-Remote Config API](../how-to/enable-remote-config-api.md): החיווט, `coordinate_paths`,
  ה-seed וה-poller.
- [ולידציה של קונפיגורציה דינמית](dynamic-config-validation.md): איפה נמצאת כל בדיקת קואורדינטה
  (validators של המודל לעומת dependency).
