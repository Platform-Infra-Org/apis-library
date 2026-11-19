<!--
  MAINTAINERS: keep this prompt in step with the library.
  On EVERY release, update:
    1. TARGET_VERSION below, the version in the dependency line in step A1, and the git tag in
       every apis-library source link (/tree/vX.Y.Z/),
    2. the "Upgrade notes by version" table (add a row for anything a consumer must change or verify),
    3. the "Library quick reference" if any public import path, signature, or default changed.
  The release checklist in MAINTAINERS.md points here.
-->

# Migrate an API to tashtiot-apis-library 1.3.1

TARGET_VERSION: **1.3.1**

You are migrating the API in the current repository to **`tashtiot-apis-library` 1.3.1** and to the
company **API standards**. You are working as a careful senior engineer: you read the code before
changing it, you verify every library name against the library's source, and you never guess.

## Sources of truth (read these, don't rely on memory)

1. **The library source at the target tag:**
   <https://github.com/Platform-Infra-Org/apis-library/tree/v1.3.1/src/tashtiot_apis_library>.
   Every import, class, method and argument you use must exist there. If the docs and the source
   disagree, the source wins. Read it from GitHub, or from a local clone checked out at `v1.3.1`.

   **Don't rely on an installed copy.** The package is private. It can only be `pip`/`uv` installed
   from Artifactory **inside the air-gapped network**, so outside it there is no installed copy to
   read. Don't switch the dependency to a git URL to work around this.

2. **The library docs**, <https://platform-infra-org.github.io/apis-library/>, especially:
    - [API standards](https://platform-infra-org.github.io/apis-library/reference/api-standards/): the rules this migration must meet.
    - [Async and the event loop](https://platform-infra-org.github.io/apis-library/explanation/async/),
      [Job queues & long-running work](https://platform-infra-org.github.io/apis-library/explanation/job-queues/) and
      [Cloud-native APIs & multiple replicas](https://platform-infra-org.github.io/apis-library/explanation/cloud-native/).
    - [How-to guides](https://platform-infra-org.github.io/apis-library/how-to/) for connectors, OIDC/JWKS, outbound SSO and the Remote Config
      API.
    - [Changelog](https://platform-infra-org.github.io/apis-library/changelog/): every change between the API's current version and 1.3.1.
3. **The `example-api` repository**, <https://github.com/Platform-Infra-Org/example-api>: the reference implementation of the structure.
   Follow its layout, but not the items listed under
   [Known gaps in `example-api`](https://platform-infra-org.github.io/apis-library/reference/api-standards/#known-gaps-in-example-api).

## Step 0: Choose the migration mode

Inspect the repository, then pick **exactly one** mode, and state which one and why before you change
anything:

| | **Mode A: Upgrade** | **Mode B: Rewrite** |
|---|---|---|
| **When** | The API already depends on `tashtiot-apis-library` (any version: check `pyproject.toml`, `uv.lock`, `requirements*.txt`, `setup.py`) | The API does **not** use the library (plain FastAPI, Flask, another framework, its own HTTP clients, sync code), **or** the user explicitly asks for a full rewrite |
| **Goal** | Move to 1.3.1 with the **smallest safe change** | Rebuild the API on the library so it fully meets the API standards |
| **Public contract** (paths, request/response shapes, status codes) | **Preserved.** Anything in the standards that would break callers is *reported*, not changed | **Redesigned to the standards** (`{metadata, spec}`, 202 for async work, …). It's a breaking change, so it ships as a **new major version** of the API |
| **Scope** | Dependency bump, the version-specific changes below, non-breaking conformance fixes | Everything: layout, config, connectors, async, auth, Remote Config, errors, tests, Docker, CI, changelog |

If the repository matches neither, or the user's intent is unclear, **stop and ask** which mode
they want.

## Ground rules (both modes)

- Work on a new branch. Run the existing test suite **before** you change anything and record the
  result, so you can tell pre-existing failures from new ones.
- Make the change in small, reviewable steps. Keep the app booting and the tests passing after each
  one.
- **Never block the event loop:** no `requests`, `time.sleep`, `subprocess.run` or sync DB/SDK
  clients inside `async def` code. Use the library's async connectors, `BaseAPI`,
  `asyncio.sleep`, `asyncio.create_subprocess_exec` or `asyncio.to_thread`.
- **Never import from `tashtiot_apis_library...._internal`.** Use only the public modules in the quick
  reference below.
- **Secrets** never go into code, `conf.py` defaults, `.env.example`, logs, tests or the image. Use
  placeholders in `.env.example`.
- **Authorization is handled outside the APIs.** Inbound auth only verifies the JWT (signature, expiry,
  audience). Don't add permission checks on token claims. If the existing code has some, don't port
  them, and list them in the report so the team can confirm they are enforced elsewhere.
- Don't add dependencies for things the library, FastAPI or the standard library already provide.
- When a decision belongs to the team (changing a public contract, removing a route, dropping
  existing authorization logic, choosing a job-queue solution), **ask**. Don't decide alone.

---

## Mode A: Upgrade from an earlier library version

### A1. Bump the dependency

- Set `tashtiot-apis-library>=1.3.1` in `pyproject.toml`. If the API still uses `setup.py` or
  `requirements.txt`, move it to `pyproject.toml` + **uv** (`uv.lock` committed, `uv.toml` never
  committed).
- Python must be **>= 3.10** (the company standard is 3.12: `.python-version`,
  `requires-python`, Dockerfile base image).
- Remove any local path override of the library (`[tool.uv.sources]`) unless the user says it is
  intentional for local development.
- **Inside the air-gapped network:** run `uv lock && uv sync --group dev`.
- **Outside it:** Artifactory isn't reachable, so `uv lock` / `uv sync` can't resolve the library.
  Leave the dependency line as `tashtiot-apis-library>=1.3.1`. Don't commit a stale or hand-edited
  `uv.lock`, and say in the report that the lock must be regenerated inside the network.

### A2. Apply the upgrade notes for every version you cross

Find the API's current library version, then apply **every row newer than it**, top to bottom.

| If the API is on… | Change or verify |
|---|---|
| **< 1.0.0** (0.x) | **Background tasks now actually run.** In 0.x, `general_create_app(async_background_tasks=[...])` accepted the list but never started it. From 1.0.0 every coroutine in it is launched at startup and cancelled on shutdown. Check that each one is safe to run, and remove any workaround that starts them another way (`@app.on_event("startup")`, a manual `create_task`), or they will run twice. |
| | **Don't pass your own `lifespan=`** to `general_create_app`. The library sets one, and a second raises `TypeError`. Register startup work through `async_background_tasks` (or append to `app.state.async_background_tasks` before startup). |
| | **Removed:** `tashtiot_apis_library.terraform_runner` and `fastapi_template._internal.models` (`ExceptionHandlerConfig`). Replace any usage. Never import `_internal`. |
| | **Inbound auth is available:** call `general_create_app(enable_auth=True, ...)`. It changes nothing until `AUTH_ENABLED=true` is set. Configure it per *Authentication* below. If the API had its own JWT check, replace it with the library's middleware and `get_current_claims`. |
| | **New request bases:** `InfraOperationRequest` / `RequiredInfraOperationRequest` (live-validated coordinates). The old `OperationRequest` requires `project`, `network`, `region`, `space` and `environment`, but the standard requires **only `project`**. Moving to the `ProjectMetadata` pattern (below) makes four fields optional, which is a non-breaking relaxation, so do it. |
| | **Outbound SSO and Remote Config** are now available (`fastapi_template.security`, `enable_remote_config_api`). Adopt them only where the API needs them (see below). |
| **< 1.1.0** | `enable_remote_config_api(..., serve_stale_on_error=...)` is new (default `False`, so behaviour is unchanged). Expose it as a setting if the team wants last-known-good config during upstream outages. |
| **< 1.1.2** | **`enable_remote_config_api` signature changed:** `config_path=` and `naming_path=` were replaced by **`coordinate_paths=[...]`**, a list of **regex strings** matched with `re.fullmatch` against route paths. Rewrite the call. The coordinate allowlists are now seeded once at startup even with `enable_polling=False`, and enums are injected into nested request-body models too. |
| **< 1.2.0** | `ArgoCD.create_app` / `ArgoCD.delete_app` are new. Replace any hand-rolled ArgoCD Application create/delete calls with them. |
| **< 1.2.1** | `Git(..., ssh_port=7995)` is now configurable (default unchanged). If the API patched the port, remove the patch and pass `ssh_port`. |
| **< 1.2.3** | **AWX status codes changed.** `AWX.get_job_status` / `get_workflow_job_status` used to return `status_code=200` for every state. They now map the AWX state: `pending`/`waiting`/`running` → **202**, `successful` → 200, `failed`/`error`/`canceled` → **500**. Launch calls still return `status="successful"`, `status_code=200`. Find every place that reads `status_code` from an AWX status response (route return values, `JSONResponse(status_code=...)`, tests, clients) and confirm the new values are intended. |
| **< 1.3.0** | `AWX.get_job_output(job_id, start_line=..., page_size=...)` (incremental playbook output) is new. Adopt it only if the API streams or polls job output. |
| **< 1.3.1** | `AWX.get_job_status` / `get_workflow_job_status` take a new keyword-only `include_logs=False`. With `True`, `stdout` carries a concise, filtered log summary (child jobs and failed-job output for workflows). The default is unchanged. Adopt it if the API's status route should return readable logs. |

### A3. Non-breaking conformance fixes

Bring the code in line with the API standards **wherever it doesn't change the public contract**:

- Connectors built once in `create_app()` and injected through router factories, never per request.
- Blocking calls replaced with async equivalents. `BaseAPI` used with `async with`, and TLS
  verification turned on where the service has a valid certificate.
- `ExternalServiceError` caught in routes and mapped to 502. Error `detail` has no secrets.
- Background tasks kept referenced (a module-level `set` + `add_done_callback(discard)`) and logging
  their own exceptions.
- Settings the library owns (`AUTH_*`, `AUTH_SSO_*`, `CONFIG_REMOTE_*`, `PORT`, `LOG_LEVEL`,
  `PROXIED`, …) removed from the API's own `BaseSettings`. `.env.example` lists every variable.
- Loguru with `{}` placeholders, no `print`, no secrets in logs.
- Tests: hermetic env, valid bearer for route tests, connectors mocked, no real network calls.

### A4. Report what you didn't change

List every remaining deviation from the standards that **would** break callers (for example: a write
route without `metadata`, `200`/`201` returned for work that is still running, a non-standard path
or version prefix). For each one, propose the fix and say it needs a new API version. Don't apply
these unless the user approves.

---

## Mode B: Rewrite onto the library and the API standards

### B1. Inventory the existing API (before writing code)

Produce a table, and show it to the user, covering:

- Every endpoint: method, path, request and response shape, status codes, whether it is
  long-running.
- Every external system it calls (AWX, ArgoCD, Bitbucket, Vault, others), and how (library, own
  client, sync/async).
- Auth today (inbound and outbound), and any authorization logic.
- Configuration and secrets (env vars, files).
- Background or periodic work.
- Tests, Dockerfile and CI that exist.

Then confirm with the user: the new API name and path prefix (`/api/<api-name>/v<N>/...`), the new
major version, and whether the old version must keep running alongside it during the transition.

### B2. Scaffold the standard layout

Follow the "Project layout" in the API standards (`app/main.py`, `app/global_conf.py`,
`app/schemas.py`, and `app/v<N>/<resource>/{conf,schemas,operations,routes}.py`), with
`general_create_app(enable_auth=True, title=..., version=APP_VERSION)` as the single wiring point.

### B3. Request and response contract

- Every write route takes `{"metadata": {...}, "spec": {...}}`, with `metadata` typed as
  `ProjectMetadata` (below): `project` required, the other coordinates optional. Metadata the API
  doesn't use is accepted and ignored.
- `spec` holds the resource's desired state, with typed, validated fields.
- Responses use `response_model=` and extend `OperationResponse` / `AWXOperationResponse` /
  `ArgoOperationResponse`.
- Status codes follow the standards table: **202 + an id** for work that finishes asynchronously, and
  **502** for upstream failures.

### B4. Connectors and async

- Replace each external call with the library connector (`AWX`, `ArgoCD`, `Git` for Bitbucket
  Server, `Vault`). Use `BaseAPI` for any other HTTP service, or `sso_authenticated_api` when the
  service needs an SSO token.
- Convert the code path to `async def` end to end. Every network call is awaited and has a timeout.
  Run independent calls with `asyncio.gather`.
- Multi-step operations (for example Git → Vault → ArgoCD): snapshot before changing, compensate in
  reverse order on failure, log failed compensations, and make every step idempotent.
- If a connector is missing something more than one team would need, note it as a library
  contribution instead of building a private client.

### B5. Long-running work

- Work that runs as an **AWX job** returns 202 with the AWX `job_id`, plus a
  `GET .../status/{job_id}` route that calls `awx.get_job_status`. AWX is the job queue.
- Short, best-effort follow-ups may use a referenced in-process task, with status derived from the
  external system.
- Long work that runs inside the API and must survive restarts needs a job queue. **The library has
  none.** Stop and ask the team whether to implement one, use an external solution, or move the work
  into AWX.

### B6. Authentication and Remote Config

Configure them per the sections below.

### B7. Errors, logging, tests, packaging, CI

- Map `ExternalServiceError` to 502. Use Loguru, with no secrets in logs.
- Tests: schemas (valid, invalid, project-only metadata, extra metadata keys), routes through
  `TestClient(create_app())` with an HS256 bearer, auth (401/401/200), operation failure and
  rollback paths, and Remote Config fallback. No real network calls.
- `pyproject.toml` + uv, `.env.example`, `README.md`.
- A Dockerfile following `example-api`'s, with the base image from JFrog Artifactory.
- `.woodpecker/` pipeline per the CI how-to: tests, formatting, linting, SonarQube, then build and
  push to JFrog Artifactory.
- `cliff.toml` (copy `example-api`'s) and a `CHANGELOG.md` generated by git-cliff. PR titles are
  conventional commits.

---

## Authentication (both modes)

- **Inbound:** `general_create_app(enable_auth=True)`. Enforced only when `AUTH_ENABLED=true`, with
  exactly **one** verification mode set:
    - Production: `AUTH_OIDC_ISSUER` or `AUTH_JWKS_URL`, plus **`AUTH_AUDIENCE`**.
    - Offline: `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH`.
    - Tests and local dev: `AUTH_HS256_SECRET`.

  Read claims with `Depends(get_current_claims)`. Probes, `/metrics` and `/docs` stay excluded.
  Add the variables, commented, to `.env.example`.
- **Outbound** (only if the API calls protected services): `sso_authenticated_api(base_url)`, configured
  by `AUTH_SSO_TOKEN_URL`, `AUTH_SSO_CLIENT_ID`, `AUTH_SSO_CLIENT_SECRET` (+ optional `AUTH_SSO_SCOPE`,
  `AUTH_SSO_AUDIENCE`). Catch `AuthConfigError` and return a clean error. Don't cache tokens
  yourself.
- **No authorization logic in the API** (see Ground rules).

## Remote Config provider (only if needed)

Use it **only** if some value varies by environment or coordinate (AWX template ids, endpoints,
quotas…). If nothing does, skip it, and say so in the report.

- Wire it **opt-in**: only when `CONFIG_API_URL` is set, wrapped in
  `try/except AuthConfigError`, and passing `coordinate_paths=[...]` (regex strings for the routes
  whose metadata should get live dropdowns).
- In operations: `resolved = await provider.resolve_infra_config(payload.metadata)`, then
  `resolved.get("<key>", config.<STATIC_DEFAULT>)`. There is always a static fallback.
- Upstream auth comes from `CONFIG_REMOTE_AUTH_METHOD` (`sso` / `bearer` / `none`) and the matching
  `CONFIG_REMOTE_*` variables.

## The `ProjectMetadata` pattern

```python
# app/schemas.py
from pydantic import BaseModel, Field
from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata


class ProjectMetadata(InfraMetadata):
    """Platform metadata: project required, every other coordinate optional."""
    project: str = Field(..., description="The platform application submitting the request")


class MetadataRequest(BaseModel):
    metadata: ProjectMetadata = Field(..., description="Platform metadata (project required).")

# app/v1/<resource>/schemas.py
class CreateThing(MetadataRequest):
    spec: CreateThingSpec
```

## Library quick reference (1.3.1)

Verify each name in the [library source at v1.3.1](https://github.com/Platform-Infra-Org/apis-library/tree/v1.3.1/src/tashtiot_apis_library)
before using it.

| Need | Import |
|---|---|
| App factory | `from tashtiot_apis_library import general_create_app` |
| Connectors | `from tashtiot_apis_library import AWX, ArgoCD, Git, Vault` |
| Connector errors | `from tashtiot_apis_library import ExternalServiceError, AWXError, ArgoCDError, GitError, VaultError` |
| Response models | `from tashtiot_apis_library.connectors import OperationResponse, AWXOperationResponse, ArgoOperationResponse` |
| Request bases | `from tashtiot_apis_library import InfraOperationRequest, RequiredInfraOperationRequest, ResourceSpec, NameNamespace, DefaultMetaSpec` |
| Metadata model | `from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata, RequiredInfraMetadata` |
| Generic async HTTP client, library settings | `from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings` |
| Inbound auth | `from tashtiot_apis_library.fastapi_template.auth import get_current_claims, verify_token` |
| Outbound SSO | `from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api, sso_auth, StaticBearerAuth` |
| Auth errors | `from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError` |
| Remote Config | `from tashtiot_apis_library.fastapi_template import enable_remote_config_api` |
| Dev key pair / tokens | the `gen-auth-material` CLI |

Connector constructors:

- `AWX(base_url, token)`
- `ArgoCD(base_url, api_key, application_set_timeout)`
- `Git(base_url, token, username_or_email, project_key, repo_slug, default_ref="main", ssh_key_file_path=..., ssh_port=7995)`
- `Vault(base_url, token)`
- `BaseAPI(base_url, headers=None, auth=None, timeout=10.0, verify=False)`

## Verification (both modes)

Before you finish, run and report the result of each:

1. `uv sync --group dev` succeeds against the target version (inside the air-gapped network; outside
   it, report this step as not run).
2. The full test suite passes (compare with the baseline you recorded). Tests need the installed
   library, so outside the air-gapped network report them as not run, rather than as passing.
3. Formatting and linting pass, if the repository is configured for them.
4. The app boots with `AUTH_ENABLED=false`, and also with `AUTH_ENABLED=true` +
   `AUTH_HS256_SECRET`. `/docs`, `/liveness` and `/readiness` respond. A protected route returns 401
   without a token and succeeds with one.
5. A search of `app/` finds no `requests.`, `time.sleep(`, `subprocess.run(` or `_internal` imports.
6. `.env.example` lists every variable the app reads, with placeholder values.

## Final report

End with a short report:

- **Mode** (A or B) and why. **Library version:** from → 1.3.1.
- **What changed**, grouped by area: dependencies, connectors/async, auth, Remote Config, contract,
  errors, tests, packaging/CI.
- **Breaking changes for callers**, or "none" in Mode A. In Mode B, the new path and version.
- **New or changed environment variables.**
- **Needs a decision:** contract changes not applied (Mode A), dropped authorization logic, the
  job-queue choice, anything you were unsure about.
- **Verification results** from the list above.
