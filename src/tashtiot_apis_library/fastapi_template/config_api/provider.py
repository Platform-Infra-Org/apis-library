import asyncio
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException
from loguru import logger

from ..utils import BaseAPI
from .models import (
    LIVE_ALLOWED_ENVIRONMENTS,
    LIVE_ALLOWED_ISLANDS,
    LIVE_ALLOWED_NETWORKS,
    LIVE_ALLOWED_PROJECTS,
    LIVE_ALLOWED_REGIONS,
    LIVE_ALLOWED_SPACES,
    LIVE_COORDINATE_TREE,
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
    ``auth`` (an `httpx.Auth`), so the caller chooses the method --
    client-side SSO (``sso_auth(config=...)``), a static bearer
    ([`StaticBearerAuth`][tashtiot_apis_library.fastapi_template._internal.security.sso.StaticBearerAuth]), or ``None`` for anonymous access. The library's
    [`enable_remote_config_api`][enable_remote_config_api] resolves this from the package-side
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
        serve_stale_on_error: bool = False,
    ):
        # Imported lazily so merely importing this module (e.g. via the top-level
        # package, which re-exports the coordinate models) never drags in aiocache --
        # it loads only when a provider is actually built.
        from aiocache import Cache

        self._base_url = base_url.rstrip("/")
        self._prefix = remote_prefix
        self._auth = auth
        self._timeout = timeout
        self._verify = verify
        self._cache_ttl = cache_ttl
        self._cache = Cache(Cache.MEMORY)
        self._serve_stale = serve_stale_on_error
        # Last-known-good per cache_key, no TTL -- the aiocache MEMORY backend drops
        # expired entries on read, so stale fallback needs its own store.
        self._stale: Dict[str, Any] = {}

    async def _get(self, path: str, params: Dict[str, Any]) -> httpx.Response:
        """GET ``path`` on the upstream with the configured auth attached.

        ``None``-valued coordinates are dropped so omitted ones are never sent as
        empty query parameters. Transport failures surface as ``502`` so a
        broken upstream is reported as a gateway error, not an opaque ``500``.
        """
        clean = {k: v for k, v in params.items() if v is not None}
        try:
            api = BaseAPI(
                self._base_url, auth=self._auth, timeout=self._timeout, verify=self._verify
            )
            async with api as client:
                return await client.get(path, params=clean)
        except httpx.HTTPError as exc:
            logger.error(f"Upstream Config API request to {path} failed: {exc}")
            raise HTTPException(
                status_code=502, detail="Upstream Config API is unreachable."
            ) from exc

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

        Sourced over HTTP from the upstream's ``/coordinates`` route (flat per-level
        allowlists + projects) and ``/coordinates/tree`` (the nested hierarchy for the
        cross-field validator), both built from the enterprise configuration tree and
        reusing the cached resolver methods below -- so a poll within the cache TTL
        window costs no extra upstream calls."""
        try:
            # Flat coordinate values + projects from the upstream coordinate catalog.
            catalog = await self.get_coordinate_catalog()
            for live_set, key in (
                (LIVE_ALLOWED_SPACES, "space"),
                (LIVE_ALLOWED_NETWORKS, "network"),
                (LIVE_ALLOWED_REGIONS, "region"),
                (LIVE_ALLOWED_ISLANDS, "island"),
                (LIVE_ALLOWED_ENVIRONMENTS, "environment"),
                (LIVE_ALLOWED_PROJECTS, "projects"),
            ):
                values = catalog.get(key, [])
                if values:  # stay permissive when a level is unseeded/empty
                    live_set.clear()
                    live_set.update(values)

            # Nested hierarchy for the cross-field (parent/child) validator.
            tree = await self.get_coordinate_tree()
            LIVE_COORDINATE_TREE.clear()
            LIVE_COORDINATE_TREE.update(tree)

            # Invalidate the cached OpenAPI schema so it regenerates with fresh enums.
            app_instance.openapi_schema = None

            logger.debug(
                "Synced Config API allowlists (networks={}, regions={}, islands={}, "
                "environments={}, spaces={}, projects={}).",
                len(LIVE_ALLOWED_NETWORKS),
                len(LIVE_ALLOWED_REGIONS),
                len(LIVE_ALLOWED_ISLANDS),
                len(LIVE_ALLOWED_ENVIRONMENTS),
                len(LIVE_ALLOWED_SPACES),
                len(LIVE_ALLOWED_PROJECTS),
            )
        except Exception as e:
            logger.error(f"Synchronization pipeline loop operation failure: {e}")

    async def start_periodic_polling(self, app_instance, interval_seconds: int = 5) -> None:
        while True:
            await self.crawl_and_sync_keys(app_instance)
            await asyncio.sleep(interval_seconds)

    async def _cached_get(self, cache_key, path, params, default, extract):
        """Cache-read → upstream GET → (404 → ``default``) → ``extract`` → cache-write.

        ``default`` is returned on a 404 *without* being cached (the upstream may
        seed the value later); ``extract`` maps the JSON body to the cached result.
        When ``serve_stale_on_error`` is set, a 502 (upstream down or 5xx) falls back
        to the last-known-good value for this key instead of propagating the error.
        """
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = await self._get(f"{self._prefix}{path}", params)
            if response.status_code == 404:
                return default
            self._ensure_ok(response)
            result = extract(response.json())
        except HTTPException:
            if self._serve_stale and cache_key in self._stale:
                logger.warning(f"Upstream Config API unavailable; serving stale '{cache_key}'.")
                return self._stale[cache_key]
            raise

        await self._cache.set(cache_key, result, ttl=self._cache_ttl)
        self._stale[cache_key] = result  # ponytail: unbounded; keys = coordinate combos
        return result

    @staticmethod
    def _coord_params(meta: InfraMetadata) -> Dict[str, Any]:
        return {
            "space": meta.space,
            "network": meta.network,
            "region": meta.region,
            "island": meta.island,
            "environment": meta.environment,
            "project": meta.project,
        }

    async def resolve_infra_config(self, meta: InfraMetadata) -> Dict[str, Any]:
        """Resolve config by delegating to the upstream ``/config`` route, which
        performs the root -> space -> network -> region -> island -> environment
        cascade. An upstream ``404`` (no matching config) maps to an empty dict so
        the route layer emits its own ``404``."""
        cache_key = f"cfg:{meta.space}:{meta.network}:{meta.region}:{meta.island}:{meta.environment}:{meta.project}"
        return await self._cached_get(
            cache_key,
            "/config",
            self._coord_params(meta),
            {},
            lambda body: body.get("configurations", {}),
        )

    async def resolve_naming_convention(self, meta: InfraMetadata) -> Dict[str, Any]:
        """Resolve the naming token suffixes by delegating to the upstream
        ``/naming`` route. With no coordinates supplied, the upstream returns the
        entire naming dictionary. An upstream ``404`` maps to an empty dict."""
        cache_key = f"name:{meta.space}:{meta.network}:{meta.region}:{meta.island}:{meta.environment}:{meta.project}"
        return await self._cached_get(
            cache_key,
            "/naming",
            self._coord_params(meta),
            {},
            lambda body: body.get("naming_parts", {}),
        )

    async def get_all_projects(self) -> List[str]:
        """Fetch every registered project from the upstream ``/projects`` route.
        An upstream ``404`` (empty registry) maps to an empty list."""
        return await self._cached_get(
            "global:project_registry:all_names",
            "/projects",
            {},
            [],
            lambda body: body.get("projects", []),
        )

    async def get_coordinate_catalog(self) -> Dict[str, List[str]]:
        """Fetch the valid values per coordinate level plus the project list from
        the upstream ``/coordinates`` route. An upstream ``404`` maps to a catalog
        of empty lists."""
        keys = ("space", "network", "region", "island", "environment", "projects")
        return await self._cached_get(
            "global:coordinate_catalog",
            "/coordinates",
            {},
            {k: [] for k in keys},
            lambda body: {k: body.get(k, []) for k in keys},
        )

    async def get_coordinate_tree(self) -> Dict[str, Any]:
        """Fetch the nested coordinate hierarchy from the upstream
        ``/coordinates/tree`` route. An upstream ``404`` maps to an empty tree."""
        return await self._cached_get(
            "global:coordinate_tree",
            "/coordinates/tree",
            {},
            {"coordinates": {}, "projects": []},
            lambda body: {
                "coordinates": body.get("coordinates", {}),
                "projects": body.get("projects", []),
            },
        )
