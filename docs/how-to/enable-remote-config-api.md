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
    remote_prefix="/api/v1",                     # upstream prefix serving /projects, /config, /naming, /coordinates
    config_path="/config",                       # your route whose coordinate params get enum dropdowns
    naming_path="/naming",
)
```

## Define routes against the provider

The returned `RemoteConfigProvider` exposes `resolve_infra_config`, `resolve_naming_convention`,
`get_all_projects`, `get_coordinate_catalog`, and `get_coordinate_tree` (all cached for `cache_ttl`
seconds, default 60):

```python
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.config_api import (
    RequiredInfraMetadata, CoordinateCatalogResponse, CoordinateTreeResponse,
)

@app.get("/config")
async def get_config(meta: RequiredInfraMetadata = Depends()):
    return await provider.resolve_infra_config(meta)

@app.get("/coordinates", response_model=CoordinateCatalogResponse)
async def get_coordinates():
    # Discovery: the valid values per coordinate level plus the project list.
    return await provider.get_coordinate_catalog()

@app.get("/coordinates/tree", response_model=CoordinateTreeResponse)
async def get_coordinates_tree():
    # Same values, shaped as the nested config hierarchy.
    return await provider.get_coordinate_tree()
```

`get_coordinate_catalog` proxies the upstream's `/coordinates` route and returns a
[`CoordinateCatalogResponse`](../reference/api/config-api.md#models-allowlists)-shaped dict — the
sorted set of values for each of `space` / `network` / `region` / `island` / `environment`, plus
`projects`. An unseeded upstream yields empty lists (a valid `200`, not a `404`).

`get_coordinate_tree` proxies the upstream's `/coordinates/tree` route and returns a
[`CoordinateTreeResponse`](../reference/api/config-api.md#models-allowlists)-shaped dict — a nested
hierarchy (`coordinates`: space → network → region → island → sorted env list) plus the flat
`projects` list. An unseeded upstream yields `{"coordinates": {}, "projects": []}`.

## What it sets up

- A `RemoteConfigProvider` (returned) for resolving config / naming / projects.
- A **background poller** (registered on `general_create_app`'s lifespan) that refreshes the live
  coordinate allowlists from the upstream every `poll_interval` seconds, hot-patching both the
  Pydantic validators and the OpenAPI `enum` dropdowns. Pass `enable_polling=False` to drive it
  yourself.
- A `pydantic.ValidationError → 422` handler so a coordinate outside its allowlist returns the same
  shape as any other invalid query parameter.

## Serve stale on upstream failure

By default an unreachable or `5xx` upstream propagates as a `502` (the strict, fail-closed contract).
Pass `serve_stale_on_error=True` to instead fall back to the **last successfully-fetched value for
that key** (last-known-good) when the upstream is down:

```python
provider = enable_remote_config_api(app, ..., serve_stale_on_error=True)
```

Notes:

- Any upstream error *except* `404` falls back — unreachable host, `5xx`, or `4xx` (all map to a
  `502` internally). A `404` is not an error: it means "no value yet" and returns the empty default.
- The last-known-good store is **unbounded** (never expires), separate from the `cache_ttl` cache, so
  a key that was fetched once stays serveable through an outage of any length.
- A key never fetched successfully has no fallback, so its first request during an outage still
  `502`s.

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
