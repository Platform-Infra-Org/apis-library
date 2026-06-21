# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`tashtiot_apis_library` is a distributable Python library (published to an internal Artifactory PyPI repo) that ships two largely independent toolsets under one package:

1. **Infrastructure connectors** (`connectors/`) — async clients for ArgoCD, AWX (Ansible Tower), Bitbucket Server ("Git"), and HashiCorp Vault.
2. **FastAPI template** (`fastapi_template/`) — a reusable FastAPI application factory (`general_create_app`) with built-in middleware, metrics, probes, and Swagger.

Consumers `pip install` this package and import from the top-level `tashtiot_apis_library` namespace. There is no application to "run" here — the library is the product.

## Commands

Dev environment is managed with **uv** (used as a fast runner — there is intentionally **no
committed `uv.lock`**: this is a library, so consumers resolve against the dependency *ranges* in
`pyproject.toml`, and a lock would only churn against the setuptools-scm dynamic version). Plain
`pip` still works for anyone not using uv.

```bash
uv venv                              # create .venv
uv pip install -e ".[dev,docs]"      # dev tools: pytest, ruff, ty, pre-commit, mkdocs…
# (equivalently: pip install -e ".[dev]")

uv run pytest                        # one suite, from the repo root (see below)
uv run pytest tests/connectors/test_awx_client.py                    # single file
uv run pytest tests/connectors/test_awx_client.py::TestAWXOperations # single class

uv run ruff format .                 # format
uv run ruff check . --fix            # lint (+ safe autofixes)
uv run ty check src                  # type check (advisory; see below)

uv run pre-commit install            # enable git hooks (ruff + ruff-format on commit)
python -m build                      # build sdist+wheel (what CI does before publishing)
```

### Tooling (Astral: Ruff, ty, uv)
- **Ruff** is the linter + formatter (config in `pyproject.toml` `[tool.ruff]`). Conservative rule
  set (`E,F,I,B,C4`); deliberately **not** `UP` (pushes PEP 585/604 annotations unsafe on the py39
  target), `TID252` (the package relies on relative imports), or `G` (mixed f-string/`{}` Loguru).
  `auth.py` carries a `per-file-ignores` for `F822` (its `__all__` lists lazily re-exported names).
- **ty** is the type checker (`[tool.ty]`), run **advisory / non-blocking** everywhere — it's beta
  with no Pydantic plugin, so it reports a known baseline (~35 diagnostics in `src`, mostly
  Optional-annotation imprecision and Pydantic false positives). Useful signal, not a gate; revisit
  blocking once it reaches 1.0.
- **Enforcement**: `.pre-commit-config.yaml` runs ruff + ruff-format on commit (ty is a `manual`
  stage hook); `.woodpecker/check.yaml` runs ruff + pytest + ty (advisory) on push/PR. The tag-only
  `build.yaml` publish pipeline is unchanged.

Python >= 3.9.

### Tests (single suite)
- All tests live in the top-level `tests/` tree (`tests/connectors/`, `tests/fastapi_template/`),
  outside the importable package, and import the package absolutely
  (`from tashtiot_apis_library.fastapi_template... import ...`).
- One config: root `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`,
  `pythonpath = ["src"]` (so tests resolve without an editable install), `--cov` coverage, custom
  markers (`asyncio`, `rest`, `ftp`). Just run `pytest` from the repo root.
- The test dirs keep `__init__.py` files because some `config_api` tests import sibling helper
  modules (`from .conftest import ...`, `from .upstream import ...`).

## Architecture

### Connector three-layer pattern (service → client → models)
Every connector under `connectors/<name>/` is split into exactly three files, and new connectors must follow this:

- **`models.py`** — Pydantic models for requests/responses. Use `Field(alias="...")` for camelCase JSON keys; `model_config = ConfigDict(extra="allow")` to tolerate unknown fields.
- **`client.py`** — low-level HTTP. Always builds its `httpx.AsyncClient` via `BaseAPI(...).client` (from `fastapi_template.utils`). Converts HTTP error status codes into typed exceptions and returns parsed Pydantic models, never raw dicts.
- **`service.py`** — high-level class that users instantiate (e.g. `AWX`, `ArgoCD`, `Git`, `Vault`). It **composes** (does not inherit) the client and adds orchestration: polling, `wait_for_*_completion`, retries. Service methods generally return standardized `OperationResponse` subclasses rather than raw API models.

Adding a capability to a connector means touching all three layers bottom-up: model (if new shapes) → client method → service method.

### Standardized responses and errors
- `connectors/response_schemas.py` defines the base `OperationResponse` (`status`, `status_code`, `return_code`, `stdout`). Connector-specific subclasses live in that connector's `models.py` (`AWXOperationResponse` adds `job_id`; `ArgoOperationResponse` adds `app_name`). Service-layer methods return these.
- `connectors/errors.py` defines `ExternalServiceError(HTTPException)` as the base, subclassed per connector (`ArgoCDError`, `GitError`, `VaultError`, `AWXError`). Because they extend `fastapi.HTTPException`, raising one inside a FastAPI route surfaces directly as an HTTP response. Clients raise these on `status_code >= 400`.

### Imports
Use **relative imports** within the package (`from .client import ...`, `from ..errors import ...`, `from ...fastapi_template.utils import BaseAPI`). Absolute imports of internal modules are considered incorrect here — they break the package's portability. Connectors depend on `fastapi_template.utils.BaseAPI`, so the FastAPI template is a dependency of the connectors, not the reverse.

### FastAPI template
- `general_create_app(**flags)` in `fastapi_template/_internal/__init__.py` is the factory. Every built-in piece (logging/timing middleware, root route, exception handlers, uptime task, metrics, swagger, probes) is toggled by an `enable_*` keyword and extra `**fastapi_kwargs` pass through to `FastAPI()`. Docs/redoc/openapi are wired manually against self-hosted static assets in `fastapi_template/static/swagger/`.
- Public surface is intentionally narrow and split by concern: `fastapi_template/__init__.py` exports `general_create_app` (+ lazy `enable_remote_config_api`); `fastapi_template/utils.py` exports only the infra utilities `BaseAPI` and `settings`; `fastapi_template/auth.py` is the inbound-JWT home (`get_current_claims` eager, `JWTVerifier`/`verify_token`/`AuthMode`/keygen lazy); `fastapi_template/security.py` is the outbound-SSO home; `fastapi_template/errors.py` holds the public auth error types. Everything under `_internal/` is private implementation.
- Configuration is `pydantic-settings` (`_internal/utils/config.py`, `ApplicationSettings`), loaded from env vars / `.env` (`PORT`, `LOG_LEVEL`, `APP_NAME`, `DEBUG`, probe paths, swagger paths, etc.). Logging is Loguru throughout.

#### Inbound JWT authentication
- **Error types** (`AuthConfigError`, `TokenError`, `SSOError`) are public via `fastapi_template/errors.py` and the top-level package (mirroring `connectors/errors.py`) — import them from there, never from `_internal.security.errors`.
- Enforced by `AuthMiddleware` (`_internal/security/`), **not** FastAPI dependencies. It extracts a `Bearer <token>` from the `AUTH_HEADER_NAME` header (default `Authorization`), verifies it, and stashes the claims on `request.state.user`. Routes read them via `Depends(get_current_claims)`. PyJWT is imported lazily so consumers with auth disabled never need it installed.
- **Dual-gate**: auth is active only when both the code flag `enable_auth=True` (passed to `general_create_app`) and the runtime switch `AUTH_ENABLED=true` are set. The verifier auto-selects exactly one mode from the configured material — `AUTH_HS256_SECRET` (HS256), `AUTH_JWKS_URL` (JWKS/RS256), or `AUTH_PUBLIC_KEY_PEM`/`AUTH_PUBLIC_KEY_PATH` (local RS256) — and raises `AuthConfigError` at startup if zero or more than one is set. `AUTH_EXCLUDE_PATHS` (plus probes/swagger/openapi) bypass auth.
- **Swagger Authorize tab**: because auth is middleware-based, the generated OpenAPI schema would otherwise carry no security info and Swagger would show no Authorize button. Under the same dual-gate, `_internal/openapi.py`'s `install_bearer_security_scheme(app)` wraps `app.openapi` to inject a global `BearerAuth` scheme so the Authorize dialog appears and "Try it out" sends the token. `Authorization` maps to an HTTP `bearer`/`JWT` scheme (Swagger adds the `Bearer ` prefix); a custom `AUTH_HEADER_NAME` maps to an `apiKey` header scheme (user types the `Bearer ` prefix themselves). Kept out of the `security/` package to avoid forcing the PyJWT import.
- **Key/token generation** (`_internal/security/keygen.py`): the signing-side companion to `JWTVerifier`. Exposes `generate_keypair`, `derive_public_pem`, `load_keypair`, and `mint_token` (re-exported lazily from `fastapi_template/auth.py`) for minting RSA keys + dev tokens that pass local-pubkey verification. Also runnable as the `gen-auth-material` console script (registered in `pyproject.toml` `[project.scripts]`) or `python -m ...security.keygen`.
- **Outbound SSO** (`_internal/security/sso.py`): the *client* side — obtaining a token to call other services via the OAuth2 **client_credentials** grant, configured from `AUTH_SSO_*` env vars (`AUTH_SSO_TOKEN_URL`/`CLIENT_ID`/`CLIENT_SECRET` required; optional `SCOPE`, `AUDIENCE`, `AUTH_STYLE` = `post`|`basic`, `VERIFY_SSL`, `TIMEOUT`, `EXPIRY_SKEW`). `SSOTokenClient` fetches/caches/refreshes the token (`get_token`, `auth_header`); `SSOClientCredentialsAuth` is an `httpx.Auth` that injects + refreshes the bearer per request and retries once on `401`. The headline helper `sso_authenticated_api(base_url)` returns a connector-style `BaseAPI` (`auth=` accepts an `httpx.Auth`) whose every request carries a fresh token — `async with sso_authenticated_api(url) as client: await client.get(...)`. All re-exported from `fastapi_template/security.py` (`get_sso_token_client`, `sso_auth`, `sso_authenticated_api`). Note: `client_credentials` issues **no** refresh token (RFC 6749 §4.4.3) — "refresh" re-runs the grant. **Server-side** verification of SSO-issued tokens reuses **JWKS mode**: set `AUTH_JWKS_URL` (+ `AUTH_AUDIENCE`/`AUTH_ISSUER`) and either protect routes with `AuthMiddleware` or check a token directly with `verify_token(token)` (`_internal/security/verifier.py`).

### Public API
Top-level `tashtiot_apis_library/__init__.py` re-exports the connector services, error types, `general_create_app`, and the shared request schemas from `schemas.py` (`OperationRequest`, `ResourceSpec`, `DefaultMetaSpec`, `NameNamespace` — Kubernetes/PaaS-oriented Pydantic models with CPU/memory regex validation). Keep `__all__` here in sync when adding exports.

## Packaging notes
- `pyproject.toml` (setuptools backend) is the single source of truth for build config and dependencies — there is no `setup.py` or `requirements.txt`.
- The version is **dynamic**, derived from git tags by `setuptools-scm` (`dynamic = ["version"]` + `[tool.setuptools_scm]`); no version is hardcoded in source. `.woodpecker/build.yaml` rewrites only the `name` and exports `SETUPTOOLS_SCM_PRETEND_VERSION="${CI_COMMIT_TAG}"` so the built version matches the tag regardless of clone depth. Publishing is triggered by a `tag` or `manual` Woodpecker event and `curl`s the wheel/sdist to Artifactory.
- Tests live in the top-level `tests/` tree (outside the package), so nothing test-related is built into the wheel; static swagger assets are included as package data.
