# Tashtiot APIs Library

A unified Python package that bundles two largely independent toolsets for building production-ready
services:

1. **Infrastructure connectors** — async clients for **AWX**, **ArgoCD**, **Bitbucket Server**
   ("Git"), and **HashiCorp Vault** that validate responses, return typed Pydantic models, and raise
   typed exceptions.
2. **FastAPI template** — a reusable application factory (`general_create_app`) with built-in
   middleware, Prometheus metrics, health probes, self-hosted Swagger, structured Loguru logging,
   inbound JWT auth, outbound SSO, and a Remote Config API capability.

## Install

From the internal Artifactory PyPI (the normal path):

```bash
pip install tashtiot-apis-library
```

Or straight from git — no Artifactory access needed (pip/uv clone the tag and build it).
Pin a released tag for reproducibility:

```bash
# pip
pip install "git+https://github.com/Platform-Infra-Org/apis-library.git@v1.0.0"

# uv (add to a project, or --with for a one-off run)
uv add "git+https://github.com/Platform-Infra-Org/apis-library.git@v1.0.0"
```

Drop the `@v1.0.0` to install the tip of `master`. Each release also attaches the prebuilt wheel/sdist —
`gh release download v1.0.0 --repo Platform-Infra-Org/apis-library --pattern '*.whl'`, then
`pip install ./*.whl`.

## Quick look

Infrastructure connectors:

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault

awx = AWX(base_url="https://awx.example.com", token="token")
response = await awx.launch_job(job_template_id=1)
result = await awx.wait_for_job_completion(response.job_id)
```

FastAPI application factory:

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import settings

app = general_create_app()   # root route, /metrics, health probes, /docs, logging — all wired

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
```

There's no app to "run" here — the library is the product. See the
[tutorials](docs/tutorials/index.md) to go from zero to a running, authenticated service.

## Documentation

Full docs live in [`docs/`](docs/index.md) (built with MkDocs — `uv run mkdocs serve` to preview),
organised by [Diátaxis](https://diataxis.fr/):

- **[Tutorials](docs/tutorials/index.md)** — learning-oriented: your first app, securing an endpoint.
- **[How-to guides](docs/how-to/index.md)** — task recipes: connectors, SSO calls, Remote Config,
  generating dev keys, extending the library.
- **[Reference](docs/reference/index.md)** — every environment variable, the `gen-auth-material` CLI,
  and the auto-generated API reference.
- **[Explanation](docs/explanation/index.md)** — the architecture, the authentication design, and how
  logging works.
- **[Contributing](docs/contributing/index.md)** — dev setup, tooling, and conventions.

## Development

Uses the [Astral](https://astral.sh/) toolchain — **uv** (env/runner), **Ruff** (lint + format), and
**ty** (type check). uv is a fast runner; there's no committed `uv.lock` (it's a library, so
consumers resolve against the dependency ranges in `pyproject.toml`).

```bash
uv venv && uv pip install -e ".[dev,docs]"   # set up; plain pip also works
uv run pytest                                 # tests
uv run ruff check . --fix && uv run ruff format .   # lint + format
uv run ty check src                           # type check (advisory)
```

Ruff and pytest are enforced in CI (`.woodpecker/check.yaml`) on every push/PR; ty runs advisory.
See [Contributing → Development](docs/contributing/development.md) for the full workflow.
