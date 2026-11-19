from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DnsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_PREFIX: str = Field(
        default="/api/my-api/v1/dns", description="Path prefix: /api/<api>/v<N>/<resource>."
    )
    API_TAGS: List[str] = Field(
        default_factory=lambda: ["v1 - DNS"], description="Swagger grouping."
    )
    AWX_CREATE_DNS_TEMPLATE_ID: int = Field(
        default=2178, description="Static fallback when Remote Config is off or has no value."
    )


config = DnsSettings()
