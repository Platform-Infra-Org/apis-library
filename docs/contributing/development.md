# Development

How to set up a working environment and run the project's checks. The toolchain is
[Astral](https://astral.sh/)'s: **uv** (environment + runner), **Ruff** (lint + format), and **ty**
(type check).

## Environment

uv is used as a fast runner — there is **no committed `uv.lock`**. This is a library, so consumers
resolve against the dependency *ranges* in `pyproject.toml`; a lockfile would only pin our own dev
environment and churn against the setuptools-scm version. Plain `pip` works too.

```bash
uv venv                              # create .venv
uv pip install -e ".[dev,docs]"      # dev tools + docs toolchain
# equivalently, without uv:
#   python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,docs]"
```

## Tests

The suite lives in the top-level `tests/` tree and runs from the repo root:

```bash
uv run pytest                                         # whole suite (with coverage)
uv run pytest tests/connectors/test_awx_client.py     # one file
```

## Lint & format (Ruff)

```bash
uv run ruff format .          # format
uv run ruff check . --fix     # lint, auto-fixing what it safely can
```

Ruff config is in `pyproject.toml` (`[tool.ruff]`). The rule set is intentionally conservative;
`UP` (pyupgrade), `TID252` (it would ban the package's relative imports), and `G` (the codebase mixes
f-string and `{}`-style Loguru calls) are deliberately **not** enabled.

## Type check (ty)

```bash
uv run ty check src           # advisory — scoped to the shipped package
```

ty is **advisory / non-blocking**: it's beta and has no Pydantic plugin yet, so it reports a known
baseline of mostly Optional-annotation and Pydantic false positives. Treat it as a signal, not a
gate.

## Pre-commit hooks

```bash
uv run pre-commit install                                  # enable on every commit
uv run pre-commit run --all-files                          # run ruff + ruff-format now
uv run pre-commit run ty --hook-stage manual --all-files   # run the advisory ty hook
```

`ruff` and `ruff-format` run on every commit; `ty` is a manual-stage hook so its beta noise never
blocks a commit.

## Docs

The docs you're reading are built with MkDocs (Material) + mkdocstrings:

```bash
uv run mkdocs serve            # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict   # what CI-equivalent checks expect: fails on any broken link
```

The API reference pages are generated from docstrings, so keep docstrings accurate when you change
public signatures.

## Before you open a PR

- `uv run ruff format . && uv run ruff check .` — clean.
- `uv run pytest` — green.
- `uv run mkdocs build --strict` — clean, if you touched docs or public docstrings.

CI (`.woodpecker/check.yaml`) runs Ruff + pytest + advisory ty on every push/PR.
