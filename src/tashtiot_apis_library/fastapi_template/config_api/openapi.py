import re
from typing import Callable, Sequence

from fastapi import FastAPI
from loguru import logger

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

    prefix = "#/components/schemas/"

    def _inject(schema: dict, name: str) -> bool:
        """Set the live-allowlist ``enum`` for coordinate field ``name`` on ``schema``
        (the JSON Schema object for one field). Returns whether it did (a no-op for
        non-coordinate names or an empty allowlist).

        Optional/nullable fields render as ``{"anyOf": [{"type": "string"}, ...]}`` --
        Swagger only shows a dropdown when the ``enum`` lives **inside** the string
        branch, not as a top-level sibling of ``anyOf`` -- so place it there; flat
        ``{"type": "string"}`` fields get it directly."""
        values = allowlists.get(name)
        if not values:
            return False
        enum = sorted(values)
        branches = [
            b
            for key in ("anyOf", "oneOf")
            for b in schema.get(key, [])
            if isinstance(b, dict) and b.get("type") == "string"
        ]
        if branches:
            for b in branches:
                b["enum"] = enum
        else:
            schema["enum"] = enum
        return True

    def _refs_in(prop_schema: dict) -> list:
        """Component-schema names reachable from a property schema -- directly, through
        an ``anyOf``/``oneOf``/``allOf`` branch, or as array ``items``."""
        out = []
        if prop_schema.get("$ref"):
            out.append(prop_schema["$ref"])
        for key in ("anyOf", "oneOf", "allOf"):
            out += [
                s["$ref"] for s in prop_schema.get(key, []) if isinstance(s, dict) and s.get("$ref")
            ]
        items = prop_schema.get("items")
        if isinstance(items, dict) and items.get("$ref"):
            out.append(items["$ref"])
        return [r[len(prefix) :] for r in out if isinstance(r, str) and r.startswith(prefix)]

    def _inject_component(openapi_schema: dict, comp_name: str, visited: set) -> bool:
        """Recursively inject coordinate enums into a component's properties and any
        nested component it references (``visited`` guards against reference cycles).
        NOTE: the component schema is patched in place, so a model shared across routes
        gets the enums on all of them -- intended (one source of truth)."""
        if comp_name in visited:
            return False
        visited.add(comp_name)
        props = (
            openapi_schema.get("components", {})
            .get("schemas", {})
            .get(comp_name, {})
            .get("properties", {})
        )
        touched = False
        for prop_name, prop_schema in props.items():
            touched |= _inject(prop_schema, prop_name)
            for ref in _refs_in(prop_schema):
                touched |= _inject_component(openapi_schema, ref, visited)
        return touched

    def _inject_body(openapi_schema: dict, operation: dict) -> bool:
        """Inject into the JSON request body's model (and everything it nests)."""
        ref = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("$ref", "")
        )
        if not ref.startswith(prefix):
            return False
        return _inject_component(openapi_schema, ref[len(prefix) :], set())

    # Last set of routes we logged an injection for -- so we log once per change,
    # not on every schema regeneration (the poller nulls the schema each cycle).
    logged_injection = None

    def custom_openapi() -> dict:
        nonlocal logged_injection
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = base_openapi()

        http_methods = ("get", "post", "put", "patch", "delete")
        injected: set = set()  # routes that actually received a coordinate enum
        for pattern in path_patterns:
            for path, path_item in openapi_schema.get("paths", {}).items():
                if not pattern.fullmatch(path):
                    continue
                touched = False
                for method in http_methods:
                    operation = path_item.get(method, {})
                    # Query/path parameters.
                    for param in operation.get("parameters", []):
                        touched |= _inject(param.get("schema", {}), param.get("name", ""))
                    # JSON request body -- recursed into nested sub-models.
                    touched |= _inject_body(openapi_schema, operation)
                if touched:
                    injected.add(path)

        frozen = frozenset(injected)
        if frozen and frozen != logged_injection:
            logger.info(
                "Remote Config API: injected live coordinate enums into routes: {}",
                sorted(frozen),
            )
            logged_injection = frozen

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi
