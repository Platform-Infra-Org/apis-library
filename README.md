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
- ✅ Inbound JWT bearer authentication (HS256 / local public key / JWKS) with a Swagger **Authorize** tab
- ✅ Outbound SSO client (OAuth2 `client_credentials`) with automatic token caching & refresh
- ✅ Dev key/token generation via the `gen-auth-material` CLI

### Authentication

The template ships a complete auth toolkit under `tashtiot_apis_library.fastapi_template.utils`. All
auth imports are lazy, so apps that don't use auth pay no import cost.

#### Protecting inbound requests (server side)

Authentication is **dual-gated**: it activates only when you pass `enable_auth=True` *and* set
`AUTH_ENABLED=true` in the environment. Configure exactly one piece of verification material —
`AUTH_HS256_SECRET` (HS256), `AUTH_JWKS_URL` (JWKS/OIDC, the usual choice for SSO), or
`AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` (offline RS256).

```python
from tashtiot_apis_library import general_create_app

app = general_create_app(enable_auth=True)   # + AUTH_ENABLED=true and one verification material
```

Requests must carry `Authorization: Bearer <token>`; verified claims land on `request.state.user`.
Read them in a route via the dependency:

```python
from fastapi import Depends
from tashtiot_apis_library.fastapi_template.utils import get_current_claims

@app.get("/me")
def me(claims: dict = Depends(get_current_claims)):
    return claims
```

When auth is active, Swagger UI (`/docs`) automatically gains an **Authorize** tab so you can paste a
token and use "Try it out" against protected routes.

To check a token outside the request flow (workers, scripts), use the standalone helper:

```python
from tashtiot_apis_library.fastapi_template.utils import verify_token

claims = verify_token(token)   # raises TokenError if invalid/expired
```

#### Calling other services with SSO (client side)

Obtain and attach a token via the OAuth2 `client_credentials` grant, configured from `AUTH_SSO_*`
env vars. `sso_authenticated_api(base_url)` returns a client whose every request carries a fresh
bearer token (cached and auto-refreshed; refreshed again on a `401`):

```python
from tashtiot_apis_library.fastapi_template.utils import sso_authenticated_api

async with sso_authenticated_api("https://downstream.example.com") as client:
    resp = await client.get("/protected")   # Authorization: Bearer <auto-managed>
```

Prefer the raw token? `get_sso_token_client().get_token()` / `.auth_header()`.

#### Generating dev key material

After install, the `gen-auth-material` CLI mints an RSA keypair and a signed JWT for exercising
local-pubkey auth:

```bash
gen-auth-material                                  # write jwt_private.pem + jwt_public.pem, print a token
gen-auth-material --no-write                       # print a keypair + token, write nothing
gen-auth-material --sub svc --aud my-api --iss https://idp/   # claims to match AUTH_AUDIENCE/AUTH_ISSUER
gen-auth-material --private-key jwt_private.pem    # reuse existing keys, mint a fresh token
```

| Option | Description | Default |
|--------|-------------|---------|
| `--sub` | Token subject (`sub` claim) | `local-dev` |
| `--aud` | Audience (`aud`); set to match `AUTH_AUDIENCE` | `None` |
| `--iss` | Issuer (`iss`); set to match `AUTH_ISSUER` | `None` |
| `--algorithm` | Signing algorithm | `RS256` |
| `--kid` | Key id placed in the JWT header | `local-dev-key` |
| `--expires-minutes` | Token lifetime in minutes | `30` |
| `--key-size` | RSA key size in bits | `2048` |
| `--out-dir` | Directory for the `.pem` files | `.` |
| `--private-name` | Private key filename | `jwt_private.pem` |
| `--public-name` | Public key filename | `jwt_public.pem` |
| `--no-write` | Print only; do not write key files | `false` |
| `--private-key` | Path to an existing private key PEM to sign with (skips key generation) | `None` |
| `--public-key` | Path to an existing public key PEM (derived from `--private-key` if omitted) | `None` |

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
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | Public key → selects offline RS256 mode | `None` |
| `AUTH_ALGORITHMS` | Allowed signing algorithms (HS256 mode forces `["HS256"]`) | `["RS256"]` |
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
