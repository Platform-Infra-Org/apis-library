# Tashtiot APIs Library

A unified Python package that consolidates infrastructure connectors and FastAPI utilities for building production-ready APIs.

## 🎯 What's Inside

This package combines two powerful toolsets:

1. **Infrastructure Connectors** - Async clients for AWX, ArgoCD, Bitbucket Server, and HashiCorp Vault
2. **FastAPI Template** - A reusable FastAPI application factory with built-in middleware, monitoring, and documentation

## 🚀 Quick Start

### Installation

```bash
pip install tashtiot-apis-library
```

### Using Infrastructure Connectors

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault

awx = AWX(
	base_url="https://awx.example.com",
    token="token",
)

# ArgoCD client
argo = ArgoCD(
    base_url="https://argo.example.com",
    api_key="token",
    application_set_timeout=30, # The time client waits for argo application to be synced/deleted
)

# Git client (Bitbucket Server)
git = Git(
    base_url="https://bitbucket.example.com", # The base Bitbucket URL
    token="token", # HTTP token with write permissions to bitbucket repo
    username_or_email="user@example.com", # Username or email that would connect to the bitbucket (svc account)
    project_key="PROJ", # The project key in bitbucket world
    repo_slug="repo-name", # The repo name in lower cases
    default_ref="default_ref", # The default branch the git would commuincate with
    ssh_key_file_path="/path/to/ssh/private/key", # Path to SSH private key with write permissions (for delete operations)
)

# Vault client
vault = Vault(
    base_url="https://vault.example.com", # The base Vault URL
    token="token", # Vault token with write permissions
)
```

#### Example: Reading a yaml file from Bitbucket Server and print as json

```python
import asyncio
from tashtiot_apis_library import Git

async def main():
    git = Git(
        base_url="https://bitbucket.example.com",
        token="token",
        username_or_email="user@example.com",
        project_key="PROJ",
        repo_slug="repo-name",
        default_ref="default_ref",
        ssh_key_file_path="/path/to/ssh/private/key",
    )
    values_file = await git.get_file_content("/hapoel/ole/ole/values.yaml")
    json_values = yaml.safe_load(response)
    print(json_values)
    
asyncio.run(main())
```

### Using FastAPI Template

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import settings

app = general_create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
```

## 📦 Components

### Infrastructure Connectors

```python
from tashtiot_apis_library.connectors import ArgoCD, Git, Vault
from tashtiot_apis_library.connectors.errors import (
    ExternalServiceError,
    ArgoCDError,
    GitError,
    VaultError,
)
```

**Features:**
- ✅ Async clients that validate responses and raise typed exceptions
- ✅ High-level helpers for ArgoCD apps, Bitbucket Server repo manipulation, and Vault secrets
- ✅ Shared logging configuration with Loguru
- ✅ Minimal dependency footprint

### Standardized Return Types

Key operations in `ArgoCD` and `AWX` connectors return standardized response models:

- **Base Schema**: `OperationResponse` (status, status_code, stdout)
- **AWX**: `AWXOperationResponse` (includes `job_id`)
- **ArgoCD**: `ArgoOperationResponse` (includes `app_name`)

**Example Usage:**

```python
response = await awx.launch_job(job_template_id=1)
if response.status == "successful":
    print(f"Job {response.job_id} finished!")
```

### FastAPI Template

```python
from tashtiot_apis_library.fastapi_template import general_create_app
```

**Features:**
- ✅ Structured logging powered by Loguru
- ✅ Prometheus-compatible metrics endpoint
- ✅ Swagger UI and ReDoc with customizable static assets
- ✅ Built-in middleware for request timing, exception handling, and logging
- ✅ Health check endpoints for Kubernetes readiness/liveness probes
- ✅ Utilities for HTTP, FTP, and Kubernetes interactions
- ✅ Inbound JWT bearer authentication (HS256 / local public key / JWKS, incl. OIDC issuer discovery) with a Swagger **Authorize** tab
- ✅ Outbound SSO client (OAuth2 `client_credentials`) with automatic token caching & refresh
- ✅ Dev key/token generation via the `gen-auth-material` CLI
- ✅ Remote Config API capability — an authenticated proxy to an upstream Config API with live OpenAPI enum dropdowns (`enable_remote_config_api`)

### Authentication

The template ships a complete auth toolkit, split by concern: inbound-JWT helpers live under
`tashtiot_apis_library.fastapi_template.auth`, outbound-SSO helpers under
`tashtiot_apis_library.fastapi_template.security`, and the auth error types under
`tashtiot_apis_library.fastapi_template.errors`. The heavy bits import lazily, so apps that don't use
auth pay no import cost.

#### Protecting inbound requests (server side)

Authentication is **dual-gated**: it activates only when you pass `enable_auth=True` *and* set
`AUTH_ENABLED=true` in the environment. Configure exactly one piece of verification material —
`AUTH_HS256_SECRET` (HS256), `AUTH_JWKS_URL` (JWKS/OIDC, the usual choice for SSO),
`AUTH_OIDC_ISSUER` (JWKS via OIDC discovery — see below), or `AUTH_PUBLIC_KEY_PEM` /
`AUTH_PUBLIC_KEY_PATH` (offline RS256).

For any standards-compliant OIDC provider you can skip looking up the JWKS endpoint and just set
`AUTH_OIDC_ISSUER`: at startup the library fetches the issuer's
`/.well-known/openid-configuration`, discovers its `jwks_uri`, and verifies in JWKS mode. The issuer
also becomes the default expected `iss` claim (unless `AUTH_ISSUER` overrides it). An explicit
`AUTH_JWKS_URL` always takes precedence over discovery.

```python
from tashtiot_apis_library import general_create_app

app = general_create_app(enable_auth=True)   # + AUTH_ENABLED=true and one verification material
```

Requests must carry `Authorization: Bearer <token>`; verified claims land on `request.state.user`.
Read them in a route via the dependency:

```python
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.auth import get_current_claims

@app.get("/me")
def me(claims: dict = Depends(get_current_claims)):
    return claims
```

When auth is active, Swagger UI (`/docs`) automatically gains an **Authorize** tab so you can paste a
token and use "Try it out" against protected routes.

To check a token outside the request flow (workers, scripts), use the standalone helper:

```python
from tashtiot_apis_library.fastapi_template.auth import verify_token

claims = verify_token(token)   # raises TokenError if invalid/expired
```

#### Calling other services with SSO (client side)

Obtain and attach a token via the OAuth2 `client_credentials` grant, configured from `AUTH_SSO_*`
env vars. `sso_authenticated_api(base_url)` returns a client whose every request carries a fresh
bearer token (cached and auto-refreshed; refreshed again on a `401`):

```python
from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

async with sso_authenticated_api("https://downstream.example.com") as client:
    resp = await client.get("/protected")   # Authorization: Bearer <auto-managed>
```

> The SSO helpers live in `…fastapi_template.security`, kept separate from the inbound-JWT machinery
> in `…fastapi_template.auth` so consumers that only mint outbound tokens never pull in PyJWT.

To call **several** upstreams that each need a different identity or audience — independently of the
`AUTH_SSO_*` singleton — pass an explicit `SSOConfig`. Build one per remote and reuse it so its
token cache is shared:

```python
from tashtiot_apis_library.fastapi_template.security import SSOConfig, sso_authenticated_api

billing = SSOConfig(
    token_url="https://idp/oauth/token",
    client_id="my-svc", client_secret="…",
    audience="https://billing.example.com",
)
async with sso_authenticated_api("https://billing.example.com", config=billing) as client:
    resp = await client.get("/invoices")
```

For an upstream secured by a long-lived service token (no token endpoint), use `StaticBearerAuth`
with any client that accepts an `httpx.Auth`:

```python
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

async with BaseAPI("https://downstream.example.com", auth=StaticBearerAuth("token")) as client:
    resp = await client.get("/protected")
```

Prefer the raw token? `get_sso_token_client().get_token()` / `.auth_header()`.

#### Generating dev key material

After install, the `gen-auth-material` CLI mints an RSA keypair and a signed JWT for exercising
local-pubkey auth:

```bash
gen-auth-material                                  # write jwt_private.pem + jwt_public.pem, print a non-expiring token
gen-auth-material --expires-minutes 30             # mint a token that expires in 30 minutes
gen-auth-material --no-write                       # print a keypair + token, write nothing
gen-auth-material --sub svc --aud my-api --iss https://idp/   # claims to match AUTH_AUDIENCE/AUTH_ISSUER
gen-auth-material --private-key jwt_private.pem    # reuse existing keys, mint a fresh token
```

By default the minted token has **no `exp` claim** and never expires. The verifier requires `exp` out
of the box, so to accept a non-expiring token set `AUTH_REQUIRE_EXP=false` on the verifying service
(the CLI prints this hint). Pass `--expires-minutes N` to mint a normally-expiring token instead.

| Option | Description | Default |
|--------|-------------|---------|
| `--sub` | Token subject (`sub` claim) | `local-dev` |
| `--aud` | Audience (`aud`); set to match `AUTH_AUDIENCE` | `None` |
| `--iss` | Issuer (`iss`); set to match `AUTH_ISSUER` | `None` |
| `--algorithm` | Signing algorithm | `RS256` |
| `--kid` | Key id placed in the JWT header | `local-dev-key` |
| `--expires-minutes` | Token lifetime in minutes; omit for a non-expiring token (no `exp`) | `None` (never expires) |
| `--key-size` | RSA key size in bits | `2048` |
| `--out-dir` | Directory for the `.pem` files | `.` |
| `--private-name` | Private key filename | `jwt_private.pem` |
| `--public-name` | Public key filename | `jwt_public.pem` |
| `--no-write` | Print only; do not write key files | `false` |
| `--private-key` | Path to an existing private key PEM to sign with (skips key generation) | `None` |
| `--public-key` | Path to an existing public key PEM (derived from `--private-key` if omitted) | `None` |

### Remote Config API

`enable_remote_config_api` wires a thin **authenticated proxy to an upstream Config API** onto your
app. The upstream resolves hierarchical infrastructure config / naming / project-registry from a set
of *allocation coordinates* (`space`, `network`, `region`, `island`, `environment`, `project`); this
capability forwards those coordinates over HTTP, caches the result in memory, and keeps your own
Swagger dropdowns and request validation in sync with the upstream's live allowlists.

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

# Define your own routes against the returned provider:
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.config_api import RequiredInfraMetadata

@app.get("/config")
async def get_config(meta: RequiredInfraMetadata = Depends()):
    return await provider.resolve_infra_config(meta)
```

What it sets up:

- A `RemoteConfigProvider` (returned) with `resolve_infra_config`, `resolve_naming_convention`, and
  `get_all_projects`, all cached for `cache_ttl` seconds (default 60).
- A background poller (registered on `general_create_app`'s lifespan) that refreshes the live
  coordinate allowlists from the upstream every `poll_interval` seconds, hot-patching both the
  Pydantic validators and the OpenAPI `enum` dropdowns. Pass `enable_polling=False` to drive it
  yourself.
- A `pydantic.ValidationError → 422` handler so a coordinate outside its allowlist returns the same
  shape as any other invalid query parameter.

Outbound auth to the upstream is **selectable via `CONFIG_REMOTE_*` env vars** (SSO
`client_credentials`, a static bearer, or none — see the configuration table below). Pass an explicit
`httpx.Auth` via `auth=` to override the settings entirely (tests / escape hatch).

> Remote Config pulls in [`aiocache`](https://pypi.org/project/aiocache/) for its in-memory cache.
> Because the import is lazy, apps that don't call `enable_remote_config_api` never need it.

## 🔧 Configuration

The FastAPI template uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `APP_NAME` | Application name | `MyApp` |
| `DEBUG` | Debug mode | `false` |

Create a `.env` file for configuration:

```env
PORT=8000
LOG_LEVEL=INFO
APP_NAME=MyFastAPIApp
```

### Inbound authentication (server side)

Active only when `general_create_app(enable_auth=True)` **and** `AUTH_ENABLED=true`. Set exactly one
verification material.

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_ENABLED` | Runtime master switch for inbound JWT auth | `false` |
| `AUTH_HEADER_NAME` | Header carrying the bearer token | `Authorization` |
| `AUTH_HS256_SECRET` | Shared secret → selects HS256 mode | `None` |
| `AUTH_JWKS_URL` | JWKS/OIDC endpoint → selects JWKS mode | `None` |
| `AUTH_OIDC_ISSUER` | OIDC issuer base URL → selects JWKS mode via discovery; also default expected `iss` | `None` |
| `AUTH_OIDC_VERIFY_SSL` | Verify TLS when fetching the OIDC discovery document | `true` |
| `AUTH_OIDC_TIMEOUT` | Timeout (seconds) for the one-shot OIDC discovery request at startup | `10.0` |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | Public key → selects offline RS256 mode | `None` |
| `AUTH_ALGORITHMS` | Allowed signing algorithms (HS256 mode forces `["HS256"]`) | `["RS256"]` |
| `AUTH_REQUIRE_EXP` | Require an `exp` claim; set `false` to accept non-expiring tokens | `true` |
| `AUTH_AUDIENCE` | Expected `aud` claim (unchecked when unset) | `None` |
| `AUTH_ISSUER` | Expected `iss` claim (unchecked when unset) | `None` |
| `AUTH_JWKS_CACHE_TTL` | Seconds to cache fetched JWKS keys | `3600` |
| `AUTH_EXCLUDE_PATHS` | Path prefixes that bypass auth | health/metrics/docs/… |

### Outbound SSO (client side)

Used by `sso_authenticated_api` / `get_sso_token_client`. The first three are required.

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_SSO_TOKEN_URL` | OAuth2 token endpoint | `None` |
| `AUTH_SSO_CLIENT_ID` | OAuth2 client id | `None` |
| `AUTH_SSO_CLIENT_SECRET` | OAuth2 client secret | `None` |
| `AUTH_SSO_SCOPE` | Space-separated scopes (omitted when unset) | `None` |
| `AUTH_SSO_AUDIENCE` | `audience` token-request param (e.g. Auth0) | `None` |
| `AUTH_SSO_AUTH_STYLE` | Credential delivery: `post` (body) or `basic` (HTTP Basic) | `post` |
| `AUTH_SSO_VERIFY_SSL` | Verify the token endpoint's TLS certificate | `true` |
| `AUTH_SSO_TIMEOUT` | Token request timeout (seconds) | `10.0` |
| `AUTH_SSO_EXPIRY_SKEW` | Refresh the token this many seconds before expiry | `30` |

##### Setting the `aud` of the service you call

How the downstream's `aud` claim gets populated is **provider-specific** — it is decided when the
token is minted at `AUTH_SSO_TOKEN_URL`, not by anything at the call site.

- **Auth0-style providers** honor a request parameter: set `AUTH_SSO_AUDIENCE` and it is sent as the
  `audience` form field, and the IdP stamps it into `aud`.
- **Keycloak ignores the `audience` request parameter**, so `AUTH_SSO_AUDIENCE` is a no-op there.
  Keycloak derives `aud` from server-side **Audience protocol mappers** on a client scope. Configure
  it on the Keycloak side and request that scope from the client:
  1. Create a client scope (e.g. `config-api-aud`) with an **Audience** mapper whose *Included Client
     Audience* is the downstream client (or *Included Custom Audience* = a literal string), and assign
     it to your client as an **Optional** client scope.
  2. Request it per call by setting `AUTH_SSO_SCOPE=config-api-aud` — the library forwards it as the
     OAuth2 `scope` field, pulling in the mapper so the issued token carries the right `aud`.

  The downstream service then validates that value via its inbound `AUTH_AUDIENCE`.

### Remote Config API (outbound to the upstream)

Read by `enable_remote_config_api` to authenticate to the upstream Config API. `CONFIG_REMOTE_AUTH_METHOD`
picks the strategy; only the knobs for the chosen method are required.

| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIG_REMOTE_AUTH_METHOD` | Outbound auth strategy: `sso`, `bearer`, or `none` | `sso` |
| `CONFIG_REMOTE_BEARER_TOKEN` | Static bearer token (required when method is `bearer`) | `None` |
| `CONFIG_REMOTE_SSO_TOKEN_URL` | OAuth2 token endpoint (method `sso`) | `None` |
| `CONFIG_REMOTE_SSO_CLIENT_ID` | OAuth2 client id (method `sso`) | `None` |
| `CONFIG_REMOTE_SSO_CLIENT_SECRET` | OAuth2 client secret (method `sso`) | `None` |
| `CONFIG_REMOTE_SSO_SCOPE` | Space-separated scopes (Keycloak: carries the downstream `aud`) | `None` |
| `CONFIG_REMOTE_SSO_AUDIENCE` | `audience` token-request param (Auth0-style; Keycloak ignores it) | `None` |
| `CONFIG_REMOTE_SSO_AUTH_STYLE` | Credential delivery: `post` or `basic` | `post` |
| `CONFIG_REMOTE_SSO_VERIFY_SSL` | Verify the token endpoint's TLS certificate | `true` |
| `CONFIG_REMOTE_SSO_TIMEOUT` | Token request timeout (seconds) | `10.0` |
| `CONFIG_REMOTE_SSO_EXPIRY_SKEW` | Refresh the token this many seconds before expiry | `30` |
