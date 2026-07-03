"""Validator behaviour for InfraMetadata / RequiredInfraMetadata.

Two guards must hold: validators are permissive when the allowlist set is empty,
and permissive for omitted (``None``) coordinates.
"""

import pytest
from pydantic import ValidationError

from tashtiot_apis_library.fastapi_template.config_api import (
    InfraMetadata,
    RequiredInfraMetadata,
    models,
)

COORD_TO_ALLOWLIST = [
    ("space", models.LIVE_ALLOWED_SPACES),
    ("network", models.LIVE_ALLOWED_NETWORKS),
    ("region", models.LIVE_ALLOWED_REGIONS),
    ("island", models.LIVE_ALLOWED_ISLANDS),
    ("environment", models.LIVE_ALLOWED_ENVIRONMENTS),
    ("project", models.LIVE_ALLOWED_PROJECTS),
]


class TestEmptyAllowlistIsPermissive:
    @pytest.mark.parametrize("field", [c for c, _ in COORD_TO_ALLOWLIST])
    def test_arbitrary_value_accepted_when_allowlist_empty(self, field):
        meta = InfraMetadata(**{field: "anything-goes"})
        assert getattr(meta, field) == "anything-goes"


class TestNoneIsPermissive:
    @pytest.mark.parametrize("field,allowlist", COORD_TO_ALLOWLIST)
    def test_none_accepted_even_when_allowlist_populated(self, field, allowlist):
        allowlist.update({"only-valid-value"})
        meta = InfraMetadata(**{field: None})
        assert getattr(meta, field) is None

    def test_all_omitted_is_valid(self):
        meta = InfraMetadata()
        assert meta.model_dump() == {
            "space": None,
            "network": None,
            "region": None,
            "island": None,
            "environment": None,
            "project": None,
        }


class TestPopulatedAllowlistEnforced:
    @pytest.mark.parametrize("field,allowlist", COORD_TO_ALLOWLIST)
    def test_value_in_allowlist_accepted(self, field, allowlist):
        allowlist.update({"good", "also-good"})
        meta = InfraMetadata(**{field: "good"})
        assert getattr(meta, field) == "good"

    @pytest.mark.parametrize("field,allowlist", COORD_TO_ALLOWLIST)
    def test_value_outside_allowlist_rejected(self, field, allowlist):
        allowlist.update({"good"})
        with pytest.raises(ValidationError) as exc:
            InfraMetadata(**{field: "bad"})
        assert "bad" in str(exc.value)


class TestRequiredInfraMetadata:
    def _all_coords(self):
        return {
            "space": "core-infrastructure",
            "network": "backbone-net",
            "region": "us-east",
            "island": "compute-island-a",
            "environment": "production",
            "project": "payment-gateway",
        }

    def test_full_coords_valid(self):
        meta = RequiredInfraMetadata(**self._all_coords())
        assert meta.environment == "production"

    @pytest.mark.parametrize(
        "missing",
        [
            "space",
            "network",
            "region",
            "island",
            "environment",
            "project",
        ],
    )
    def test_missing_any_coordinate_is_error(self, missing):
        coords = self._all_coords()
        del coords[missing]
        with pytest.raises(ValidationError) as exc:
            RequiredInfraMetadata(**coords)
        assert missing in str(exc.value)

    def test_inherits_allowlist_validation(self):
        models.LIVE_ALLOWED_ENVIRONMENTS.update({"production"})
        coords = self._all_coords()
        coords["environment"] = "not-a-real-env"
        with pytest.raises(ValidationError):
            RequiredInfraMetadata(**coords)


class TestCoordinateTreeHierarchy:
    """Tier 2: a coordinate must sit under its selected parent per LIVE_COORDINATE_TREE.

    The autouse conftest fixture clears the flat allowlists (permissive) and the tree
    before each test, so the hierarchy check is the only gate exercised here.
    """

    TREE = {
        "coordinates": {
            "core-infrastructure": {
                "backbone-net": {
                    "us-east": {"compute-island-a": ["production", "staging"]},
                },
            },
        },
        "projects": ["payment-gateway"],
    }

    def _full(self, **overrides):
        coords = {
            "space": "core-infrastructure",
            "network": "backbone-net",
            "region": "us-east",
            "island": "compute-island-a",
            "environment": "production",
            "project": "payment-gateway",
        }
        coords.update(overrides)
        return coords

    def test_valid_chain_passes(self):
        models.LIVE_COORDINATE_TREE.update(self.TREE)
        assert RequiredInfraMetadata(**self._full()).island == "compute-island-a"

    def test_island_not_under_region_rejected(self):
        models.LIVE_COORDINATE_TREE.update(self.TREE)
        with pytest.raises(ValidationError) as exc:
            RequiredInfraMetadata(**self._full(island="compute-island-z"))
        assert "island" in str(exc.value)

    def test_region_not_under_network_rejected(self):
        models.LIVE_COORDINATE_TREE.update(self.TREE)
        with pytest.raises(ValidationError) as exc:
            RequiredInfraMetadata(**self._full(region="eu-west"))
        assert "region" in str(exc.value)

    def test_environment_not_in_leaf_rejected(self):
        models.LIVE_COORDINATE_TREE.update(self.TREE)
        with pytest.raises(ValidationError) as exc:
            RequiredInfraMetadata(**self._full(environment="dev"))
        assert "environment" in str(exc.value)

    def test_partial_selection_is_permissive(self):
        models.LIVE_COORDINATE_TREE.update(self.TREE)
        # network omitted -> descent stops; deeper coordinates aren't constrained.
        meta = InfraMetadata(space="core-infrastructure", region="anything", island="anything")
        assert meta.region == "anything"

    def test_empty_tree_is_permissive(self):
        # tree left empty by the conftest reset -> any combination is accepted.
        meta = RequiredInfraMetadata(**self._full(region="anywhere", island="anything"))
        assert meta.space == "core-infrastructure"

    def test_shallow_subtree_is_permissive(self):
        models.LIVE_COORDINATE_TREE.update({"coordinates": {"core-infrastructure": {}}})
        meta = InfraMetadata(space="core-infrastructure", network="anything")
        assert meta.network == "anything"
