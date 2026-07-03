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
