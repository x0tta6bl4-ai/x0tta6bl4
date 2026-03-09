"""Unit tests for pure helper functions in src/api/maas_auth.py."""

from __future__ import annotations

import sys
import importlib
from unittest import mock

import pytest

# Pre-import so patch.dict teardown doesn't evict it, which would break
# isinstance(MeshPermission, ...) checks inside the loaded module.
import src.core.rbac  # noqa: F401


# ---------------------------------------------------------------------------
# Module load — stub heavy dependencies so no DB/auth infra needed
# ---------------------------------------------------------------------------

def _load_auth_module():
    stubs = {
        "src.database": mock.MagicMock(),
        "src.api.maas_security": mock.MagicMock(),
        "src.services.maas_auth_service": mock.MagicMock(),
        "src.utils.audit": mock.MagicMock(),
        "authlib": mock.MagicMock(),
        "authlib.integrations": mock.MagicMock(),
        "authlib.integrations.starlette_client": mock.MagicMock(),
    }
    # Provide a no-op MaaSAuthService constructor
    mock_service_cls = mock.MagicMock(return_value=mock.MagicMock())
    stubs["src.services.maas_auth_service"].MaaSAuthService = mock_service_cls
    # ApiKeyManager.generate
    stubs["src.api.maas_security"].ApiKeyManager = mock.MagicMock()
    stubs["src.api.maas_security"].oidc_validator = mock.MagicMock(enabled=False)

    key = "src.api.maas_auth"
    if key in sys.modules:
        del sys.modules[key]
    with mock.patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    return mod


_mod = _load_auth_module()
_permission_to_value = _mod._permission_to_value
_default_permissions_for_role = _mod._default_permissions_for_role
_LEGACY_ROLE_DEFAULTS = _mod._LEGACY_ROLE_DEFAULTS

from src.core.rbac import MeshPermission, DEFAULT_ROLE_PERMISSIONS


# ---------------------------------------------------------------------------
# _permission_to_value
# ---------------------------------------------------------------------------


class TestPermissionToValue:
    def test_enum_returns_value(self):
        assert _permission_to_value(MeshPermission.MESH_READ) == "mesh:read"

    def test_string_returned_as_is(self):
        assert _permission_to_value("mesh:write") == "mesh:write"

    def test_string_with_whitespace_stripped(self):
        assert _permission_to_value("  node:view  ") == "node:view"

    def test_all_enum_values_round_trip(self):
        for perm in MeshPermission:
            assert _permission_to_value(perm) == perm.value

    def test_arbitrary_string_passthrough(self):
        assert _permission_to_value("custom:scope") == "custom:scope"

    def test_enum_value_matches_str_value(self):
        """Passing the .value string produces the same result as passing the enum."""
        for perm in MeshPermission:
            assert _permission_to_value(perm) == _permission_to_value(perm.value)


# ---------------------------------------------------------------------------
# _default_permissions_for_role
# ---------------------------------------------------------------------------


class TestDefaultPermissionsForRole:
    # --- admin ---

    def test_admin_has_all_permissions(self):
        perms = _default_permissions_for_role("admin")
        for p in MeshPermission:
            assert p.value in perms, f"admin missing {p.value}"

    def test_admin_result_is_set_of_strings(self):
        perms = _default_permissions_for_role("admin")
        assert isinstance(perms, set)
        assert all(isinstance(p, str) for p in perms)

    # --- operator ---

    def test_operator_has_mesh_view(self):
        perms = _default_permissions_for_role("operator")
        assert "mesh:view" in perms

    def test_operator_has_node_approve(self):
        perms = _default_permissions_for_role("operator")
        assert "node:approve" in perms

    def test_operator_has_telemetry_view(self):
        perms = _default_permissions_for_role("operator")
        assert "telemetry:view" in perms

    def test_operator_has_analytics_view(self):
        perms = _default_permissions_for_role("operator")
        assert "analytics:view" in perms

    def test_operator_has_playbook_create(self):
        perms = _default_permissions_for_role("operator")
        assert "playbook:create" in perms

    def test_operator_has_legacy_audit_view(self):
        """Operator gets audit:view from _LEGACY_ROLE_DEFAULTS."""
        perms = _default_permissions_for_role("operator")
        assert "audit:view" in perms

    def test_operator_does_not_have_billing_view_via_rbac(self):
        """operator is not in DEFAULT_ROLE_PERMISSIONS for billing:view."""
        rbac_only = {_permission_to_value(p) for p in DEFAULT_ROLE_PERMISSIONS.get("operator", set())}
        assert "billing:view" not in rbac_only

    # --- user ---

    def test_user_has_mesh_create(self):
        perms = _default_permissions_for_role("user")
        assert "mesh:create" in perms

    def test_user_has_billing_view(self):
        perms = _default_permissions_for_role("user")
        assert "billing:view" in perms

    def test_user_has_marketplace_list(self):
        perms = _default_permissions_for_role("user")
        assert "marketplace:list" in perms

    def test_user_has_marketplace_rent(self):
        perms = _default_permissions_for_role("user")
        assert "marketplace:rent" in perms

    def test_user_has_playbook_view(self):
        perms = _default_permissions_for_role("user")
        assert "playbook:view" in perms

    def test_user_does_not_have_node_approve(self):
        perms = _default_permissions_for_role("user")
        assert "node:approve" not in perms

    # --- viewer ---

    def test_viewer_has_mesh_view(self):
        perms = _default_permissions_for_role("viewer")
        assert "mesh:view" in perms

    def test_viewer_has_analytics_view(self):
        perms = _default_permissions_for_role("viewer")
        assert "analytics:view" in perms

    def test_viewer_does_not_have_mesh_create(self):
        perms = _default_permissions_for_role("viewer")
        assert "mesh:create" not in perms

    def test_viewer_does_not_have_node_approve(self):
        perms = _default_permissions_for_role("viewer")
        assert "node:approve" not in perms

    # --- unknown role ---

    def test_unknown_role_returns_empty_set(self):
        perms = _default_permissions_for_role("nonexistent")
        assert perms == set()

    def test_empty_string_role_returns_empty_set(self):
        perms = _default_permissions_for_role("")
        assert perms == set()

    # --- result type ---

    def test_result_is_set_for_all_known_roles(self):
        for role in ("admin", "operator", "user", "viewer"):
            result = _default_permissions_for_role(role)
            assert isinstance(result, set), f"role {role!r} did not return a set"

    def test_rbac_and_legacy_merged(self):
        """operator permissions come from both DEFAULT_ROLE_PERMISSIONS and _LEGACY_ROLE_DEFAULTS."""
        rbac_perms = {_permission_to_value(p) for p in DEFAULT_ROLE_PERMISSIONS.get("operator", set())}
        legacy_perms = _LEGACY_ROLE_DEFAULTS.get("operator", set())
        combined = rbac_perms | legacy_perms
        result = _default_permissions_for_role("operator")
        assert result == combined

    def test_mutating_result_does_not_affect_next_call(self):
        """Return value is a fresh set each call — mutations are not shared."""
        perms1 = _default_permissions_for_role("operator")
        perms1.add("fake:perm")
        perms2 = _default_permissions_for_role("operator")
        assert "fake:perm" not in perms2

    # --- legacy role defaults coverage ---

    def test_legacy_operator_node_revoke(self):
        assert "node:revoke" in _LEGACY_ROLE_DEFAULTS["operator"]

    def test_legacy_user_mesh_delete(self):
        assert "mesh:delete" in _LEGACY_ROLE_DEFAULTS["user"]
