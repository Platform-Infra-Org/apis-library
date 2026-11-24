# קריאה וכתיבה של קבצים ב-Bitbucket {#read-write-bitbucket-files}

השתמשו במחבר `Git` כדי לטפל בקבצים במאגר Bitbucket Server דרך ה-API של HTTP שלו (ופעולות מחיקה
עוברות דרך SSH). כל המתודות אסינכרוניות.

## יצירת הלקוח {#construct-the-client}

```python
from tashtiot_apis_library import Git

git = Git(
    base_url="https://bitbucket.example.com",  # base Bitbucket URL
    token="token",  # HTTP token with write access
    username_or_email="user@example.com",  # service account identity
    project_key="PROJ",  # Bitbucket project key
    repo_slug="repo-name",  # repo name, lowercase
    default_ref="main",  # default branch to operate on
    ssh_key_file_path="/path/to/ssh/private/key",  # SSH key (used for delete)
)
```

## קריאת קובץ {#read-a-file}

```python
content = await git.get_file_content("/path/to/values.yaml")  # returns str
```

פענחו את התוכן איך שנוח לכם, למשל כ-YAML:

```python
import yaml

data = yaml.safe_load(await git.get_file_content("/app/values.yaml"))
```

## הוספה, שינוי ומחיקה של קבצים {#add-modify-and-delete-files}

```python
await git.add_file("/new/file.txt", "Add file", "hello world")
await git.modify_file("/app/values.yaml", "Bump replicas", new_yaml_str)
await git.delete_file("/old/file.txt", "Remove obsolete file")
```

כל אחת מהן מקבלת הודעת commit; העבירו `branch=` כדי לעבוד על branch אחר מ-`default_ref`.

## הצגת תוכן ובדיקת קיום {#list-and-check-existence}

```python
entries = await git.list_dir("/app")  # List[Tuple[name, type]]
all_files = await git.list_files_recursive("/app")  # List[str]
exists = await git.file_exists("/app/values.yaml")  # bool
```

## דוגמה מלאה {#a-complete-example}

```python
import asyncio
import yaml
from tashtiot_apis_library import Git


async def main():
    git = Git(
        base_url="https://bitbucket.example.com",
        token="token",
        username_or_email="user@example.com",
        project_key="PROJ",
        repo_slug="repo-name",
        default_ref="main",
        ssh_key_file_path="/path/to/ssh/private/key",
    )
    values = yaml.safe_load(await git.get_file_content("/app/values.yaml"))
    print(values)


asyncio.run(main())
```

## שגיאות {#errors}

פעולות שנתקלות ב-`4xx`/`5xx` מעלות `GitError` (תת-מחלקה של `fastapi.HTTPException`), כך שהעלאה
שלה בתוך נתיב FastAPI הופכת ישירות לתשובת HTTP. ייבאו אותה מ-
`tashtiot_apis_library.connectors.errors`; ראו את [מידע העזר על השגיאות](../reference/api/errors.md).

## ראו גם {#see-also}

- [מידע עזר על ה-API של המחברים](../reference/api/connectors.md)
- [ארכיטקטורה: דפוס המחברים בשלוש שכבות](../explanation/architecture.md)
