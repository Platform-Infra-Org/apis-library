import asyncio
from typing import Any, Dict, List, Optional

import httpx
from aiocache import Cache
from fastapi import HTTPException
from loguru import logger

from .._internal.database import BaseAPI

from .schemas import (
    LIVE_ALLOWED_NETWORKS, LIVE_ALLOWED_REGIONS, LIVE_ALLOWED_ISLANDS,
    LIVE_ALLOWED_ENVIRONMENTS, LIVE_ALLOWED_SPACES, LIVE_ALLOWED_PROJECTS,
    InfraMetadata,
)


class RemoteConfigProvider:
    """Resolves config / naming / projects by calling an **upstream Config API**
    (same routes) over HTTP, with in-memory caching (``cache_ttl``-second TTL,
    default 60s) and the background allowlist-sync loop.

    The upstream already performs the cascade merge and naming/registry lookups,
    so this is a thin authenticated proxy: it forwards the coordinate query
    parameters and returns the upstream's resolved payload.

    **Pluggable auth.** Outbound requests authenticate via the injected
    ``auth`` (an :class:`httpx.Auth`), so the caller chooses the method --
    client-side SSO (``sso_auth(config=...)``), a static bearer
    (:class:`StaticBearerAuth`), or ``None`` for anonymous access. The library's
    :func:`enable_remote_config_api` resolves this from the package-side
    ``CONFIG_REMOTE_*`` settings; tests/callers may pass an ``auth`` directly.
    """

    def __init__(
        self,
        base_url: str,
        remote_prefix: str,
        *,
        auth: Optional[httpx.Auth] = None,
        timeout: float = 10.0,
        verify: bool = True,
        cache_ttl: int = 60,
    ):
        self._base_url = base_url.rstrip("/")
        self._prefix = remote_prefix
        self._auth = auth
        self._timeout = timeout
        self._verify = verify
        self._cache_ttl = cache_ttl
        self._cache = Cache(Cache.MEMORY)

    async def _get(self, path: str, params: Dict[str, Any]) -> httpx.Response:
        """GET ``path`` on the upstream with the configured auth attached.

        ``None``-valued coordinates are dropped so omitted ones are never sent as
        empty query parameters. Transport failures surface as ``502`` so a
        broken upstream is reported as a gateway error, not an opaque ``500``.
        """
        clean = {k: v for k, v in params.items() if v is not None}
        try:
            api = BaseAPI(self._base_url, auth=self._auth, timeout=self._timeout, verify=self._verify)
            async with api as client:
                return await client.get(path, params=clean)
        except httpx.HTTPError as exc:
            logger.error(f"Upstream Config API request to {path} failed: {exc}")
            raise HTTPException(status_code=502, detail="Upstream Config API is unreachable.") from exc

    @staticmethod
    def _ensure_ok(response: httpx.Response) -> None:
        """Map a non-404 upstream error response onto a ``502`` (404 is handled by
        callers as an empty result, mirroring the original 'not found' semantics)."""
        if response.status_code >= 400:
            logger.error(
                f"Upstream Config API returned {response.status_code}: {response.text[:300]}"
            )
            raise HTTPException(
                status_code=502,
                detail=f"Upstream Config API error ({response.status_code}).",
            )

    async def crawl_and_sync_keys(self, app_instance) -> None:
        """Discover allowed coordinate values from the **upstream** and hot-patch
        the live allowlists, then invalidate the cached Swagger schema so the enum
        dropdowns regenerate on the next request.

        Sourced over HTTP from the upstream's ``/naming`` (full dictionary) and
        ``/projects`` routes, reusing the cached resolver methods below -- so a poll
        within the cache TTL window costs no extra upstream calls."""
        try:
            # 1. Naming convention coordinate tokens (keys of each per-level map).
            naming = await self.resolve_naming_convention(InfraMetadata())
            if naming:
                LIVE_ALLOWED_NETWORKS.clear()
                LIVE_ALLOWED_NETWORKS.update(naming.get("network", {}).keys())
                LIVE_ALLOWED_REGIONS.clear()
                LIVE_ALLOWED_REGIONS.update(naming.get("region", {}).keys())
                LIVE_ALLOWED_ISLANDS.clear()
                LIVE_ALLOWED_ISLANDS.update(naming.get("island", {}).keys())
                LIVE_ALLOWED_ENVIRONMENTS.clear()
                LIVE_ALLOWED_ENVIRONMENTS.update(naming.get("environment", {}).keys())
                LIVE_ALLOWED_SPACES.clear()
                LIVE_ALLOWED_SPACES.update(naming.get("space", {}).keys())

            # 2. Global project registry catalog.
            projects = await self.get_all_projects()
            if projects:
                LIVE_ALLOWED_PROJECTS.clear()
                LIVE_ALLOWED_PROJECTS.update(projects)

            # Invalidate the cached OpenAPI schema so it regenerates with fresh enums.
            app_instance.openapi_schema = None
        except Exception as e:
            logger.error(f"Synchronization pipeline loop operation failure: {e}")

    async def start_periodic_polling(self, app_instance, interval_seconds: int = 5) -> None:
        while True:
            await self.crawl_and_sync_keys(app_instance)
            await asyncio.sleep(interval_seconds)

    async def resolve_infra_config(self, meta: InfraMetadata) -> Dict[str, Any]:
        """Resolve config by delegating to the upstream ``/config`` route, which
        performs the root -> space -> network -> region -> island -> environment
        cascade. An upstream ``404`` (no matching config) maps to an empty dict so
        the route layer emits its own ``404``."""
        cache_key = f"cfg:{meta.space}:{meta.network}:{meta.region}:{meta.island}:{meta.environment}:{meta.project}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(
            f"{self._prefix}/config",
            {
                "space": meta.space, "network": meta.network, "region": meta.region,
                "island": meta.island, "environment": meta.environment, "project": meta.project,
            },
        )
        if response.status_code == 404:
            return {}
        self._ensure_ok(response)

        result = response.json().get("configurations", {})
        await self._cache.set(cache_key, result, ttl=self._cache_ttl)
        return result

    async def resolve_naming_convention(self, meta: InfraMetadata) -> Dict[str, Any]:
        """Resolve the naming token suffixes by delegating to the upstream
        ``/naming`` route. With no coordinates supplied, the upstream returns the
        entire naming dictionary. An upstream ``404`` maps to an empty dict."""
        cache_key = f"name:{meta.space}:{meta.network}:{meta.region}:{meta.island}:{meta.environment}:{meta.project}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(
            f"{self._prefix}/naming",
            {
                "space": meta.space, "network": meta.network, "region": meta.region,
                "island": meta.island, "environment": meta.environment, "project": meta.project,
            },
        )
        if response.status_code == 404:
            return {}
        self._ensure_ok(response)

        payload = response.json().get("naming_parts", {})
        await self._cache.set(cache_key, payload, ttl=self._cache_ttl)
        return payload

    async def get_all_projects(self) -> List[str]:
        """Fetch every registered project from the upstream ``/projects`` route.
        An upstream ``404`` (empty registry) maps to an empty list."""
        cache_key = "global:project_registry:all_names"

        cached_list = await self._cache.get(cache_key)
        if cached_list is not None:
            return cached_list

        response = await self._get(f"{self._prefix}/projects", {})
        if response.status_code == 404:
            return []
        self._ensure_ok(response)

        result_list = response.json().get("projects", [])
        await self._cache.set(cache_key, result_list, ttl=self._cache_ttl)
        return result_list
