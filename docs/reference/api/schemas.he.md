# ‏API של הסכמות {#schemas-api}

מודלי בקשה משותפים, מכוונים ל-Kubernetes/PaaS, שמיוצאים מחדש מהחבילה הראשית. הם כוללים ולידציה של
CPU/זיכרון באמצעות ביטויים רגולריים.

```python
from tashtiot_apis_library import (
    OperationRequest,
    ResourceSpec,
    DefaultMetaSpec,
    NameNamespace,
    InfraOperationRequest,
    RequiredInfraOperationRequest,
)
```

המודלים העיקריים האלה מיוצאים מחדש מהחבילה הראשית; השאר הם אבני הבניין שלהם (`CpuAndMemory`,
`PaasLabels`, `MetadataRequest`). ‏`InfraOperationRequest` / `RequiredInfraOperationRequest` משקפים
את `OperationRequest`, אבל נושאים את ה-metadata **הדינמי** של הקואורדינטות, `InfraMetadata` /
`RequiredInfraMetadata` (שעובר ולידציה מול רשימות הערכים המותרים והעץ החיים של ה-Remote Config),
במקום ה-`MetadataRequest` הסטטי.

::: tashtiot_apis_library.schemas
