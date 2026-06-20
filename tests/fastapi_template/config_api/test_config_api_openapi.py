"""make_config_openapi injects the live allowlists as enum dropdowns."""
import pytest
from fastapi import APIRouter, Depends, FastAPI

from tashtiot_apis_library.fastapi_template.config_api import schemas
from tashtiot_apis_library.fastapi_template.config_api import (
    InfraMetadata, RequiredInfraMetadata, make_config_openapi,
)

API_PREFIX = "/api/v1/infra"
CONFIG_PATH = f"{API_PREFIX}/config"
NAMING_PATH = f"{API_PREFIX}/naming"


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
    app.openapi = make_config_openapi(app, config_path=CONFIG_PATH, naming_path=NAMING_PATH)
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
        schemas.LIVE_ALLOWED_NETWORKS.update({"backbone-net", "edge-net"})
        schemas.LIVE_ALLOWED_PROJECTS.update({"payment-gateway", "authentication-service"})
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
        schemas.LIVE_ALLOWED_REGIONS.update({"us-east"})
        cached = app_with_openapi.openapi()
        assert "enum" not in _params_for(cached, CONFIG_PATH)["region"]["schema"]
        app_with_openapi.openapi_schema = None
        regenerated = app_with_openapi.openapi()
        assert _params_for(regenerated, CONFIG_PATH)["region"]["schema"]["enum"] == ["us-east"]
