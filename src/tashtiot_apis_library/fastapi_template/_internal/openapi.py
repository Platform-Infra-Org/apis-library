"""OpenAPI schema customization for the FastAPI Template.

Inbound authentication is enforced by ``AuthMiddleware``, not by FastAPI
dependencies, so the generated OpenAPI schema carries no security information
and Swagger UI shows no "Authorize" button. This module injects a global
bearer security scheme when auth is active, so the UI gains an Authorize tab
and "Try it out" requests send the token on the configured auth header.
"""

from typing import Any, Dict

from fastapi import FastAPI

from .utils import settings


def install_bearer_security_scheme(app: FastAPI) -> None:
    """Override ``app.openapi`` to advertise inbound JWT bearer auth.

    Adds a ``BearerAuth`` security scheme to the schema's components and applies
    it globally so every operation shows the lock icon and Swagger UI's
    Authorize dialog populates the auth header. The auth header name is taken
    from ``settings.AUTH_HEADER_NAME``:

    - ``Authorization`` (default) maps to an HTTP ``bearer`` scheme, so Swagger
      prepends ``Bearer `` to the pasted token automatically.
    - Any other header maps to an ``apiKey`` header scheme; the middleware still
      expects a ``Bearer <token>`` value, so the dialog tells the user to
      include the ``Bearer `` prefix themselves.
    """

    original_openapi = app.openapi

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        # Let FastAPI build (and cache) the base schema, then augment it.
        schema = original_openapi()

        header_name = settings.AUTH_HEADER_NAME
        if header_name.lower() == "authorization":
            scheme: Dict[str, Any] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Paste a JWT access token. Swagger sends it as "
                    "`Authorization: Bearer <token>`."
                ),
            }
        else:
            scheme = {
                "type": "apiKey",
                "in": "header",
                "name": header_name,
                "description": (
                    f"Provide `Bearer <token>` in the `{header_name}` header."
                ),
            }

        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {})["BearerAuth"] = scheme
        # Apply globally so every operation is marked as secured.
        schema["security"] = [{"BearerAuth": []}]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
