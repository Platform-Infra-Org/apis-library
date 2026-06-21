# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The version itself is derived from git
tags by setuptools-scm.

## [1.0.0] - 2026-06-21

First stable release. Adds a full inbound/outbound authentication story and a Remote Config
capability to the FastAPI template, reorganizes the public API surface by concern (a breaking
change), and modernizes packaging, tooling, and documentation.

### Added

**FastAPI template — authentication**
- **Inbound JWT authentication**, enforced by `AuthMiddleware` and **dual-gated** (`enable_auth=True`
  *and* `AUTH_ENABLED=true`). The verifier auto-selects one mode from the configured material —
  HS256 (`AUTH_HS256_SECRET`), local public key (`AUTH_PUBLIC_KEY_PEM`/`AUTH_PUBLIC_KEY_PATH`), or
  JWKS (`AUTH_JWKS_URL`) — and raises `AuthConfigError` at startup on ambiguous/missing config.
- **OIDC issuer discovery**: set `AUTH_OIDC_ISSUER` to resolve the `jwks_uri` from the issuer's
  well-known document and verify in JWKS mode.
- **Non-expiring-token support** via `AUTH_REQUIRE_EXP=false`.
- **Swagger Authorize tab** appears automatically when auth is active.
- Route helper `get_current_claims` and the standalone `verify_token()`.
- **Dev key/token generation**: the `gen-auth-material` CLI plus `generate_keypair` / `mint_token` /
  `load_keypair` / `derive_public_pem`.

**FastAPI template — outbound SSO**
- OAuth2 **`client_credentials`** client: `SSOConfig`, `SSOTokenClient`, `SSOClientCredentialsAuth`,
  `StaticBearerAuth`, and the headline `sso_authenticated_api(base_url)` — with token caching,
  pre-expiry refresh, and a one-shot retry on `401`.

**FastAPI template — Remote Config API**
- `enable_remote_config_api(app, …)`: an authenticated proxy to an upstream Config API with
  in-memory caching, a background allowlist poller, live OpenAPI `enum` dropdowns, a
  coordinate-validation→422 handler, and selectable `CONFIG_REMOTE_*` outbound auth (`sso`/`bearer`/
  `none`).

**Public API**
- New public modules `fastapi_template.auth` (inbound JWT) and `fastapi_template.security` (outbound
  SSO); auth error types (`AuthConfigError`, `TokenError`, `SSOError`) public via
  `fastapi_template.errors` and the top-level package. `AuthMode` is now public.

**Observability**
- Standardized Loguru logging added across the auth, SSO, and Remote Config code, following the
  library's level conventions (INFO ops / DEBUG internals / WARNING misconfig / ERROR before raising).

**Tooling & CI**
- Adopted the Astral toolchain: **Ruff** (lint + format), **ty** (advisory type check), and **uv**
  (fast runner). Added `.pre-commit-config.yaml` and a Woodpecker `check.yaml` pipeline that runs
  Ruff + pytest + advisory ty on push/PR.

**Documentation**
- A MkDocs (Material + mkdocstrings) documentation site organized by Diátaxis — tutorials, how-to
  guides, reference (configuration, CLI, auto-generated API), explanation, and contributing.

### Changed

- **Public API surface reorganized by concern**: `fastapi_template.utils` now holds only the infra
  utilities (`BaseAPI`, `settings`); inbound JWT lives in `auth`, outbound SSO in `security`, auth
  errors in `errors`. (See **Removed** for the breaking move.)
- **Packaging consolidated to a single source of truth** in `pyproject.toml`; the version is now
  **dynamic via setuptools-scm** (`dynamic = ["version"]`) — no version is hardcoded in source, and
  CI pins the published version from the git tag.
- **Dependencies reconciled** (added `starlette`, `aiocache`, `cryptography`, `python-dotenv`;
  corrected to Pydantic v2).
- **Tests consolidated** into one top-level `tests/` tree with a single pytest config; tests now
  import via the public API.
- Connector clients use **relative imports** for `BaseAPI`.
- Importing the `_internal.security` package (or running an auth-disabled app) **no longer pulls in
  PyJWT** — the lazy-auth design now actually holds.
- Background tasks run via the application lifespan.
- **README and MAINTAINERS slimmed** to complement the docs site (now the single source of truth).

### Removed

- **Breaking:** the auth/SSO helpers are **no longer re-exported from `fastapi_template.utils`**.
  Import inbound JWT from `fastapi_template.auth` and outbound SSO from `fastapi_template.security`
  (clean break — no deprecation shims).
- Deleted the legacy `setup.py`, `requirements.txt`, and the redundant `MANIFEST.in` (obsolete under
  the src-layout + setuptools-scm).
- Removed the dead `terraform_runner` module.

### Fixed

- `connectors/argocd/service.py`: defined the undefined `ParamList` type alias and added the missing
  typing imports (a latent bug surfaced by Ruff's `F821`).
- Top-level package exports: `AWXError` and the auth error types are now declared in `__all__`.
- Docs home page: grid cards and Material icons now render (added the `md_in_html` and
  `pymdownx.emoji` markdown extensions).
