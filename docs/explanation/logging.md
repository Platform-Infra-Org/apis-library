# Logging

The library logs with **Loguru, everywhere** — and does so through a single shared logger configured
once. This page explains how that works and the conventions it follows.

## One global logger, configured at import

Unlike the standard library's `logging` (where each module fetches its own named logger), Loguru
exports a single pre-instantiated `logger` object. Every module does:

```python
from loguru import logger
```

…and they all bind the **same** object. Configuration doesn't create a new logger — it mutates that
shared object's *sinks*. The library does this once, as an import side-effect, in
`_internal/utils/__init__.py`:

```python
logger_config = Logger(settings.LOG_LEVEL)
```

`Logger.__init__` runs two steps (in `_internal/utils/logger.py`):

- **`setup_loguru()`** — `logger.remove()` drops the default handler, then `logger.add(sys.stdout, …)`
  installs a single colored stdout sink with a custom formatter (which does smart source-location
  detection) at the configured level.
- **`configure_uvicorn()`** — installs a `UvicornHandler` that bridges stdlib/uvicorn log records into
  the same Loguru sink, so framework logs and library logs share one stream.

Because this runs the first time anything imports `fastapi_template._internal.utils` (which nearly
everything does, transitively), logging is configured before any request — or even before app wiring.

## Consequences worth knowing

- **It's order-dependent, last-writer-wins.** The configuration calls `logger.remove()`, which clears
  *all* sinks — including ones you added yourself before importing the library. If you want your own
  sink, add it *after* importing the package.
- **`LOG_LEVEL` is read once.** The sink is added with `level=settings.LOG_LEVEL` a single time, so
  changing the variable after import has no effect — set `LOG_LEVEL` before the process starts.

## The level convention

The connectors are the most thoroughly-logged code and set the house style the rest of the library
(including auth, SSO, and the Remote Config API) follows:

| Level | Used for |
|---|---|
| **INFO** | User-facing operations and state transitions |
| **DEBUG** | Internal reads, polling loops, cache decisions, key resolution |
| **WARNING** | Misconfiguration or degraded-but-recoverable behavior |
| **ERROR** | External-service failures — logged *immediately before* raising the typed error |

A record may pass `extra={"location": "..."}` to override the displayed source label — the request
logger uses `"Request"`/`"Response"`, and the auth middleware uses `"Auth"`.

## See also

- [Configuration: `LOG_LEVEL`](../reference/configuration.md#core-settings)
