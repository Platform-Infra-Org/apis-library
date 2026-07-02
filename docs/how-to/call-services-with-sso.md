# Call other services with SSO

When your service needs to call **another** protected service, use the outbound SSO helpers. They
obtain a bearer token via the OAuth2 **`client_credentials`** grant, cache it, refresh it before
expiry, and retry once on a `401`.

These helpers live in `tashtiot_apis_library.fastapi_template.security`, deliberately separate from
the inbound-JWT machinery so a client-only consumer never pulls in PyJWT.

## The simple case: settings-driven

Configure the `AUTH_SSO_*` environment variables (see [Configuration](../reference/configuration.md))
and use `sso_authenticated_api`. Every request through the returned client carries a fresh token:

```python
from tashtiot_apis_library.fastapi_template.security import sso_authenticated_api

async with sso_authenticated_api("https://downstream.example.com") as client:
    resp = await client.get("/protected")     # Authorization: Bearer <auto-managed>
```

## Several upstreams with different identities

To call multiple upstreams that each need a different identity or audience — independently of the
`AUTH_SSO_*` singleton — pass an explicit `SSOConfig`. Build **one per remote and reuse it** so its
token cache is shared:

```python
from tashtiot_apis_library.fastapi_template.security import SSOConfig, sso_authenticated_api

billing = SSOConfig(
    token_url="https://idp/oauth/token",
    client_id="my-svc",
    client_secret="…",
    audience="https://billing.example.com",
)

async with sso_authenticated_api("https://billing.example.com", config=billing) as client:
    resp = await client.get("/invoices")
```

## A fixed, long-lived token

For an upstream secured by a static service token (no token endpoint), use `StaticBearerAuth` with
any client that accepts an `httpx.Auth` — including the library's `BaseAPI`:

```python
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

async with BaseAPI("https://downstream.example.com", auth=StaticBearerAuth("token")) as client:
    resp = await client.get("/protected")
```

## Just the raw token

```python
from tashtiot_apis_library.fastapi_template.security import get_sso_token_client

token = await get_sso_token_client().get_token()
headers = await get_sso_token_client().auth_header()   # {"Authorization": "Bearer …"}
```

## Setting the downstream audience (`aud`)

How the downstream's `aud` claim is populated is **provider-specific** — it's decided when the token
is minted at the token endpoint, not at the call site:

- **Auth0-style providers** honour a request parameter: set `AUTH_SSO_AUDIENCE` and it is sent as the
  `audience` form field; the IdP stamps it into `aud`.
- **Keycloak ignores the `audience` parameter.** Configure an **Audience** protocol mapper on a
  client scope, then request that scope via `AUTH_SSO_SCOPE` so the issued token carries the right
  `aud`. The downstream then validates it via its inbound `AUTH_AUDIENCE`.

!!! note "No refresh token"
    `client_credentials` issues no OAuth2 refresh token (RFC 6749 §4.4.3). "Refresh" here means
    re-running the grant to mint a new access token when the cached one nears expiry.

## See also

- [API reference: security](../reference/api/security.md)
- [Configuration: Outbound SSO](../reference/configuration.md#outbound-sso-client-side)
- [Verify a token (the inbound side)](verify-a-token.md)
- [Secure an API with OIDC & JWKS](secure-with-oidc-jwks.md) — the inbound counterpart these tokens are minted for.
