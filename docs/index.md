# Tashtiot APIs Library

A unified Python package that bundles two largely independent toolsets for building
production-ready services:

1. **Infrastructure connectors** — async clients for **AWX** (Ansible Tower), **ArgoCD**,
   **Bitbucket Server** ("Git"), and **HashiCorp Vault**. Each validates responses, returns typed
   Pydantic models, and raises typed exceptions.
2. **FastAPI template** — a reusable application factory (`general_create_app`) with built-in
   middleware, Prometheus metrics, health probes, self-hosted Swagger, structured Loguru logging,
   inbound JWT auth, outbound SSO, and a Remote Config API capability.

You `pip install` the package and import from the top-level `tashtiot_apis_library` namespace —
there is no app to "run" here, the library is the product.

```bash
pip install tashtiot-apis-library
```

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault, general_create_app
```

## How this documentation is organised

These docs follow the [Diátaxis](https://diataxis.fr/) framework — four sections, each answering a
different need. Start in the corner that matches what you're trying to do:

<div class="grid cards" markdown>

- :material-school: **[Tutorials](tutorials/index.md)**

    Learning-oriented. Hands-on lessons that take you from zero to a working, secured app.

- :material-wrench: **[How-to guides](how-to/index.md)**

    Task-oriented. Focused recipes for a specific goal — read a file from Bitbucket, call a service
    with SSO, enable the Remote Config API.

- :material-book-open-variant: **[Reference](reference/index.md)**

    Information-oriented. The dry facts: every environment variable, the CLI flags, and the
    auto-generated API reference for every public symbol.

- :material-lightbulb: **[Explanation](explanation/index.md)**

    Understanding-oriented. The "why" — the architecture, the auth design, and how logging works.

</div>

Working **on** the library rather than with it? See **[Contributing](contributing/index.md)** for the
dev setup, tooling, and conventions.

## At a glance

| You want to… | Go to |
|---|---|
| Stand up a FastAPI service in minutes | [Tutorial: Your first app](tutorials/first-app.md) |
| Protect endpoints with JWT bearer auth | [Tutorial: Secure your API](tutorials/secure-your-api.md) |
| Talk to ArgoCD / AWX / Vault / Bitbucket | [How-to: connectors](how-to/use-awx-argocd-vault.md) |
| Authenticate outbound calls to other services | [How-to: Call services with SSO](how-to/call-services-with-sso.md) |
| Look up an environment variable | [Reference: Configuration](reference/configuration.md) |
| Understand the connector pattern | [Explanation: Architecture](explanation/architecture.md) |

!!! note "Requirements"
    Python ≥ 3.9. The package depends on FastAPI, httpx, Pydantic v2, Loguru, and PyJWT; the heavy
    auth and caching dependencies are imported lazily, so features you don't use cost nothing at
    import time.
