# Constrain a field by resolved config

Sometimes a request field's valid values depend on the **config resolved for the request's own
coordinates** — e.g. the OS templates a VM may use differ at every leaf of the enterprise config. The
library deliberately **doesn't ship** a helper for this (the config key, the field, and the request
model are all app-specific). Instead, write a small FastAPI dependency in your app. Here's the pattern.

For *why* this is a dependency rather than a Pydantic validator, see
[Dynamic config validation](../explanation/dynamic-config-validation.md).

## The pattern

```python
from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from tashtiot_apis_library.fastapi_template.config_api import RequiredInfraMetadata


class VMSpec(BaseModel):
    os_template: str
    instance_size: str


class VMRequest(BaseModel):
    metadata: RequiredInfraMetadata      # coordinates — validated against the allowlists + tree
    spec: VMSpec                          # the fields whose allowed values depend on the config


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
            if allowed and value not in allowed:          # permissive when the config is unset/empty
                errors.append(
                    {
                        "type": "value_error",
                        "loc": ("body", "spec", field),    # points clients at the offending field
                        "msg": f"'{value}' is not permitted for the selected coordinates; "
                        f"allowed: {sorted(allowed)}",
                        "input": value,
                    }
                )
        if errors:
            raise RequestValidationError(errors)           # -> a standard 422, one entry per field
        return req

    return dependency


@app.post("/vms")
async def create_vm(req: VMRequest = Depends(constrain_vm(provider))):
    ...   # req is fully validated: coordinates AND spec.os_template / spec.instance_size
```

`provider` is the `RemoteConfigProvider` returned by
[`enable_remote_config_api`](enable-remote-config-api.md).

## How it reads

- **The request is a JSON body.** A plain model parameter on the dependency function
  (`req: VMRequest`) is parsed as the request body — you don't have to make the coordinates query
  parameters. FastAPI validates it (running the coordinate allowlist + hierarchy checks) *before* the
  dependency runs.
- **`req.metadata` drives the lookup.** The coordinate submodel is passed to `resolve_infra_config`,
  which returns the merged config for that leaf. Your config places each field's allowed values under a
  known key (`os_templates`, `instance_sizes`, …).
- **The constrained fields can sit anywhere** in the body — here they're under `spec`, reached with
  plain attribute access (`req.spec.os_template`). Match the `loc` to the field's real position so the
  `422` points clients at the right place.
- **It runs after the model's own validators**, so by the time the dependency executes the coordinates
  are already known-valid.

## Use cases

- Per-leaf VM **OS templates / images**.
- **Instance sizes / flavors** permitted in a given region or island.
- Allowed **backup targets** or **networks** per environment.
- **Quotas** or **feature toggles** resolved per leaf.

## Fail-open vs fail-closed

The example is **permissive**: if the config doesn't list the key (or the list is empty), the field is
accepted. That mirrors the coordinate validators, which don't reject when their allowlist is empty
(pre-poll or upstream missing). To **fail closed** instead — reject anything not explicitly allowed —
drop the `allowed and` guard and require a non-empty `allowed`.

## See also

- [Dynamic config validation](../explanation/dynamic-config-validation.md) — why this is a dependency,
  not a validator.
- [Enable the Remote Config API](enable-remote-config-api.md) — the provider and coordinate models.
