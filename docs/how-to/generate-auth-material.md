# Generate dev auth material

The package installs a `gen-auth-material` console script that mints an RSA keypair and a signed JWT
for exercising **local public-key** inbound auth. It's the signing-side companion to the verifier —
handy for local development and tests, where you don't want to stand up a real identity provider.

## Common recipes

```bash
# Write jwt_private.pem + jwt_public.pem, print a non-expiring token
gen-auth-material

# Mint a token that expires in 30 minutes instead
gen-auth-material --expires-minutes 30

# Print a keypair + token, write nothing to disk
gen-auth-material --no-write

# Set claims to match the verifier's AUTH_AUDIENCE / AUTH_ISSUER
gen-auth-material --sub svc --aud my-api --iss https://idp/

# Reuse existing keys, mint a fresh token
gen-auth-material --private-key jwt_private.pem
```

You can also run it as a module: `python -m tashtiot_apis_library.fastapi_template._internal.security.keygen`.

## Using the output

Point a verifying service at the generated public key:

```env
AUTH_ENABLED=true
AUTH_PUBLIC_KEY_PATH=jwt_public.pem
AUTH_REQUIRE_EXP=false        # only needed for the default non-expiring token
```

Then send the printed token as `Authorization: Bearer <token>`. The
[Secure your API](../tutorials/secure-your-api.md) tutorial walks through this end-to-end.

!!! warning "Non-expiring by default"
    Without `--expires-minutes`, the minted token has **no `exp` claim** and never expires. The
    verifier requires `exp` out of the box, so the verifying service must set `AUTH_REQUIRE_EXP=false`
    to accept it (the CLI prints this hint).

## Full flag list

The complete option table lives in the [CLI reference](../reference/cli.md).
