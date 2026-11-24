# פיתוח {#development}

איך מקימים סביבת עבודה ומריצים את הבדיקות של הפרויקט. ערכת הכלים היא של
[Astral](https://astral.sh/): ‏**uv** (סביבה + הרצה), **Ruff** (lint + עיצוב קוד) ו-**ty** (בדיקת
טיפוסים).

## סביבה {#environment}

‏uv משמש כמריץ מהיר, ו**אין `uv.lock` במאגר**. זו ספרייה, ולכן הצרכנים פותרים תלויות מול
*הטווחים* שב-`pyproject.toml`; קובץ נעילה היה נועל רק את סביבת הפיתוח שלנו ומשתנה שוב ושוב מול
הגרסה של setuptools-scm. גם `pip` רגיל עובד.

```bash
uv venv                              # create .venv
uv pip install -e ".[dev,docs]"      # dev tools + docs toolchain
# equivalently, without uv:
#   python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,docs]"
```

## בדיקות {#tests}

חבילת הבדיקות נמצאת בעץ `tests/` הראשי ורצה משורש המאגר:

```bash
uv run pytest                                         # whole suite (with coverage)
uv run pytest tests/connectors/test_awx_client.py     # one file
```

## ‏Lint ועיצוב קוד (Ruff) {#lint-format-ruff}

```bash
uv run ruff format .          # format
uv run ruff check . --fix     # lint, auto-fixing what it safely can
```

הקונפיגורציה של Ruff נמצאת ב-`pyproject.toml` (`[tool.ruff]`). סט הכללים שמרני בכוונה;
`UP` (‏pyupgrade), `TID252` (הוא היה אוסר את הייבוא היחסי של החבילה) ו-`G` (בקוד יש ערבוב של
קריאות Loguru עם f-string ועם סגנון `{}`) **לא** מופעלים, במכוון.

## בדיקת טיפוסים (ty) {#type-check-ty}

```bash
uv run ty check src           # advisory — scoped to the shipped package
```

‏ty הוא **מייעץ בלבד ולא חוסם**: הוא בגרסת בטא ועדיין אין לו plugin ל-Pydantic, ולכן הוא מדווח על
בסיס ידוע של התראות שווא, רובן על הערות Optional ועל Pydantic. התייחסו אליו כאל סימן, לא כאל שער.

## ‏Pre-commit hooks {#pre-commit-hooks}

```bash
uv run pre-commit install                                  # enable on every commit
uv run pre-commit run --all-files                          # run ruff + ruff-format now
uv run pre-commit run ty --hook-stage manual --all-files   # run the advisory ty hook
```

‏`ruff` ו-`ruff-format` רצים בכל commit; ‏`ty` הוא hook בשלב ידני, כך שהרעש של גרסת הבטא לעולם לא
חוסם commit.

## תיעוד {#docs}

התיעוד שאתם קוראים נבנה עם MkDocs (Material) + mkdocstrings:

```bash
uv run mkdocs serve            # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict   # what CI-equivalent checks expect: fails on any broken link
```

דפי מידע העזר של ה-API נוצרים מה-docstrings, לכן הקפידו שה-docstrings יהיו מדויקים כשאתם משנים
חתימות ציבוריות.

### תרגומים (עברית) {#translations-hebrew}

האתר נבנה באנגלית (ב-`/`) ובעברית (ב-`/he/`, מימין לשמאל), עם בורר שפה בכותרת העליונה. זה נעשה עם
ה-plugin ‏`mkdocs-static-i18n` (שמוגדר תחת `plugins: - i18n` ב-`mkdocs.yml`):

- **כדי לתרגם דף**, הוסיפו `<page>.he.md` ליד `<page>.md` (למשל `explanation/async.he.md`).
  הקישורים נשארים אותו דבר (`job-queues.md`); כל שפה מפנה אותם לגרסה שלה.
- **דפים שלא תורגמו** נופלים חזרה לאנגלית תחת `/he/`, עם הודעה "עדיין לא תורגם"
  (`overrides/main.html`).
- **כותרות הניווט וכותרות ה-admonitions** מתורגמות ב-`mkdocs.yml` (`nav_translations`,
  `admonition_translations`). כשאתם מוסיפים דף ל-`nav`, הוסיפו שם גם את הכותרת העברית שלו.
- **כשאתם משנים דף באנגלית שיש לו גרסה עברית**, עדכנו את הדף העברי באותו PR, או מחקו אותו כדי
  שהקוראים יקבלו את הגרסה האנגלית העדכנית במקום תרגום מיושן.
- **כל כותרת בעברית נושאת את המזהה של הכותרת באנגלית** (`## כללי async {#async-rules}`), כך
  שהעוגנים זהים בשתי השפות, וקישור כמו `api-standards.md#async-rules` עובד מכל אחת מהן. לכן דף
  בעברית שומר על הכותרות של הדף באנגלית: אותו מספר, אותן רמות ואותו סדר. אחרי כתיבה או עריכה של
  דף בעברית, הריצו:

    ```bash
    uv run --extra docs python scripts/docs_i18n.py check docs/<page>.md docs/<page>.he.md  # structure
    uv run --extra docs python scripts/docs_i18n.py ids docs                                 # add/refresh ids
    ```

## לפני שפותחים PR {#before-you-open-a-pr}

- `uv run ruff format . && uv run ruff check .`: נקי.
- `uv run pytest`: ירוק.
- `uv run mkdocs build --strict`: נקי, אם נגעתם בתיעוד או ב-docstrings ציבוריים.

ה-CI (`.woodpecker/check.yaml`) מריץ Ruff + pytest + ty מייעץ בכל push/PR.
