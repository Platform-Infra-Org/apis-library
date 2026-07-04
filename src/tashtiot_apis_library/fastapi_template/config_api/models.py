from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

# Mutable module-level allowlists, repopulated in place by the background polling
# loop (provider.crawl_and_sync_keys) from the upstream Config API. They drive BOTH
# Pydantic request validation (the field_validators below) AND the OpenAPI enum
# dropdowns (see openapi.py).
LIVE_ALLOWED_NETWORKS: Set[str] = set()
LIVE_ALLOWED_REGIONS: Set[str] = set()
LIVE_ALLOWED_ISLANDS: Set[str] = set()
LIVE_ALLOWED_ENVIRONMENTS: Set[str] = set()
LIVE_ALLOWED_SPACES: Set[str] = set()
LIVE_ALLOWED_PROJECTS: Set[str] = set()

# Nested coordinate hierarchy (space -> network -> region -> island -> [envs]) plus the
# flat projects list, repopulated in place by the poller from the upstream /coordinates/tree.
# Drives the hierarchical model_validator below (a child must sit under its selected parent).
# Mutated in place so a captured reference stays current.
LIVE_COORDINATE_TREE: Dict[str, Any] = {}

# Maps each coordinate field to its allowlist. Holds the same set objects above,
# which the poller repopulates in place, so these references stay current.
_COORDINATE_ALLOWLISTS: Dict[str, Set[str]] = {
    "space": LIVE_ALLOWED_SPACES,
    "network": LIVE_ALLOWED_NETWORKS,
    "region": LIVE_ALLOWED_REGIONS,
    "island": LIVE_ALLOWED_ISLANDS,
    "environment": LIVE_ALLOWED_ENVIRONMENTS,
    "project": LIVE_ALLOWED_PROJECTS,
}


class InfraMetadata(BaseModel):
    """The environment allocation coordinates layout mapping contract.

    All coordinates are optional. Omitting them on the naming route returns the
    entire naming dictionary; on the config route a missing coordinate simply
    contributes no override layer to the cascade.

    Validators are permissive when the corresponding allowlist is empty (e.g.
    before the first poll, or when the upstream is unreachable / its document is
    missing) and for omitted (``None``) coordinates. Preserve this guard when
    editing them.
    """

    space: Optional[str] = Field(
        None, description="Target organizational data partitioning space name"
    )
    network: Optional[str] = Field(None, description="Target network partition layer name")
    region: Optional[str] = Field(None, description="Target geographical region code")
    island: Optional[str] = Field(None, description="Target logical compute cluster zone")
    environment: Optional[str] = Field(None, description="Target lifecycle deployment tier status")
    project: Optional[str] = Field(
        None, description="The platform application name submitting the request"
    )

    @field_validator("space", "network", "region", "island", "environment", "project")
    @classmethod
    def _validate_coordinate(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        # Permissive when the allowlist is empty (pre-poll / upstream missing) or v is None.
        allowed = _COORDINATE_ALLOWLISTS[info.field_name]
        if v is not None and allowed and v not in allowed:
            raise ValueError(
                f"Invalid {info.field_name} selection '{v}'. Permitted: {list(allowed)}"
            )
        return v

    @model_validator(mode="after")
    def _validate_hierarchy(self) -> "InfraMetadata":
        """Reject a coordinate that isn't a child of its selected parent per the live
        coordinate tree (``LIVE_COORDINATE_TREE``).

        Permissive when the tree -- or the subtree reached so far -- is empty (pre-poll
        or partially seeded), and stops at the first omitted (``None``) level so partial
        selections aren't over-constrained. Complements the per-field allowlist checks
        above: those catch a value invalid *on its own*, this catches an invalid
        *combination*. Preserve both guards when editing."""
        node: Any = LIVE_COORDINATE_TREE.get("coordinates", {})
        for name in ("space", "network", "region", "island"):
            if not isinstance(node, dict) or not node:
                return self  # tree absent/shallow here -> permissive
            value = getattr(self, name)
            if value is None:
                return self  # partial selection -> stop descending
            if value not in node:
                raise ValueError(
                    f"Invalid {name} selection '{value}' for the chosen parent coordinates"
                )
            node = node[value]
        # environment is the leaf list under the selected island.
        if (
            self.environment is not None
            and isinstance(node, list)
            and node
            and self.environment not in node
        ):
            raise ValueError(
                f"Invalid environment selection '{self.environment}' for the chosen coordinates"
            )
        return self


class RequiredInfraMetadata(InfraMetadata):
    """Strict variant where every coordinate is mandatory.

    Used by the config cascade route, which cannot resolve without a full set of
    coordinates. Field validators are inherited; only requiredness is overridden,
    so a missing coordinate yields FastAPI's standard 422 automatically.
    """

    space: str = Field(..., description="Target organizational data partitioning space name")
    network: str = Field(..., description="Target network partition layer name")
    region: str = Field(..., description="Target geographical region code")
    island: str = Field(..., description="Target logical compute cluster zone")
    environment: str = Field(..., description="Target lifecycle deployment tier status")
    project: str = Field(..., description="The platform application name submitting the request")


class ConfigResolutionResponse(BaseModel):
    metadata: InfraMetadata
    configurations: Dict[str, Any]


class NamingConventionResponse(BaseModel):
    metadata: InfraMetadata
    naming_parts: Dict[str, Any] = Field(
        ..., description="Dictionary segment tracking resolved metadata DNS tokens"
    )


class AllProjectsResponse(BaseModel):
    projects: List[str] = Field(
        ..., description="List of all platform application names inside the cluster catalog"
    )


class CoordinateCatalogResponse(BaseModel):
    """Every valid value per coordinate level plus the project list.

    Backs a ``/coordinates`` discovery route: it lets clients learn which
    coordinate values the config/naming routes will accept (the same data behind
    the live ``LIVE_ALLOWED_*`` allowlists). Each field is the sorted set of keys
    for that level; an unseeded source yields empty lists (a valid 200 response,
    not a 404)."""

    space: List[str] = Field(default_factory=list, description="Allowed organizational space names")
    network: List[str] = Field(default_factory=list, description="Allowed network partition names")
    region: List[str] = Field(default_factory=list, description="Allowed geographical region codes")
    island: List[str] = Field(
        default_factory=list, description="Allowed compute cluster zone names"
    )
    environment: List[str] = Field(default_factory=list, description="Allowed lifecycle tier names")
    projects: List[str] = Field(
        default_factory=list, description="All registered platform application names"
    )


class CoordinateTreeResponse(BaseModel):
    """Nested variant of the coordinate catalog (``/coordinates?format=tree``).

    ``coordinates`` mirrors the enterprise config hierarchy
    (space → network → region → island → sorted env list); ``projects`` stays flat.
    An unseeded source yields ``{"coordinates": {}, "projects": []}`` (a valid 200)."""

    coordinates: Dict[str, Any] = Field(
        default_factory=dict, description="Nested coordinate hierarchy"
    )
    projects: List[str] = Field(
        default_factory=list, description="All registered platform application names"
    )
