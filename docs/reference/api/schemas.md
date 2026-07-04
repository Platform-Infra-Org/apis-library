# Schemas API

Shared, Kubernetes/PaaS-oriented request models re-exported at the top level. They include CPU/memory
regex validation.

```python
from tashtiot_apis_library import (
    OperationRequest, ResourceSpec, DefaultMetaSpec, NameNamespace,
    InfraOperationRequest, RequiredInfraOperationRequest,
)
```

These headline models are re-exported at the top level; the rest are their building blocks
(`CpuAndMemory`, `PaasLabels`, `MetadataRequest`). `InfraOperationRequest` /
`RequiredInfraOperationRequest` mirror `OperationRequest` but carry the **dynamic** `InfraMetadata` /
`RequiredInfraMetadata` coordinate metadata (validated against the live Remote Config allowlists +
tree) instead of the static `MetadataRequest`.

::: tashtiot_apis_library.schemas
