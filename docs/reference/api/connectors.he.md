# ‏API של המחברים {#connectors-api}

ארבעת מחברי התשתית. כל אחד הוא מחסנית של שלוש שכבות: **service** ברמה גבוהה שהמשתמשים יוצרים,
**client** ברמה נמוכה, ו**מודלים של Pydantic** לבקשות ולתשובות (ראו
[ארכיטקטורה](../../explanation/architecture.md)). ייבאו את ה-services מהחבילה הראשית:

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault
```

ה-clients והמודלים זמינים מתת-החבילה של כל מחבר, למשל
`from tashtiot_apis_library.connectors.awx import AWXClient, AWXJob`.

לשימוש מכוון משימה, ראו [עבודה עם AWX, ArgoCD ו-Vault](../../how-to/use-awx-argocd-vault.md) ו-
[קריאה וכתיבה של קבצים ב-Bitbucket](../../how-to/read-write-bitbucket.md).

## ‏Services {#services}

::: tashtiot_apis_library.connectors.awx.service.AWX

::: tashtiot_apis_library.connectors.argocd.service.ArgoCD

::: tashtiot_apis_library.connectors.argocd.service.evaluate_argo_result

::: tashtiot_apis_library.connectors.git.service.Git

::: tashtiot_apis_library.connectors.vault.service.Vault

## ‏Clients ברמה נמוכה {#low-level-clients}

שכבת ה-HTTP שכל service מרכיב. השתמשו בהם ישירות רק אם אתם צריכים גישה גולמית, מתחת לפונקציות
העזר של ה-service.

::: tashtiot_apis_library.connectors.awx.client.AWXClient

::: tashtiot_apis_library.connectors.argocd.client.ArgoCDClient

::: tashtiot_apis_library.connectors.git.client.GitClient

::: tashtiot_apis_library.connectors.vault.client.VaultClient

## תשובות סטנדרטיות {#standardized-responses}

מודל התשובה הבסיסי שפעולות ה-service מחזירות (תת-המחלקות הספציפיות לכל מחבר נמצאות במודלים של כל
מחבר, בהמשך).

::: tashtiot_apis_library.connectors.response_schemas.OperationResponse

## מודלים {#models}

מודלי ה-Pydantic של הבקשות והתשובות לכל מחבר.

### ‏AWX {#awx}

::: tashtiot_apis_library.connectors.awx.models

### ‏ArgoCD {#argocd}

::: tashtiot_apis_library.connectors.argocd.models

### ‏Git (Bitbucket Server) {#git-bitbucket-server}

::: tashtiot_apis_library.connectors.git.models

### ‏Vault {#vault}

::: tashtiot_apis_library.connectors.vault.models
