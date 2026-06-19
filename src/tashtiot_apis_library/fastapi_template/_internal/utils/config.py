"""Settings definition for the FastAPI Template application factory."""

from typing import Optional

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

    # --- Inbound JWT authentication ---

    AUTH_ENABLED: bool = Field(
        default=False,
        description="Runtime master switch for inbound JWT bearer authentication.",
        examples=[True, False],
    )

    AUTH_HEADER_NAME: str = Field(
        default="Authorization",
        description="Request header carrying the bearer token.",
        examples=["Authorization", "X-Auth-Token"],
    )

    AUTH_HS256_SECRET: Optional[str] = Field(
        default=None,
        description="Shared secret for HS256 verification. If set, selects HS256 mode.",
        examples=["super-secret-value"],
    )

    AUTH_JWKS_URL: Optional[str] = Field(
        default=None,
        description="JWKS/OIDC endpoint URL for RS256 verification with key caching. Selects JWKS mode.",
        examples=["https://idp.example.com/.well-known/jwks.json"],
    )

    AUTH_PUBLIC_KEY_PEM: Optional[str] = Field(
        default=None,
        description="Inline PEM public key for offline RS256 verification. Selects local-pubkey mode.",
        examples=["-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"],
    )

    AUTH_PUBLIC_KEY_PATH: Optional[str] = Field(
        default=None,
        description="Filesystem path to a PEM public key (alternative to AUTH_PUBLIC_KEY_PEM). Selects local-pubkey mode.",
        examples=["/etc/secrets/jwt_pub.pem"],
    )

    AUTH_ALGORITHMS: list[str] = Field(
        default=["RS256"],
        description="Allowed JWT signing algorithms. HS256 mode forces ['HS256'].",
        examples=[["RS256"], ["HS256"], ["RS256", "RS384"]],
    )

    AUTH_AUDIENCE: Optional[str] = Field(
        default=None,
        description="Expected 'aud' claim. When None, audience is not validated.",
        examples=["my-api"],
    )

    AUTH_ISSUER: Optional[str] = Field(
        default=None,
        description="Expected 'iss' claim. When None, issuer is not validated.",
        examples=["https://idp.example.com/"],
    )

    AUTH_JWKS_CACHE_TTL: int = Field(
        default=3600,
        description="Seconds to cache fetched JWKS keys before refetching.",
        examples=[3600, 300],
    )

    AUTH_EXCLUDE_PATHS: list[str] = Field(
        default=[
            "/health", "/metrics", "/static", "/docs", "/redoc",
            "/openapi.json", "/.well-known", "/liveness", "/readiness",
        ],
        description="Path prefixes/regexes that bypass authentication. Matched like LOG_REQUEST_EXCLUDE_PATHS.",
        examples=[["/health", "/metrics"]],
    )

    # --- Outbound SSO (OAuth2 client_credentials) ---

    AUTH_SSO_TOKEN_URL: Optional[str] = Field(
        default=None,
        description="OAuth2 token endpoint for the client_credentials grant. Required to use the SSO token client.",
        examples=["https://idp.example.com/oauth/token", "https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token"],
    )

    AUTH_SSO_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="OAuth2 client id for the client_credentials grant.",
        examples=["my-service"],
    )

    AUTH_SSO_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="OAuth2 client secret for the client_credentials grant.",
        examples=["super-secret-value"],
    )

    AUTH_SSO_SCOPE: Optional[str] = Field(
        default=None,
        description="Space-separated OAuth2 scopes to request. When None, no scope is sent.",
        examples=["api.read api.write"],
    )

    AUTH_SSO_AUDIENCE: Optional[str] = Field(
        default=None,
        description="Optional 'audience' parameter sent in the token request (e.g. Auth0). When None, it is omitted.",
        examples=["https://api.example.com"],
    )

    AUTH_SSO_AUTH_STYLE: str = Field(
        default="post",
        description="How client credentials are sent to the token endpoint: 'post' (form body) or 'basic' (HTTP Basic).",
        examples=["post", "basic"],
    )

    AUTH_SSO_VERIFY_SSL: bool = Field(
        default=True,
        description="Verify the TLS certificate of the SSO token endpoint.",
        examples=[True, False],
    )

    AUTH_SSO_TIMEOUT: float = Field(
        default=10.0,
        description="Timeout in seconds for token endpoint requests.",
        examples=[10.0, 5.0],
    )

    AUTH_SSO_EXPIRY_SKEW: int = Field(
        default=30,
        description="Refresh the cached access token this many seconds before its expiry.",
        examples=[30, 60],
    )

