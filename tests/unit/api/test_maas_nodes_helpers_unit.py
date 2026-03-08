"""Unit tests for pure helper functions in src/api/maas_nodes.py."""

from __future__ import annotations

from typing import Set
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.maas_nodes import (
    MeshOperator,
    _expand_permission_aliases,
    _normalize_external_telemetry_payload,
    _to_optional_float,
)
from src.core.rbac import MeshPermission


# ---------------------------------------------------------------------------
# _to_optional_float
# ---------------------------------------------------------------------------


class TestToOptionalFloat:
    def test_none_returns_none(self):
        assert _to_optional_float(None) is None

    def test_int_converted(self):
        assert _to_optional_float(5) == 5.0

    def test_float_passthrough(self):
        assert _to_optional_float(3.14) == pytest.approx(3.14)

    def test_string_number_converted(self):
        assert _to_optional_float("2.5") == pytest.approx(2.5)

    def test_invalid_string_returns_none(self):
        assert _to_optional_float("not-a-number") is None

    def test_empty_string_returns_none(self):
        assert _to_optional_float("") is None

    def test_list_returns_none(self):
        assert _to_optional_float([1, 2]) is None

    def test_zero_converted(self):
        assert _to_optional_float(0) == 0.0

    def test_negative_converted(self):
        assert _to_optional_float(-5) == -5.0


# ---------------------------------------------------------------------------
# _normalize_external_telemetry_payload
# ---------------------------------------------------------------------------


class TestNormalizeExternalTelemetryPayload:
    def test_latency_alias_added(self):
        result = _normalize_external_telemetry_payload({"latency": 12.5})
        assert result["latency_ms"] == 12.5

    def test_latency_ms_not_overridden_if_present(self):
        result = _normalize_external_telemetry_payload({"latency_ms": 10.0, "latency": 20.0})
        assert result["latency_ms"] == 10.0

    def test_negative_latency_not_added(self):
        result = _normalize_external_telemetry_payload({"latency": -1.0})
        assert "latency_ms" not in result

    def test_neighbors_int_aliased(self):
        result = _normalize_external_telemetry_payload({"neighbors": 5})
        assert result["neighbors_count"] == 5

    def test_neighbors_count_not_overridden(self):
        result = _normalize_external_telemetry_payload({"neighbors_count": 3, "neighbors": 10})
        assert result["neighbors_count"] == 3

    def test_neighbors_bool_not_aliased(self):
        # bool is a subclass of int but should be excluded
        result = _normalize_external_telemetry_payload({"neighbors": True})
        assert "neighbors_count" not in result

    def test_neighbors_float_whole_number_aliased(self):
        result = _normalize_external_telemetry_payload({"neighbors": 4.0})
        assert result["neighbors_count"] == 4

    def test_neighbors_float_fractional_not_aliased(self):
        result = _normalize_external_telemetry_payload({"neighbors": 4.7})
        assert "neighbors_count" not in result

    def test_status_stripped_and_lowercased(self):
        result = _normalize_external_telemetry_payload({"status": "  ACTIVE  "})
        assert result["status"] == "active"

    def test_non_string_status_not_modified(self):
        result = _normalize_external_telemetry_payload({"status": 200})
        assert result["status"] == 200

    def test_original_dict_not_mutated(self):
        original = {"latency": 5.0, "status": "UP"}
        _normalize_external_telemetry_payload(original)
        assert original["status"] == "UP"

    def test_empty_payload_returns_empty(self):
        result = _normalize_external_telemetry_payload({})
        assert result == {}

    def test_unknown_keys_preserved(self):
        result = _normalize_external_telemetry_payload({"custom": "data", "x": 42})
        assert result["custom"] == "data"
        assert result["x"] == 42


# ---------------------------------------------------------------------------
# _expand_permission_aliases
# ---------------------------------------------------------------------------


class TestExpandPermissionAliases:
    def test_mesh_read_expands_to_mesh_view(self):
        perms = {MeshPermission.MESH_READ}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.MESH_VIEW in expanded

    def test_mesh_view_expands_to_mesh_read(self):
        perms = {MeshPermission.MESH_VIEW}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.MESH_READ in expanded

    def test_node_read_expands_to_node_view(self):
        perms = {MeshPermission.NODE_READ}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.NODE_VIEW in expanded

    def test_acl_read_expands_to_acl_view(self):
        perms = {MeshPermission.ACL_READ}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.ACL_VIEW in expanded

    def test_acl_write_expands_to_acl_update(self):
        perms = {MeshPermission.ACL_WRITE}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.ACL_UPDATE in expanded

    def test_telemetry_read_expands_to_telemetry_view(self):
        perms = {MeshPermission.TELEMETRY_READ}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.TELEMETRY_VIEW in expanded

    def test_unrelated_permissions_not_affected(self):
        perms = {MeshPermission.NODE_DELETE}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.NODE_DELETE in expanded
        # No accidental expansion into unrelated groups
        assert MeshPermission.MESH_READ not in expanded

    def test_empty_set_returns_empty(self):
        expanded = _expand_permission_aliases(set())
        assert expanded == set()

    def test_original_permissions_retained(self):
        perms = {MeshPermission.MESH_READ}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.MESH_READ in expanded

    def test_multiple_groups_expanded(self):
        perms = {MeshPermission.MESH_READ, MeshPermission.NODE_WRITE}
        expanded = _expand_permission_aliases(perms)
        assert MeshPermission.MESH_VIEW in expanded
        assert MeshPermission.NODE_WRITE in expanded


# ---------------------------------------------------------------------------
# MeshOperator (with custom_permissions, no DB needed)
# ---------------------------------------------------------------------------


def _make_user(uid: str = "u-1", role: str = "operator") -> MagicMock:
    user = MagicMock()
    user.id = uid
    user.role = role
    return user


def _make_db(owner_id: str | None = None, mesh_id: str = "mesh-1") -> MagicMock:
    db = MagicMock()
    if owner_id is not None:
        mesh = MagicMock()
        mesh.owner_id = owner_id
        db.query.return_value.filter.return_value.first.return_value = mesh
    else:
        db.query.return_value.filter.return_value.first.return_value = None
    return db


class TestMeshOperatorWithCustomPermissions:
    def test_has_permission_true(self):
        user = _make_user()
        db = _make_db()
        perms = {MeshPermission.NODE_READ, MeshPermission.NODE_APPROVE}
        op = MeshOperator(user, "mesh-1", db, custom_permissions=perms)
        assert op.has_permission(MeshPermission.NODE_READ) is True

    def test_has_permission_false(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions={MeshPermission.NODE_READ})
        assert op.has_permission(MeshPermission.NODE_DELETE) is False

    def test_require_permission_raises_when_missing(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions=set())
        with pytest.raises(HTTPException) as exc_info:
            op.require_permission(MeshPermission.MESH_WRITE)
        assert exc_info.value.status_code == 403

    def test_require_permission_does_not_raise_when_granted(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions={MeshPermission.MESH_WRITE})
        op.require_permission(MeshPermission.MESH_WRITE)  # should not raise

    def test_has_any_permission_true(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions={MeshPermission.NODE_READ})
        assert op.has_any_permission({MeshPermission.NODE_READ, MeshPermission.MESH_WRITE}) is True

    def test_has_any_permission_false(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions={MeshPermission.NODE_READ})
        assert op.has_any_permission({MeshPermission.MESH_WRITE, MeshPermission.NODE_DELETE}) is False

    def test_has_all_permissions_true(self):
        user = _make_user()
        db = _make_db()
        perms = {MeshPermission.NODE_READ, MeshPermission.MESH_READ}
        op = MeshOperator(user, "mesh-1", db, custom_permissions=perms)
        assert op.has_all_permissions({MeshPermission.NODE_READ, MeshPermission.MESH_READ}) is True

    def test_has_all_permissions_false_when_subset_missing(self):
        user = _make_user()
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions={MeshPermission.NODE_READ})
        assert op.has_all_permissions({MeshPermission.NODE_READ, MeshPermission.MESH_WRITE}) is False

    def test_is_owner_true_when_user_owns_mesh(self):
        user = _make_user("u-owner")
        db = _make_db(owner_id="u-owner")
        op = MeshOperator(user, "mesh-1", db, custom_permissions=set())
        assert op.is_owner is True

    def test_is_owner_false_when_different_owner(self):
        user = _make_user("u-other")
        db = _make_db(owner_id="u-owner")
        op = MeshOperator(user, "mesh-1", db, custom_permissions=set())
        assert op.is_owner is False

    def test_is_owner_false_when_mesh_not_found(self):
        user = _make_user("u-1")
        db = _make_db(owner_id=None)
        op = MeshOperator(user, "mesh-1", db, custom_permissions=set())
        assert op.is_owner is False

    def test_user_id_and_mesh_id_stored(self):
        user = _make_user("u-abc")
        db = _make_db()
        op = MeshOperator(user, "mesh-xyz", db, custom_permissions=set())
        assert op.user_id == "u-abc"
        assert op.mesh_id == "mesh-xyz"

    def test_role_stored(self):
        user = _make_user(role="admin")
        db = _make_db()
        op = MeshOperator(user, "mesh-1", db, custom_permissions=set())
        assert op.role == "admin"
