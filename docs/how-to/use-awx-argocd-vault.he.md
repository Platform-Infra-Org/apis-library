# עבודה עם AWX, ArgoCD ו-Vault {#drive-awx-argocd-vault}

מתכונים לשלושת המחברים הנותרים. כל המתודות אסינכרוניות; צרו כל לקוח עם כתובת ה-URL הבסיסית שלו
וטוקן.

## AWX: הפעלת משימה והמתנה לה {#awx-launch-a-job-and-await-it}

```python
from tashtiot_apis_library import AWX

awx = AWX(base_url="https://awx.example.com", token="token")

# Launch a job template; returns an AWXOperationResponse (carries job_id)
response = await awx.launch_job(job_template_id=1, extra_vars={"env": "prod"})

# Block until it finishes, then inspect the standardized result
result = await awx.wait_for_job_completion(response.job_id)
if result.status == "successful":
    print(f"Job {result.job_id} finished!")
```

`launch_workflow_job` / `wait_for_workflow_completion` עושות את אותו הדבר עבור תבניות של משימות
workflow, ו-`get_job_status(job_id)` בודקת סטטוס בודד.

!!! tip "תשובות אחידות"
    מתודות השירות מחזירות תת-מחלקות של `OperationResponse`, ולא את התשובה הגולמית של ה-API. מחלקת
    הבסיס כוללת את `status`, `status_code`, `return_code` ו-`stdout`; ‏`AWXOperationResponse` מוסיפה
    את `job_id`, ו-`ArgoOperationResponse` מוסיפה את `app_name`. ראו את
    [מידע העזר על הסכמות](../reference/api/schemas.md).

## ArgoCD: סנכרון אפליקציה והמתנה לה {#argocd-sync-an-app-and-wait-for-it}

```python
from tashtiot_apis_library import ArgoCD

argo = ArgoCD(
    base_url="https://argo.example.com",
    api_key="token",
    application_set_timeout=30,  # seconds to wait for sync/delete
)

await argo.sync("my-app")
app = await argo.wait_for_update("my-app")  # ArgoApplication once healthy/synced
status = await argo.get_app_status("my-app")  # ArgoOperationResponse
```

פונקציות עזר נוספות: `wait_for_app_creation`, `wait_for_app_deletion`, `get_app_values`,
`modify_values`, `get_app_parameters` ו-`modify_parameters`.

## Vault: קריאה וכתיבה של סודות {#vault-read-and-write-secrets}

```python
from tashtiot_apis_library import Vault

vault = Vault(base_url="https://vault.example.com", token="token")

secret = await vault.read_secret("secret/data/myapp")  # VaultSecret (.data, .metadata)
await vault.write_secret("secret/data/myapp", {"api_key": "value"})
await vault.delete_secret("secret/data/myapp")
```

`write_secret` מקבלת mapping רגיל, `VaultSecretPayload` או כל מודל Pydantic (הוא מומר ל-dict,
בלי ערכי `None`).

## שגיאות {#errors}

כל מחבר מעלה שגיאה מטיפוס משלו על `4xx`/`5xx`: ‏`AWXError`, `ArgoCDError`, `VaultError`. כולן
תת-מחלקות של `ExternalServiceError(HTTPException)`. ייבאו אותן
מ-`tashtiot_apis_library.connectors.errors`.

## ראו גם {#see-also}

- [מידע עזר על ה-API של המחברים](../reference/api/connectors.md)
- [קריאה וכתיבה של קבצים ב-Bitbucket](read-write-bitbucket.md)

## פלט הדרגתי של playbook ב-AWX עבור Argo dispatcher {#incremental-awx-playbook-output-for-an-argo-dispatcher}

`get_job_output` היא מתודה שמפעילים לפי בחירה, עבור **משימות playbook בודדות**, כולל משימות
שהופעלו על ידי ה-APIs של CloudCore/Linux. ‏Argo Workflow ומשימת workflow של AWX הם דברים שונים:
המתודה הזו לא מאחדת את משימות הבן של משימת workflow ב-AWX.

```python
chunk = await awx.get_job_output(job_id, start_line=0, page_size=100)
# Serialize chunk with model_dump(mode="json") in your API.
# On the dispatcher: print chunk.stdout, then retain chunk.next_line per job.
```

התשובה כוללת את השדות הקיימים `status`, `status_code`, `job_id`, `stdout`, ובנוסף:

- `next_line`: המיקום הבא ב-stdout של AWX; שלחו אותו כ-`start_line` בבקשה הבאה.
- `has_more`: יש עמוד נוסף, או פער באירועים שעדיין מגיעים, ולכן צריך לשלוף שוב.
- `finished`: המשימה במצב סופי, AWX מדווח `event_processing_finished=true`,
  והמקטע הזה מרוקן את כל הפלט הזמין. **הדפיסו את המקטע הזה לפני שעוצרים.**

API יכול לחשוף endpoint נפרד לפלט שמחזיר HTTP 200 על קריאות מוצלחות, עם סטטוס המשימה בתוך
ה-JSON. השדה `status_code` נשאר המיפוי הקיים של סטטוס AWX; הוא לא סטטוס התעבורה של endpoint
הפלט הנפרד הזה. השאירו את endpoint הסטטוס הקיים ללא שינוי. ה-dispatcher חייב לעצור על
`finished`, ולא רק על סטטוס משימה מוצלח, ולקבוע את קוד היציאה הסופי שלו לפי `status`. גם
למשימות שנכשלו או בוטלו יכול להיות פלט שצריך לרוקן. שגיאות רשת ואימות הן כשלי בקשה; אל תקדמו
את הסמן בעקבותיהן. שמרו על timeout כולל להמתנה, גם בזמן המתנה לפלט מאוחר או למטא-דאטה חסר של
עיבוד האירועים.

המימוש קורא עמוד אחד מ-`/api/v2/jobs/{id}/job_events/`, ממוין לפי המיקום ב-stdout, ומתקדם רק
לאורך שורות רציפות. קריאות ריקות משאירות את הסמן במקומו. רוקנו עמודים מיד כל עוד `has_more`
הוא true ו-`next_line` מתקדם. אם הסמן לא מתקדם (פער), המתינו לפני ניסיון חוזר כדי להימנע
מלולאה עסוקה. אירועים בלי שורות מסוננים לפני העימוד, כך שהם לא יכולים לתקוע את הסמן.
גודל העמוד מגביל את מספר האירועים, לא את גודלם בבתים. הפלט של AWX מוחזר במפורש;
הספרייה לא כותבת ללוגים את פלט ה-playbook אוטומטית ולא חושפת את `event_data`/משתנים.
הפלט עצמו יכול להכיל ערכים רגישים מה-playbook, ולכן החילו את אותן הגבלות גישה כמו על
המשימה הקיימת ואת הגנות `no_log` של AWX. הסמנים ספציפיים לכל משימה; שמרו אותם מחוץ לתהליך
אם ה-dispatcher צריך להמשיך אחרי הפעלה מחדש. אין כאן מסירה של בדיוק-פעם-אחת (exactly-once)
במקרה של קריסות.

ה-API חייב לאשר גישה לכל משימה, בדיוק כמו ש-endpoint הסטטוס עושה. שום טוקן של AWX לא מועבר
ל-dispatcher. מודל תשובה של FastAPI חייב לשמור על השדות החדשים ולא להמיר את התשובה
ל-`AWXOperationResponse`.

### בדיקה מקומית בלי AWX או Tyk {#local-check-without-awx-or-tyk}

```bash
DEBUG=false .venv/bin/pytest tests/connectors/test_awx_output.py tests/connectors/test_awx_client.py --no-cov
DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_output_demo.py
```

ההדגמה משתמשת בתשובות HTTP מדומות של AWX וב-endpoint של FastAPI שרץ בתוך התהליך, ומדפיסה
שלושה מקטעים הדרגתיים מלקוח HTTP שמתנהג כמו dispatcher. ה-playbook המדומה מוסיף את
המקטעים האלה בזמן שה-dispatcher ממתין; לאחר מכן ה-dispatcher מרוקן כמה עמודים
בלי להמתין שוב. גם ה-workflow של בדיקות GitHub מריץ את הסימולציה הזו. היא דורשת את תלויות
הפיתוח. זה מאמת את הספרייה ואת חוזה ה-HTTP המוצע, לא את ה-API ברשת הסגורה ולא את Tyk.
לפני קידום, ודאו שה-AWX הפרוס חושף את `start_line`, `end_line`,
`event_processing_finished`, תומך בסינוני האירועים, ומאפשר לטוקן של ה-API לקרוא
אירועי משימות. גרסאות ישנות שחסר בהן מטא-דאטה של סיום ייכשלו ב-timeout, במקום לטעון בשקט
שכל הפלט נמסר.

שיטת הסידור וזיהוי הסיום של האירועים מבוססת על
[ה-monitor של AWX CLI](https://github.com/ansible/awx/blob/devel/awxkit/awxkit/cli/stdout.py).

## סיכומי סטטוס תמציתיים (משימות ומשימות workflow) {#concise-status-summaries-jobs-and-workflow-jobs}

באינטגרציה של Linux API/Dispatcher, שכבר מדפיסה את גופי התשובות, השתמשו
ב-`include_logs=True` על **מתודות הסטטוס הקיימות**:

```python
# Inside your existing JOBSTATUS handler; return the result as before.
result = await awx.get_workflow_job_status(workflow_job_id, include_logs=True)
# Or, for a standalone playbook job:
result = await awx.get_job_status(job_id, include_logs=True)
```

שתיהן עדיין מחזירות `AWXOperationResponse`, עם אותו מיפוי של סטטוס וקוד HTTP.
הסיכום האופציונלי ממלא את `stdout`; ברירת המחדל (`False`) שומרת על ההתנהגות הקיימת.
השאירו את האימות ואת הטיפול בקודי התשובה הקיימים של ה-API שלכם. אין צורך
ב-endpoint חדש או בסמן ב-dispatcher עבור מצב ה-snapshot הזה. ה-dispatcher
חייב להציג את `stdout` של התשובה (הלוג הקיים של גוף התשובה עשוי להציג אותו
כ-JSON עם ירידות שורה מוברחות; הדפסה נפרדת של `stdout` נותנת שורות קריאות).

דוגמה ל-`stdout` של workflow:

```text
[✓] Create VM: successful
[✓] Configure Linux: successful
[✗] Install monitoring: failed
  TASK [Install monitoring agent]
  fatal: [server-01]: FAILED!
    → No package monitoring-agent available
  PLAY RECAP *********************************************************************
  server-01 : ok=4 changed=2 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
```

סיכומי workflow מפרטים את משימות הבן שהתחילו, ושולפים את עשר השורות המסוננות האחרונות רק
עבור משימות playbook שנכשלו, הסתיימו בשגיאה או בוטלו. צמתי Project-update מדולגים.
משימות workflow מקוננות נסרקות, עם הגנה מפני מעגלים ועומק. סוגי צמתים אחרים מציגים
סטטוס בלבד; צמתים בלי משימה או בלי סיכום משימה מושמטים. עמודי הצמתים נקראים לפי סדר
ה-ID (לא מיזוג כרונולוגי של פלט מקבילי), עד 100 עמודים של 100 צמתים.
משימות עצמאיות מציגות את הכותרת שלהן ועוד שתי שורות ה-recap האחרונות כשהן מצליחות, או עשר
שורות מסוננות בכישלון/שגיאה/ביטול. מצבי Pending/running מוצגים עם אייקון ניטרלי.

המסנן שומר כותרות play/task, תוצאות פעולות, אזהרות, שגיאות, הודעות קצרות
ואת ה-play recap. הוא מסיר צבעי ANSI ומשמיט גופי תוצאה מפורטים של מודולים. הוא שומר
לכל היותר 100 שורות נבחרות ו-10,000 תווים לכל לוג מסונן, ומגביל את סיכום ה-workflow
המשולב ל-10,000 תווים עם סימון קיטוע. אלה מגבלות פלט; תשובת ה-stdout בטקסט רגיל של AWX
עדיין נשלפת במלואה. זה מסנן תצוגה, **לא הסתרת סודות**: שמות משימות והודעות עדיין עלולים
להכיל מידע רגיש.

זה **סיכום snapshot**, לא streaming הדרגתי: בדיקות חוזרות עשויות לחזור על
כותרות/פלט, משימות בן מוצלחות של workflow לא כוללות את פלט ה-playbook המלא שלהן,
וזיהוי הסיום הקיים של הסטטוס לא ממתין לעיבוד מאוחר של אירועי AWX.
השתמשו ב-`get_job_output` כשנדרש פלט הדרגתי ומרוקן במלואו של משימה בודדת.
שגיאות בשליפה האופציונלית של לוגים/צמתים מייצרות סימון "לא זמין" ואזהרה, ועדיין
שומרות על הסטטוס הראשי. שגיאות בשליפת הסטטוס הראשי עדיין מעלות חריגה כרגיל.

תצוגה מקדימה מקומית בלי AWX/Tyk:

```bash
DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_status_summary_demo.py
```

AWX חושף [צמתי workflow ואת ה-stdout של משימות דרך ה-API שלו](https://docs.ansible.com/projects/awx/en/latest/rest_api/api_ref.html).
לטוקן ה-AWX של ה-API צריכה להיות הרשאה לקרוא את המשאבים האלה.
