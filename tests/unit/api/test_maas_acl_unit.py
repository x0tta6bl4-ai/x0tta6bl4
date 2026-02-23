"""Unit tests for src/api/maas/acl.py."""

from datetime import datetime, timedelta
from unittest.mock import patch

from src.api.maas.acl import (
    ACLEntry,
    ACLEvaluator,
    ACLManager,
    Effect,
    create_default_policies,
    create_readonly_policy,
)


class TestACLEntry:
    def test_round_trip_to_dict_from_dict(self):
        created_at = datetime.utcnow().replace(microsecond=0)
        expires_at = created_at + timedelta(hours=1)
        entry = ACLEntry(
            id="acl-1",
            principal="user-1",
            action="read",
            resource="mesh/abc",
            effect=Effect.DENY,
            conditions={"attributes": {"tier": "pro"}},
            created_at=created_at,
            created_by="admin-1",
            expires_at=expires_at,
        )

        reloaded = ACLEntry.from_dict(entry.to_dict())
        assert reloaded.id == "acl-1"
        assert reloaded.principal == "user-1"
        assert reloaded.action == "read"
        assert reloaded.resource == "mesh/abc"
        assert reloaded.effect == Effect.DENY
        assert reloaded.conditions == {"attributes": {"tier": "pro"}}
        assert reloaded.created_at == created_at
        assert reloaded.created_by == "admin-1"
        assert reloaded.expires_at == expires_at


class TestACLEvaluator:
    def test_default_deny_without_matching_policy(self):
        evaluator = ACLEvaluator()
        assert evaluator.evaluate("mesh-1", "user-1", "read", "mesh/1") is False

    def test_write_policy_allows_read(self):
        evaluator = ACLEvaluator()
        evaluator.add_policy(
            "mesh-1",
            ACLEntry(
                id="allow-write",
                principal="*",
                action="write",
                resource="mesh/*",
                effect=Effect.ALLOW,
            ),
        )
        assert evaluator.evaluate("mesh-1", "user-2", "read", "mesh/abc") is True

    def test_deny_policy_overrides_previous_allow(self):
        evaluator = ACLEvaluator()
        evaluator.add_policy(
            "mesh-1",
            ACLEntry(
                id="allow-all",
                principal="user-1",
                action="*",
                resource="*",
                effect=Effect.ALLOW,
            ),
        )
        evaluator.add_policy(
            "mesh-1",
            ACLEntry(
                id="deny-delete",
                principal="user-1",
                action="delete",
                resource="mesh/abc",
                effect=Effect.DENY,
            ),
        )
        assert evaluator.evaluate("mesh-1", "user-1", "delete", "mesh/abc") is False

    def test_expired_policy_is_ignored(self):
        evaluator = ACLEvaluator()
        evaluator.add_policy(
            "mesh-1",
            ACLEntry(
                id="expired",
                principal="user-1",
                action="read",
                resource="mesh/abc",
                effect=Effect.ALLOW,
                expires_at=datetime.utcnow() - timedelta(seconds=1),
            ),
        )
        assert evaluator.evaluate("mesh-1", "user-1", "read", "mesh/abc") is False

    def test_match_resource_supports_single_and_double_wildcards(self):
        evaluator = ACLEvaluator()
        assert evaluator._match_resource("mesh/*", "mesh/abc") is True
        assert evaluator._match_resource("mesh/*", "mesh/abc/nodes") is False
        assert evaluator._match_resource("nodes/**", "nodes/x/actions/read") is True

    def test_evaluate_conditions_ip_and_attributes(self):
        evaluator = ACLEvaluator()
        conditions = {
            "ip_range": {"cidr": "10.0.0.0/8"},
            "attributes": {"tier": "pro"},
        }
        context = {"ip": "10.1.2.3", "attributes": {"tier": "pro"}}
        assert evaluator._evaluate_conditions(conditions, context) is True

    def test_evaluate_conditions_fails_when_attribute_mismatch(self):
        evaluator = ACLEvaluator()
        conditions = {"attributes": {"tier": "pro"}}
        context = {"attributes": {"tier": "free"}}
        assert evaluator._evaluate_conditions(conditions, context) is False

    def test_check_ip_range_returns_false_for_invalid_cidr(self):
        evaluator = ACLEvaluator()
        assert evaluator._check_ip_range({"cidr": "invalid-cidr"}, "10.1.2.3") is False


class TestACLManager:
    def test_grant_access_registers_policy_and_updates_registry(self, monkeypatch):
        evaluator = ACLEvaluator()
        manager = ACLManager(evaluator)
        recorded = []
        monkeypatch.setattr(
            "src.api.maas.registry.add_mesh_policy",
            lambda mesh_id, policy: recorded.append((mesh_id, policy)),
        )

        with patch("secrets.token_hex", return_value="abcd1234"):
            entry = manager.grant_access(
                mesh_id="mesh-1",
                user_id="user-1",
                action="read",
                resource="mesh/*",
                granted_by="admin-1",
            )

        assert entry.id == "acl-abcd1234"
        assert evaluator.evaluate("mesh-1", "user-1", "read", "mesh/abc") is True
        assert len(recorded) == 1
        assert recorded[0][0] == "mesh-1"
        assert recorded[0][1]["id"] == "acl-abcd1234"

    def test_list_user_permissions_includes_user_and_wildcard(self):
        evaluator = ACLEvaluator()
        manager = ACLManager(evaluator)
        evaluator.add_policy(
            "mesh-1",
            ACLEntry("user-policy", "user-1", "read", "mesh/1", Effect.ALLOW),
        )
        evaluator.add_policy(
            "mesh-1",
            ACLEntry("wildcard-policy", "*", "read", "mesh/*", Effect.ALLOW),
        )
        evaluator.add_policy(
            "mesh-1",
            ACLEntry("other-user-policy", "user-2", "read", "mesh/1", Effect.ALLOW),
        )

        permissions = manager.list_user_permissions("mesh-1", "user-1")
        ids = {item["id"] for item in permissions}
        assert ids == {"user-policy", "wildcard-policy"}


class TestPolicyFactories:
    def test_create_default_policies_grants_owner_full_access(self):
        policies = create_default_policies(mesh_id="mesh-1", owner_id="owner-1")
        assert len(policies) == 1
        entry = policies[0]
        assert entry.principal == "owner-1"
        assert entry.action == "*"
        assert entry.resource == "*"
        assert entry.effect == Effect.ALLOW
        assert entry.created_by == "system"

    def test_create_readonly_policy_sets_expected_fields(self):
        entry = create_readonly_policy(
            mesh_id="mesh-1",
            user_id="user-1",
            granted_by="admin-1",
        )
        assert entry.principal == "user-1"
        assert entry.action == "read"
        assert entry.resource == "*"
        assert entry.effect == Effect.ALLOW
        assert entry.created_by == "admin-1"

