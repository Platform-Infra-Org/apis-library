---
name: building-tashtiot-apis
description: Use when creating, extending, reviewing or fixing a company HTTP API built on tashtiot-apis-library (FastAPI) - adding routes, request/response schemas, AWX/ArgoCD/Git/Vault calls, auth, Remote Config, long-running jobs, tests, Dockerfile or packaging - on GitHub or inside the air-gapped network. Also use when a repo imports tashtiot_apis_library or follows the example-api layout.
---

# Building APIs on tashtiot-apis-library

## Overview

Company APIs are thin **async orchestrators** on `tashtiot-apis-library`. They validate a
`{metadata, spec}` request, call AWX, ArgoCD, Git (Bitbucket), Vault or other services through the
library, and return a standard response.

**This folder is self-contained.** It works with no access to GitHub or the docs site:

| File | Use it for |
|---|---|
| `SKILL.md` (this file) | The rules |
| [`reference.md`](reference.md) | The library's public API: imports, connector signatures and return models, errors, every library env var, auth, SSO, Remote Config, the `gen-auth-material` CLI |
| [`template/`](template/) | A complete, tested API (one AWX-backed resource, optional Remote Config, auth, tests, `pyproject.toml`, `Dockerfile`, `.env.example`, `uv.toml.example`, `cliff.toml`). Copy it to start a new API, or use it as the pattern for a new module. |

**Never guess a library name.** Check every import, class, method and argument against, in order:

1. **The installed package:** `.venv/lib/python3.*/site-packages/tashtiot_apis_library/`.
   - **Inside the air-gapped network**, it installs from JFrog Artifactory, so it's available.
   - **Outside the network**, the package is private and there may be no installed copy.
2. **`reference.md`**, written for library 1.3.2. If the installed version differs, the installed
   source wins.
3. **When GitHub is reachable:** the source at the matching tag,
   `https://github.com/Platform-Infra-Org/apis-library/tree/vX.Y.Z/src/tashtiot_apis_library`.

Never switch the dependency to a git URL or a local path to get the package.

**When reachable:**
- **Docs:** `https://platform-infra-org.github.io/apis-library/`, which has the full API
  standards, why the rules exist, and how-to guides.
- **Reference implementation:** `https://github.com/Platform-Infra-Org/example-api`. Avoid the
  "Known gaps" listed on the docs' API standards page.

This file is a condensed copy of those standards. If they disagree, the docs win.

## Where the work happens

- **On GitHub:** code for the library and the APIs is developed here, including PR checks
  (format, lint, tests) and the release tag.
- **Inside the air-gapped network:** a mirror or a copy of `main` is transferred in. Woodpecker CI
  builds the image, runs internal tests and SonarQube, and pushes to **JFrog Artifactory**.
- **CI conventions, plugins and secrets are internal.** For pipeline, image or deployment work,
  follow the CI how-to in the internal Confluence, and the internal CI skill if one is installed.
  This skill covers the application code.
- **Keep this skill in the API repo:** commit this folder as `.claude/skills/building-tashtiot-apis/`
  in each API repository, so it travels with the mirror. Refresh it from the library release
  whenever the API bumps `tashtiot-apis-library`.
- **Migrating an API to a new library version, or rewriting one onto the library?** Use the
  library's migration prompt (`prompts/migrate-api.md` in the library repo; on the docs site,
  *How-to → Migrate an API*) instead of this skill.

## Module layout

Each resource lives in `app/v<N>/<resource>/` and is wired **only** in `app/main.py:create_app()`.
See `template/app/`.

| File | Holds | Never |
|---|---|---|
| `conf.py` | `BaseSettings` singleton `config` with `API_PREFIX="/api/<api>/v<N>/<resource>"`, `API_TAGS`, ids | Secret defaults, or settings the library owns (`AUTH_*`, `AUTH_SSO_*`, `CONFIG_REMOTE_*`, `PORT`, `LOG_LEVEL`, `PROXIED`) |
| `schemas.py` | `{metadata, spec}` request models, response models | I/O |
| `operations.py` | `async def` business logic that **receives connectors as arguments** | `Request`/`Response`, `os.environ`, building connectors |
| `routes.py` | `get_<resource>_router(<connectors>) -> APIRouter` | Business logic, building connectors |

Shared files:
- **`app/schemas.py`:** `ProjectMetadata` / `MetadataRequest`.
- **`app/global_conf.py`:** app-wide settings. Secrets are required fields with no default.
- **`.env.example`:** lists every variable, including the library's own as commented placeholders.

| Pattern | Where in `template/` |
|---|---|
| Request contract (`ProjectMetadata`, `MetadataRequest`) | `app/schemas.py` |
| Wiring: connectors built once, opt-in Remote Config, routers | `app/main.py` |
| Validated `spec`, AWX response model | `app/v1/dns/schemas.py` |
| Operation with a Remote Config lookup and static fallback | `app/v1/dns/operations.py` |
| 202 + job id, status route (HTTP 200, state in body), 404, 502 mapping | `app/v1/dns/routes.py` |
| Hermetic env, HS256 bearer, mocked AWX, the required test cases | `tests/` |

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

**Connectors and errors** (signatures in `reference.md`)

- `AWX`, `ArgoCD`, `Git`, `Vault` are built once in `create_app()` and passed through router
  factories. They are not injected with `Depends`.
- Any other service goes through `async with BaseAPI(url, ...) as client:`, or
  `sso_authenticated_api(url)` when it needs an SSO bearer. Set `verify=True` when the service has a
  valid certificate (the default is `False`).
- `ExternalServiceError` (and `AWXError`, `ArgoCDError`, `GitError`, `VaultError`) is an
  `HTTPException` carrying the **upstream's** code. Catch it in routes and return 502. An expected
  upstream 404 (for example `vault.read_secret` on a missing secret) is handled in the operation.
- `vault.read_secret()` returns a `VaultSecret`, and **its key/values are on `.data`**. Back up and
  restore `secret.data`, never the object: writing the object stores
  `{"data": ..., "metadata": ...}`.
- `Vault` paths are KV v2: `/<mount>/<path>` is read and written at `<mount>/data/<path>`, and
  `delete_secret` removes the secret's metadata, which means **all versions**. Every operation on
  one resource uses the same path.
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
- Never `await awx.wait_for_job_completion(...)` inside a request.
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
  conflicts (`Git.add_file` raises 409 on an existing path) and return 409. `asyncio.Lock` doesn't
  protect across pods.
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
| App factory, connectors, connector errors, request bases | `from tashtiot_apis_library import general_create_app, AWX, ArgoCD, Git, Vault, ExternalServiceError, AWXError` |
| Response models | `from tashtiot_apis_library.connectors import OperationResponse, AWXOperationResponse, ArgoOperationResponse` |
| Metadata model, Remote Config provider type | `from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata, RemoteConfigProvider` |
| Remote Config wiring | `from tashtiot_apis_library.fastapi_template import enable_remote_config_api` |
| HTTP client, library settings | `from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings` |
| Inbound auth | `from tashtiot_apis_library.fastapi_template.auth import get_current_claims, verify_token` |
| Outbound SSO | `from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api` |
| Auth errors | `from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError` |

Never import from `..._internal`. The full list is in `reference.md`.

## Tests

`template/tests/` is the working pattern:

- **Layout:** `tests/conftest.py`, then `tests/v<N>/<resource>/conftest.py` + `test_*.py` per
  module.
- **`tests/conftest.py`** runs before any app or library import. It blanks the optional
  `AUTH_*`/`CONFIG_*` env vars, sets the required ones, and sets `AUTH_ENABLED=true` +
  `AUTH_HS256_SECRET` (32+ bytes). The library and the settings singletons read the env **at
  import time**.
- **Route tests** use `TestClient(create_app())` and a bearer from `jwt.encode(...)`.
- **Required cases:**
    - schema: valid, invalid → 422, project-only metadata, extra metadata keys
    - auth: no token → 401, bad token → 401, good token → 200
    - every upstream failure (→ 502) and rollback path
    - Remote Config fallback
- **No real network calls.** Mock connectors with `monkeypatch.setattr(AWX, "launch_job", fake_async)`
  (fakes return the real response models), or mock HTTP with `respx`.

## Shipping

- **Packaging** (`template/pyproject.toml`, `template/uv.toml.example`):
    - uv, with `uv.lock` committed and `uv.toml` never committed (it carries Artifactory
      credentials)
    - `tashtiot-apis-library>=<current>` from JFrog Artifactory
    - Python 3.12
    - `uv lock` / `uv sync` only resolve where Artifactory is reachable, so regenerate the lock
      there
- **Docker** (`template/Dockerfile`): the base image from **JFrog Artifactory**, passed as
  `BASE_IMAGE`, `APP_VERSION` set from the git tag, one uvicorn process, and no secrets in the
  image.
- **CI:** Woodpecker inside the air-gapped network (tests, formatting, linting, SonarQube, then
  build and push to JFrog Artifactory). The CI how-to in the internal Confluence is the source of
  truth.
- **Release:** semver via git-cliff (`template/cliff.toml`). **The PR title is the changelog line**
  and must be a conventional commit (`feat:` bumps the minor version, `fix:` the patch, `!` /
  `BREAKING CHANGE` the major). Never edit `CHANGELOG.md` by hand.

## Common mistakes

| Mistake | Fix |
|---|---|
| Route body is just the spec fields, or `metadata` is missing on an API that "doesn't need it" | `{metadata: ProjectMetadata, spec: ...}` everywhere |
| Using `OperationRequest` / `MetadataRequest` from the library (requires 5 coordinates) | `ProjectMetadata` (only `project` required) |
| Returning 200 after `launch_job` | 202 + `job_id`, plus a status route |
| Letting `ExternalServiceError` propagate (client sees Vault's 403 as its own) | Catch it, return 502 |
| Backing up `await vault.read_secret(p)` and writing it back | Back up `secret.data` |
| `AWX(...)` / `Vault(...)` created inside a handler | Build once in `create_app()` and inject |
| `requests.post` / `time.sleep` in an `async def` | `BaseAPI` / `asyncio.sleep` |
| `if claims["project"] != body.metadata.project: raise 403` | Remove it. Authorization is outside the APIs. |
| `asyncio.create_task(...)` with the result dropped | Keep the task in a set |
| Job status kept in a module-level dict, or an hourly cleanup loop in `async_background_tasks` | Status from AWX or a shared store; once-only work as a CronJob or AWX schedule |
| Declaring `AUTH_HS256_SECRET` in the API's `BaseSettings` | The library reads `AUTH_*` itself |
| Pointing the dependency at a git URL or `../apis-library` to make it install | Keep `tashtiot-apis-library>=X.Y.Z` from Artifactory; resolve inside the network |
