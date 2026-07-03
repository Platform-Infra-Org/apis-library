import re
from typing import Callable, Sequence

from fastapi import FastAPI

from .models import (
    LIVE_ALLOWED_ENVIRONMENTS,
    LIVE_ALLOWED_ISLANDS,
    LIVE_ALLOWED_NETWORKS,
    LIVE_ALLOWED_PROJECTS,
    LIVE_ALLOWED_REGIONS,
    LIVE_ALLOWED_SPACES,
)


def make_config_openapi(app: FastAPI, coordinate_paths: Sequence[str]) -> Callable[[], dict]:
    """Build an ``app.openapi`` replacement that injects the live allowlists as
    ``enum`` values into the coordinate fields on the routes matched by
    ``coordinate_paths`` -- whether they arrive as **query/path parameters** or
    inside a **JSON request body**.

    Each ``coordinate_paths`` entry is a **regex string** matched with
    ``re.fullmatch`` against every route path, so one entry can target a family of
    routes (``r"/api/v\\d+/infra/(config|naming)"``). A plain path is just a literal
    regex that matches only itself, so exact-path entries keep working; escape regex
    metacharacters (``.``, ``+``, ...) if you need them literal. FastAPI path params
    like ``{id}`` are matched literally. An entry that matches no route is a no-op.

    This **wraps** whatever ``app.openapi`` is already installed rather than
    rebuilding the schema from scratch, so it composes with the library's other
    OpenAPI customizations -- notably the bearer-auth security scheme that
    ``general_create_app`` injects when auth is enabled (the source of Swagger's
    Authorize button). Replacing ``app.openapi`` outright would drop it.

    Title/version/openapi_version come from the underlying generator (set on the
    FastAPI app at construction). The background polling loop nulls
    ``app.openapi_schema`` whenever the allowlists change, so the next schema
    request regenerates -- through the same wrapped chain -- with current enums.
    """

    # Captured at wire-up time: the generator installed before us (the library's
    # bearer-security wrapper when auth is on, else FastAPI's default).
    base_openapi = app.openapi

    # Compile each entry once (fail fast on a bad pattern); matched with fullmatch
    # against route paths at schema-generation time. A plain path is a literal regex.
    try:
        path_patterns = [re.compile(p) for p in coordinate_paths]
    except re.error as exc:
        raise ValueError(f"Invalid coordinate_paths regex {exc.pattern!r}: {exc}") from exc

    # name -> live allowlist set (mutated in place by the poller, so a captured
    # reference always reflects the current values).
    allowlists = {
        "space": LIVE_ALLOWED_SPACES,
        "network": LIVE_ALLOWED_NETWORKS,
        "region": LIVE_ALLOWED_REGIONS,
        "island": LIVE_ALLOWED_ISLANDS,
        "environment": LIVE_ALLOWED_ENVIRONMENTS,
        "project": LIVE_ALLOWED_PROJECTS,
    }

    def _inject(schema: dict, name: str) -> None:
        """Set ``schema['enum']`` from the live allowlist for ``name`` (a no-op
        for non-coordinate names or an empty allowlist). ``schema`` is the JSON
        Schema object for one field -- a parameter's ``schema`` or a body
        model's property."""
        values = allowlists.get(name)
        if values:
            schema["enum"] = sorted(values)

    def _body_property_schemas(openapi_schema: dict, operation: dict) -> dict:
        """Resolve an operation's JSON request body to the property schemas of
        its referenced component (``{prop_name: schema}``), or ``{}`` if the body
        isn't a ``$ref`` to a component schema."""
        ref = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("$ref", "")
        )
        prefix = "#/components/schemas/"
        if not ref.startswith(prefix):
            return {}
        name = ref[len(prefix) :]
        return (
            openapi_schema.get("components", {})
            .get("schemas", {})
            .get(name, {})
            .get("properties", {})
        )

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = base_openapi()

        http_methods = ("get", "post", "put", "patch", "delete")
        for pattern in path_patterns:
            for path, path_item in openapi_schema.get("paths", {}).items():
                if not pattern.fullmatch(path):
                    continue
                for method in http_methods:
                    operation = path_item.get(method, {})
                    # Query/path parameters.
                    for param in operation.get("parameters", []):
                        _inject(param.get("schema", {}), param.get("name", ""))
                    # JSON request-body model. NOTE: the body's component schema is
                    # patched in place, so a model shared across several routes gets
                    # the enums on all of them -- intended (one source of truth).
                    for prop_name, prop_schema in _body_property_schemas(
                        openapi_schema, operation
                    ).items():
                        _inject(prop_schema, prop_name)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi
