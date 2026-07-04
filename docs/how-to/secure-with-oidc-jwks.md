# Secure an API with OIDC & JWKS

To protect your service against tokens minted by the **platform SSO**, verify inbound bearer tokens
in **JWKS mode**: the verifier fetches the provider's RS256 signing keys from its JWKS endpoint (by
their `kid`) and validates every request against them. This is the standards path for any OIDC
provider and needs no shared secret or key file on your side — unlike the local-pubkey mode used in
the [Secure your API](../tutorials/secure-your-api.md) tutorial.

Two sides have to line up: the **SSO** (issues tokens carrying the right audience), and **your API**
(verifies the signature, `iss`, and `aud`). Callers get their tokens via the OAuth2
`client_credentials` grant.

## 1. What to request from the SSO team

The verification material and the audience aren't something you generate — ask the SSO team for:

- **A client** (client id + secret) for each *caller* that will reach your API. Callers use it with
  the `client_credentials` grant (see step 3). Human callers front-ended by a UI use their own flow;
  this is for **service-to-service** calls.
- **An audience** (a.k.a. API identifier) for *your* service — the value the SSO stamps into the
  `aud` claim of issued tokens, and the value your API checks. Agree on one string (e.g.
  `https://my-api.platform.example`).
- **The client scope that carries the platform audience.** On Keycloak-style providers the `aud` is
  set by an **Audience** protocol mapper attached to a **client scope**. This platform scope should
  **already exist in the SSO** — callers just need it granted/requested so their tokens carry your
  audience. (On Auth0-style providers the audience is a request parameter instead — see step 3.)
- **The issuer URL** (for OIDC discovery) *or* the **JWKS endpoint URL** directly.

## 2. Configure your API (inbound verification)

Turn on inbound auth. It's **dual-gated** — both the code flag and the runtime switch must be set:

```python
from tashtiot_apis_library import general_create_app

app = general_create_app(enable_auth=True)   # gate 1: the code flag
```

Point the verifier at the SSO in your environment (`.env` or process env). Prefer **OIDC discovery**
— give it the issuer and it fetches `/.well-known/openid-configuration` at startup to find the
`jwks_uri`:

```env
AUTH_ENABLED=true                                        # gate 2: the runtime switch
AUTH_OIDC_ISSUER=https://sso.platform.example/realms/platform
AUTH_AUDIENCE=https://my-api.platform.example            # must equal the audience the SSO assigned you
```

Or skip discovery and name the JWKS endpoint directly (use one **or** the other, not both):

```env
AUTH_ENABLED=true
AUTH_JWKS_URL=https://sso.platform.example/realms/platform/protocol/openid-connect/certs
AUTH_AUDIENCE=https://my-api.platform.example
AUTH_ISSUER=https://sso.platform.example/realms/platform  # expected iss (OIDC discovery sets this for you)
```

!!! warning "Set `AUTH_AUDIENCE` or audience isn't checked"
    Audience is validated **only when `AUTH_AUDIENCE` is set**. Leave it unset and any validly-signed
    token from the issuer is accepted regardless of who it was minted for — so a token meant for a
    different service would pass. Always set it to your assigned audience.

With `enable_auth=True` + `AUTH_ENABLED=true`, the `AuthMiddleware` protects **every** route (minus
the [exclude list](../reference/configuration.md#inbound-authentication-server-side): probes, docs,
`/.well-known`, …). Routes read the verified identity via `Depends(get_current_claims)`; a missing or
invalid token gets a `401`. See the full [inbound `AUTH_*` table](../reference/configuration.md#inbound-authentication-server-side)
for every knob (`AUTH_ISSUER`, `AUTH_ALGORITHMS`, `AUTH_JWKS_CACHE_TTL`, `AUTH_REQUIRE_EXP`, …).

## 3. How a caller obtains a token (`client_credentials`)

A caller exchanges its client id/secret for a token at the SSO's token endpoint, then sends it as
`Authorization: Bearer <token>`. The issued token's `aud` **must match your `AUTH_AUDIENCE`**, so the
caller has to make the SSO stamp it:

- **Keycloak-style:** request the platform **client scope** (step 1) so the Audience mapper adds your
  `aud`. With this library's helpers, set `AUTH_SSO_SCOPE` to that scope.
- **Auth0-style:** the provider honours an `audience` request parameter — set `AUTH_SSO_AUDIENCE` to
  your audience and the IdP stamps it.

If the caller is itself a service built on this library, it doesn't need to hand-roll the grant — the
outbound helpers fetch, cache, and refresh the token automatically:

```python
from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

async with sso_authenticated_api("https://my-api.platform.example") as client:
    resp = await client.get("/protected")     # Authorization: Bearer <auto-managed>
```

See **[Call other services with SSO](call-services-with-sso.md)** for the full outbound setup
(`AUTH_SSO_*` variables, per-upstream `SSOConfig`, and how the downstream `aud` is populated).

## Verify a token outside a request

Workers, CLIs, or routes that receive a token by other means can verify it directly with the same
JWKS configuration — see [Verify a token outside a request](verify-a-token.md).

## See also

- [Call other services with SSO](call-services-with-sso.md) — the caller/outbound side.
- [Verify a token outside a request](verify-a-token.md) — the inbound check off the request path.
- [Authentication design](../explanation/authentication.md) — why modes exist and how they're selected.
- [Configuration reference](../reference/configuration.md) — every `AUTH_*` / `AUTH_SSO_*` variable.
