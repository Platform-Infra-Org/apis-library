# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`tashtiot-apis-library` is a Python package published to an internal Artifactory PyPI registry. It provides two things:
1. **Infrastructure connectors** — async clients for AWX, ArgoCD, Bitbucket Server (Git), and HashiCorp Vault
2. **FastAPI app factory** — `general_create_app()` with built-in middleware, Prometheus metrics, Swagger UI, and Kubernetes health probes

Package is under `src/tashtiot_apis_library/`. Tests live in two places: `src/tests/` (connector tests, run with `unittest`) and `src/tashtiot_apis_library/fastapi_template/tests/` (template tests, run with `pytest`).

## Commands

**Install dependencies:**
```bash
pip install -e ".[dev]"
# or
pip install -r requirements.txt
```

**Run pytest (FastAPI template tests):**
```bash
cd src && pytest
```

**Run connector unit tests:**
```bash
cd src && python -m pytest tests/
```

**Run a single test file:**
```bash
cd src && python -m pytest tests/test_awx_client.py
```

**Build the package:**
```bash
python -m build
```

## Architecture

### Connector pattern

Each connector under `connectors/<name>/` follows a two-layer pattern:
- `client.py` — thin `httpx.AsyncClient` wrapper; raw HTTP calls, raises typed errors
- `service.py` — high-level class (e.g. `ArgoCD`, `AWX`) that orchestrates client calls with polling/retry logic

All clients inherit from `fastapi_template/_internal/database/basic_api.py:BaseAPI`, which manages an `httpx.AsyncClient` and supports both `async with` context manager and fire-and-forget usage.

All service methods return either a connector-specific response model (e.g. `AWXOperationResponse`, `ArgoOperationResponse`) or raise a subclass of `ExternalServiceError` (which extends `fastapi.HTTPException`). This means connector errors propagate naturally when used inside FastAPI route handlers.

### Response schema hierarchy

```
OperationResponse          (connectors/response_schemas.py)
├── AWXOperationResponse   (adds job_id)
└── ArgoOperationResponse  (adds app_name)
```

### FastAPI template

`general_create_app()` in `fastapi_template/_internal/__init__.py` is the entry point. It wires:
- Middlewares: request logging, process-time header, exception → `ExternalServiceError` translation
- Routes: `/metrics` (Prometheus), `/readiness` + `/liveness` (k8s probes), Swagger UI at `/docs`
- Static files: bundled Swagger/ReDoc assets served from `fastapi_template/static/swagger/`

Configuration is via `pydantic-settings` (`ApplicationSettings` in `_internal/utils/config.py`), reading env vars or a `.env` file. Key settings: `PORT`, `LOG_LEVEL`, `APP_NAME`, `DEBUG`, `PROXIED`, `PROXY_LISTEN_PATH`.

### Shared schemas

`schemas.py` contains Pydantic models shared across APIs:
- `OperationRequest` / `MetadataRequest` — base request body with project/network/region/space/environment metadata
- `ResourceSpec` — Kubernetes CPU/memory limits with format validation (e.g. `100m`, `512Mi`)
- `DefaultMetaSpec` / `NameNamespace` — k8s name+namespace helpers

### CI/CD

Woodpecker CI (`.woodpecker/build.yaml`) triggers on tags or manual runs. It updates `pyproject.toml` with the tag as the version, builds the wheel, and uploads to Artifactory at `https://artifactory.app.com/artifactory/pypi-local/`.
