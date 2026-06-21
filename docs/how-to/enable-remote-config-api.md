# Enable the Remote Config API

`enable_remote_config_api` wires a thin **authenticated proxy to an upstream Config API** onto your
app. The upstream resolves hierarchical infrastructure config / naming / project-registry from a set
of *allocation coordinates* (`space`, `network`, `region`, `island`, `environment`, `project`); this
capability forwards those coordinates over HTTP, caches the result in memory, and keeps your own
Swagger dropdowns and request validation in sync with the upstream's live allowlists.

## Wire it up

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template import enable_remote_config_api

app = general_create_app()

provider = enable_remote_config_api(
    app,
    base_url="https://config-api.example.com",  # where the upstream lives
    remote_prefix="/api/v1",                     # upstream prefix serving /projects, /config, /naming
    config_path="/config",                       # your route whose coordinate params get enum dropdowns
    naming_path="/naming",
)
```

## Define routes against the provider

The returned `RemoteConfigProvider` exposes `resolve_infra_config`, `resolve_naming_convention`, and
`get_all_projects` (all cached for `cache_ttl` seconds, default 60):

```python
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.config_api import RequiredInfraMetadata

@app.get("/config")
async def get_config(meta: RequiredInfraMetadata = Depends()):
    return await provider.resolve_infra_config(meta)
```

## What it sets up

- A `RemoteConfigProvider` (returned) for resolving config / naming / projects.
- A **background poller** (registered on `general_create_app`'s lifespan) that refreshes the live
  coordinate allowlists from the upstream every `poll_interval` seconds, hot-patching both the
  Pydantic validators and the OpenAPI `enum` dropdowns. Pass `enable_polling=False` to drive it
  yourself.
- A `pydantic.ValidationError → 422` handler so a coordinate outside its allowlist returns the same
  shape as any other invalid query parameter.

## Choose the outbound auth

Authentication to the upstream is **selectable via `CONFIG_REMOTE_*` environment variables** —
`CONFIG_REMOTE_AUTH_METHOD` picks `sso` (OAuth2 `client_credentials`), `bearer` (a static token), or
`none`. See the [Remote Config configuration table](../reference/configuration.md#remote-config-api-outbound-to-the-upstream).

To override settings entirely (tests / escape hatch), pass an explicit `httpx.Auth`:

```python
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth

provider = enable_remote_config_api(app, ..., auth=StaticBearerAuth("token"))
```

!!! note "Lazy dependency"
    Remote Config pulls in [`aiocache`](https://pypi.org/project/aiocache/) for its in-memory cache.
    Because both the cache and `enable_remote_config_api` import lazily, apps that don't call it never
    need `aiocache`.

## See also

- [API reference: Remote Config API](../reference/api/config-api.md)
- [Configuration reference](../reference/configuration.md)
