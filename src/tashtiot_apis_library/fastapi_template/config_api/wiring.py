"""High-level, one-call wiring for the Remote Config capability.

``enable_remote_config_api`` builds the provider (with the package-side, selectable
outbound auth), installs the dynamic OpenAPI enum patcher and the coordinate
validation -> 422 handler, and registers the background allowlist poller. The
service is left to define its own routes against the returned provider.
"""
from typing import Any, Optional

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
    config_path: str,
    naming_path: str,
    cache_ttl: int = 60,
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
    config_path, naming_path:
        This service's own route paths whose coordinate query params get the live
        ``enum`` dropdowns injected.
    settings:
        Package-side ``CONFIG_REMOTE_*`` settings driving the outbound auth method;
        defaults to a freshly-read :class:`ConfigRemoteSettings`.
    auth:
        Explicit outbound :class:`httpx.Auth` that overrides ``settings`` (escape
        hatch / tests). When given, ``settings`` is not consulted for auth.
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
    app.openapi = make_config_openapi(app, config_path=config_path, naming_path=naming_path)
    install_coordinate_validation_error_handler(app)

    if enable_polling:
        async def _poll() -> None:
            await provider.start_periodic_polling(app, interval_seconds=poll_interval)

        registry = getattr(app.state, "async_background_tasks", None)
        if registry is None:
            # App not built by general_create_app: keep the registry available, but
            # note the lifespan won't launch it -- the caller must drive polling.
            app.state.async_background_tasks = []
            registry = app.state.async_background_tasks
            logger.warning(
                "enable_remote_config_api: app has no general_create_app lifespan; "
                "the allowlist poller was registered but will not auto-start."
            )
        registry.append(_poll)

    return provider
