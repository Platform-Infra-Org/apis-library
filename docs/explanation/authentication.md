# Authentication design

The library has two distinct auth concerns that are easy to conflate, so they're kept in separate
public modules:

- **Inbound** (`fastapi_template.auth`) — *verifying* bearer tokens on requests this service
  receives.
- **Outbound** (`fastapi_template.security`) — *obtaining* bearer tokens to call other services.

This page explains the design behind both.

## Inbound: enforced by middleware, not dependencies

Inbound auth is enforced by an `AuthMiddleware`, not by per-route FastAPI dependencies. The
middleware extracts a `Bearer <token>` from the configured header, verifies it, and stashes the
claims on `request.state.user`; routes read them via `Depends(get_current_claims)`. Doing it in
middleware means **every** route is protected by default (minus an explicit exclude list), rather
than relying on each route remembering to add a dependency.

A consequence: because the OpenAPI schema wouldn't otherwise carry security info, the library
injects a global `BearerAuth` scheme so Swagger shows an **Authorize** button when auth is active.

## The dual-gate

Auth activates only when **both** are true:

- the **code flag** `enable_auth=True` passed to `general_create_app`, and
- the **runtime switch** `AUTH_ENABLED=true` in the environment.

Two gates make it impossible to accidentally ship auth-on code that runs auth-off (or vice versa) by
changing only one of them. A deployment can also flip auth off at runtime without a code change.

## Verification modes

The verifier **auto-selects exactly one mode** from the configured material, and raises
`AuthConfigError` at startup if zero or more than one is set (fail fast, not on first request):

| Material | Mode |
|---|---|
| `AUTH_HS256_SECRET` | **HS256** — symmetric shared secret |
| `AUTH_PUBLIC_KEY_PEM` / `AUTH_PUBLIC_KEY_PATH` | **LOCAL_PUBKEY** — offline RS256 against a public key |
| `AUTH_JWKS_URL` *or* `AUTH_OIDC_ISSUER` | **JWKS** — RS256 against keys fetched from a JWKS endpoint |

### OIDC discovery

For any standards-compliant OIDC provider you can set `AUTH_OIDC_ISSUER` alone: at startup the
library fetches the issuer's `/.well-known/openid-configuration`, discovers its `jwks_uri`, and
verifies in JWKS mode. The issuer also becomes the default expected `iss` claim. An explicit
`AUTH_JWKS_URL` always wins over discovery. (`AUTH_JWKS_URL` and `AUTH_OIDC_ISSUER` are treated as one
material group, not two competing ones.)

### Non-expiring tokens

The verifier requires an `exp` claim by default. Set `AUTH_REQUIRE_EXP=false` to accept tokens minted
without one (e.g. dev tokens from [`gen-auth-material`](../how-to/generate-auth-material.md)). A token
that *does* carry `exp` is still validated, so expired tokens remain rejected either way.

## Outbound: client_credentials, cached and refreshed

Outbound SSO uses the OAuth2 **`client_credentials`** grant. The token client fetches a token, caches
it, refreshes it shortly before expiry (`AUTH_SSO_EXPIRY_SKEW`), serialises concurrent refreshes with
a lock, and the `httpx.Auth` retries once on a `401`. Note that `client_credentials` issues no refresh
token (RFC 6749 §4.4.3) — "refresh" means re-running the grant.

Server-side verification of SSO-issued tokens reuses **JWKS mode**: point `AUTH_JWKS_URL` at the
provider's JWKS endpoint. So the inbound and outbound sides meet at JWKS.

## Why PyJWT is lazy

PyJWT and cryptography are only needed when you actually verify or mint tokens. The public `auth`
module serves its verifier/keygen names through a module-level `__getattr__`, and the
`_internal/security` package `__init__` is empty, so **importing the package — or an auth-disabled
app — never imports PyJWT.** Consumers that only mint outbound tokens import from `security`, which
pulls in the SSO code but not the inbound-JWT machinery. The cost of a feature is paid only when it's
used.

## See also

- [Secure your API](../tutorials/secure-your-api.md) — the inbound side, hands-on.
- [Call other services with SSO](../how-to/call-services-with-sso.md) — the outbound side.
- [Configuration](../reference/configuration.md) — every `AUTH_*` / `AUTH_SSO_*` variable.
