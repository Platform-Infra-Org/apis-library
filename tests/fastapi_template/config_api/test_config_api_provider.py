"""RemoteConfigProvider: proxying config/naming/registry to the upstream Config
API (mocked via respx), in-memory caching, and the background allowlist poller."""

import httpx
import pytest
import respx

from tashtiot_apis_library.fastapi_template.config_api import InfraMetadata, models

from .conftest import REMOTE_PREFIX, TOKEN_URL, UPSTREAM_BASE, FakeApp, make_provider
from .upstream import register_token_route


def _full_meta(**overrides):
    base = {
        "space": "core-infrastructure",
        "network": "backbone-net",
        "region": "us-east",
        "island": "compute-island-a",
        "environment": "production",
        "project": "payment-gateway",
    }
    base.update(overrides)
    return InfraMetadata(**base)


class TestResolveInfraConfig:
    @pytest.mark.asyncio
    async def test_full_path_merges_all_layers_deeper_overrides_shallower(self, provider):
        result = await provider.resolve_infra_config(_full_meta(environment="production"))
        assert result["global_timeout_ms"] == 3000
        assert result["monitoring_provider"] == "datadog"
        assert result["space_policy_class"] == "tier-1-governed"
        assert result["ntp_server"] == "pool.ntp.org"
        assert result["aws_vpc_id"] == "vpc-0a1b2c3d"
        assert result["cluster_size"] == 20
        assert result["debug_mode"] is False

    @pytest.mark.asyncio
    async def test_shallower_value_survives_when_deeper_layer_is_empty(self, provider):
        result = await provider.resolve_infra_config(_full_meta(environment="staging"))
        assert result["cluster_size"] == 5
        assert "debug_mode" not in result

    @pytest.mark.asyncio
    async def test_partial_coordinates_contribute_only_present_layers(self, provider):
        meta = InfraMetadata(space="core-infrastructure")
        result = await provider.resolve_infra_config(meta)
        assert result["global_timeout_ms"] == 3000
        assert result["space_policy_class"] == "tier-1-governed"
        assert "ntp_server" not in result

    @pytest.mark.asyncio
    async def test_unknown_coordinates_yield_only_root(self, provider):
        meta = InfraMetadata(space="does-not-exist")
        result = await provider.resolve_infra_config(meta)
        assert result == {"global_timeout_ms": 3000, "monitoring_provider": "datadog"}

    @pytest.mark.asyncio
    async def test_missing_config_document_returns_empty(self, empty_provider):
        assert await empty_provider.resolve_infra_config(_full_meta()) == {}

    @pytest.mark.asyncio
    async def test_result_is_cached_second_call_skips_upstream(self, provider):
        meta = _full_meta()
        first = await provider.resolve_infra_config(meta)
        hits_after_first = provider._router["config"].call_count
        second = await provider.resolve_infra_config(meta)
        assert second == first
        assert provider._router["config"].call_count == hits_after_first


class TestResolveNamingConvention:
    @pytest.mark.asyncio
    async def test_no_coordinates_returns_entire_dictionary(self, provider):
        payload = await provider.resolve_naming_convention(InfraMetadata())
        assert set(payload.keys()) == {"network", "region", "island", "environment", "space"}
        assert "_id" not in payload and "doc_type" not in payload
        assert payload["space"]["tenant-alpha"] == "alpha.tenant.com"

    @pytest.mark.asyncio
    async def test_coordinates_resolve_token_maps(self, provider):
        meta = InfraMetadata(network="backbone-net", region="us-east", environment="production")
        payload = await provider.resolve_naming_convention(meta)
        assert payload["network"] == {"host": "bb", "cname": "net"}
        assert payload["region"] == {"host": "use1", "cname": "east"}
        assert payload["environment"] == {"host": "prd", "cname": "prod"}
        assert payload["island"] == {}
        assert payload["space"] == {}

    @pytest.mark.asyncio
    async def test_unknown_coordinate_resolves_to_empty_map(self, provider):
        payload = await provider.resolve_naming_convention(InfraMetadata(network="ghost-net"))
        assert payload["network"] == {}

    @pytest.mark.asyncio
    async def test_missing_naming_document_returns_empty(self, empty_provider):
        assert await empty_provider.resolve_naming_convention(InfraMetadata()) == {}


class TestGetAllProjects:
    @pytest.mark.asyncio
    async def test_returns_registry_list(self, provider):
        projects = await provider.get_all_projects()
        assert projects == [
            "payment-gateway",
            "authentication-service",
            "notification-engine",
            "data-warehouse-pipeline",
        ]

    @pytest.mark.asyncio
    async def test_missing_registry_returns_empty_list(self, empty_provider):
        assert await empty_provider.get_all_projects() == []

    @pytest.mark.asyncio
    async def test_cached_after_first_fetch(self, provider):
        await provider.get_all_projects()
        hits = provider._router["projects"].call_count
        await provider.get_all_projects()
        assert provider._router["projects"].call_count == hits


class TestUpstreamErrors:
    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_upstream_5xx_maps_to_502(self, respx_mock):
        from fastapi import HTTPException

        register_token_route(respx_mock, TOKEN_URL)
        respx_mock.get(f"{UPSTREAM_BASE}{REMOTE_PREFIX}/projects").mock(
            return_value=httpx.Response(500, text="boom")
        )
        prov = make_provider()
        await prov._cache.clear()
        with pytest.raises(HTTPException) as exc:
            await prov.get_all_projects()
        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_upstream_transport_error_maps_to_502(self, respx_mock):
        from fastapi import HTTPException

        register_token_route(respx_mock, TOKEN_URL)
        respx_mock.get(f"{UPSTREAM_BASE}{REMOTE_PREFIX}/projects").mock(
            side_effect=httpx.ConnectError("refused")
        )
        prov = make_provider()
        await prov._cache.clear()
        with pytest.raises(HTTPException) as exc:
            await prov.get_all_projects()
        assert exc.value.status_code == 502


class TestCrawlAndSyncKeys:
    @pytest.mark.asyncio
    async def test_populates_allowlists_in_place_and_invalidates_schema(self, provider):
        net_set_id = id(models.LIVE_ALLOWED_NETWORKS)
        proj_set_id = id(models.LIVE_ALLOWED_PROJECTS)
        app = FakeApp()

        await provider.crawl_and_sync_keys(app)

        assert models.LIVE_ALLOWED_NETWORKS == {"backbone-net"}
        assert models.LIVE_ALLOWED_REGIONS == {"us-east"}
        assert models.LIVE_ALLOWED_ISLANDS == {"compute-island-a"}
        assert models.LIVE_ALLOWED_ENVIRONMENTS == {"staging", "production"}
        assert models.LIVE_ALLOWED_SPACES == {"core-infrastructure", "tenant-alpha"}
        assert models.LIVE_ALLOWED_PROJECTS == {
            "payment-gateway",
            "authentication-service",
            "notification-engine",
            "data-warehouse-pipeline",
        }
        assert id(models.LIVE_ALLOWED_NETWORKS) == net_set_id
        assert id(models.LIVE_ALLOWED_PROJECTS) == proj_set_id
        assert app.openapi_schema is None

    @pytest.mark.asyncio
    async def test_missing_documents_leave_allowlists_untouched(self, empty_provider):
        models.LIVE_ALLOWED_NETWORKS.update({"preexisting"})
        app = FakeApp()
        await empty_provider.crawl_and_sync_keys(app)
        assert models.LIVE_ALLOWED_NETWORKS == {"preexisting"}
        assert app.openapi_schema is None

    @pytest.mark.asyncio
    @respx.mock(assert_all_called=False)
    async def test_exception_is_swallowed(self, respx_mock):
        register_token_route(respx_mock, TOKEN_URL)
        respx_mock.get(f"{UPSTREAM_BASE}{REMOTE_PREFIX}/naming").mock(
            return_value=httpx.Response(500, text="boom")
        )
        prov = make_provider()
        await prov._cache.clear()

        app = FakeApp()
        await prov.crawl_and_sync_keys(app)  # should not raise
        assert app.openapi_schema == "stale-cached-schema"
