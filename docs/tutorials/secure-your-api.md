# Secure your API

In this tutorial you'll add **inbound JWT authentication** to the app from
[Your first app](first-app.md): mint a dev key + token, turn auth on, protect a route, and call it
with a bearer token through Swagger. We'll use **local public-key** mode because it needs no external
identity provider — perfect for learning.

## 1. Generate dev key material

The package installs a `gen-auth-material` command. Run it to create an RSA keypair and a signed
token:

```bash
gen-auth-material
```

This writes `jwt_private.pem` and `jwt_public.pem` to the current directory and prints a JWT plus a
hint. By default the token has **no `exp` claim** and never expires — convenient for a tutorial.

!!! note "Non-expiring tokens"
    Because the minted token has no `exp`, the verifier must be told to accept it. We do that below
    with `AUTH_REQUIRE_EXP=false`. To mint a normally-expiring token instead, pass
    `--expires-minutes 30`. See the [CLI reference](../reference/cli.md).

## 2. Turn auth on

Authentication is **dual-gated**: it activates only when you both pass `enable_auth=True` in code
**and** set `AUTH_ENABLED=true` in the environment. This makes it impossible to ship auth-on code
that silently runs auth-off (or vice versa).

Update `main.py`:

```python
from fastapi import Depends
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.auth import get_current_claims

app = general_create_app(enable_auth=True)   # gate 1: the code flag

@app.get("/me")
def me(claims: dict = Depends(get_current_claims)):
    return claims
```

`get_current_claims` is a FastAPI dependency that returns the verified JWT claims (the auth
middleware put them on `request.state.user`), or raises `401` if the request wasn't authenticated.

## 3. Point the verifier at your public key

Create a `.env` file next to `main.py`:

```env
AUTH_ENABLED=true                 # gate 2: the runtime switch
AUTH_PUBLIC_KEY_PATH=jwt_public.pem
AUTH_REQUIRE_EXP=false            # accept the non-expiring dev token from step 1
```

The verifier auto-selects its mode from whatever material you configure — here a public key file
selects offline **RS256** verification. (Set exactly one material; see
[Authentication design](../explanation/authentication.md).)

## 4. Run and try it

```bash
python main.py
```

Call the protected route **without** a token — you get a `401`:

```bash
curl -i http://localhost:8000/me
# HTTP/1.1 401 Unauthorized
```

Now pass the token printed in step 1:

```bash
TOKEN="<paste the token from gen-auth-material>"
curl -s http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# {"sub": "local-dev", ...}
```

## 5. Use the Swagger Authorize button

Because auth is active, Swagger UI gains an **Authorize** button. Open `http://localhost:8000/docs`,
click **Authorize**, paste the token, and use **Try it out** on `/me` — the request now carries your
bearer token.

## What you learned

- Auth is **dual-gated** (`enable_auth=True` + `AUTH_ENABLED=true`).
- The verifier picks its mode from the configured material (here, a local public key).
- Routes read the verified identity via `Depends(get_current_claims)`.

## Next steps

- **[Verify a token outside a request](../how-to/verify-a-token.md)** — for workers and scripts.
- **[Call other services with SSO](../how-to/call-services-with-sso.md)** — the outbound side.
- **[Authentication design](../explanation/authentication.md)** — the verification modes (HS256 /
  JWKS / OIDC discovery) and why they exist.
- **[Configuration reference](../reference/configuration.md)** — every `AUTH_*` variable.
