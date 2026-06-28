"""In-test stand-in for the upstream Config API used by the config_api tests.

Mounts the upstream's ``/projects``, ``/config`` and ``/naming`` routes (plus the
SSO token endpoint) with ``respx``, resolving from the seed documents exactly as
the real upstream would (cascade merge / naming lookups / registry list).
"""

from typing import Any, Dict, List, Optional

import httpx

ENTERPRISE_CONFIG_DOC = {
    "doc_type": "enterprise_configuration",
    "config": {"global_timeout_ms": 3000, "monitoring_provider": "datadog"},
    "space": {
        "core-infrastructure": {
            "config": {"space_policy_class": "tier-1-governed"},
            "network": {
                "backbone-net": {
                    "config": {
                        "ntp_server": "pool.ntp.org",
                        "dns_servers": ["10.0.0.1", "10.0.0.2"],
                    },
                    "region": {
                        "us-east": {
                            "config": {"aws_vpc_id": "vpc-0a1b2c3d"},
                            "island": {
                                "compute-island-a": {
                                    "config": {"cluster_size": 5},
                                    "environment": {
                                        "staging": {"config": {}},
                                        "production": {
                                            "config": {"cluster_size": 20, "debug_mode": False}
                                        },
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }
    },
}

NAMING_DOC = {
    "doc_type": "naming_conventions",
    "network": {"backbone-net": {"host": "bb", "cname": "net"}},
    "region": {"us-east": {"host": "use1", "cname": "east"}},
    "island": {"compute-island-a": {"host": "isla", "cname": "alpha"}},
    "environment": {
        "staging": {"host": "stg", "cname": "stage"},
        "production": {"host": "prd", "cname": "prod"},
    },
    "space": {
        "core-infrastructure": "core.internal",
        "tenant-alpha": "alpha.tenant.com",
    },
}

PROJECT_REGISTRY_DOC = {
    "doc_type": "project_registry",
    "projects": [
        "payment-gateway",
        "authentication-service",
        "notification-engine",
        "data-warehouse-pipeline",
    ],
}

ALL_SEED_DOCS = [ENTERPRISE_CONFIG_DOC, NAMING_DOC, PROJECT_REGISTRY_DOC]


# --------------------------------------------------------------------------- #
# Resolution — mirrors the real upstream's behaviour over the seed documents.
# --------------------------------------------------------------------------- #


def _find(docs: List[Dict[str, Any]], doc_type: str) -> Optional[Dict[str, Any]]:
    for doc in docs:
        if doc.get("doc_type") == doc_type:
            return doc
    return None


def resolve_config(docs: List[Dict[str, Any]], p: Dict[str, Any]) -> Dict[str, Any]:
    doc = _find(docs, "enterprise_configuration")
    if not doc:
        return {}

    layers = [doc.get("config", {})]
    space_node = doc.get("space", {}).get(p.get("space"), {})
    layers.append(space_node.get("config", {}))
    net_node = space_node.get("network", {}).get(p.get("network"), {})
    layers.append(net_node.get("config", {}))
    reg_node = net_node.get("region", {}).get(p.get("region"), {})
    layers.append(reg_node.get("config", {}))
    isl_node = reg_node.get("island", {}).get(p.get("island"), {})
    layers.append(isl_node.get("config", {}))
    env_node = isl_node.get("environment", {}).get(p.get("environment"), {})
    layers.append(env_node.get("config", {}))

    result: Dict[str, Any] = {}
    for layer in layers:
        result.update(layer)
    return result


def resolve_naming(docs: List[Dict[str, Any]], p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    doc = _find(docs, "naming_conventions")
    if not doc:
        return None

    if not any(p.get(k) for k in ("network", "region", "island", "environment", "space")):
        return {k: v for k, v in doc.items() if k not in ("_id", "doc_type")}

    return {
        "network": doc.get("network", {}).get(p.get("network"), {}),
        "region": doc.get("region", {}).get(p.get("region"), {}),
        "island": doc.get("island", {}).get(p.get("island"), {}),
        "environment": doc.get("environment", {}).get(p.get("environment"), {}),
        "space": doc.get("space", {}).get(p.get("space"), {}),
    }


def list_projects(docs: List[Dict[str, Any]]) -> Optional[List[str]]:
    doc = _find(docs, "project_registry")
    if not doc:
        return None
    return doc.get("projects", [])


def resolve_coordinates(docs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Collect valid coordinate values by walking the enterprise config tree, plus
    the project registry — mirrors the origin's ``/coordinates`` route."""
    doc = _find(docs, "enterprise_configuration") or {}
    projects_doc = _find(docs, "project_registry") or {}

    spaces, networks, regions, islands, environments = set(), set(), set(), set(), set()
    space_map = doc.get("space", {})
    spaces.update(space_map.keys())
    for space_node in space_map.values():
        network_map = space_node.get("network", {})
        networks.update(network_map.keys())
        for network_node in network_map.values():
            region_map = network_node.get("region", {})
            regions.update(region_map.keys())
            for region_node in region_map.values():
                island_map = region_node.get("island", {})
                islands.update(island_map.keys())
                for island_node in island_map.values():
                    environments.update(island_node.get("environment", {}).keys())

    return {
        "space": sorted(spaces),
        "network": sorted(networks),
        "region": sorted(regions),
        "island": sorted(islands),
        "environment": sorted(environments),
        "projects": sorted(projects_doc.get("projects", [])),
    }


def resolve_coordinate_tree(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Nested variant of ``resolve_coordinates`` — mirrors the origin's
    ``/coordinates?format=tree`` route. Deepest level is the sorted env list."""
    doc = _find(docs, "enterprise_configuration") or {}
    projects_doc = _find(docs, "project_registry") or {}

    tree: Dict[str, Any] = {}
    for space_name, space_node in doc.get("space", {}).items():
        networks = tree.setdefault(space_name, {})
        for network_name, network_node in space_node.get("network", {}).items():
            regions = networks.setdefault(network_name, {})
            for region_name, region_node in network_node.get("region", {}).items():
                islands = regions.setdefault(region_name, {})
                for island_name, island_node in region_node.get("island", {}).items():
                    islands[island_name] = sorted(island_node.get("environment", {}).keys())

    return {"coordinates": tree, "projects": sorted(projects_doc.get("projects", []))}


# --------------------------------------------------------------------------- #
# respx wiring.
# --------------------------------------------------------------------------- #


def _config_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        result = resolve_config(docs, params)
        if not result:
            return httpx.Response(
                404, json={"detail": "No matching configuration metrics located."}
            )
        return httpx.Response(200, json={"metadata": params, "configurations": result})

    return handler


def _naming_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        parts = resolve_naming(docs, params)
        if not parts:
            return httpx.Response(404, json={"detail": "Target translation guidelines missing."})
        return httpx.Response(200, json={"metadata": params, "naming_parts": parts})

    return handler


def _projects_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        projects = list_projects(docs)
        if not projects:
            return httpx.Response(404, json={"detail": "The project inventory catalog is empty."})
        return httpx.Response(200, json={"projects": projects})

    return handler


def _coordinates_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=resolve_coordinates(docs))

    return handler


def _coordinate_tree_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=resolve_coordinate_tree(docs))

    return handler


def register_upstream_routes(router, docs, base_url: str, prefix: str):
    base = base_url.rstrip("/")
    router.get(f"{base}{prefix}/projects", name="projects").mock(
        side_effect=_projects_handler(docs)
    )
    router.get(f"{base}{prefix}/coordinates/tree", name="coordinates_tree").mock(
        side_effect=_coordinate_tree_handler(docs)
    )
    router.get(f"{base}{prefix}/coordinates", name="coordinates").mock(
        side_effect=_coordinates_handler(docs)
    )
    router.get(f"{base}{prefix}/config", name="config").mock(side_effect=_config_handler(docs))
    router.get(f"{base}{prefix}/naming", name="naming").mock(side_effect=_naming_handler(docs))
    return router


def register_token_route(
    router, token_url: str, *, name: str = "token", access_token: str = "sso-token-abc"
):
    router.post(token_url, name=name).mock(
        return_value=httpx.Response(
            200, json={"access_token": access_token, "token_type": "Bearer", "expires_in": 3600}
        )
    )
    return router
