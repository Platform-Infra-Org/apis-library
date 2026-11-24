# tashtiot-apis-library reference (1.3.2)

The public API of the library, for working **without network access to GitHub or the docs site**.
It was extracted from the library source at the version above. If the installed version differs,
the installed source wins: `.venv/lib/python3.*/site-packages/tashtiot_apis_library/`. Never
import from `..._internal`.

## Contents

- [Imports](#imports)
- [App factory](#app-factory)
- [Connectors](#connectors)
- [Response models](#response-models)
- [Errors](#errors)
- [Request models and metadata](#request-models-and-metadata)
- [Library settings (environment variables)](#library-settings-environment-variables)
- [Inbound auth](#inbound-auth)
- [Outbound SSO](#outbound-sso)
- [Remote Config](#remote-config)
- [`gen-auth-material` CLI](#gen-auth-material-cli)

## Imports

| Need | Import |
|---|---|
| App factory | `from tashtiot_apis_library import general_create_app` |
| Connectors | `from tashtiot_apis_library import AWX, ArgoCD, Git, Vault` |
| Connector errors | `from tashtiot_apis_library import ExternalServiceError, AWXError, ArgoCDError, GitError, VaultError` |
| Response models | `from tashtiot_apis_library.connectors import OperationResponse, AWXOperationResponse, ArgoOperationResponse` |
| Request bases | `from tashtiot_apis_library import InfraOperationRequest, RequiredInfraOperationRequest, ResourceSpec, NameNamespace, DefaultMetaSpec` |
| Metadata models | `from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata, RequiredInfraMetadata` |
| Remote Config | `from tashtiot_apis_library.fastapi_template import enable_remote_config_api` and `from tashtiot_apis_library.fastapi_template.config_api import RemoteConfigProvider` |
| Generic HTTP client, settings | `from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings` |
| Inbound auth | `from tashtiot_apis_library.fastapi_template.auth import get_current_claims, verify_token` |
| Outbound SSO | `from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api, sso_auth, get_sso_token_client, StaticBearerAuth` |
| Auth errors | `from tashtiot_apis_library.fastapi_template.errors import AuthConfigError, TokenError, SSOError` |
| Vault models (tests) | `from tashtiot_apis_library.connectors.vault.models import VaultSecret` |

## App factory

```python
general_create_app(
    *,
    async_background_tasks=None,  # list of zero-arg coroutine functions: started at startup, cancelled at shutdown (on EVERY replica)
    enable_logging_middleware=True,  # logs request + response (probes/docs/metrics at DEBUG)
    enable_time_recording_middleware=True,  # X-Process-Time header (ns)
    enable_root_route=True,  # GET / -> {"message": "Welcome to <APP_NAME>!"}
    enable_exception_handlers=True,  # HTTPException -> {"detail": ...}; 422 without submitted values; other -> 500
    enable_uptime_background_task=True,
    enable_metrics_route=True,  # GET /metrics (Prometheus)
    enable_swagger_routes=True,  # GET /docs, /redoc (self-hosted assets, work offline)
    enable_probe_routes=True,  # GET /liveness, /readiness (static "OK", no upstream checks)
    enable_auth=False,  # always pass True; AUTH_ENABLED decides at runtime
    **fastapi_kwargs,  # title=, version=, description=, ... (NOT lifespan=: the library sets one -> TypeError)
) -> FastAPI
```

The 422 body is `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. It carries no `input`
or `ctx`, so a rejected value is never echoed back or logged.

## Connectors

Every method is `async`, so always `await` it. Build each connector once in `create_app()`.

### `AWX(base_url: str, token: str)`

| Method | Returns | Notes |
|---|---|---|
| `launch_job(job_template_id: int, extra_vars: dict \| None = None, inventory: int \| None = None, limit: str \| None = None, credential: int \| None = None)` | `AWXOperationResponse` | `status="successful"`, `status_code=200`, `job_id`. This means **queued in AWX**, not finished. |
| `launch_workflow_job(workflow_id: int, extra_vars=None, inventory=None, limit=None)` | `AWXOperationResponse` | Same as above, for workflow templates. |
| `get_job_status(job_id: int, *, include_logs: bool = False)` | `AWXOperationResponse` | `status` is the AWX state. `status_code` maps it: `pending`/`waiting`/`running` → 202, `successful` → 200, `failed`/`error`/`canceled` → 500. With `include_logs=True`, `stdout` holds a short log summary. |
| `get_workflow_job_status(workflow_job_id: int, *, include_logs: bool = False)` | `AWXOperationResponse` | As above. The log summary covers child jobs and failed-job output. |
| `wait_for_job_completion(job_id: int, timeout: int = 300, poll_interval: int = 5)` | `AWXOperationResponse` | Polls with `asyncio.sleep`. Raises `TimeoutError`. Don't call it inside a request; return 202 instead. |
| `wait_for_workflow_completion(workflow_job_id: int, timeout: int = 300, poll_interval: int = 5)` | `AWXOperationResponse` | As above. |
| `get_job_output(job_id: int, *, start_line: int = 0, page_size: int = 100)` | `AWXJobOutputResponse` | Incremental playbook output. Adds `next_line`, `has_more`, `finished`. The caller keeps the cursor. `page_size` must be 1–1000. |

### `ArgoCD(base_url: str, api_key: str, application_set_timeout: int)`

`application_set_timeout` is the maximum number of seconds the `wait_for_*` methods poll (1 s
steps). They raise `TimeoutError`.

| Method | Returns |
|---|---|
| `sync(app_name: str)` | `None` |
| `get_app_status(app_name: str)` | `ArgoOperationResponse`: `status` is `successful` / `failed` / `inprogress`, `status_code=200`, `stdout` holds the message |
| `create_app(app_definition: ArgoApplication \| Mapping \| BaseModel, validate=True, upsert=False, wait=False)` | `ArgoApplication`. With `upsert=False`, an existing app with a different spec is rejected. |
| `delete_app(app_name: str, app_namespace: str \| None = None, cascade=True, wait=False)` | `None` |
| `wait_for_app_creation(app_name: str)` / `wait_for_app_deletion(app_name: str)` | `None` |
| `wait_for_update(app_name: str)` | `ArgoApplication` |
| `get_app_values(app_name)` / `get_app_parameters(app_name)` | `str` |
| `modify_values(values: BaseModel \| Mapping, app_name, namespace, project)` | `None` |
| `modify_parameters(parameters: list[dict] \| Mapping, app_name, namespace, project)` | `None` |
| `add_namespace_to_cluster_secret(cluster_secret_name, namespace, project)` | `None` |

### `Git(base_url, token, username_or_email, project_key, repo_slug, default_ref="main", ssh_key_file_path="/etc/.ssh/private_key", ssh_port=7995)`

Bitbucket Server. Paths are repo paths, for example `/dev/team-ns/edge.yaml`.

| Method | Returns | Notes |
|---|---|---|
| `get_file_content(path, ref=None, encoding="utf-8")` | `str` | Raises `GitError` if the file is missing. |
| `file_exists(path, ref=None)` | `bool` | |
| `add_file(path, commit_message, content, *, branch=None)` | `None` | Raises **`GitError(409)` if the path already exists**. Use it as the cross-replica conflict check. |
| `modify_file(path, commit_message, content, *, branch=None)` | `None` | Raises `GitError` if the file is missing. |
| `delete_file(path, commit_message, *, branch=None)` | `None` | Raises `GitError` if the file is missing. |
| `list_dir(path, ref=None)` | `list[tuple[name, path]]` | |
| `list_files_recursive(path="", ref=None)` | `list[str]` | |

### `Vault(base_url: str, token: str)`

KV v2. `"/<mount>/<rest>"` is read and written at `<mount>/data/<rest>`.

| Method | Returns | Notes |
|---|---|---|
| `read_secret(path)` | `VaultSecret` | **The key/values are on `.data`** (with `.metadata` alongside). A missing secret raises `VaultError` with `status_code == 404`. |
| `write_secret(path, data: Mapping \| BaseModel)` | `None` | Pass the plain dict, for example `secret.data`, never the `VaultSecret` itself: a model is written with `model_dump()`, so passing a `VaultSecret` would write `{"data": ..., "metadata": ...}`. |
| `delete_secret(path)` | `None` | Deletes the metadata path, which removes **all versions**. |

### `BaseAPI(base_url, headers=None, auth=None, timeout=10.0, verify=False)`

The generic async HTTP client, a wrapper around `httpx.AsyncClient`.

```python
async with BaseAPI("https://svc.internal", headers={"x-api-token": token}, verify=True) as client:
    r = await client.get("/things")  # an httpx.Response
```

`auth=` takes an `httpx.Auth` (for example `sso_auth()` or `StaticBearerAuth(token)`) or a
`(user, password)` tuple. Set `verify=True` for services with a valid certificate.

## Response models

| Model | Fields |
|---|---|
| `OperationResponse` | `status: str` (required), `status_code: int \| None`, `return_code: int \| None`, `stdout: str = ""` |
| `AWXOperationResponse` | the above + `job_id: int` |
| `AWXJobOutputResponse` | `AWXOperationResponse` + `next_line: int`, `has_more: bool`, `finished: bool` |
| `ArgoOperationResponse` | `OperationResponse` + `app_name: str` |

Subclass them for route responses, for example `class DNSRecordResponse(AWXOperationResponse): pass`.
Build them from a connector result with `DNSRecordResponse(**result.model_dump())`.

## Errors

| Error | Raised by | Carries |
|---|---|---|
| `ExternalServiceError(HTTPException)` | Base class of the four below | `service_name`, `status_code` (**the upstream's**), `detail` |
| `AWXError`, `ArgoCDError`, `GitError`, `VaultError` | The connectors, on any upstream status >= 400 | `service_name` = `"AWX"` / `"ArgoCD"` / `"Git"` / `"Vault"` |
| `AuthConfigError` | App creation (bad auth config); `sso_authenticated_api` / `enable_remote_config_api` with missing settings | message |
| `TokenError` | `verify_token` on an invalid token | `detail` |
| `SSOError` | The token endpoint failing | message |
| `fastapi.HTTPException(502)` | `RemoteConfigProvider` when the upstream is down or returns 5xx (unless `serve_stale_on_error`) | It isn't an `ExternalServiceError`, so let it propagate. |

Routes catch `ExternalServiceError` and return **502** (`{"detail": f"{err.service_name}: {err.detail}"}`).
An *expected* upstream 404 is handled in the operation (`if err.status_code == 404: ...`).

## Request models and metadata

`InfraMetadata` has six fields, all optional strings: `space`, `network`, `region`, `island`,
`environment`, `project`.
- **Allowlists:** each value is checked against live allowlists, and the combination against the
  coordinate tree. Both checks are permissive while those are empty, before the first Remote
  Config poll or when Remote Config is off.
- **Unknown keys** are ignored.
- **`RequiredInfraMetadata`** makes all six required.

The company standard is `project` required and the rest optional:

```python
class ProjectMetadata(InfraMetadata):
    project: str = Field(..., description="The platform application submitting the request")
```

Other building blocks:

| Model | Fields |
|---|---|
| `InfraOperationRequest` | `metadata: InfraMetadata`. Prefer your own `MetadataRequest` with `ProjectMetadata`. |
| `OperationRequest` | Legacy: requires 5 coordinates. Don't use in new code. |
| `NameNamespace` | `namespace: StrictStr`, `name: StrictStr` |
| `DefaultMetaSpec` | `NameNamespace` + `paasLabels: {operational_purpose: str, operational: bool, critical: bool}` |
| `ResourceSpec` | `limits` / `requests`: `{cpu: "100m", memory: "128Mi"}`, regex-validated, `extra="forbid"` |

## Library settings (environment variables)

The library reads these itself, from env vars or `.env`, with env vars taking precedence. **Don't
redeclare them** in your `BaseSettings`. They are read once, at import time.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port, if the app reads `settings.PORT` |
| `LOG_LEVEL` | `INFO` | Loguru level |
| `APP_NAME` | `MyApp` | Shown by `GET /` |
| `DEBUG` | `false` | |
| `PROCESS_TIME_HEADER` | `X-Process-Time` | |
| `PROXIED` / `PROXY_LISTEN_PATH` | `false` / `/` | Set both when served under an ingress path prefix |
| `OPENAPI_JSON_URL` | `/openapi.json` | |
| `PROBE_LIVENESS_PATH` / `PROBE_READINESS_PATH` | `/liveness` / `/readiness` | |
| `LOG_REQUEST_EXCLUDE_PATHS` | health, metrics, static, docs, redoc, openapi.json, .well-known | Logged at DEBUG |
| `AUTH_ENABLED` | `false` | Runtime switch for inbound auth |
| `AUTH_HEADER_NAME` | `Authorization` | |
| `AUTH_HS256_SECRET` | – | HS256 mode (tests and local dev) |
| `AUTH_JWKS_URL` | – | JWKS mode (RS256) |
| `AUTH_OIDC_ISSUER` | – | JWKS mode with discovery; also the default `iss` |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | – | Local public-key mode (RS256) |
| `AUTH_ALGORITHMS` | `["RS256"]` | HS256 mode forces `["HS256"]` |
| `AUTH_REQUIRE_EXP` | `true` | |
| `AUTH_AUDIENCE` | – | Expected `aud`. **Set it in production.** |
| `AUTH_ISSUER` | – | Expected `iss` (optional) |
| `AUTH_JWKS_CACHE_TTL` | `3600` | |
| `AUTH_EXCLUDE_PATHS` | health, metrics, static, docs, redoc, openapi.json, .well-known, liveness, readiness | Prefixes or regexes that skip auth |
| `AUTH_SSO_TOKEN_URL` / `AUTH_SSO_CLIENT_ID` / `AUTH_SSO_CLIENT_SECRET` | – | Outbound `client_credentials` |
| `AUTH_SSO_SCOPE` / `AUTH_SSO_AUDIENCE` | – | Keycloak ignores `AUDIENCE`; use a scope with an Audience mapper |
| `AUTH_SSO_AUTH_STYLE` | `post` | `post` or `basic` |
| `AUTH_SSO_VERIFY_SSL` / `AUTH_SSO_TIMEOUT` / `AUTH_SSO_EXPIRY_SKEW` | `true` / `10.0` / `30` | |
| `CONFIG_REMOTE_AUTH_METHOD` | `sso` | Remote Config upstream auth: `sso` / `bearer` / `none` |
| `CONFIG_REMOTE_BEARER_TOKEN` | – | For `bearer` |
| `CONFIG_REMOTE_SSO_TOKEN_URL` / `_CLIENT_ID` / `_CLIENT_SECRET` / `_SCOPE` / `_AUDIENCE` / `_AUTH_STYLE` / `_VERIFY_SSL` / `_TIMEOUT` / `_EXPIRY_SKEW` | – | For `sso` |

## Inbound auth

- **When it runs:** `general_create_app(enable_auth=True)` registers it, but it's enforced only when
  `AUTH_ENABLED=true`.
- **Exactly one mode** must be set: `AUTH_HS256_SECRET`, `AUTH_JWKS_URL` / `AUTH_OIDC_ISSUER`, or
  `AUTH_PUBLIC_KEY_*`. Zero or more than one raises `AuthConfigError` at app creation.
- **What's checked:** signature, `exp` (unless `AUTH_REQUIRE_EXP=false`), `aud` if `AUTH_AUDIENCE`
  is set, and `iss` if `AUTH_ISSUER` is set. Nothing else, because **authorization happens outside
  the APIs**.
- **On failure:** 401 with `{"detail": ...}` and `WWW-Authenticate: Bearer`.
- **Verified claims:** stored on `request.state.user`.
- **In a route:** `claims: dict = Depends(get_current_claims)` (401 when there is no identity).
- **Outside a request:** `verify_token(token: str, *, settings=None) -> dict`, which raises
  `TokenError`.
- **Swagger:** shows an Authorize button when auth is enforced.

## Outbound SSO

```python
async with sso_authenticated_api(base_url) as client:  # httpx.AsyncClient, bearer added per request
    r = await client.get("/protected")
```

- **Signature:** `sso_authenticated_api(base_url, *, config: SSOConfig | None = None, settings=None, **base_api_kwargs)`.
  `base_api_kwargs` are passed to `BaseAPI` (`timeout`, `verify`, `headers`).
- **Configuration:** it reads `AUTH_SSO_*`. If those are missing, it raises `AuthConfigError`, so
  catch it.
- **Tokens** are cached and refreshed `AUTH_SSO_EXPIRY_SKEW` seconds before expiry, with one retry
  on a 401.
- **Other helpers:**
    - `sso_auth(source=None) -> httpx.Auth`, for `BaseAPI(auth=...)`
    - `get_sso_token_client(source=None)`, for the raw token
    - `StaticBearerAuth(token)`, for a fixed bearer

## Remote Config

```python
provider = enable_remote_config_api(
    app,
    *,
    base_url: str,
    remote_prefix: str,  # e.g. "/api/v1"
    coordinate_paths: Sequence[str],  # regexes (re.fullmatch) of routes whose metadata gets live enum dropdowns
    cache_ttl: int = 60,
    serve_stale_on_error: bool = False,  # True: upstream down -> last good value instead of 502
    poll_interval: int = 5,
    settings=None,  # ConfigRemoteSettings; default reads CONFIG_REMOTE_*
    auth=None,  # explicit httpx.Auth override
    enable_polling: bool = True,  # allowlists are seeded once at startup either way
) -> RemoteConfigProvider
```

- **When to wire it:** only when `CONFIG_API_URL` is set, wrapped in `try/except AuthConfigError`.
  The default `sso` method raises if its credentials are missing.
- **Provider methods** (all async):
    - `resolve_infra_config(meta) -> dict`: the config cascade. Returns `{}` when there is no
      config.
    - `resolve_naming_convention(meta) -> dict`
    - `get_all_projects() -> list[str]`
    - `get_coordinate_catalog() -> dict[str, list[str]]`
    - `get_coordinate_tree() -> dict`
- **Always fall back** to a static default: `resolved.get("<key>", config.<DEFAULT>)`.

## `gen-auth-material` CLI

Mints an RSA key pair and a JWT for local public-key mode. It is installed with the library.

```bash
gen-auth-material --sub local-dev --aud my-api --expires-minutes 30   # writes jwt_private.pem + jwt_public.pem
gen-auth-material --no-write --sub local-dev                           # print only
gen-auth-material --private-key jwt_private.pem --sub other-user       # reuse a key, mint a new token
```

Then set `AUTH_ENABLED=true` and `AUTH_PUBLIC_KEY_PATH=jwt_public.pem`, and send
`Authorization: Bearer <token>`. If you omit `--expires-minutes`, the token never expires, and the
API must also set `AUTH_REQUIRE_EXP=false`.
