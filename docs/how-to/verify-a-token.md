# Verify a token outside a request

The [auth middleware](../tutorials/secure-your-api.md) verifies tokens for inbound HTTP requests
automatically. When you need to verify a token **outside** the request flow — in a background worker,
a CLI, or a route that receives the token by other means — use the standalone `verify_token` helper.

```python
from tashtiot_apis_library.fastapi_template.auth import verify_token
from tashtiot_apis_library.fastapi_template.errors import TokenError

try:
    claims = verify_token(token)      # returns the decoded claims dict
except TokenError as exc:
    ...                               # invalid signature, expired, wrong audience, etc.
```

`verify_token` uses the same configuration as the middleware (it reads the package `settings`), so it
honours whatever verification material and claim checks you've configured via `AUTH_*` environment
variables — see [Configuration](../reference/configuration.md).

## Verify against a different configuration

Pass an explicit settings object to verify against a configuration other than the package default —
useful when one worker validates tokens from several issuers:

```python
claims = verify_token(token, settings=other_settings)
```

## Server-side verification of SSO-issued tokens

To verify tokens minted by an SSO provider (the [outbound](call-services-with-sso.md) side issuing
tokens that *this* service receives), use **JWKS mode**: point `AUTH_JWKS_URL` at the provider's JWKS
endpoint and set `AUTH_AUDIENCE` / `AUTH_ISSUER` to match the issued tokens. Then either protect
routes with the middleware (`enable_auth=True`) or check a token directly with `verify_token`.

!!! warning "Non-expiring tokens"
    The verifier requires an `exp` claim by default. To accept a token minted without one (e.g. a dev
    token from [`gen-auth-material`](generate-auth-material.md)), set `AUTH_REQUIRE_EXP=false` on the
    verifying service. A token that *does* carry `exp` is still validated, so expired tokens remain
    rejected.

## See also

- [API reference: auth](../reference/api/auth.md)
- [Authentication design](../explanation/authentication.md)
