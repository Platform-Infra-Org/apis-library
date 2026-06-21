# Auth API (inbound JWT)

The public inbound-JWT surface. Import everything here from `tashtiot_apis_library.fastapi_template.auth`:

```python
from tashtiot_apis_library.fastapi_template.auth import (
    get_current_claims, verify_token, JWTVerifier, AuthMode,
    generate_keypair, mint_token, load_keypair, derive_public_pem,
)
```

See [Secure your API](../../tutorials/secure-your-api.md) and
[Verify a token outside a request](../../how-to/verify-a-token.md) for usage.

## get_current_claims

::: tashtiot_apis_library.fastapi_template._internal.security.dependency.get_current_claims

## verify_token

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.verify_token

## JWTVerifier

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.JWTVerifier

## AuthMode

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.AuthMode

## Key & token generation

The signing-side companion to the verifier (see the [CLI](../cli.md) for the command-line wrapper).

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.generate_keypair

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.mint_token

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.load_keypair

::: tashtiot_apis_library.fastapi_template._internal.security.keygen.derive_public_pem

## Lower-level building blocks

Implementation pieces behind the dual-gate. You normally don't use these directly — they're wired up
by `general_create_app(enable_auth=True)` — but they're documented for completeness.

### AuthMiddleware

The middleware that enforces bearer auth on every non-excluded request.

::: tashtiot_apis_library.fastapi_template._internal.security.middleware.AuthMiddleware

### get_verifier

Returns a memoized `JWTVerifier` (above) for the given settings — built at app startup so
misconfiguration fails fast.

::: tashtiot_apis_library.fastapi_template._internal.security.verifier.get_verifier

### discover_jwks_uri

Resolves a provider's `jwks_uri` from its OIDC discovery document — backs `AUTH_OIDC_ISSUER`.

::: tashtiot_apis_library.fastapi_template._internal.security.oidc.discover_jwks_uri
