# Contributing

This section is for people working **on** the library (extending it, fixing it, releasing it), as
opposed to consuming it. If you're using the package, start with the
[Tutorials](../tutorials/index.md).

## Where to look

- **[Development](development.md)** — set up your environment with uv, run the tests, the linter
  (Ruff), and the type checker (ty), and build the docs.
- **[Architecture](../explanation/architecture.md)** — the two toolsets, the three-layer connector
  pattern, and the public-surface / `_internal` boundary you should respect.
- **[Logging](../explanation/logging.md)** — the Loguru conventions new code should follow.
- **Extending the library:**
    - [Add a new connector](../how-to/add-a-connector.md) — the `models → client → service` pattern.
    - [Extend the FastAPI template](../how-to/extend-the-template.md) — add a middleware, route, or
      utility.

## House rules in one paragraph

Use **relative imports** within the package; keep the connector three-layer split; return typed
Pydantic models and raise typed errors (never raw dicts/HTTP codes); log with `from loguru import
logger` at the [standard levels](../explanation/logging.md); and keep new public symbols on the
narrow public surface (`utils` / `auth` / `security` / `errors`), with implementation under
`_internal/`. Run Ruff + the tests before opening a PR — see [Development](development.md).

Maintainer-only concerns (owners, the release/publish process) live in the repo's `MAINTAINERS.md`.
