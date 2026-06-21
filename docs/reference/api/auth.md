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
