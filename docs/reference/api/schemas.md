# Schemas API

Shared, Kubernetes/PaaS-oriented request models re-exported at the top level. They include CPU/memory
regex validation.

```python
from tashtiot_apis_library import (
    OperationRequest, ResourceSpec, DefaultMetaSpec, NameNamespace,
)
```

The four headline models are re-exported at the top level; the rest are their building blocks
(`CpuAndMemory`, `PaasLabels`, `MetadataRequest`).

::: tashtiot_apis_library.schemas
