"""enable_remote_config_api wiring + selectable CONFIG_REMOTE_* outbound auth."""

import pytest
import respx
from fastapi import APIRouter, Depends
from pydantic import ValidationError

from tashtiot_apis_library.fastapi_template import general_create_app
from tashtiot_apis_library.fastapi_template.config_api import (
    ConfigRemoteSettings,
    InfraMetadata,
    RequiredInfraMetadata,
    enable_remote_config_api,
    models,
)
from tashtiot_apis_library.fastapi_template.errors import AuthConfigError
from tashtiot_apis_library.fastapi_template.security import StaticBearerAuth, sso_auth

from .conftest import REMOTE_PREFIX, SSO_CONFIG, UPSTREAM_BASE
from .upstream import ALL_SEED_DOCS, register_upstream_routes

API_PREFIX = "/api/v1/infra"
CONFIG_PATH = f"{API_PREFIX}/config"
NAMING_PATH = f"{API_PREFIX}/naming"


def _coord_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)

    @router.get("/config")
    async def _config(metadata: RequiredInfraMetadata = Depends()):
        return {}

    @router.get("/naming")
    async def _naming(metadata: InfraMetadata = Depends()):
        return {}

    return router


# --------------------------------------------------------------------------- #
# resolve_auth — the three selectable methods.
# --------------------------------------------------------------------------- #


class TestResolveAuth:
    def test_none_method_yields_no_auth(self):
        auth, kwargs = ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="none").resolve_auth()
        assert auth is None and kwargs == {}

    def test_bearer_method_yields_static_bearer(self):
        auth, kwargs = ConfigRemoteSettings(
            CONFIG_REMOTE_AUTH_METHOD="bearer", CONFIG_REMOTE_BEARER_TOKEN="tok"
        ).resolve_auth()
        assert isinstance(auth, StaticBearerAuth)

    def test_bearer_method_missing_token_raises(self):
        with pytest.raises(AuthConfigError, match="CONFIG_REMOTE_BEARER_TOKEN"):
            ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="bearer").resolve_auth()

    def test_sso_method_yields_sso_auth(self):
        auth, kwargs = ConfigRemoteSettings(
            CONFIG_REMOTE_AUTH_METHOD="sso",
            CONFIG_REMOTE_SSO_TOKEN_URL="http://t",
            CONFIG_REMOTE_SSO_CLIENT_ID="c",
            CONFIG_REMOTE_SSO_CLIENT_SECRET="s",
        ).resolve_auth()
        assert auth is not None
        assert kwargs == {"timeout": 10.0, "verify": True}

    def test_sso_method_missing_config_raises(self):
        with pytest.raises(AuthConfigError, match="token_url|client_id|client_secret"):
            ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="sso").resolve_auth()

    def test_unknown_method_raises(self):
        with pytest.raises(AuthConfigError, match="must be 'sso', 'bearer', or 'none'"):
            ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="weird").resolve_auth()


# --------------------------------------------------------------------------- #
# enable_remote_config_api — wiring onto a general_create_app app.
# --------------------------------------------------------------------------- #


class TestWiring:
    def _app(self):
        return general_create_app(title="Wiring Test", version="1.0.0")

    def test_registers_poller_openapi_and_error_handler(self):
        app = self._app()
        before = len(app.state.async_background_tasks)
        provider = enable_remote_config_api(
            app,
            base_url=UPSTREAM_BASE,
            remote_prefix=REMOTE_PREFIX,
            coordinate_paths=[CONFIG_PATH, NAMING_PATH],
            auth=sso_auth(SSO_CONFIG),
        )
        # Poller appended to the lifespan-read registry.
        assert len(app.state.async_background_tasks) == before + 1
        # Coordinate-validation -> 422 handler installed.
        assert ValidationError in app.exception_handlers
        # Returned provider is usable.
        assert provider is not None

    def test_enum_injection_through_wired_openapi(self):
        app = self._app()
        enable_remote_config_api(
            app,
            base_url=UPSTREAM_BASE,
            remote_prefix=REMOTE_PREFIX,
            coordinate_paths=[CONFIG_PATH, NAMING_PATH],
            settings=ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="none"),
            enable_polling=False,
        )
        app.include_router(_coord_router())

        models.LIVE_ALLOWED_NETWORKS.update({"backbone-net", "edge-net"})
        app.openapi_schema = None
        schema = app.openapi()
        params = {p["name"]: p for p in schema["paths"][CONFIG_PATH]["get"]["parameters"]}
        assert params["network"]["schema"]["enum"] == ["backbone-net", "edge-net"]

    def test_enable_polling_false_still_registers_a_seed_task(self):
        # Even with polling off, one background task is registered to seed the allowlists once.
        app = self._app()
        before = len(app.state.async_background_tasks)
        enable_remote_config_api(
            app,
            base_url=UPSTREAM_BASE,
            remote_prefix=REMOTE_PREFIX,
            coordinate_paths=[CONFIG_PATH, NAMING_PATH],
            settings=ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="none"),
            enable_polling=False,
        )
        assert len(app.state.async_background_tasks) == before + 1

    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_polling_false_seed_task_populates_allowlists(self, respx_mock):
        register_upstream_routes(respx_mock, ALL_SEED_DOCS, UPSTREAM_BASE, REMOTE_PREFIX)
        app = self._app()
        enable_remote_config_api(
            app,
            base_url=UPSTREAM_BASE,
            remote_prefix=REMOTE_PREFIX,
            coordinate_paths=[CONFIG_PATH, NAMING_PATH],
            settings=ConfigRemoteSettings(CONFIG_REMOTE_AUTH_METHOD="none"),
            enable_polling=False,
        )
        # Running the one-shot seed task (as the lifespan would) fills the allowlists + tree.
        await app.state.async_background_tasks[-1]()
        assert models.LIVE_ALLOWED_SPACES == {"core-infrastructure"}
        assert models.LIVE_ALLOWED_NETWORKS == {"backbone-net"}
        assert models.LIVE_COORDINATE_TREE["coordinates"]["core-infrastructure"]["backbone-net"][
            "us-east"
        ]["compute-island-a"] == ["production", "staging"]


# --------------------------------------------------------------------------- #
# Outbound auth actually applied on upstream calls.
# --------------------------------------------------------------------------- #


class TestOutboundAuthHeaders:
    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_bearer_method_sends_static_token(self, respx_mock):
        register_upstream_routes(respx_mock, ALL_SEED_DOCS, UPSTREAM_BASE, REMOTE_PREFIX)
        settings = ConfigRemoteSettings(
            CONFIG_REMOTE_AUTH_METHOD="bearer", CONFIG_REMOTE_BEARER_TOKEN="static-xyz"
        )
        auth, kwargs = settings.resolve_auth()
        from tashtiot_apis_library.fastapi_template.config_api import RemoteConfigProvider

        prov = RemoteConfigProvider(UPSTREAM_BASE, REMOTE_PREFIX, auth=auth, **kwargs)
        await prov._cache.clear()

        await prov.get_all_projects()
        assert (
            respx_mock["projects"].calls.last.request.headers["Authorization"]
            == "Bearer static-xyz"
        )

    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_none_method_sends_no_authorization(self, respx_mock):
        register_upstream_routes(respx_mock, ALL_SEED_DOCS, UPSTREAM_BASE, REMOTE_PREFIX)
        from tashtiot_apis_library.fastapi_template.config_api import RemoteConfigProvider

        prov = RemoteConfigProvider(UPSTREAM_BASE, REMOTE_PREFIX, auth=None)
        await prov._cache.clear()

        await prov.get_all_projects()
        assert "Authorization" not in respx_mock["projects"].calls.last.request.headers
