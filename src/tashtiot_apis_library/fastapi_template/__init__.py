"""FastAPI application template package.

This module provides a reusable FastAPI application factory with built-in
middleware, monitoring, and documentation support.
"""

from ._internal import general_create_app, settings

__all__ = ["general_create_app", "settings", "enable_remote_config_api"]


def __getattr__(name: str):
    # Imported lazily so consumers that don't use the Remote Config capability
    # don't pull in its dependencies (e.g. aiocache).
    if name == "enable_remote_config_api":
        from .config_api import enable_remote_config_api

        return enable_remote_config_api
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
