"""Fixtures for the Remote Config capability tests.

Isolated in this subpackage so the autouse allowlist/token-cache resets don't
bleed into the other fastapi_template tests. The upstream Config API and the SSO
token endpoint are mocked with respx.
"""
import copy
from typing import Any

import pytest
import pytest_asyncio
import respx

from ...config_api import schemas
from ...config_api import RemoteConfigProvider
from ...security import SSOConfig, sso_auth
from ..._internal.security import sso as sso_mod

from .upstream import ALL_SEED_DOCS, register_token_route, register_upstream_routes


UPSTREAM_BASE = "http://upstream.test"
TOKEN_URL = "https://idp.test/oauth/token"
REMOTE_PREFIX = "/api/v1/infra"

# A reusable client-side SSO config — one instance so its token cache is shared
# (and cleared between tests via the autouse fixture below).
SSO_CONFIG = SSOConfig(
    token_url=TOKEN_URL,
    client_id="infra-config-proxy",
    client_secret="s3cret",
    auth_style="post",
)


class FakeApp:
    """Stand-in for the FastAPI app: the poller only touches ``openapi_schema``."""

    def __init__(self):
        self.openapi_schema: Any = "stale-cached-schema"


@pytest.fixture
def seed_docs():
    return [copy.deepcopy(d) for d in ALL_SEED_DOCS]


@pytest.fixture(autouse=True)
def reset_live_allowlists():
    """The ``LIVE_ALLOWED_*`` sets are mutable module globals; reset around each test."""
    sets = [
        schemas.LIVE_ALLOWED_NETWORKS, schemas.LIVE_ALLOWED_REGIONS,
        schemas.LIVE_ALLOWED_ISLANDS, schemas.LIVE_ALLOWED_ENVIRONMENTS,
        schemas.LIVE_ALLOWED_SPACES, schemas.LIVE_ALLOWED_PROJECTS,
    ]
    for s in sets:
        s.clear()
    yield
    for s in sets:
        s.clear()


@pytest.fixture(autouse=True)
def reset_sso_token_cache():
    """Clear the memoized SSO token-client cache so token state never leaks."""
    sso_mod._token_client_cache.clear()
    yield
    sso_mod._token_client_cache.clear()


def make_provider():
    return RemoteConfigProvider(UPSTREAM_BASE, REMOTE_PREFIX, auth=sso_auth(SSO_CONFIG))


@pytest_asyncio.fixture
async def provider(seed_docs):
    with respx.mock(assert_all_called=False) as router:
        register_token_route(router, TOKEN_URL)
        register_upstream_routes(router, seed_docs, UPSTREAM_BASE, REMOTE_PREFIX)
        prov = make_provider()
        await prov._cache.clear()
        prov._router = router
        yield prov
        await prov._cache.clear()


@pytest_asyncio.fixture
async def empty_provider():
    with respx.mock(assert_all_called=False) as router:
        register_token_route(router, TOKEN_URL)
        register_upstream_routes(router, [], UPSTREAM_BASE, REMOTE_PREFIX)
        prov = make_provider()
        await prov._cache.clear()
        prov._router = router
        yield prov
        await prov._cache.clear()
