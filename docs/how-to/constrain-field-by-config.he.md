# הגבלת שדה לפי קונפיגורציה {#constrain-a-field-by-resolved-config}

לפעמים הערכים התקינים של שדה בבקשה תלויים ב**קונפיגורציה שחושבה עבור הקואורדינטות של הבקשה
עצמה**. למשל, תבניות מערכת ההפעלה ש-VM יכול להשתמש בהן שונות בכל עלה של הקונפיגורציה הארגונית.
הספרייה **לא כוללת** בכוונה פונקציית עזר לזה (מפתח הקונפיגורציה, השדה ומודל הבקשה הם כולם ספציפיים
לאפליקציה). במקום זאת, כתבו dependency קטן של FastAPI באפליקציה שלכם. הנה הדפוס.

כדי להבין *למה* זה dependency ולא validator של Pydantic, ראו
[ולידציה דינמית של קונפיגורציה](../explanation/dynamic-config-validation.md).

## הדפוס {#the-pattern}

```python
from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from tashtiot_apis_library.fastapi_template.config_api import RequiredInfraMetadata


class VMSpec(BaseModel):
    os_template: str
    instance_size: str


class VMRequest(BaseModel):
    metadata: RequiredInfraMetadata  # coordinates — validated against the allowlists + tree
    spec: VMSpec  # the fields whose allowed values depend on the config


def constrain_vm(provider):
    async def dependency(req: VMRequest) -> VMRequest:
        # The coordinate + spec models were already validated when the body was parsed.
        # Resolve the config for THIS request's coordinates, then check each field.
        config = await provider.resolve_infra_config(req.metadata)
        errors = []
        for field, config_key in (
            ("os_template", "os_templates"),
            ("instance_size", "instance_sizes"),
        ):
            value = getattr(req.spec, field)
            allowed = config.get(config_key) or []
            if allowed and value not in allowed:  # permissive when the config is unset/empty
                errors.append(
                    {
                        "type": "value_error",
                        "loc": ("body", "spec", field),  # points clients at the offending field
                        "msg": f"'{value}' is not permitted for the selected coordinates; "
                        f"allowed: {sorted(allowed)}",
                        "input": value,
                    }
                )
        if errors:
            raise RequestValidationError(errors)  # -> a standard 422, one entry per field
        return req

    return dependency


@app.post("/vms")
async def create_vm(
    req: VMRequest = Depends(constrain_vm(provider)),
): ...  # req is fully validated: coordinates AND spec.os_template / spec.instance_size
```

`provider` הוא ה-`RemoteConfigProvider` שמוחזר
מ-[`enable_remote_config_api`](enable-remote-config-api.md).

## איך לקרוא את הקוד {#how-it-reads}

- **הבקשה היא גוף JSON.** פרמטר מודל רגיל בפונקציית ה-dependency
  (`req: VMRequest`) מפוענח כגוף הבקשה, כך שלא צריך להפוך את הקואורדינטות לפרמטרי query.
  ‏FastAPI מאמת אותו (ומריץ את בדיקות רשימת הערכים המותרים וההיררכיה של הקואורדינטות) *לפני*
  שה-dependency רץ.
- **`req.metadata` מניע את החיפוש.** תת-המודל של הקואורדינטות מועבר ל-`resolve_infra_config`,
  שמחזירה את הקונפיגורציה הממוזגת עבור העלה הזה. הקונפיגורציה שלכם שמה את הערכים המותרים של כל שדה
  תחת מפתח ידוע (`os_templates`, `instance_sizes`, …).
- **השדות המוגבלים יכולים לשבת בכל מקום** בגוף הבקשה. כאן הם תחת `spec`, ומגיעים אליהם בגישה
  רגילה לתכונה (`req.spec.os_template`). התאימו את `loc` למיקום האמיתי של השדה, כדי שה-`422`
  יפנה את הלקוחות למקום הנכון.
- **הוא רץ אחרי ה-validators של המודל עצמו**, כך שכשה-dependency מתבצע, כבר ידוע שהקואורדינטות
  תקינות.

## מקרי שימוש {#use-cases}

- **תבניות מערכת הפעלה / images** של VM לכל עלה.
- **גדלי מכונות / flavors** שמותרים ב-region או ב-island מסוימים.
- **יעדי גיבוי** או **רשתות** מותרים לכל סביבה.
- **מכסות** או **מתגי פיצ'רים** שמחושבים לכל עלה.

## Fail-open לעומת fail-closed {#fail-open-vs-fail-closed}

הדוגמה **מתירנית**: אם הקונפיגורציה לא מציינת את המפתח (או שהרשימה ריקה), השדה מתקבל. זה תואם את
ה-validators של הקואורדינטות, שלא דוחים כשרשימת הערכים המותרים שלהם ריקה (לפני ה-poll או כשה-upstream
חסר). כדי **לחסום כברירת מחדל** (fail closed) במקום זאת, כלומר לדחות כל דבר שלא הותר במפורש, הסירו את
התנאי `allowed and` ודרשו `allowed` לא ריק.

## ראו גם {#see-also}

- [ולידציה דינמית של קונפיגורציה](../explanation/dynamic-config-validation.md): למה זה dependency
  ולא validator.
- [הפעלת Remote Config API](enable-remote-config-api.md): ה-provider ומודלי הקואורדינטות.
