# CLI: `gen-auth-material`

A console script (registered as `gen-auth-material`, also runnable as
`python -m tashtiot_apis_library.fastapi_template._internal.security.keygen`) that generates an RSA
keypair and a signed JWT for exercising local public-key inbound auth.

See [Generate dev auth material](../how-to/generate-auth-material.md) for task-oriented usage.

## Behaviour

By default the command writes `jwt_private.pem` and `jwt_public.pem` to the current directory and
prints a signed JWT. The minted token has **no `exp` claim** and never expires; the verifier requires
`exp` out of the box, so the verifying service must set `AUTH_REQUIRE_EXP=false` to accept it (the CLI
prints this hint). Pass `--expires-minutes N` to mint a normally-expiring token instead.

## Options

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
