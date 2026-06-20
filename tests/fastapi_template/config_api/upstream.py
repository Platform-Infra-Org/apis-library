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
                    "config": {"ntp_server": "pool.ntp.org", "dns_servers": ["10.0.0.1", "10.0.0.2"]},
                    "region": {
                        "us-east": {
                            "config": {"aws_vpc_id": "vpc-0a1b2c3d"},
                            "island": {
                                "compute-island-a": {
                                    "config": {"cluster_size": 5},
                                    "environment": {
                                        "staging": {"config": {}},
                                        "production": {"config": {"cluster_size": 20, "debug_mode": False}},
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


# --------------------------------------------------------------------------- #
# respx wiring.
# --------------------------------------------------------------------------- #

def _config_handler(docs):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        result = resolve_config(docs, params)
        if not result:
            return httpx.Response(404, json={"detail": "No matching configuration metrics located."})
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


def register_upstream_routes(router, docs, base_url: str, prefix: str):
    base = base_url.rstrip("/")
    router.get(f"{base}{prefix}/projects", name="projects").mock(side_effect=_projects_handler(docs))
    router.get(f"{base}{prefix}/config", name="config").mock(side_effect=_config_handler(docs))
    router.get(f"{base}{prefix}/naming", name="naming").mock(side_effect=_naming_handler(docs))
    return router


def register_token_route(router, token_url: str, *, name: str = "token", access_token: str = "sso-token-abc"):
    router.post(token_url, name=name).mock(
        return_value=httpx.Response(
            200, json={"access_token": access_token, "token_type": "Bearer", "expires_in": 3600}
        )
    )
    return router
