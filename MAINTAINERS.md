# Maintainers

Maintainer-facing notes for `tashtiot_apis_library`: who owns it, how it's released, and where the
rest of the documentation lives.

> Architecture, conventions, dev setup, and how to extend the library are **not** repeated here —
> they live in the docs (`docs/`). This file is intentionally limited to maintainer concerns.

## Owners

| Maintainer | |
|---|---|
| Yehonatan Magen | review / release |
| Alon Elimelech | review / release |
| Chaim Mendelson | review |
| Daniel Tsytrinbaum | review |

Ping any owner for reviews; releases are cut by a release-capable owner.

## Versioning & releasing

The version is **derived from git tags by setuptools-scm** — nothing is hardcoded in source
(`pyproject.toml` declares `dynamic = ["version"]`). To cut a release:

```bash
git tag 0.4.0        # PEP 440 version, no leading "v"
git push --tags
```

That tag triggers the publish pipeline. Between tags, the version is a dev string
(`0.4.1.devN+g<hash>`); see [Explanation → … setuptools-scm](docs/explanation/architecture.md) and
`pyproject.toml` `[tool.setuptools_scm]`.

## CI pipelines (Woodpecker)

| File | Trigger | What it does |
|------|---------|--------------|
| `.woodpecker/check.yaml` | `push`, `pull_request` | Installs with uv, runs `ruff check`, `ruff format --check`, `pytest`, and `ty check src` (advisory). |
| `.woodpecker/build.yaml` | `tag`, `manual` | Rewrites the distribution `name`, exports `SETUPTOOLS_SCM_PRETEND_VERSION="${CI_COMMIT_TAG}"`, builds the sdist + wheel, and uploads them to Artifactory (`pypi-local`). |

`SETUPTOOLS_SCM_PRETEND_VERSION` pins the built version to the tag, so the publish doesn't depend on
git clone depth / tag reachability in CI.

## Build locally (sanity check before tagging)

```bash
SETUPTOOLS_SCM_PRETEND_VERSION=9.9.9 uv build   # -> dist/*-9.9.9*.whl / .tar.gz
```

## Everything else

- **Develop / run checks** → [docs/contributing/development.md](docs/contributing/development.md)
- **Architecture & conventions** → [docs/explanation/architecture.md](docs/explanation/architecture.md)
- **Add a connector** → [docs/how-to/add-a-connector.md](docs/how-to/add-a-connector.md)
- **Extend the FastAPI template** → [docs/how-to/extend-the-template.md](docs/how-to/extend-the-template.md)
- **Logging conventions** → [docs/explanation/logging.md](docs/explanation/logging.md)
