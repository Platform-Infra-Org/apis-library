# Configuration

The FastAPI template is configured entirely through environment variables (loaded from the process
environment or a `.env` file via `pydantic-settings`). This page lists every variable with its
default.

## Core settings

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | `8000` |
| `LOG_LEVEL` | Logging level (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`) | `INFO` |
| `APP_NAME` | Application name | `MyApp` |
| `DEBUG` | FastAPI debug mode | `false` |

Example `.env`:

```env
PORT=8000
LOG_LEVEL=INFO
APP_NAME=MyFastAPIApp
```

## Inbound authentication (server side)

Active only when `general_create_app(enable_auth=True)` **and** `AUTH_ENABLED=true`. Set exactly one
verification material (HS256 secret, JWKS/OIDC, or a local public key).

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_ENABLED` | Runtime master switch for inbound JWT auth | `false` |
| `AUTH_HEADER_NAME` | Header carrying the bearer token | `Authorization` |
| `AUTH_HS256_SECRET` | Shared secret → selects HS256 mode | `None` |
| `AUTH_JWKS_URL` | JWKS/OIDC endpoint → selects JWKS mode | `None` |
| `AUTH_OIDC_ISSUER` | OIDC issuer base URL → selects JWKS mode via discovery; also default expected `iss` | `None` |
| `AUTH_OIDC_VERIFY_SSL` | Verify TLS when fetching the OIDC discovery document | `true` |
| `AUTH_OIDC_TIMEOUT` | Timeout (seconds) for the one-shot OIDC discovery request at startup | `10.0` |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | Public key (inline or file) → selects offline RS256 mode | `None` |
| `AUTH_ALGORITHMS` | Allowed signing algorithms (HS256 mode forces `["HS256"]`) | `["RS256"]` |
| `AUTH_REQUIRE_EXP` | Require an `exp` claim; set `false` to accept non-expiring tokens | `true` |
| `AUTH_AUDIENCE` | Expected `aud` claim (unchecked when unset) | `None` |
| `AUTH_ISSUER` | Expected `iss` claim (unchecked when unset) | `None` |
| `AUTH_JWKS_CACHE_TTL` | Seconds to cache fetched JWKS keys | `3600` |
| `AUTH_EXCLUDE_PATHS` | Path prefixes that bypass auth | health/metrics/docs/… |

!!! warning "Exactly one material"
    Configuring zero materials (while auth is enabled) or more than one raises `AuthConfigError` at
    startup, so misconfiguration fails fast rather than on the first request.

## Outbound SSO (client side)

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

See [Call other services with SSO](../how-to/call-services-with-sso.md) for how the downstream `aud`
is populated (it's provider-specific).

## Remote Config API (outbound to the upstream)

Read by `enable_remote_config_api` to authenticate to the upstream Config API.
`CONFIG_REMOTE_AUTH_METHOD` picks the strategy; only the knobs for the chosen method are required.

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
