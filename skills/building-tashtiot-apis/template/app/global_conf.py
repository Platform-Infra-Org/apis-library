"""App-wide settings shared across modules. Settings the library owns (AUTH_*, AUTH_SSO_*,
CONFIG_REMOTE_*, PORT, LOG_LEVEL, PROXIED, ...) are NOT declared here: the library reads them."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GlobalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_TITLE: str = Field(default="My API", description="Title shown in Swagger.")
    APP_VERSION: str = Field(
        default="v0.0.0", description="Release version, injected from the git tag at build time."
    )

    # Required, no defaults: a missing value fails the app at startup, and secrets never live in code.
    AWX_URL: str = Field(..., description="AWX base URL.")
    AWX_TOKEN: str = Field(..., description="AWX API token.")

    # Remote Config provider: optional. Unset -> provider off, static conf defaults are used.
    CONFIG_API_URL: Optional[str] = Field(default=None, description="Upstream Config API base URL.")
    CONFIG_API_REMOTE_PREFIX: str = Field(
        default="/api/v1", description="Route prefix of the upstream Config API."
    )


global_config = GlobalSettings()
