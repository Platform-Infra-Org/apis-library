"""High-level, one-call wiring for the Remote Config capability.

``enable_remote_config_api`` builds the provider (with the package-side, selectable
outbound auth), installs the dynamic OpenAPI enum patcher and the coordinate
validation -> 422 handler, and registers the background allowlist poller. The
service is left to define its own routes against the returned provider.
"""

from typing import Optional, Sequence

import httpx
from fastapi import FastAPI
from loguru import logger

from .conf import ConfigRemoteSettings
from .errors import install_coordinate_validation_error_handler
from .openapi import make_config_openapi
from .provider import RemoteConfigProvider


def enable_remote_config_api(
    app: FastAPI,
    *,
    base_url: str,
    remote_prefix: str,
    coordinate_paths: Sequence[str],
    cache_ttl: int = 60,
    serve_stale_on_error: bool = False,
    poll_interval: int = 5,
    settings: Optional[ConfigRemoteSettings] = None,
    auth: Optional[httpx.Auth] = None,
    enable_polling: bool = True,
) -> RemoteConfigProvider:
    """Wire the Remote Config capability onto ``app`` and return its provider.

    Parameters
    ----------
    base_url, remote_prefix:
        Where the upstream Config API lives and the route prefix under which it
        serves ``/projects``, ``/config`` and ``/naming``.
    coordinate_paths:
        Route paths whose coordinate fields get the live ``enum`` dropdowns injected.
        Each entry is a **regex string** (``re.fullmatch`` against route paths), so a
        plain path targets exactly itself (``["/config", "/naming"]``) and a pattern
        can target a family of routes (``[r"/api/v\\d+/.*/(config|naming)"]``). Not
        limited to two.
    settings:
        Package-side ``CONFIG_REMOTE_*`` settings driving the outbound auth method;
        defaults to a freshly-read [`ConfigRemoteSettings`][ConfigRemoteSettings].
    auth:
        Explicit outbound `httpx.Auth` that overrides ``settings`` (escape
        hatch / tests). When given, ``settings`` is not consulted for auth.
    serve_stale_on_error:
        When ``True``, an unreachable or 5xx upstream falls back to the last
        successfully-fetched value for that key (last-known-good, unbounded) instead
        of raising ``502``. Defaults to ``False`` (preserve the strict 502 contract).
    enable_polling:
        Register the background allowlist poller (the task is appended to
        ``app.state.async_background_tasks``, which ``general_create_app``'s
        lifespan launches at startup). Set ``False`` to drive polling yourself.
    """
    if auth is not None:
        resolved_auth, api_kwargs = auth, {}
        auth_source = "explicit"
    else:
        effective_settings = settings or ConfigRemoteSettings()
        resolved_auth, api_kwargs = effective_settings.resolve_auth()
        auth_source = effective_settings.CONFIG_REMOTE_AUTH_METHOD

    provider = RemoteConfigProvider(
        base_url,
        remote_prefix,
        auth=resolved_auth,
        cache_ttl=cache_ttl,
        serve_stale_on_error=serve_stale_on_error,
        **api_kwargs,
    )

    logger.info(
        "Remote Config API enabled: upstream={}{} auth={} polling={} (interval={}s).",
        base_url,
        remote_prefix,
        auth_source,
        enable_polling,
        poll_interval,
    )

    # Wrap the existing app.openapi (preserving any bearer-security scheme) with the
    # dynamic enum patcher, and translate escaped coordinate validation -> 422.
    app.openapi = make_config_openapi(app, coordinate_paths)
    install_coordinate_validation_error_handler(app)

    # Always seed the allowlists once at startup so validation + enum injection work even
    # with polling off; when polling is on, keep refreshing after that first crawl.
    async def _background() -> None:
        if enable_polling:
            await provider.start_periodic_polling(app, interval_seconds=poll_interval)
        else:
            await provider.crawl_and_sync_keys(app)

    registry = getattr(app.state, "async_background_tasks", None)
    if registry is None:
        # App not built by general_create_app: keep the registry available, but note the
        # lifespan won't launch it -- the caller must seed/poll themselves.
        app.state.async_background_tasks = []
        registry = app.state.async_background_tasks
        logger.warning(
            "enable_remote_config_api: app has no general_create_app lifespan; the allowlist "
            "task was registered but will not auto-start -- seed it yourself with crawl_and_sync_keys()."
        )
    registry.append(_background)

    return provider
