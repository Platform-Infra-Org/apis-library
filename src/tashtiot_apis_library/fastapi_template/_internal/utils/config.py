"""Settings definition for the FastAPI Template application factory."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ApplicationSettings"]


class ApplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PORT: int = Field(
        default=8000,
        description="The port the application will run on.",
        examples=[8000, 8080],
    )

    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level for the application.",
        examples=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    DEBUG: bool = Field(
        default=False,
        description="Whether the application should run in debug mode.",
        examples=[True, False],
    )

    RELOAD_INCLUDES: list[str] = Field(
        default=[".env"],
        description="List of paths to files that triggers reloading.",
        examples=[["*.py"]]
    )

    APP_NAME: str = Field(
        default="MyApp",
        description="The name of the application.",
        examples=["UserService", "PaymentAPI"],
    )

    PROCESS_TIME_HEADER: str = Field(
        default="X-Process-Time",
        description="Header name to include process time in responses.",
        examples=["X-Process-Time", "X-Response-Time"],
    )

    OPENAPI_VERSION: str = Field(
        default="3.0.2",
        description="OpenAPI version used for the Swagger UI.",
        examples=["3.0.2", "3.1.0"],
    )

    OPENAPI_JSON_URL: str = Field(
        default="/openapi.json",
        description="Path to the OpenAPI JSON schema.",
        examples=["/openapi.json", "/api/openapi.json"],
    )

    PROXIED: bool = Field(
        default=False,
        description="Whether the Api is behind a proxy.",
        examples=[True, False],
    )

    PROXY_LISTEN_PATH: str = Field(
        default="/",
        description="Path where the proxy listens for requests.",
        examples=["/proxy", "/api/proxy"],
    )

    SWAGGER_STATIC_FILES: str = Field(
        default="/static/swagger",
        description="URL path to serve Swagger UI static files.",
        examples=["/static/swagger"],
    )

    SWAGGER_OPENAPI_JSON_URL: str = OPENAPI_JSON_URL

    LOG_REQUEST_EXCLUDE_PATHS: list[str] = Field(
        default=["/health", "/metrics", "/static", "/docs", "/redoc", "/openapi.json", "/.well-known"],
        description="List of paths to ignore for logging.",
        examples=[["/health", "/metrics"]],
    )

    PROBE_READINESS_PATH: str = Field(
        default="/readiness",
        description="Path for readiness probe.",
        examples=["/readiness", "/api/readiness"],
    )

    PROBE_LIVENESS_PATH: str = Field(
        default="/liveness",
        description="Path for liveness probe.",
        examples=["/liveness", "/api/liveness"],
    )

