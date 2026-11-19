"""Hermetic test environment. Runs before any app or library import, because the library reads its
settings (AUTH_*, ...) and the app builds its settings singletons at import time."""

import os

HS256_SECRET = "test-secret-test-secret-test-secret"  # 32+ bytes avoids PyJWT's short-key warning

# Blank every optional knob so a developer's .env can't change results (env beats .env).
for _key in (
    "CONFIG_API_URL",
    "AUTH_JWKS_URL",
    "AUTH_OIDC_ISSUER",
    "AUTH_PUBLIC_KEY_PEM",
    "AUTH_PUBLIC_KEY_PATH",
    "AUTH_AUDIENCE",
    "AUTH_ISSUER",
    "AUTH_SSO_TOKEN_URL",
    "AUTH_SSO_CLIENT_ID",
    "AUTH_SSO_CLIENT_SECRET",
):
    os.environ[_key] = ""

# Required settings + inbound auth on (HS256), so route tests run with the global middleware.
os.environ.update(
    {
        "AWX_URL": "https://awx.test",
        "AWX_TOKEN": "test-token",
        "AUTH_ENABLED": "true",
        "AUTH_HS256_SECRET": HS256_SECRET,
    }
)
