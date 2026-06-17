# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`tashtiot_apis_library` is a distributable Python library (published to an internal Artifactory PyPI repo) that ships two largely independent toolsets under one package:

1. **Infrastructure connectors** (`connectors/`) — async clients for ArgoCD, AWX (Ansible Tower), Bitbucket Server ("Git"), and HashiCorp Vault.
2. **FastAPI template** (`fastapi_template/`) — a reusable FastAPI application factory (`general_create_app`) with built-in middleware, metrics, probes, and Swagger.

Consumers `pip install` this package and import from the top-level `tashtiot_apis_library` namespace. There is no application to "run" here — the library is the product.

## Commands

```bash
pip install -e ".[dev]"          # install with dev deps (pytest, pytest-asyncio, respx)

# Two separate test suites with two configs — run from the directory whose config you want:
cd src && pytest                 # uses src/pytest.ini → src/tests/ (unittest-style, with coverage)
pytest                           # uses pyproject [tool.pytest.ini_options] → fastapi_template/tests/

pytest src/tests/test_awx_client.py                    # single file
pytest src/tests/test_awx_client.py::TestAWXOperations # single class
python -m build                  # build sdist+wheel (what CI does before publishing)
```

There is no linter configured. Python >= 3.9.

### Two pytest configurations (important)
- `src/pytest.ini`: `testpaths = tests`, runs with `--cov`, expects `pythonpath = .` (so tests use package-relative imports like `from ..tashtiot_apis_library...`). Run it from inside `src/`.
- root `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths = ["tashtiot_apis_library/fastapi_template/tests"]`, declares custom markers (`asyncio`, `rest`, `ftp`) and enables live log output.

They cover different trees; running `pytest` from the wrong directory will collect the wrong suite or fail on imports.

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
- Public surface is intentionally narrow: `fastapi_template/__init__.py` exports only `general_create_app`; `fastapi_template/utils.py` exports only `BaseAPI` and `settings`. Everything under `_internal/` is private implementation.
- Configuration is `pydantic-settings` (`_internal/utils/config.py`, `ApplicationSettings`), loaded from env vars / `.env` (`PORT`, `LOG_LEVEL`, `APP_NAME`, `DEBUG`, probe paths, swagger paths, etc.). Logging is Loguru throughout.

### Public API
Top-level `tashtiot_apis_library/__init__.py` re-exports the connector services, error types, `general_create_app`, and the shared request schemas from `schemas.py` (`OperationRequest`, `ResourceSpec`, `DefaultMetaSpec`, `NameNamespace` — Kubernetes/PaaS-oriented Pydantic models with CPU/memory regex validation). Keep `__all__` here in sync when adding exports.

## Packaging notes
- Both `pyproject.toml` (the active build backend, setuptools) and a legacy `setup.py` exist with **divergent versions and dependency lists**. CI uses `pyproject.toml`: `.woodpecker/build.yaml` rewrites the `name`/`version` from the git tag (`CI_COMMIT_TAG`) at build time, so the `version` committed in `pyproject.toml` is not the published one. Publishing is triggered by a `tag` or `manual` Woodpecker event and `curl`s the wheel/sdist to Artifactory.
- `fastapi_template/tests/` is excluded from the built package (`pyproject.toml` packages.find exclude); static swagger assets are included as package data.
- `terraform_runner.py` is not wired into the package exports and imports modules not present in the tree (`logger`, `from schemas import ...`, `status_code_mappings`); treat it as dead/legacy unless you are deliberately resurrecting it.
