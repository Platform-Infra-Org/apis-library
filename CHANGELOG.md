# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The version is derived from git tags by
setuptools-scm.

## [Unreleased]

### Added

- Add general-purpose async job manager for operations Ansible can't drive, on any system (pluggable `Executor` Protocol with a generic stdlib command executor)

### Changed

- Migrate the job-manager queue engine from SAQ to Dramatiq + dramatiq-abort; the Redis-backed `JobRepository` is now the sole source of truth for status/result/history, the worker runs via `dramatiq ...:worker`, and cancellation is cooperative + abort-middleware driven (no monitoring UI — use the app's own surface + Prometheus)

## [1.1.1] - 2026-07-02

### Documentation

- Add OIDC/JWKS how-to and SSO client-scope setup

## [1.1.0] - 2026-06-30

### Added

- Optional stale-on-upstream-down fallback

### Documentation

- Document serve_stale_on_error fallback
## [1.0.0] - 2026-06-29

### Added

- Add inbound JWT authentication
- Run async_background_tasks via lifespan
- Show Swagger Authorize tab when auth is enabled
- Add JWT key/token generation utility to security
- Add external SSO client_credentials auth (client + server)
- Expose auth error types from a public module
- Add OIDC issuer discovery and non-expiring token support for inbound JWT
- Add client-side SSOConfig and StaticBearerAuth via public security module
- Add Remote Config API capability
- Add standard logging to auth, SSO, and config-api
- Add CoordinateCatalogResponse + coordinate-catalog proxy
- Add coordinate-tree proxy + CoordinateTreeResponse

### Changed

- Drop auth error types from the top-level public export
- Consolidate packaging, unify tests, and reorganize public API surface
- Hoist BaseAPI import so its cross-refs resolve via scope
- Split SSO Pydantic models into co-located models.py
- Rename schemas.py to models.py
- Cut over-engineering flagged by audit (internal only)

### Documentation

- Add CLAUDE.md repository guide
- Document auth toolkit in README and MAINTAINERS
- Document OIDC discovery, SSO client config, Remote Config API, and token expiry
- Add MkDocs documentation site (Diátaxis)
- Slim README and MAINTAINERS to complement the docs
- Render the home-page grid cards and icons
- Add CHANGELOG with the 1.0.0 release notes
- Surface the changelog in the MkDocs site
- Convert RST docstring roles to Markdown for mkdocstrings
- Expand the API reference to cover more of the package
- Note the comprehensive API reference in the 1.0.0 changelog
- Document the Remote Config coordinate-catalog discovery
- Fix broken config-api anchor link + validate anchors
- Document GitHub Actions release process in MAINTAINERS.md

### Build & CI

- Configure Ruff, ty, and uv (no lockfile) + docs deps
- Enforce Ruff/ty/pytest via pre-commit and Woodpecker
- Remove redundant MANIFEST.in
- Require Python >=3.10 and use scoped mkdocstrings cross-references
- Add git-cliff release automation and GitHub Actions workflows
- Deploy docs to Pages via GitHub Actions instead of gh-deploy
- Run checks via uv-managed venv instead of --system
