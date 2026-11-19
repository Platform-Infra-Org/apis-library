---
name: building-tashtiot-apis
description: Use when creating, extending, reviewing or fixing a company HTTP API built on tashtiot-apis-library (FastAPI) - adding routes, request/response schemas, AWX/ArgoCD/Git/Vault calls, auth, Remote Config, long-running jobs, tests, Dockerfile or Woodpecker CI. Also use when a repo imports tashtiot_apis_library or follows the example-api layout.
---

# Building APIs on tashtiot-apis-library

## Overview

Company APIs are thin **async orchestrators** on `tashtiot-apis-library`. They validate a
`{metadata, spec}` request, call AWX, ArgoCD, Git (Bitbucket), Vault or other services through the
library, and return a standard response. Every rule here comes from the library's
[API standards](https://platform-infra-org.github.io/apis-library/reference/api-standards/) page. That page wins if this skill drifts from it.

| Resource | Link |
|---|---|
| Library docs | <https://platform-infra-org.github.io/apis-library/> |
| Library source (`tashtiot-apis-library`) | <https://github.com/Platform-Infra-Org/apis-library> (code under `src/tashtiot_apis_library/`) |
| Reference implementation (`example-api`) | <https://github.com/Platform-Infra-Org/example-api> |
| Why: async, job queues, replicas | [async](https://platform-infra-org.github.io/apis-library/explanation/async/), [job queues](https://platform-infra-org.github.io/apis-library/explanation/job-queues/), [replicas](https://platform-infra-org.github.io/apis-library/explanation/cloud-native/) |

**Never guess a library name.** Check every import, class, method and argument against the
[library source](https://github.com/Platform-Infra-Org/apis-library/tree/master/src/tashtiot_apis_library), at the tag matching the version the
API depends on (`/tree/vX.Y.Z/`).

The package is private: it installs only from Artifactory inside the air-gapped network.
Outside it, read the source on GitHub, and never switch the dependency to a git URL.

**Migrating an existing API to a new library version, or rewriting one onto the library?** Use the
[migration prompt](https://platform-infra-org.github.io/apis-library/how-to/migrate-an-api/) instead of this skill.

## Module layout

Each resource lives in `app/v<N>/<resource>/` and is wired **only** in `app/main.py:create_app()`:

| File | Holds | Never |
|---|---|---|
| `conf.py` | `BaseSettings` singleton `config` with `API_PREFIX="/api/<api>/v<N>/<resource>"`, `API_TAGS`, ids | Secret defaults, or settings the library owns (`AUTH_*`, `AUTH_SSO_*`, `CONFIG_REMOTE_*`, `PORT`, `LOG_LEVEL`, `PROXIED`) |
| `schemas.py` | `{metadata, spec}` request models, response models | I/O |
| `operations.py` | `async def` business logic that **receives connectors as arguments** | `Request`/`Response`, `os.environ`, building connectors |
| `routes.py` | `get_<resource>_router(<connectors>) -> APIRouter` | Business logic, building connectors |

Shared models go in `app/schemas.py`, app-wide settings in `app/global_conf.py`, and every variable
is listed in `.env.example`, including the library's `AUTH_*` / `AUTH_SSO_*` / `CONFIG_*` ones as
commented placeholders.

## Core pattern

```python
# app/schemas.py: the request contract, defined once per API
from pydantic import BaseModel, Field
from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata

class ProjectMetadata(InfraMetadata):           # space/network/region/island/environment stay optional
    project: str = Field(..., description="The platform application submitting the request")

class MetadataRequest(BaseModel):
    metadata: ProjectMetadata                    # always accepted; unused fields are just ignored

# app/v1/dns/schemas.py
from ipaddress import IPv4Address
from tashtiot_apis_library.connectors import AWXOperationResponse

class DNSRecordCreateSpec(BaseModel):
    record_name: str = Field(..., max_length=15, description="Record name")
    ip: IPv4Address = Field(..., description="Target IPv4 address")

class DNSRecordCreate(MetadataRequest):
    spec: DNSRecordCreateSpec

class DNSRecordResponse(AWXOperationResponse):
    pass

# app/v1/dns/operations.py
async def create_dns(record: DNSRecordCreate, awx, provider=None) -> DNSRecordResponse:
    template_id = config.AWX_CREATE_DNS_TEMPLATE_ID                      # static fallback
    if provider is not None:                                             # Remote Config only if wired
        resolved = await provider.resolve_infra_config(record.metadata)
        template_id = resolved.get("awx_create_dns_template_id", template_id)
    job = await awx.launch_job(job_template_id=template_id,
                               extra_vars={"RECORD_NAME": record.spec.record_name,
                                           "RECORD_ADDRESS": str(record.spec.ip)})
    return DNSRecordResponse(**job.model_dump())

# app/v1/dns/routes.py
def get_v1_dns_router(awx: AWX, provider=None) -> APIRouter:
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", response_model=DNSRecordResponse, status_code=202,
                 summary="Create DNS record", description="Launches the AWX create-DNS job.")
    async def create(record: DNSRecordCreate):
        try:
            return await create_dns(record, awx, provider)
        except ExternalServiceError as err:                              # upstream failed -> 502
            return JSONResponse(status_code=502, content={"detail": f"{err.service_name}: {err.detail}"})

    @router.get("/status/{job_id}", response_model=DNSRecordResponse, summary="DNS job status",
                description="Reads the AWX job state (HTTP 200; the state is in the body).")
    async def status(job_id: int):
        try:
            return await awx.get_job_status(job_id)                      # AWX is the job queue
        except ExternalServiceError as err:
            return JSONResponse(status_code=502, content={"detail": f"{err.service_name}: {err.detail}"})

    return router

# app/main.py
def create_app() -> FastAPI:
    app = general_create_app(enable_auth=True, title=global_config.API_TITLE,
                             version=global_config.APP_VERSION)
    awx = AWX(global_config.AWX_URL, global_config.AWX_TOKEN)           # once, never per request
    app.include_router(get_v1_dns_router(awx, provider=None))
    return app
```

## Rules

**Contract**

- Every write route takes `{"metadata": {...}, "spec": {...}}`, with `metadata: ProjectMetadata`.
  `project` is required and the other coordinates are optional. Metadata is accepted even when the
  API uses none of it. Never `extra="forbid"` on metadata.
- Every route has a `response_model`, `summary`, `description` and an explicit status code. Every
  field has a `description`.
- Status codes:
    - `200` for a read, `201` for a finished create, `204` for a delete.
    - **`202` + an id** when the work finishes later (AWX job, ArgoCD sync, queued job).
    - `422` for validation errors (automatic), `401` for auth failures (automatic, middleware).
    - `404` / `409` as usual.
    - **`502` for an upstream failure**, `504` for an upstream timeout.
- Paths are `/api/<api>/v<N>/<resource>`, where `<api>` is the API's own name (for example
  `example` for `example-api`). Ask if it isn't obvious from the repo. A breaking change goes in a new
  `app/v<N+1>/` and is released as a major version.

**Async**

- Handlers and operations that do I/O are `async def`, and every connector call is `await`ed.
- Never inside async code: `requests`, `time.sleep`, `subprocess.run`, sync DB/SDK clients.
  Use `BaseAPI` / connectors, `asyncio.sleep`, `asyncio.create_subprocess_exec`,
  `asyncio.to_thread`.
- Every network wait has a timeout. Independent calls run with `asyncio.gather`.
- `asyncio.create_task` results are kept in a module-level `set`, with
  `add_done_callback(set.discard)`, and catch and log their own exceptions.

**Connectors and errors**

- `AWX`, `ArgoCD`, `Git`, `Vault` are built once in `create_app()` and passed through router
  factories. They are not injected with `Depends`.
- Any other service goes through `async with BaseAPI(url, ...) as client:`, or
  `sso_authenticated_api(url)` when it needs an SSO bearer. Set `verify=True` when the service has a
  valid certificate (the default is `False`).
- `ExternalServiceError` (and `AWXError`, `ArgoCDError`, `GitError`, `VaultError`) is an
  `HTTPException` carrying the **upstream's** code. Catch it in routes and return 502. An expected
  upstream 404 (for example `vault.read_secret` on a missing secret raises `VaultError` with
  `status_code == 404`) is handled in the operation.
- `Vault` paths are KV v2: `/<mount>/<path>` is read and written at `<mount>/data/<path>`, and
  `delete_secret` removes the secret's metadata, which means **all versions**.
- Multi-step writes (Git → Vault → ArgoCD, Vault → AWX, …):
    - run the step a later one depends on first (for example, write the Vault secret before
      launching the AWX job that reads it)
    - snapshot state first
    - on failure, compensate in reverse order, each step in its own `try/except` with
      `logger.exception`, then re-raise
    - make every step idempotent (skip no-op writes, treat a 404 on delete as success)

**Long-running work**

- **AWX already is a job queue.** Launch the job, return 202 + `job_id`, and expose
  `GET .../status/{job_id}` → `awx.get_job_status`.
- The status route **always returns HTTP 200** when it read the job successfully. The job's state is
  in the body: `status` (`pending`/`running`/`successful`/`failed`/…) and `status_code` (202 while
  running, 200 when done, 500 when failed). **Never copy that `status_code` into the HTTP
  status**, because a failed job is a result, not a server error. Use HTTP 404 for an unknown job
  id, and 502 when AWX itself fails.
- In-process tasks are for short, best-effort work only, and their status comes from the external
  system.
- The library has **no job queue**. For durable work inside the API, **ask the team** whether to
  implement one, use an external solution, or move the work into AWX.

**Auth**

- Always `general_create_app(enable_auth=True)`. It is enforced only when `AUTH_ENABLED=true`, with
  exactly one mode configured:
    - production: `AUTH_OIDC_ISSUER` / `AUTH_JWKS_URL` + `AUTH_AUDIENCE`
    - tests and local dev: `AUTH_HS256_SECRET`
- The API only **authenticates**: it checks the JWT signature, expiry and audience. **Authorization
  is handled outside the APIs**, so never add permission checks on `project`, roles or scopes. Read
  claims with `Depends(get_current_claims)` only for logging and auditing.
- Outbound calls use `sso_authenticated_api`. Catch `AuthConfigError`. Never cache tokens yourself.

**Remote Config** (only when a value varies by environment or coordinate)

- Wire it opt-in: `if CONFIG_API_URL:`, wrapped in `try/except AuthConfigError`, passing
  `coordinate_paths=[regex, ...]`.
- Resolve with `await provider.resolve_infra_config(payload.metadata)`, and always fall back to a
  static `conf.py` default.

**Multiple replicas** (every API runs as several pods, and old and new versions overlap during
rollouts)

- No source of truth in memory or on local disk: any pod must answer any request.
- Operations are safe when duplicated across pods at the same time. Let the upstream reject
  conflicts and return 409. `asyncio.Lock` doesn't protect across pods.
- `async_background_tasks` runs on **every** pod, so only idempotent loops go there. Once-only work
  goes to a CronJob, an AWX schedule or a queue.
- Probes don't depend on upstreams. Changes stay backward compatible for one release. One uvicorn
  process per pod.

**Logging and secrets**

- Loguru with `{}` placeholders. No `print`.
- Never log or return tokens, secrets, `Authorization` headers or Vault payloads.
- The library's 422 bodies and validation logs show only `loc`, `msg` and `type`. Keep it that way:
  a validator's error message must not contain the submitted value.
- Secrets never appear in code, defaults, `.env.example`, tests or the image.

## Quick reference: imports

| Need | Import |
|---|---|
| App factory, connectors, connector errors, request bases | `from tashtiot_apis_library import general_create_app, AWX, ArgoCD, Git, Vault, ExternalServiceError, InfraOperationRequest, ResourceSpec, NameNamespace, DefaultMetaSpec` |
| Response models | `from tashtiot_apis_library.connectors import OperationResponse, AWXOperationResponse, ArgoOperationResponse` |
| Metadata model | `from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata` |
| HTTP client, library settings | `from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings` |
| Inbound auth | `from tashtiot_apis_library.fastapi_template.auth import get_current_claims, verify_token` |
| Outbound SSO | `from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api` |
| Auth errors | `from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError` |
| Remote Config | `from tashtiot_apis_library.fastapi_template import enable_remote_config_api` |

Never import from `..._internal`.

## Tests

- Layout: `tests/conftest.py`, then `tests/v<N>/<resource>/conftest.py` + `test_*.py` per module.
- `tests/conftest.py` blanks optional `AUTH_*`/`CONFIG_*` env vars.
- Module conftests set `AUTH_ENABLED=true` + `AUTH_HS256_SECRET` (32+ bytes) and the required base
  env vars **before** importing `app.main`.
- Route tests use `TestClient(create_app())` and a bearer from `jwt.encode(...)`.
- Required cases:
    - schema: valid, invalid → 422, project-only metadata, extra metadata keys
    - auth: no token → 401, bad token → 401, good token → 200
    - every operation failure and rollback path
    - Remote Config fallback
- Mock connectors with `monkeypatch.setattr(AWX, "launch_job", fake_async)`, or mock HTTP with
  `respx`. No real network calls.

## Shipping

- Packaging:
    - uv, with `uv.lock` committed and `uv.toml` never committed
    - `tashtiot-apis-library>=<current>`
    - Python 3.12
- Docker: follow [`example-api`](https://github.com/Platform-Infra-Org/example-api)'s Dockerfile, with the base image from **JFrog Artifactory** and
  `APP_VERSION` set from the git tag.
- CI: Woodpecker runs in the air-gapped network (tests, formatting, linting, SonarQube, then build
  and push to JFrog Artifactory). The CI how-to in the internal Confluence is the source of truth.
- Release: semver via git-cliff. **The PR title is the changelog line** and must be a conventional
  commit (`feat:` bumps the minor version, `fix:` the patch, `!` / `BREAKING CHANGE` the major).
  Never edit `CHANGELOG.md` by hand.

## Common mistakes

| Mistake | Fix |
|---|---|
| Route body is just the spec fields, or `metadata` is missing on an API that "doesn't need it" | `{metadata: ProjectMetadata, spec: ...}` everywhere |
| Using `OperationRequest` / `MetadataRequest` from the library (requires 5 coordinates) | `ProjectMetadata` (only `project` required) |
| Returning 200 after `launch_job` | 202 + `job_id`, plus a status route |
| Letting `ExternalServiceError` propagate (client sees Vault's 403 as its own) | Catch it, return 502 |
| `AWX(...)` / `Vault(...)` created inside a handler | Build once in `create_app()` and inject |
| `requests.post` / `time.sleep` in an `async def` | `BaseAPI` / `asyncio.sleep` |
| `if claims["project"] != body.metadata.project: raise 403` | Remove it. Authorization is outside the APIs. |
| `asyncio.create_task(...)` with the result dropped | Keep the task in a set |
| Job status kept in a module-level dict, or an hourly cleanup loop in `async_background_tasks` | Status from AWX or a shared store; once-only work as a CronJob or AWX schedule |
| Declaring `AUTH_HS256_SECRET` in the API's `BaseSettings` | The library reads `AUTH_*` itself |
| Copying `example-api`'s stubs (`dns` PUT/GET), the chat route without metadata, or its Harbor base image | See [Known gaps in `example-api`](https://platform-infra-org.github.io/apis-library/reference/api-standards/#known-gaps-in-example-api) |
