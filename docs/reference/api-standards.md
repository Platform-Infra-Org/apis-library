# API standards

The company rules for every HTTP API built on **`tashtiot-apis-library`**. New APIs must follow
them, and existing APIs should move towards them. This page lists the rules. The reasoning is in the
[Explanation](../explanation/index.md) pages, and the step-by-step recipes are in the
[How-to guides](../how-to/index.md).

!!! info "Reference implementation"
    The **[`example-api`](https://github.com/Platform-Infra-Org/example-api)** repository is a complete, runnable API built on this library. Copy its
    **structure** and **library usage**. Where it disagrees with this page, this page wins (see
    [Known gaps in `example-api`](#known-gaps-in-example-api)).

New to the library? Start with the [Your first app](../tutorials/first-app.md) and
[Secure your API](../tutorials/secure-your-api.md) tutorials.

!!! tip "Working with an AI coding agent"
    - **Day-to-day API work:** the library repository ships an agent skill with these rules,
      [`skills/building-tashtiot-apis/`](https://github.com/Platform-Infra-Org/apis-library/tree/master/skills/building-tashtiot-apis). Copy that folder into your API repository's
      `.claude/skills/` (or into `~/.claude/skills/` for every repo).
    - **Upgrading to a new library version, or rewriting an API onto the library:** use the
      [migration prompt](../how-to/migrate-an-api.md).

---

## Stack

| Concern | Standard |
|---|---|
| Language | Python **3.12** (the library itself supports >= 3.10) |
| Web framework | **FastAPI** + **uvicorn** (ASGI) |
| Shared SDK | **`tashtiot-apis-library`** ([Architecture](../explanation/architecture.md)) |
| Models / validation | **Pydantic v2**, **pydantic-settings** for config |
| HTTP client | **httpx** (async), always via the library's `BaseAPI` |
| Logging | **Loguru**, configured by the library ([Logging](../explanation/logging.md)) |
| Package manager | **uv** (`uv.lock` committed, `uv.toml` never committed) |
| Tests | **pytest** + `pytest-asyncio` (`asyncio_mode = "auto"`) + `respx` |
| CI | Woodpecker (`.woodpecker/*.yaml`). See [CI](#ci) |
| Image registry | **JFrog Artifactory** (base images are pulled from it, built images are pushed to it) |

---

## Project layout

```
<your-api>/
├── app/
│   ├── main.py            # create_app(): the ONLY wiring point (connectors + routers)
│   ├── global_conf.py     # app-wide BaseSettings -> `global_config`
│   ├── schemas.py         # shared models (e.g. ProjectMetadata)
│   ├── helpers.py         # shared pure helpers (naming conventions, payload parsing)
│   └── v1/
│       └── <resource>/
│           ├── conf.py        # module BaseSettings -> `config` (API_PREFIX, API_TAGS, ids…)
│           ├── schemas.py     # Pydantic request/response models ({metadata, spec})
│           ├── operations.py  # business logic; receives connectors as arguments
│           └── routes.py      # get_<resource>_router(deps) -> APIRouter
├── tests/
│   ├── conftest.py        # hermetic env (shadows a developer .env)
│   └── v1/<resource>/     # conftest.py + test_*.py per module
├── .env.example           # every variable, documented. Committed.
├── .env                   # local values. NEVER committed.
├── pyproject.toml
├── uv.lock                # committed
├── uv.toml                # Artifactory index + creds. NEVER committed.
├── Dockerfile
├── .woodpecker/build.yaml
└── README.md
```

| Layer | May | May not |
|---|---|---|
| `routes.py` | Declare paths, models and status codes; translate exceptions into HTTP responses | Contain business logic; construct connectors |
| `operations.py` | Orchestrate connectors; apply business rules; roll back | Import `Request`/`Response`; read env vars directly |
| `schemas.py` | Define shape and validation | Perform I/O |
| `conf.py` | Declare settings with defaults and descriptions | Hold real secrets as defaults |

---

## Application factory

`general_create_app()` ([API reference](api/fastapi-app.md)) provides these built-ins:

| Built-in | Path / behaviour | Flag (default) |
|---|---|---|
| Request logging middleware | Logs every request and response (health/docs/metrics at DEBUG) | `enable_logging_middleware=True` |
| Timing middleware | Adds the `X-Process-Time` header (ns) | `enable_time_recording_middleware=True` |
| Exception handlers | `HTTPException` → `{"detail": ...}`; validation → 422; anything else → 500 `"Internal Server Error"` | `enable_exception_handlers=True` |
| Prometheus metrics | `GET /metrics` (+ `app_uptime_seconds` gauge) | `enable_metrics_route=True` |
| Swagger / ReDoc | `GET /docs`, `GET /redoc` (self-hosted assets) | `enable_swagger_routes=True` |
| Probes | `GET /liveness`, `GET /readiness` | `enable_probe_routes=True` |
| Root route | `GET /` → welcome message | `enable_root_route=True` |
| Inbound JWT auth | Global middleware ([Authentication](#authentication)) | `enable_auth=False` |
| Background tasks | Coroutines launched at startup and cancelled on shutdown | `async_background_tasks=[...]` |

Any other keyword (`title`, `version`, `description`…) is passed through to `FastAPI()`.

**Rules:**

- `create_app()` in `app/main.py` is the **single wiring point**. It builds every connector
  **once**, builds Remote Config if needed, and mounts every router.
- **Always pass `enable_auth=True`.** The runtime switch `AUTH_ENABLED` decides whether auth is
  enforced.
- Set `title` and `version` (`APP_VERSION`, injected from the git tag at build time).
- Something every API needs (a middleware, a route, a utility) goes into the library, not into one
  API ([Extend the FastAPI template](../how-to/extend-the-template.md)).

---

## Configuration

- All configuration is **pydantic-settings `BaseSettings`**, read from environment variables with
  `.env` as a fallback. Environment variables take precedence.
- **`app/global_conf.py`** holds settings shared across modules (connector URLs and tokens,
  `TEAM_NAME`, `CONFIG_API_*`, `API_TITLE`, `APP_VERSION`) in the singleton `global_config`.
- **`app/v1/<resource>/conf.py`** holds one module's settings, including **`API_PREFIX`** and
  **`API_TAGS`**, in the singleton `config`.
- Every field has a `description=`. Use `SettingsConfigDict(env_file=".env", extra="ignore")`.
- Required settings have no default, so a missing value fails the app at startup.
- **Don't redeclare settings the library owns** (`PORT`, `LOG_LEVEL`, `PROXIED`,
  `PROXY_LISTEN_PATH`, `AUTH_*`, `AUTH_SSO_*`, `CONFIG_REMOTE_*`, probe and Swagger paths). The full
  list is in [Configuration](configuration.md).
- When served under an ingress path prefix, set `PROXIED=true` and `PROXY_LISTEN_PATH=/<prefix>`.

**Secrets:**

- Secrets come from the deployment's secret store (Vault or Kubernetes Secrets, injected as env vars
  or mounted files). **Never** put them in git, a `conf.py` default, `.env.example`, logs or the
  image.
- `.env.example` lists **every** variable with a placeholder value and a comment.
- `.env`, `uv.toml` and private keys are git-ignored.

---

## Request contract

### Shape

Every write route's request body has exactly two top-level objects:

```json
{
  "metadata": {
    "project": "payments",
    "space": "net",
    "network": "core",
    "region": "kirya",
    "island": "a1",
    "environment": "prod"
  },
  "spec": {
    "record_name": "api-01",
    "ip": "10.0.0.15",
    "record_type": "A",
    "dns_zone": "net.com"
  }
}
```

| Object | Contents |
|---|---|
| **`metadata`** | **Who** is asking and **where** the operation targets: `project`, `space`, `network`, `region`, `island` and `environment`. |
| **`spec`** | **What** to do: the resource-specific desired state. It is owned and defined by your API. |

### Metadata rules

1. **`project` is always populated** by callers and is **required**.
2. **`space`, `network`, `region`, `island` and `environment` are optional.** Use the ones your
   operation needs. Some APIs need none.
3. **Every API accepts the `metadata` object**, even if it uses none of it. Unused fields are
   ignored, never rejected.
4. An API that **needs** an optional coordinate enforces it in its own schema or operation and
   returns a 422. It is not made required platform-wide.
5. Unknown extra keys inside `metadata` are dropped (Pydantic's default `extra="ignore"`). Don't set
   `extra="forbid"` on metadata models.

### Base models

From the top-level `tashtiot_apis_library` package ([Schemas](api/schemas.md)):

| Base | `metadata` type | Validation |
|---|---|---|
| `InfraOperationRequest` | `InfraMetadata`: **all** coordinates optional | Live allowlists and coordinate hierarchy from the Config API ([Dynamic config validation](../explanation/dynamic-config-validation.md)). **Start from this one.** |
| `RequiredInfraOperationRequest` | `RequiredInfraMetadata`: **all** coordinates required | Same validation. Use only if your API needs every coordinate. |
| `OperationRequest` | `MetadataRequest`: static, no live validation | Legacy. Not for new code. |

None of these marks **only** `project` as required. Every API defines this once, in
`app/schemas.py`, and reuses it:

```python
from pydantic import BaseModel, Field
from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata


class ProjectMetadata(InfraMetadata):
    """Platform metadata: project required, every other coordinate optional."""
    project: str = Field(..., description="The platform application submitting the request")


class MetadataRequest(BaseModel):
    metadata: ProjectMetadata = Field(..., description="Platform metadata (project required).")


# app/v1/dns/schemas.py
class DNSRecordCreate(MetadataRequest):
    spec: DNSRecordCreateSpec
```

### Field conventions

- **Validate at the boundary.** Use typed fields (`IPv4Address`, `Enum`, `constr`, `max_length`)
  and `field_validator`s. Bad input fails with **422** before any connector is called.
- Reuse library building blocks inside `spec` where they fit: `ResourceSpec`, `NameNamespace`,
  `DefaultMetaSpec`.
- For a `spec` field whose allowed values depend on the request's coordinates, see
  [Constrain a field by resolved config](../how-to/constrain-field-by-config.md).
- Every field has a `description=`.
- **Read and delete routes** identify a resource with path or query parameters. Prefer query
  parameters over a DELETE body, because some proxies drop DELETE bodies.

---

## Responses and status codes

- Every route declares `response_model=` (or a return type annotation). Raw dicts from external
  services are never passed through.
- Operation results extend **`OperationResponse`** (`status`, `status_code`, `return_code`,
  `stdout`), or one of its connector subclasses: `AWXOperationResponse` (+ `job_id`) or
  `ArgoOperationResponse` (+ `app_name`). See
  [Architecture](../explanation/architecture.md#standardized-responses-and-errors).

| Situation | Code |
|---|---|
| Synchronous read succeeded | `200` |
| Synchronous create finished | `201` |
| **Work accepted, finishing asynchronously** (AWX job launched, ArgoCD sync started, job queued) | **`202`** + an id to poll ([Long-running work](#long-running-work)) |
| Delete finished, no body | `204` |
| Validation failed | `422` (automatic) |
| Missing, invalid or wrong-audience token | `401` (automatic, from the middleware) |
| Resource not found | `404` |
| Conflict (already exists, concurrent change) | `409` |
| An upstream (AWX, ArgoCD, Vault, Git, …) failed | **`502`** |
| An upstream timed out | `504` |
| Bug | `500` (automatic; never raised deliberately) |

---

## Errors

- Connectors raise subclasses of **`ExternalServiceError`**: `AWXError`, `ArgoCDError`,
  `GitError` and `VaultError`. Each carries `service_name`, `status_code` and `detail`
  ([Errors](api/errors.md)).
- `ExternalServiceError` is a FastAPI `HTTPException`. Uncaught, it returns the **upstream's**
  status code to the client. Routes catch it and return **502**:
    ```python
    app_name = build_app_name(cluster, namespace, name, "haproxy")
    try:
        await create_haproxy_operation(git=git, vault=vault, argocd=argocd, payload=payload.spec)
    except ExternalServiceError as err:
        return JSONResponse(
            ArgoOperationResponse(app_name=app_name, status="Failed", status_code=err.status_code,
                                  stdout=f"{err.service_name}: {err.detail}").model_dump(),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    ```
- An expected upstream `404` (for example "secret doesn't exist yet") is handled in the operation by
  checking `exc.status_code == 404`. It is not treated as a failure.
- Auth error types (`AuthConfigError`, `TokenError`, `SSOError`) are imported from
  `tashtiot_apis_library.fastapi_template.errors` or the top-level package, never from `_internal`.
- Error `detail` never contains stack traces, tokens, or upstream bodies that may hold secrets.
- Error bodies use the shape `{"detail": "..."}`.
- 422 responses and validation log lines contain only each error's `loc`, `msg` and `type`. The
  library strips the submitted value (`input`) and `ctx`, so a rejected password is never echoed or
  logged. Custom validator messages must not include the value either: write
  `"not a valid IPv4 address"`, not `f"'{v}' is not a valid IPv4 address"`.

---

## Paths and versioning

- Path scheme: **`/api/<api-name>/v<N>/<resource>`**, for example `/api/example/v1/dns`, set as
  `API_PREFIX` in the module's `conf.py`.
- Resource names are plural nouns, and HTTP verbs carry the action. Job status:
  `GET .../status/{job_id}` or `GET .../status?...`.
- **A breaking change means a new version.** It goes in `app/v2/<resource>/` alongside `v1`.
  Removing or renaming a field, changing a type, or making an optional field required is breaking.
  Adding an optional field is not.
- Endpoints are grouped in Swagger with `API_TAGS`, for example `["v1 - DNS Operations"]`.
- Every route has a `summary`, a `description`, a `response_model` and an explicit status code.

### Router factories

Each module exposes `get_<resource>_router(<connectors...>) -> APIRouter`. Connectors are captured in
the closure and passed explicitly to operations. They are not injected with FastAPI `Depends`, and
they are never constructed per request.

```python
def get_v1_dns_router(awx_client: AWX, provider=None) -> APIRouter:
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", response_model=DNSRecordResponse, status_code=202,
                 summary="Create DNS Record", description="Launches the AWX create-DNS job.")
    async def create(record: DNSRecordCreate) -> DNSRecordResponse:
        return await create_dns(record, awx_client, provider)

    return router
```

---

## Async rules

Why these rules exist: [Async and the event loop](../explanation/async.md).

1. Route handlers that do I/O are `async def` and `await` async libraries.
2. Nothing blocks the event loop inside `async def` code:

    | Forbidden | Use instead |
    |---|---|
    | `requests.get(...)` | `BaseAPI` / `httpx.AsyncClient` |
    | `time.sleep(n)` | `await asyncio.sleep(n)` |
    | `subprocess.run(...)` | `await asyncio.create_subprocess_exec(...)` |
    | A sync DB or SDK client | Its async driver, or `await asyncio.to_thread(fn, ...)` |
    | Heavy CPU work | `await asyncio.to_thread(...)`, or move it off the request path ([Long-running work](#long-running-work)) |

3. Plain `def` handlers are only for trivial CPU-only work (such as `/whoami`), never as a way to
   call sync I/O.
4. Independent calls run concurrently with `asyncio.gather`.
5. No `asyncio.run()` or `loop.run_until_complete()` inside the app.
6. Every network `await` has a timeout. `BaseAPI` defaults to 10 s, and the connector `wait_for_*`
   helpers take explicit timeouts.
7. Every task created with `asyncio.create_task` is kept referenced until it finishes
   ([why](../explanation/job-queues.md#in-process-background-tasks-are-not-a-queue)).

---

## Connectors

From the top-level `tashtiot_apis_library` package ([Connectors](api/connectors.md)):

| Connector | Construct | Main async methods |
|---|---|---|
| **`AWX`** | `AWX(base_url, token)` | `launch_job`, `launch_workflow_job`, `get_job_status(job_id, include_logs=False)`, `get_workflow_job_status`, `wait_for_job_completion(job_id, timeout=300, poll_interval=5)`, `wait_for_workflow_completion`, `get_job_output(job_id, start_line, page_size)` |
| **`ArgoCD`** | `ArgoCD(base_url, api_key, application_set_timeout)` | `sync`, `create_app`, `delete_app`, `get_app_status`, `wait_for_app_creation`, `wait_for_app_deletion`, `wait_for_update`, `get_app_values`/`modify_values`, `get_app_parameters`/`modify_parameters`, `add_namespace_to_cluster_secret` |
| **`Git`** (Bitbucket Server) | `Git(base_url, token, username_or_email, project_key, repo_slug, default_ref="main", ssh_key_file_path=..., ssh_port=7995)` | `add_file`, `modify_file`, `delete_file`, `get_file_content`, `file_exists`, `list_dir`, `list_files_recursive` |
| **`Vault`** | `Vault(base_url, token)` | `read_secret`, `write_secret`, `delete_secret` |
| **`BaseAPI`** (generic) | `BaseAPI(base_url, headers=None, auth=None, timeout=10.0, verify=False)` | Any `httpx.AsyncClient` call |

Recipes: [Drive AWX, ArgoCD & Vault](../how-to/use-awx-argocd-vault.md),
[Read & write Bitbucket files](../how-to/read-write-bitbucket.md).

**Rules:**

1. Connectors are constructed once in `create_app()` and injected.
2. A connector is used instead of raw HTTP whenever one exists. Other services are called through
   `BaseAPI`, or through `sso_authenticated_api` when they need an SSO token.
3. `BaseAPI` defaults to `verify=False`. Services with a valid certificate get `verify=True`, or
   `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` pointing at the corporate CA bundle. Turning verification off
   is a deliberate, commented decision.
4. Connector results are used as returned (Pydantic models / `OperationResponse`s). Raw JSON isn't
   parsed by hand.
5. An AWX launch result (`status="successful"`, `status_code=200`, `job_id`) means the job was
   **queued**, not finished ([AWX is already a job queue](../explanation/job-queues.md#awx-is-already-a-job-queue)).
6. A new integration that more than one team will use is added to the library as a connector
   ([Add a new connector](../how-to/add-a-connector.md), [Contributing](../contributing/index.md)),
   not copied between APIs.

---

## Authentication

Design background: [Authentication design](../explanation/authentication.md).

### Inbound

- Wired by `general_create_app(enable_auth=True)` and enforced only when `AUTH_ENABLED=true`. With it
  off, the app boots **open** (development only).
- Exactly **one** verification mode is configured. Otherwise app creation fails with
  `AuthConfigError`.

    | Mode | Setting | Use for |
    |---|---|---|
    | **JWKS / OIDC (RS256)** | `AUTH_OIDC_ISSUER` (discovery) or `AUTH_JWKS_URL` | **Production** ([Secure an API with OIDC & JWKS](../how-to/secure-with-oidc-jwks.md)) |
    | Local public key (RS256) | `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | Offline or air-gapped verification |
    | Shared secret (HS256) | `AUTH_HS256_SECRET` | Tests and local development only |

- **What is checked:** the token's signature, its expiry (`AUTH_REQUIRE_EXP=true` by default) and its
  audience. **Production sets `AUTH_AUDIENCE`** to the API's audience. `AUTH_ISSUER` is an optional
  extra check.
- The token is read from `Authorization: Bearer <jwt>` (`AUTH_HEADER_NAME`). A failure returns 401
  with `WWW-Authenticate: Bearer`.
- Paths excluded by default: `/health`, `/metrics`, `/static`, `/docs`, `/redoc`,
  `/openapi.json`, `/.well-known`, `/liveness` and `/readiness`. More can be added with
  `AUTH_EXCLUDE_PATHS`. The probes stay excluded.
- Verified claims are read with `Depends(get_current_claims)` from
  `tashtiot_apis_library.fastapi_template.auth`, for logging and auditing.
- Tokens are verified outside a request with `verify_token`
  ([Verify a token outside a request](../how-to/verify-a-token.md)).
- Swagger's **Authorize** button appears automatically when auth is enforced
  ([OpenAPI & Swagger injection](../explanation/openapi-swagger-injection.md)).

!!! important "Authorization is handled outside the APIs"
    For now, inbound auth is **authentication only**: the API checks that the JWT is valid and was
    issued for its audience. **Authorization** (which caller may do what, on which project) is
    enforced **outside the APIs**. APIs do **not** add permission checks on token claims such as
    `project`, roles or scopes.

### Outbound (service to service)

- Protected downstream services are called with `sso_authenticated_api(base_url)` from
  `tashtiot_apis_library.fastapi_template.security`, which uses the OAuth2 `client_credentials`
  grant.
- It is configured by `AUTH_SSO_TOKEN_URL`, `AUTH_SSO_CLIENT_ID` and `AUTH_SSO_CLIENT_SECRET` (plus
  the optional `SCOPE`, `AUDIENCE` and `AUTH_STYLE`).
- Tokens are cached and refreshed by the library. APIs don't cache tokens themselves.
- On Keycloak, the downstream `aud` comes from a scope with an Audience mapper (`AUTH_SSO_SCOPE`).
- Missing configuration raises `AuthConfigError`, which the operation catches and turns into a clean
  error result.
- Recipes: [Call other services with SSO](../how-to/call-services-with-sso.md).

### Remote Config upstream

- `CONFIG_REMOTE_AUTH_METHOD`: `sso` (default, `CONFIG_REMOTE_SSO_*`), `bearer`
  (`CONFIG_REMOTE_BEARER_TOKEN`) or `none` (local dev). See
  [Enable the Remote Config API](../how-to/enable-remote-config-api.md#choose-the-outbound-auth).

### Dev tokens

- Generated with `gen-auth-material` ([Generate dev auth material](../how-to/generate-auth-material.md),
  [CLI](cli.md)).

---

## Remote Config

- Values that **vary by environment or coordinate** (template ids, endpoints, quotas) are resolved
  through `enable_remote_config_api` and `provider.resolve_infra_config(payload.metadata)`, not
  hard-coded per environment ([Enable the Remote Config API](../how-to/enable-remote-config-api.md)).
- Wiring is **opt-in**: it is enabled only when `CONFIG_API_URL` is set, and an `AuthConfigError`
  is caught and logged.
- Every resolved value has a static `conf.py` default used when the provider is disabled or the key
  is missing:
    ```python
    resolved = await provider.resolve_infra_config(payload.metadata)
    template_id = resolved.get("awx_create_dns_template_id", config.AWX_CREATE_DNS_TEMPLATE_ID)
    ```

---

## Long-running work

Concepts and the decision table: [Job queues and long-running work](../explanation/job-queues.md).

- Work that doesn't finish well within a request (about 5 s) is **not awaited in the request**.
- The API contract for such work:

    ```
    POST   /api/<api>/v1/<resource>                -> 202 {id, status, ...}
    GET    /api/<api>/v1/<resource>/status/{id}    -> 200 {id, status, stdout, ...}
    ```

    Statuses use the `OperationResponse` vocabulary: `pending`/`running` while in progress, and
    `successful`, `failed` or `canceled` when terminal.
- The status route returns **HTTP 200** whenever it read the job, including a failed one. The
    job's state goes in the body (`status`, and for AWX the mapped `status_code`). It is never copied
    into the HTTP status. An unknown id returns 404, and an upstream failure returns 502.
- **AWX jobs are the job queue.** An API that launches AWX jobs returns the AWX `job_id` and reads
  status with `awx.get_job_status`.
- **The library has no job queue implementation.** A team that needs a durable queue for work
  running inside its API implements one or uses an external solution.
- In-process background tasks are only for short, best-effort work. Their status comes from the
  external systems, never from memory, and each task is kept referenced.
- Periodic work uses `general_create_app(async_background_tasks=[...])` and is idempotent (one copy
  runs per replica).

---

## Multiple replicas

Every API runs as several identical replicas behind a load balancer, and rolling updates run two
versions side by side. Why each rule exists: [Cloud-native APIs and multiple replicas](../explanation/cloud-native.md).

- **Stateless:** no source of truth in process memory or on the local filesystem. Any replica must
  be able to answer any request, so status comes from the owning system (AWX, ArgoCD, Git, Vault) or
  a shared store.
- Per-pod caches are allowed only as caches, where a miss refetches.
- **Idempotent and race-tolerant:** operations are safe to repeat and safe to run concurrently on two
  replicas. Cross-replica conflicts are left to the upstream (for example Git `add_file` on an
  existing path) and returned as `409`. `asyncio.Lock` is not used as a cross-request guard.
- **Background tasks run on every replica.** Only idempotent loops go in `async_background_tasks`.
  Work that must run once goes to a Kubernetes CronJob, an AWX schedule or a single-consumer queue.
- **Disposable:** the app starts fast and fails fast on bad config. Requests are short enough to
  finish within the shutdown grace period (30 s by default).
- **Probes:** liveness and readiness don't depend on upstream systems.
- **Backward compatible across one release**, because old and new pods serve together during a
  rollout. Breaking changes go to a new API version.
- **One uvicorn process per pod.** Scale with replicas.
- Logs go to stdout with correlation ids. Dashboards aggregate metrics across pods.

---

## Multi-step operations

Operations that touch several systems (Git → Vault → ArgoCD) have no distributed transaction. They
follow these rules:

1. Steps are ordered so the cheapest-to-undo step runs first, and nothing user-visible goes live
   until the last step.
2. State is snapshotted (the current Git file, the current Vault secret) before it is changed.
3. On failure, completed steps are compensated in reverse order. Each compensation has its own
   `try/except`, and a failed compensation is logged with `logger.exception`. The original error is
   then re-raised.
4. Rollback is symmetric wherever the work continues (inline and in background tasks or jobs).
5. Operations are idempotent:
    - **Create:** an existing resource with the same spec returns success or `409` (documented).
    - **Update:** no-op writes are skipped (`example-api` compares YAML with `yaml_data_equals`).
    - **Delete:** "already gone" (`404`) counts as success.
6. Empty secret values are stripped before writing to Vault (`filter_secret_payload` in
   `example-api`).
7. Resource names are deterministic, derived from the request (for example
   `{cluster}-{namespace}-{resource}-{name}`).

---

## Logging and observability

Logger setup and level convention: [Logging](../explanation/logging.md).

- Logging uses `from loguru import logger`. Requests and responses are already logged by the
  library.
- Use lazy placeholders: `logger.info("Syncing app {} in {}", app_name, cluster)`.

| Level | Used for |
|---|---|
| `debug` | Payload details (no secrets) |
| `info` | Business events ("launched AWX job 123 for record X") |
| `warning` | Degraded but working |
| `error` / `exception` | Failures, including stack traces |

- Log lines include correlation identifiers: `job_id`, `app_name`, `metadata.project` and the
  caller's `sub`.
- **Never logged:** tokens, secrets, `Authorization` headers, Vault payloads, or request bodies that
  contain `secrets`.
- No `print()` in application code.
- `/metrics` is exposed for Prometheus. Business metrics are added with `prometheus_client`.
- `/liveness` and `/readiness` stay unauthenticated.
- The OpenAPI schema (`/docs`) is the public contract, so summaries, descriptions and examples are
  kept accurate.

---

## Testing

Configuration: `asyncio_mode = "auto"`, `pythonpath = ["."]`, `testpaths = ["tests"]`. Run with
`uv run pytest`.

| Required test | Example in `example-api` |
|---|---|
| Schema validation: valid and invalid payloads (→ 422), including a request with **only** `metadata.project` and one with extra metadata keys | `tests/v1/dns/test_dns_schema.py` |
| Routes through `TestClient(create_app())` with a valid bearer | `tests/v1/dns/test_dns_routes.py` |
| Auth: no token → 401, bad token → 401, good token → 200 | `tests/v1/auth_demo/test_auth_demo_routes.py` |
| Operations: every failure path, and a check that rollback is invoked | — |
| Remote Config fallback (provider disabled or key missing → static default) | `tests/v1/dns_config/` |

- **Hermetic environment:** the root `tests/conftest.py` blanks optional `AUTH_*`/`CONFIG_*`
  variables. Module conftests set the required variables **before** importing `app.main`.
- **Auth in tests:** HS256 (`AUTH_ENABLED=true`, `AUTH_HS256_SECRET=<32+ bytes>`), with tokens
  minted by `jwt.encode(...)` or [`gen-auth-material`](../how-to/generate-auth-material.md).
- **No real network calls.** Mock connector methods with `monkeypatch.setattr(...)` (mocked async
  methods are `async def`), or mock HTTP with `respx`.
- Operations take connectors as arguments, so they are unit-tested directly with fakes.

---

## Packaging and Docker

- `uv sync --group dev` installs everything. `uv.lock` is committed. It is regenerated with
  `uv lock` in an environment with full Artifactory access.
- `uv.toml` (Artifactory index + credentials) lives in the repo root or `~/.config/uv/uv.toml` and is
  never committed.
- `tashtiot-apis-library` is pinned with a minimum version (`>=1.1.0`). A `[tool.uv.sources]` path
  override is for local library development only. Check the [Changelog](../changelog.md) when you
  bump the version.
- No new dependency for something the library, the standard library or FastAPI already does. No
  sync HTTP clients (`requests`).
- Dockerfile (follow `example-api`'s):
    - the approved Python 3.12 base image from JFrog Artifactory
    - copy `pyproject.toml`, `uv.lock` and `.python-version`, then run `uv sync --frozen --no-dev`,
      then copy `app/`
    - `ARG APP_VERSION` / `ENV APP_VERSION` set from the git tag
    - `CMD ["uv","run","--no-sync","-m","app.main","--host","0.0.0.0","--port","5000"]`
    - no secrets in the image

---

## CI

CI runs on **Woodpecker** (`.woodpecker/*.yaml` in each repo) **inside the air-gapped network**,
because it needs the internal JFrog Artifactory and SonarQube.

!!! tip "CI how-to: internal Confluence"
    The CI how-to and full specification are in the **internal Confluence**, which is reachable only
    from the air-gapped network. It defines the pipeline steps, required secrets, images and
    quality-gate thresholds. Follow it when setting up or changing a pipeline.

### Pipeline

Every API's pipeline does the following:

| Step | What it checks or produces |
|---|---|
| **Tests** | The pytest suite passes ([Testing](#testing)) |
| **Formatting** | The code matches the formatter (the library itself uses `ruff format --check`) |
| **Linting** | The linter passes (the library itself uses `ruff check`) |
| **SonarQube** | The SonarQube scan passes the project's quality gate |
| **Build & push** | The Docker image is built (kaniko) and pushed to **JFrog Artifactory**, tagged with the release version, which is also passed as `APP_VERSION` |

### Versioning and changelog (git-cliff)

Releases are versioned with **semver** (`vMAJOR.MINOR.PATCH` git tags), and both the version and
`CHANGELOG.md` are generated by **git-cliff** from `cliff.toml` (see `example-api`'s, or this
library's own [Changelog](../changelog.md) for the result).

- **The PR message is the changelog text, not the individual commits.** Each merged PR lands on
  `master` as one commit carrying the PR's title and description, and that is what git-cliff reads.
  Commit messages inside a branch are not used.
- **PR titles must be conventional commits**, because the prefix decides both the changelog section
  and the version bump:

    | PR title prefix | Changelog section | Version bump |
    |---|---|---|
    | `feat: ...` | Added | **minor** |
    | `fix: ...` | Fixed | patch |
    | `refactor: ...`, `perf: ...` | Changed | patch |
    | `docs: ...` | Documentation | patch |
    | `revert: ...` | Reverted | patch |
    | `build: ...`, `ci: ...` | Build, CI | patch |
    | `chore: ...`, `style: ...`, `test: ...` | *(not listed)* | — |
    | `feat!: ...` / `fix!: ...` or a `BREAKING CHANGE:` footer | (its section) | **major** |

    A PR description that mentions `security` puts the entry under **Security**.

- **A PR title that isn't a conventional commit is dropped** from the changelog and doesn't bump the
  version (`filter_unconventional = true`).
- Write the PR title as the changelog line readers will see, for example
  `feat: add DNS record status endpoint`.
- `CHANGELOG.md` is committed and generated by git-cliff, so it isn't edited by hand.
- A breaking API change (a new `v<N>`, see [Paths and versioning](#paths-and-versioning)) is
  released as a **major** version.

---

## Known gaps in `example-api`

`example-api` is the reference for **structure and library usage**. Don't copy the following:

| In `example-api` | Standard |
|---|---|
| `dns` `PUT`/`GET /{record_name}` are stubs (`print`, hard-coded IP and `job_id=1234`) | Real operations, or no route |
| `chat` request body has no `metadata` | Every write route takes `{metadata, spec}` ([Request contract](#request-contract)) |
| `InfraOperationRequest` used directly (`project` optional) | `ProjectMetadata` with `project` required ([Base models](#base-models)) |
| Operations still running return `200`/`201` | `202` + an id to poll ([Responses and status codes](#responses-and-status-codes)) |
| `asyncio.create_task(...)` without keeping a reference | Tasks are kept referenced ([Async rules](#async-rules)) |
| `requests` listed as a dependency | Async `httpx` via `BaseAPI` only |
| `chat_client = BaseAPI(...).client` used without `async with` (never closed) | `async with BaseAPI(...) as client:`, or close the client in the app lifespan |
| Test and Sonar steps commented out in `.woodpecker/build.yaml` | The [CI](#ci) how-to |
| `Dockerfile` pulls its base image from `harbor.app.com` | Base images come from JFrog Artifactory |
| Secret-looking defaults in `global_conf.py` (`AWX_TOKEN="sheker123"`) | Secrets are required fields with no default |

---

## Pre-merge checklist

**Structure and contract**

- [ ] Module follows `conf.py / schemas.py / operations.py / routes.py`, wired only in `create_app()`.
- [ ] Every write route accepts `{metadata, spec}`. `metadata.project` is required, the other
      coordinates are optional, and unused metadata is accepted and ignored.
- [ ] Path is `/api/<api>/v<N>/<resource>`, and breaking changes went to a new version.
- [ ] Every route has `response_model`, `summary`, `description` and the correct status code.

**Async**

- [ ] No blocking calls in `async def` (`requests`, `time.sleep`, sync clients, heavy CPU work).
- [ ] Every network `await` has a timeout. Independent calls use `asyncio.gather`.
- [ ] Long work returns `202` + an id ([Long-running work](#long-running-work)). Every created task
      is referenced.

**Connectors and errors**

- [ ] Connectors are built once and injected. No raw HTTP where a connector exists.
- [ ] `ExternalServiceError` is mapped to `502`. No secrets or stack traces in `detail`.
- [ ] Multi-step flows snapshot state, compensate in reverse order, log rollback failures, and are
      idempotent.
- [ ] Replica-safe: no state in memory or on local disk, safe under concurrent duplicate requests,
      no once-only work in `async_background_tasks`, backward compatible with the previous release.

**Security**

- [ ] `general_create_app(enable_auth=True)`. Production configuration uses JWKS/OIDC and sets
      `AUTH_AUDIENCE`.
- [ ] No permission checks on token claims in the API (authorization is handled outside the APIs).
- [ ] No secrets in git, `.env.example`, `conf.py` defaults, logs or the image. TLS verification
      is on, or turned off with a documented reason.

**Quality**

- [ ] `.env.example` and `README.md` are updated for every new variable and route.
- [ ] Tests cover schema (valid, invalid, project-only metadata), routes with auth, failure and
      rollback paths. No real network calls.
- [ ] CI is green (tests, formatting, linting, SonarQube) according to the CI how-to in the internal Confluence ([CI](#ci)).
- [ ] The PR title is a conventional commit that reads well as a changelog line
      ([Versioning and changelog](#versioning-and-changelog-git-cliff)).
