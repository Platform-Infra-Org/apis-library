# שילוב בתוך operation_linux.py

הקובץ `operation_linux.py` כאן מכיל את שתי פונקציות הסטטוס ששמותיהן, החתימות
וטיפוס ההחזרה שלהן נראים בתמונות. זה **אינו שחזור מלא של הקובץ הפנימי**:
הגוף המלא של פונקציות ההפעלה, ה־payloads וקובץ `conf` אינם מופיעים בתמונות.
אין להחליף את הקובץ הפנימי כולו בקובץ הדוגמה.

## מה להשאיר

- את `from .conf import config` ואת ההגדרות הקיימות.
- את `create_new_machine`, פונקציית המחיקה, `launch_ssh_keys_job` וכל פונקציה
  אחרת שמפעילה פעולה, כולל כל ה־payloads, ה־extra_vars וה־limit הקיימים.
- את ה־routers, ה־endpoints, ההרשאות, העברת ה־job_id ומיפוי קוד ה־HTTP הקיימים.
- את הייבוא של `AWX` ושל `AWXOperationResponse`.

## מה למחוק לאחר בדיקת השימושים בקובץ

התוספות הבאות מהתמונות עוברות לאחריות הספרייה, ולכן אפשר להסיר אותן מה־API
אם אין פונקציות אחרות שמשתמשות בהן:

- `import re`.
- `MAX_LOG_CHARS`, `MAX_FILTERED_LINES`.
- `_RESULT_RE`, `_KEEP_RE`, `_ACTION_RE`, `_MSG_RE`, `_ACTION_PREFIX_RE`.
- `_update_yaml_state`, `_extract_filter_match`, `_filter_ansible_logs`.
- `_fetch_job_logs`, `_fetch_workflow_logs`.

## מה להחליף

את הגוף המלא של `get_machine_status` מחליפים בקריאה אחת:

```python
async def get_machine_status(
    awx: AWX,
    workflow_job_id: int,
) -> AWXOperationResponse:
    return await awx.get_workflow_job_status(workflow_job_id, include_logs=True)
```

כך גם עבור `get_ssh_keys_job_status`:

```python
async def get_ssh_keys_job_status(
    awx: AWX,
    job_id: int,
) -> AWXOperationResponse:
    return await awx.get_job_status(job_id, include_logs=True)
```

אין צורך להשאיר אחריהן `result.stdout = logs`, גישת HTTP ישירה דרך
`awx.client.api`, שליפת שם ה־Job שוב, או עיצוב מקומי של הסיכום.

## הפצה ותצוגה

יש לבנות מחדש את אימג׳ ה־API עם גרסת הספרייה הכוללת `include_logs`.
עותק ישן של הספרייה יזרוק `TypeError` על הפרמטר החדש.
תוצאת הסטטוס שומרת על אותה סכמת תשובה; רק תוכן `stdout` משתנה במצב החדש.
קריאות בספרייה שאינן מעבירות `include_logs=True` ממשיכות להתנהג כמו קודם.

ה־Dispatcher שבתמונה כבר מדפיס `response.text`. לכן הפלט יגיע ללוגים אם
ה־endpoint מחזיר את כל `AWXOperationResponse` כולל `stdout`, גם בתשובות כישלון.
JSON עשוי להציג ירידות שורה בתור `\n`. לתצוגה קריאה ניתן להדפיס את
`response.json()["stdout"]` **לפני** בדיקת קוד הסטטוס וה־break.
אין צורך לשנות את תנאי הסיום או את הודעות ה־warning בשביל מצב הסיכום.
זו תמונת מצב שחוזרת בכל דגימה, לא הזרמת כל שורות ה־Playbook ללא חזרות.
סיכום Workflow מציג מצב לכל Job; פירוט Playbook מצורף רק ל־Jobs שנכשלו,
בוטלו או הסתיימו בשגיאה. Job רגיל שהצליח מציג גם recap.

## בדיקה משותפת של קובץ ה־API והספרייה

מהשורש של הפרויקט:

```bash
DEBUG=false .venv/bin/pytest tests/connectors/test_linux_api_integration.py --no-cov -v
DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_status_summary_demo.py
```

הבדיקות מייבאות את `operation_linux.py` שבדוגמה, מפעילות את הספרייה האמיתית,
ומדמות רק את תגובות HTTP של AWX. הן מכסות גם החזרה דרך FastAPI,
כולל שמירת HTTP 202/200/500 והחזרת פלט כישלון בגוף התשובה.
ה־router בבדיקות הוא דוגמה בלבד: אין כאן את ה־router הפנימי שלכם או Tyk.
הסימולציה מפעילה גם היא את `get_machine_status` שבקובץ הדוגמה.
