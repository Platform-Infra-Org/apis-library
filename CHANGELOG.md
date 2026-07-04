# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The version is derived from git tags by
setuptools-scm.

## [Unreleased]

### CI

- Split build/ci changelog groups and exclude ci from releasing
## [1.1.1] - 2026-07-02

### Documentation

- Add OIDC/JWKS how-to and SSO client-scope setup

### CI

- Skip release for docs-only merges, refresh unreleased changelog
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

### Build

- Configure Ruff, ty, and uv (no lockfile) + docs deps
- Remove redundant MANIFEST.in
- Require Python >=3.10 and use scoped mkdocstrings cross-references

### CI

- Enforce Ruff/ty/pytest via pre-commit and Woodpecker
- Add git-cliff release automation and GitHub Actions workflows
- Deploy docs to Pages via GitHub Actions instead of gh-deploy
- Run checks via uv-managed venv instead of --system
