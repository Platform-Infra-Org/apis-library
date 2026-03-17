"""Utility helpers for general application configuration."""

from __future__ import annotations

from pydantic import ValidationError
from loguru import logger

from .config import ApplicationSettings
from .logger import Logger

__all__ = ["settings", "logger_config", "ApplicationSettings"]


def _apply_proxy_overrides(settings: ApplicationSettings) -> None:
    if settings.PROXIED:
        settings.PROXY_LISTEN_PATH = settings.PROXY_LISTEN_PATH.rstrip("/")
        settings.SWAGGER_STATIC_FILES = (
            settings.PROXY_LISTEN_PATH + "/" + settings.SWAGGER_STATIC_FILES.lstrip("/")
        )
        settings.SWAGGER_OPENAPI_JSON_URL = (
            settings.PROXY_LISTEN_PATH + "/" + settings.OPENAPI_JSON_URL.lstrip("/")
        )

        settings.LOG_REQUEST_EXCLUDE_PATHS.extend([
            settings.PROXY_LISTEN_PATH + "/" + path.lstrip("/")
            for path in settings.LOG_REQUEST_EXCLUDE_PATHS
        ])

    else:
        settings.PROXY_LISTEN_PATH = ""


try:
    settings = ApplicationSettings()
    _apply_proxy_overrides(settings)
except ValidationError as e:
    logger.error(
        f"Configuration error: {e}\n"
        "Please ensure that all required environment variables are set correctly."
    )
    raise SystemExit(1) from e

logger_config = Logger(settings.LOG_LEVEL)
