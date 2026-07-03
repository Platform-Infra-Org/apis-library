"""make_config_openapi injects the live allowlists as enum dropdowns."""

import pytest
from fastapi import APIRouter, Depends, FastAPI

from tashtiot_apis_library.fastapi_template.config_api import (
    InfraMetadata,
    RequiredInfraMetadata,
    make_config_openapi,
    models,
)

API_PREFIX = "/api/v1/infra"
CONFIG_PATH = f"{API_PREFIX}/config"
NAMING_PATH = f"{API_PREFIX}/naming"
BODY_PATH = f"{API_PREFIX}/config-body"


def _router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)

    @router.get("/config")
    async def _config(metadata: RequiredInfraMetadata = Depends()):
        return {}

    @router.get("/naming")
    async def _naming(metadata: InfraMetadata = Depends()):
        return {}

    return router


@pytest.fixture
def app_with_openapi():
    app = FastAPI(title="Test API", version="1.0.0")
    app.include_router(_router())
    app.openapi = make_config_openapi(app, [CONFIG_PATH, NAMING_PATH])
    return app


def _params_for(schema, path, method="get"):
    return {p["name"]: p for p in schema["paths"][path][method]["parameters"]}


class TestEnumInjection:
    def test_no_enums_when_allowlists_empty(self, app_with_openapi):
        schema = app_with_openapi.openapi()
        params = _params_for(schema, CONFIG_PATH)
        assert "enum" not in params["network"]["schema"]
        assert "enum" not in params["project"]["schema"]

    def test_populated_allowlists_inject_sorted_enums(self, app_with_openapi):
        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net", "edge-net"})
        models.LIVE_ALLOWED_PROJECTS.update({"payment-gateway", "authentication-service"})
        app_with_openapi.openapi_schema = None

        schema = app_with_openapi.openapi()
        config_params = _params_for(schema, CONFIG_PATH)
        assert config_params["network"]["schema"]["enum"] == ["backbone-net", "edge-net"]
        assert config_params["project"]["schema"]["enum"] == sorted(
            ["payment-gateway", "authentication-service"]
        )
        naming_params = _params_for(schema, NAMING_PATH)
        assert naming_params["network"]["schema"]["enum"] == ["backbone-net", "edge-net"]

    def test_schema_is_cached_until_invalidated(self, app_with_openapi):
        first = app_with_openapi.openapi()
        assert app_with_openapi.openapi() is first
        models.LIVE_ALLOWED_REGIONS.update({"us-east"})
        cached = app_with_openapi.openapi()
        assert "enum" not in _params_for(cached, CONFIG_PATH)["region"]["schema"]
        app_with_openapi.openapi_schema = None
        regenerated = app_with_openapi.openapi()
        assert _params_for(regenerated, CONFIG_PATH)["region"]["schema"]["enum"] == ["us-east"]


class TestBodyEnumInjection:
    """Coordinates carried in a JSON request body (a Pydantic model, not Depends)
    get enums injected into the referenced component schema, not `parameters`."""

    def _body_app(self):
        app = FastAPI(title="Body API", version="1.0.0")

        @app.post(BODY_PATH)
        async def _config_body(metadata: RequiredInfraMetadata):  # body model
            return {}

        app.openapi = make_config_openapi(app, [BODY_PATH])
        return app

    def test_body_model_coordinates_get_enums(self):
        models.LIVE_ALLOWED_ENVIRONMENTS.update({"prod", "staging"})
        app = self._body_app()
        schema = app.openapi()
        # The body op references the model by $ref; enums land on the component.
        ref = schema["paths"][BODY_PATH]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        props = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]
        assert props["environment"]["enum"] == sorted(models.LIVE_ALLOWED_ENVIRONMENTS)
        assert {"prod", "staging"} <= set(props["environment"]["enum"])


class TestRegexCoordinatePaths:
    """coordinate_paths entries are regex strings matched with re.fullmatch."""

    def _app(self, coordinate_paths):
        app = FastAPI(title="Regex API", version="1.0.0")
        app.include_router(_router())
        app.openapi = make_config_openapi(app, coordinate_paths)
        return app

    def test_one_pattern_injects_into_all_matching_routes(self):
        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net"})
        app = self._app([rf"{API_PREFIX}/(config|naming)"])  # one entry -> both routes
        schema = app.openapi()
        assert _params_for(schema, CONFIG_PATH)["network"]["schema"]["enum"] == ["backbone-net"]
        assert _params_for(schema, NAMING_PATH)["network"]["schema"]["enum"] == ["backbone-net"]

    def test_wildcard_pattern_matches(self):
        models.LIVE_ALLOWED_REGIONS.update({"us-east"})
        app = self._app([rf"{API_PREFIX}/.*"])
        schema = app.openapi()
        assert _params_for(schema, CONFIG_PATH)["region"]["schema"]["enum"] == ["us-east"]

    def test_non_matching_pattern_injects_nothing(self):
        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net"})
        app = self._app([r"/nope/.*"])
        schema = app.openapi()
        assert "enum" not in _params_for(schema, CONFIG_PATH)["network"]["schema"]

    def test_plain_string_still_matches_only_its_route(self):
        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net"})
        app = self._app([CONFIG_PATH])  # metachar-free -> exact behaviour
        schema = app.openapi()
        assert _params_for(schema, CONFIG_PATH)["network"]["schema"]["enum"] == ["backbone-net"]
        assert "enum" not in _params_for(schema, NAMING_PATH)["network"]["schema"]

    def test_invalid_regex_raises_at_wireup(self):
        app = FastAPI(title="Bad", version="1.0.0")
        app.include_router(_router())
        with pytest.raises(ValueError, match="Invalid coordinate_paths regex"):
            make_config_openapi(app, [r"[unclosed"])


class TestInjectionLogging:
    """One INFO log naming the routes that actually received coordinate enums."""

    _MARK = "injected live coordinate enums"

    def _app(self):
        app = FastAPI(title="Log API", version="1.0.0")
        app.include_router(_router())
        app.openapi = make_config_openapi(app, [CONFIG_PATH, NAMING_PATH])
        return app

    def _capture(self, fn):
        from loguru import logger

        records: list = []
        sink_id = logger.add(records.append, level="INFO", format="{message}")
        try:
            fn()
        finally:
            logger.remove(sink_id)
        return [str(r) for r in records if self._MARK in str(r)]

    def test_logs_injected_routes_once(self):
        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net"})
        app = self._app()

        def _gen():
            app.openapi()  # first build -> logs once
            app.openapi_schema = None
            app.openapi()  # regenerate, same injected set -> no new log

        msgs = self._capture(_gen)
        assert len(msgs) == 1
        assert CONFIG_PATH in msgs[0] and NAMING_PATH in msgs[0]

    def test_no_log_when_nothing_injected(self):
        # allowlists cleared by the autouse conftest fixture -> no enum -> no log
        app = self._app()
        assert self._capture(app.openapi) == []
