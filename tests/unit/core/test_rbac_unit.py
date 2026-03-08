"""Unit tests for src.core.rbac — MeshPermission enum and DEFAULT_ROLE_PERMISSIONS."""

from __future__ import annotations

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")


from src.core.rbac import DEFAULT_ROLE_PERMISSIONS, MeshPermission


# ---------------------------------------------------------------------------
# MeshPermission enum
# ---------------------------------------------------------------------------


class TestMeshPermission:
    """Tests for the MeshPermission string enum."""

    def test_all_values_are_strings(self):
        for perm in MeshPermission:
            assert isinstance(perm.value, str), f"{perm.name} value should be str"

    def test_values_contain_colon_namespace(self):
        """Every permission value must follow the 'namespace:action' convention."""
        for perm in MeshPermission:
            assert ":" in perm.value, f"{perm.name} value '{perm.value}' missing ':' separator"

    def test_mesh_permissions_present(self):
        assert MeshPermission.MESH_READ.value == "mesh:read"
        assert MeshPermission.MESH_WRITE.value == "mesh:write"
        assert MeshPermission.MESH_CREATE.value == "mesh:create"
        assert MeshPermission.MESH_UPDATE.value == "mesh:update"
        assert MeshPermission.MESH_DELETE.value == "mesh:delete"
        assert MeshPermission.MESH_VIEW.value == "mesh:view"

    def test_node_permissions_present(self):
        assert MeshPermission.NODE_READ.value == "node:read"
        assert MeshPermission.NODE_VIEW.value == "node:view"
        assert MeshPermission.NODE_WRITE.value == "node:write"
        assert MeshPermission.NODE_APPROVE.value == "node:approve"
        assert MeshPermission.NODE_REVOKE.value == "node:revoke"
        assert MeshPermission.NODE_DELETE.value == "node:delete"
        assert MeshPermission.NODE_HEAL.value == "node:heal"

    def test_acl_permissions_present(self):
        assert MeshPermission.ACL_READ.value == "acl:read"
        assert MeshPermission.ACL_VIEW.value == "acl:view"
        assert MeshPermission.ACL_WRITE.value == "acl:write"
        assert MeshPermission.ACL_UPDATE.value == "acl:update"

    def test_analytics_telemetry_permissions_present(self):
        assert MeshPermission.ANALYTICS_VIEW.value == "analytics:view"
        assert MeshPermission.TELEMETRY_READ.value == "telemetry:read"
        assert MeshPermission.TELEMETRY_VIEW.value == "telemetry:view"
        assert MeshPermission.TELEMETRY_EXPORT.value == "telemetry:export"

    def test_playbook_permissions_present(self):
        assert MeshPermission.PLAYBOOK_CREATE.value == "playbook:create"
        assert MeshPermission.PLAYBOOK_VIEW.value == "playbook:view"

    def test_billing_marketplace_permissions_present(self):
        assert MeshPermission.BILLING_VIEW.value == "billing:view"
        assert MeshPermission.MARKETPLACE_LIST.value == "marketplace:list"
        assert MeshPermission.MARKETPLACE_RENT.value == "marketplace:rent"

    def test_vpn_permissions_present(self):
        assert MeshPermission.VPN_CONFIG.value == "vpn:config"
        assert MeshPermission.VPN_STATUS.value == "vpn:status"
        assert MeshPermission.VPN_ADMIN.value == "vpn:admin"

    def test_permission_is_str_subclass(self):
        """MeshPermission inherits from str, so instances compare equal to plain strings."""
        assert MeshPermission.MESH_READ == "mesh:read"
        assert MeshPermission.VPN_ADMIN == "vpn:admin"

    def test_permission_enum_identity(self):
        """Lookups by value return the same enum member."""
        assert MeshPermission("mesh:read") is MeshPermission.MESH_READ
        assert MeshPermission("vpn:admin") is MeshPermission.VPN_ADMIN

    def test_enum_total_count(self):
        """Ensure no accidental removal of permissions — at least 30 defined."""
        assert len(list(MeshPermission)) >= 25

    def test_unique_values(self):
        """All enum values must be unique."""
        values = [p.value for p in MeshPermission]
        assert len(values) == len(set(values)), "Duplicate permission values found"

    def test_permission_in_set_membership(self):
        perm_set = {MeshPermission.MESH_READ, MeshPermission.NODE_APPROVE}
        assert MeshPermission.MESH_READ in perm_set
        assert MeshPermission.VPN_ADMIN not in perm_set


# ---------------------------------------------------------------------------
# DEFAULT_ROLE_PERMISSIONS
# ---------------------------------------------------------------------------


class TestDefaultRolePermissions:
    """Tests for the DEFAULT_ROLE_PERMISSIONS mapping."""

    def test_expected_roles_defined(self):
        for role in ("admin", "operator", "user", "viewer"):
            assert role in DEFAULT_ROLE_PERMISSIONS, f"Role '{role}' missing"

    def test_each_role_has_non_empty_permissions(self):
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            assert len(perms) > 0, f"Role '{role}' has no permissions"

    def test_permissions_are_mesh_permission_instances(self):
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            for perm in perms:
                assert isinstance(perm, MeshPermission), (
                    f"Role '{role}' contains non-MeshPermission value: {perm!r}"
                )

    # ---- admin ----

    def test_admin_has_all_permissions(self):
        admin_perms = DEFAULT_ROLE_PERMISSIONS["admin"]
        all_perms = set(MeshPermission)
        assert admin_perms == all_perms

    def test_admin_has_vpn_admin(self):
        assert MeshPermission.VPN_ADMIN in DEFAULT_ROLE_PERMISSIONS["admin"]

    # ---- operator ----

    def test_operator_has_key_operational_permissions(self):
        op_perms = DEFAULT_ROLE_PERMISSIONS["operator"]
        for perm in (
            MeshPermission.MESH_VIEW,
            MeshPermission.MESH_UPDATE,
            MeshPermission.NODE_VIEW,
            MeshPermission.NODE_APPROVE,
            MeshPermission.NODE_REVOKE,
            MeshPermission.NODE_HEAL,
            MeshPermission.ACL_VIEW,
            MeshPermission.ACL_UPDATE,
            MeshPermission.ANALYTICS_VIEW,
            MeshPermission.TELEMETRY_VIEW,
            MeshPermission.PLAYBOOK_VIEW,
            MeshPermission.PLAYBOOK_CREATE,
            MeshPermission.VPN_CONFIG,
            MeshPermission.VPN_STATUS,
        ):
            assert perm in op_perms, f"Operator missing expected permission: {perm}"

    def test_operator_lacks_vpn_admin(self):
        """Operators should not have the elevated VPN_ADMIN permission."""
        assert MeshPermission.VPN_ADMIN not in DEFAULT_ROLE_PERMISSIONS["operator"]

    def test_operator_lacks_node_delete(self):
        """Operators should not be able to delete nodes directly."""
        assert MeshPermission.NODE_DELETE not in DEFAULT_ROLE_PERMISSIONS["operator"]

    def test_operator_lacks_billing_view(self):
        assert MeshPermission.BILLING_VIEW not in DEFAULT_ROLE_PERMISSIONS["operator"]

    # ---- user ----

    def test_user_has_mesh_crud_permissions(self):
        user_perms = DEFAULT_ROLE_PERMISSIONS["user"]
        for perm in (
            MeshPermission.MESH_VIEW,
            MeshPermission.MESH_CREATE,
            MeshPermission.MESH_UPDATE,
            MeshPermission.MESH_DELETE,
            MeshPermission.NODE_VIEW,
        ):
            assert perm in user_perms, f"User missing expected permission: {perm}"

    def test_user_has_billing_and_marketplace(self):
        user_perms = DEFAULT_ROLE_PERMISSIONS["user"]
        assert MeshPermission.BILLING_VIEW in user_perms
        assert MeshPermission.MARKETPLACE_LIST in user_perms
        assert MeshPermission.MARKETPLACE_RENT in user_perms

    def test_user_has_vpn_config_and_status(self):
        user_perms = DEFAULT_ROLE_PERMISSIONS["user"]
        assert MeshPermission.VPN_CONFIG in user_perms
        assert MeshPermission.VPN_STATUS in user_perms

    def test_user_lacks_vpn_admin(self):
        assert MeshPermission.VPN_ADMIN not in DEFAULT_ROLE_PERMISSIONS["user"]

    def test_user_lacks_node_approve_and_revoke(self):
        user_perms = DEFAULT_ROLE_PERMISSIONS["user"]
        assert MeshPermission.NODE_APPROVE not in user_perms
        assert MeshPermission.NODE_REVOKE not in user_perms

    def test_user_lacks_acl_write(self):
        assert MeshPermission.ACL_WRITE not in DEFAULT_ROLE_PERMISSIONS["user"]

    # ---- viewer ----

    def test_viewer_has_read_only_permissions(self):
        viewer_perms = DEFAULT_ROLE_PERMISSIONS["viewer"]
        for perm in (
            MeshPermission.MESH_VIEW,
            MeshPermission.NODE_VIEW,
            MeshPermission.ACL_VIEW,
            MeshPermission.ANALYTICS_VIEW,
            MeshPermission.TELEMETRY_VIEW,
            MeshPermission.VPN_STATUS,
        ):
            assert perm in viewer_perms, f"Viewer missing expected permission: {perm}"

    def test_viewer_lacks_write_permissions(self):
        viewer_perms = DEFAULT_ROLE_PERMISSIONS["viewer"]
        for write_perm in (
            MeshPermission.MESH_WRITE,
            MeshPermission.MESH_CREATE,
            MeshPermission.MESH_UPDATE,
            MeshPermission.MESH_DELETE,
            MeshPermission.NODE_WRITE,
            MeshPermission.NODE_APPROVE,
            MeshPermission.NODE_REVOKE,
            MeshPermission.NODE_DELETE,
            MeshPermission.ACL_WRITE,
            MeshPermission.ACL_UPDATE,
            MeshPermission.VPN_CONFIG,
            MeshPermission.VPN_ADMIN,
        ):
            assert write_perm not in viewer_perms, (
                f"Viewer incorrectly has write permission: {write_perm}"
            )

    def test_viewer_is_subset_of_operator(self):
        """Viewer permissions must be a strict subset of operator permissions."""
        viewer_perms = DEFAULT_ROLE_PERMISSIONS["viewer"]
        operator_perms = DEFAULT_ROLE_PERMISSIONS["operator"]
        assert viewer_perms.issubset(operator_perms)

    # ---- cross-role ----

    def test_admin_is_superset_of_all_other_roles(self):
        admin_perms = DEFAULT_ROLE_PERMISSIONS["admin"]
        for role in ("operator", "user", "viewer"):
            role_perms = DEFAULT_ROLE_PERMISSIONS[role]
            assert role_perms.issubset(admin_perms), (
                f"Admin should have all permissions that '{role}' has"
            )

    def test_permissions_are_sets_not_lists(self):
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            assert isinstance(perms, set), f"Role '{role}' permissions should be a set, got {type(perms)}"

    def test_role_permissions_are_independent_objects(self):
        """Mutating one role's permission set must not affect others."""
        admin_copy = set(DEFAULT_ROLE_PERMISSIONS["admin"])
        viewer_perms = DEFAULT_ROLE_PERMISSIONS["viewer"]
        # Verify sizes haven't changed (no cross-references)
        assert DEFAULT_ROLE_PERMISSIONS["admin"] == admin_copy
        assert DEFAULT_ROLE_PERMISSIONS["viewer"] is viewer_perms
