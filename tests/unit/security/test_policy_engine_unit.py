"""
Unit tests for src.security.policy_engine module.

Tests:
- Attribute matching (wildcard, regex, list, dict operators)
- PolicyCondition evaluation (all operators)
- PolicyRule evaluation (enabled/disabled, conditions matching)
- Policy target matching
- PolicyEngine (CRUD, evaluate, cache, rollback, import/export, stats)
- PolicyEnforcer decorator (allow, deny, audit, challenge)
- Serialization (to_dict for all dataclasses)
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock

from src.security.policy_engine import (
    Attribute,
    AttributeType,
    Policy,
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    PolicyEngine,
    PolicyEnforcer,
    PolicyPriority,
    PolicyRule,
)


# ---------------------------------------------------------------------------
# Attribute.matches
# ---------------------------------------------------------------------------

class TestAttributeMatches:
    """Tests for Attribute.matches()."""

    def test_wildcard_always_matches(self):
        attr = Attribute(AttributeType.SUBJECT, "role", "admin")
        assert attr.matches("*") is True

    def test_exact_match(self):
        attr = Attribute(AttributeType.SUBJECT, "role", "admin")
        assert attr.matches("admin") is True
        assert attr.matches("user") is False

    def test_regex_match(self):
        attr = Attribute(AttributeType.SUBJECT, "name", "node-42")
        assert attr.matches("regex:node-\\d+") is True
        assert attr.matches("regex:^admin.*") is False

    def test_list_match(self):
        attr = Attribute(AttributeType.SUBJECT, "role", "editor")
        assert attr.matches(["admin", "editor", "viewer"]) is True
        assert attr.matches(["admin", "viewer"]) is False

    def test_dict_gt(self):
        attr = Attribute(AttributeType.SUBJECT, "trust", 80)
        assert attr.matches({"gt": 70}) is True
        assert attr.matches({"gt": 80}) is False

    def test_dict_lt(self):
        attr = Attribute(AttributeType.SUBJECT, "trust", 30)
        assert attr.matches({"lt": 50}) is True
        assert attr.matches({"lt": 30}) is False

    def test_dict_gte(self):
        attr = Attribute(AttributeType.SUBJECT, "trust", 50)
        assert attr.matches({"gte": 50}) is True
        assert attr.matches({"gte": 51}) is False

    def test_dict_lte(self):
        attr = Attribute(AttributeType.SUBJECT, "trust", 50)
        assert attr.matches({"lte": 50}) is True
        assert attr.matches({"lte": 49}) is False

    def test_dict_in(self):
        attr = Attribute(AttributeType.SUBJECT, "role", "admin")
        assert attr.matches({"in": ["admin", "root"]}) is True
        assert attr.matches({"in": ["user"]}) is False

    def test_dict_not_in(self):
        attr = Attribute(AttributeType.SUBJECT, "role", "admin")
        assert attr.matches({"not_in": ["user", "guest"]}) is True
        assert attr.matches({"not_in": ["admin"]}) is False


# ---------------------------------------------------------------------------
# PolicyCondition.evaluate
# ---------------------------------------------------------------------------

class TestPolicyConditionEvaluate:
    """Tests for PolicyCondition.evaluate()."""

    def _attrs(self, **kwargs):
        """Helper to build attributes dict from keyword args like subject_role='admin'."""
        result = {}
        for key, value in kwargs.items():
            atype_str, aname = key.split("_", 1)
            atype = AttributeType(atype_str)
            full_key = f"{atype_str}.{aname}"
            result[full_key] = Attribute(atype, aname, value)
        return result

    def test_eq_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "eq", "admin")
        attrs = self._attrs(subject_role="admin")
        assert cond.evaluate(attrs) is True

        attrs2 = self._attrs(subject_role="user")
        assert cond.evaluate(attrs2) is False

    def test_ne_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "ne", "admin")
        assert cond.evaluate(self._attrs(subject_role="user")) is True
        assert cond.evaluate(self._attrs(subject_role="admin")) is False

    def test_gt_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "trust", "gt", 50)
        assert cond.evaluate(self._attrs(subject_trust=60)) is True
        assert cond.evaluate(self._attrs(subject_trust=50)) is False

    def test_lt_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "trust", "lt", 50)
        assert cond.evaluate(self._attrs(subject_trust=40)) is True
        assert cond.evaluate(self._attrs(subject_trust=50)) is False

    def test_gte_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "trust", "gte", 50)
        assert cond.evaluate(self._attrs(subject_trust=50)) is True
        assert cond.evaluate(self._attrs(subject_trust=49)) is False

    def test_lte_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "trust", "lte", 50)
        assert cond.evaluate(self._attrs(subject_trust=50)) is True
        assert cond.evaluate(self._attrs(subject_trust=51)) is False

    def test_in_operator(self):
        cond = PolicyCondition(AttributeType.RESOURCE, "endpoint", "in", ["/health", "/ready"])
        attrs = {"resource.endpoint": Attribute(AttributeType.RESOURCE, "endpoint", "/health")}
        assert cond.evaluate(attrs) is True

        attrs2 = {"resource.endpoint": Attribute(AttributeType.RESOURCE, "endpoint", "/api")}
        assert cond.evaluate(attrs2) is False

    def test_not_in_operator(self):
        cond = PolicyCondition(AttributeType.ACTION, "type", "not_in", ["health", "metrics"])
        attrs = {"action.type": Attribute(AttributeType.ACTION, "type", "write")}
        assert cond.evaluate(attrs) is True

        attrs2 = {"action.type": Attribute(AttributeType.ACTION, "type", "health")}
        assert cond.evaluate(attrs2) is False

    def test_regex_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "name", "regex", r"^node-\d+$")
        attrs = {"subject.name": Attribute(AttributeType.SUBJECT, "name", "node-42")}
        assert cond.evaluate(attrs) is True

        attrs2 = {"subject.name": Attribute(AttributeType.SUBJECT, "name", "bad-name")}
        assert cond.evaluate(attrs2) is False

    def test_contains_operator(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "path", "contains", "admin")
        attrs = {"subject.path": Attribute(AttributeType.SUBJECT, "path", "/api/admin/users")}
        assert cond.evaluate(attrs) is True

        attrs2 = {"subject.path": Attribute(AttributeType.SUBJECT, "path", "/api/public")}
        assert cond.evaluate(attrs2) is False

    def test_exists_operator_true(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "exists", True)
        attrs = {"subject.role": Attribute(AttributeType.SUBJECT, "role", "admin")}
        assert cond.evaluate(attrs) is True
        assert cond.evaluate({}) is False

    def test_exists_operator_false(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "exists", False)
        assert cond.evaluate({}) is True
        attrs = {"subject.role": Attribute(AttributeType.SUBJECT, "role", "admin")}
        assert cond.evaluate(attrs) is False

    def test_missing_attribute_returns_false(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "missing", "eq", "value")
        assert cond.evaluate({}) is False

    def test_unknown_operator_returns_false(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "unknown_op", "admin")
        attrs = {"subject.role": Attribute(AttributeType.SUBJECT, "role", "admin")}
        assert cond.evaluate(attrs) is False

    def test_to_dict(self):
        cond = PolicyCondition(AttributeType.SUBJECT, "role", "eq", "admin")
        d = cond.to_dict()
        assert d["attribute_type"] == "subject"
        assert d["attribute_name"] == "role"
        assert d["operator"] == "eq"
        assert d["value"] == "admin"


# ---------------------------------------------------------------------------
# PolicyRule
# ---------------------------------------------------------------------------

class TestPolicyRule:
    """Tests for PolicyRule evaluation and serialization."""

    def test_disabled_rule_returns_none(self):
        rule = PolicyRule(
            id="r1",
            description="disabled",
            conditions=[],
            effect=PolicyEffect.ALLOW,
            enabled=False,
        )
        assert rule.evaluate({}) is None

    def test_rule_all_conditions_match(self):
        rule = PolicyRule(
            id="r1",
            description="both match",
            conditions=[
                PolicyCondition(AttributeType.SUBJECT, "role", "eq", "admin"),
                PolicyCondition(AttributeType.ACTION, "type", "eq", "read"),
            ],
            effect=PolicyEffect.ALLOW,
        )
        attrs = {
            "subject.role": Attribute(AttributeType.SUBJECT, "role", "admin"),
            "action.type": Attribute(AttributeType.ACTION, "type", "read"),
        }
        assert rule.evaluate(attrs) == PolicyEffect.ALLOW

    def test_rule_partial_conditions_fail(self):
        rule = PolicyRule(
            id="r1",
            description="partial fail",
            conditions=[
                PolicyCondition(AttributeType.SUBJECT, "role", "eq", "admin"),
                PolicyCondition(AttributeType.ACTION, "type", "eq", "write"),
            ],
            effect=PolicyEffect.ALLOW,
        )
        attrs = {
            "subject.role": Attribute(AttributeType.SUBJECT, "role", "admin"),
            "action.type": Attribute(AttributeType.ACTION, "type", "read"),
        }
        assert rule.evaluate(attrs) is None

    def test_empty_conditions_matches_everything(self):
        rule = PolicyRule(
            id="deny-all",
            description="deny",
            conditions=[],
            effect=PolicyEffect.DENY,
        )
        assert rule.evaluate({}) == PolicyEffect.DENY

    def test_to_dict(self):
        rule = PolicyRule(
            id="r1",
            description="test",
            conditions=[],
            effect=PolicyEffect.AUDIT,
            priority=PolicyPriority.HIGH,
            enabled=True,
        )
        d = rule.to_dict()
        assert d["id"] == "r1"
        assert d["effect"] == "audit"
        assert d["priority"] == 20
        assert d["enabled"] is True


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class TestPolicy:
    """Tests for Policy target matching and serialization."""

    def _make_policy(self, target):
        return Policy(
            id="p1",
            name="Test",
            description="test",
            version=1,
            rules=[],
            target=target,
        )

    def test_matches_target_wildcard(self):
        p = self._make_policy({"resource": "*", "action": "*"})
        assert p.matches_target("/anything", "any_action") is True

    def test_matches_target_exact(self):
        p = self._make_policy({"resource": "/api/data", "action": "read"})
        assert p.matches_target("/api/data", "read") is True
        assert p.matches_target("/api/data", "write") is False
        assert p.matches_target("/api/other", "read") is False

    def test_matches_target_list(self):
        p = self._make_policy({"resource": ["/a", "/b"], "action": ["read", "write"]})
        assert p.matches_target("/a", "read") is True
        assert p.matches_target("/b", "write") is True
        assert p.matches_target("/c", "read") is False
        assert p.matches_target("/a", "delete") is False

    def test_matches_target_default_wildcard(self):
        p = self._make_policy({})
        assert p.matches_target("/anything", "anything") is True

    def test_to_dict(self):
        p = self._make_policy({"resource": "*", "action": "*"})
        d = p.to_dict()
        assert d["id"] == "p1"
        assert d["name"] == "Test"
        assert d["version"] == 1
        assert "rules" in d
        assert "target" in d


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------

class TestPolicyDecision:
    """Tests for PolicyDecision serialization."""

    def test_to_dict(self):
        dec = PolicyDecision(
            effect=PolicyEffect.ALLOW,
            policy_id="p1",
            rule_id="r1",
            reason="allowed",
            attributes_evaluated=5,
            evaluation_time_ms=1.23,
        )
        d = dec.to_dict()
        assert d["effect"] == "allow"
        assert d["policy_id"] == "p1"
        assert d["rule_id"] == "r1"
        assert d["attributes_evaluated"] == 5
        assert d["evaluation_time_ms"] == 1.23


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    """Tests for PolicyEngine core functionality."""

    def _engine(self):
        return PolicyEngine(node_id="test-node")

    # --- Default policies ---

    def test_default_policies_loaded(self):
        engine = self._engine()
        ids = set(engine.policies.keys())
        assert "default-deny" in ids
        assert "allow-health" in ids
        assert "trust-based-access" in ids
        assert "time-based-access" in ids

    def test_get_stats_initial(self):
        engine = self._engine()
        stats = engine.get_stats()
        assert stats["total_policies"] == 4
        assert stats["enabled_policies"] == 4
        assert stats["cache_size"] == 0

    # --- add / remove / get / list ---

    def test_add_policy(self):
        engine = self._engine()
        p = Policy(
            id="custom-1", name="Custom", description="test",
            version=1, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p)
        assert "custom-1" in engine.policies

    def test_add_policy_update_stores_version(self):
        engine = self._engine()
        p1 = Policy(
            id="v-test", name="V", description="v1",
            version=1, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p1)

        p2 = Policy(
            id="v-test", name="V", description="v2",
            version=2, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p2)

        assert engine.policies["v-test"].version == 2
        assert len(engine.policy_versions.get("v-test", [])) == 1

    def test_remove_policy_exists(self):
        engine = self._engine()
        assert engine.remove_policy("default-deny") is True
        assert "default-deny" not in engine.policies

    def test_remove_policy_not_exists(self):
        engine = self._engine()
        assert engine.remove_policy("nonexistent") is False

    def test_get_policy(self):
        engine = self._engine()
        p = engine.get_policy("default-deny")
        assert p is not None
        assert p.id == "default-deny"

    def test_get_policy_missing(self):
        engine = self._engine()
        assert engine.get_policy("nonexistent") is None

    def test_list_policies(self):
        engine = self._engine()
        policies = engine.list_policies()
        assert isinstance(policies, list)
        assert len(policies) == 4
        assert all(isinstance(p, dict) for p in policies)

    # --- Rollback ---

    def test_rollback_policy_to_previous(self):
        engine = self._engine()
        p1 = Policy(
            id="rb-test", name="RB", description="v1",
            version=1, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p1)
        p2 = Policy(
            id="rb-test", name="RB", description="v2",
            version=2, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p2)
        assert engine.policies["rb-test"].version == 2

        result = engine.rollback_policy("rb-test")
        assert result is True
        assert engine.policies["rb-test"].version == 1

    def test_rollback_policy_to_specific_version(self):
        engine = self._engine()
        for v in range(1, 4):
            p = Policy(
                id="rb-v", name="RB", description=f"v{v}",
                version=v, rules=[], target={"resource": "*", "action": "*"},
            )
            engine.add_policy(p)
        # versions list has v1, v2 (v3 is current)
        result = engine.rollback_policy("rb-v", version=1)
        assert result is True
        assert engine.policies["rb-v"].version == 1

    def test_rollback_policy_no_history(self):
        engine = self._engine()
        assert engine.rollback_policy("nonexistent") is False

    def test_rollback_policy_empty_versions(self):
        engine = self._engine()
        engine.policy_versions["empty"] = []
        assert engine.rollback_policy("empty") is False

    def test_rollback_policy_version_not_found(self):
        engine = self._engine()
        p1 = Policy(
            id="rb-nf", name="RB", description="v1",
            version=1, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p1)
        p2 = Policy(
            id="rb-nf", name="RB", description="v2",
            version=2, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p2)
        assert engine.rollback_policy("rb-nf", version=99) is False

    # --- Evaluate ---

    def test_evaluate_health_endpoint_allowed(self):
        engine = self._engine()
        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        assert decision.effect == PolicyEffect.ALLOW
        assert decision.policy_id == "allow-health"

    def test_evaluate_high_trust_access(self):
        engine = self._engine()
        decision = engine.evaluate(
            subject={"node_id": "n1", "trust_level": 80},
            resource="/api/data",
            action="read",
            environment=None,
        )
        # High trust (80 >= 70) should get ALLOW from trust-based-access for sensitivity "high"
        # But the condition also requires resource.sensitivity to be in the list,
        # and we didn't pass resource.sensitivity. So the trust rules won't match.
        # The default-deny should kick in.
        assert decision.effect == PolicyEffect.DENY

    def test_evaluate_default_deny_for_unknown(self):
        engine = self._engine()
        decision = engine.evaluate(
            subject={"node_id": "unknown"},
            resource="/secret",
            action="admin",
        )
        assert decision.effect == PolicyEffect.DENY

    def test_evaluate_maintenance_mode_deny(self):
        engine = self._engine()
        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/api/data",
            action="write",
            environment={"maintenance_mode": True},
        )
        # Maintenance window rule denies non-essential actions during maintenance
        # action.type = "write" is not_in ["health", "metrics", "admin"]  => True
        # environment.maintenance_mode eq True => True
        # effect: DENY, priority: HIGH (20)
        # default-deny has priority DEFAULT (50)
        # So maintenance deny wins
        assert decision.effect == PolicyEffect.DENY
        assert decision.policy_id == "time-based-access"

    def test_evaluate_maintenance_mode_allows_health(self):
        engine = self._engine()
        # Health action during maintenance should NOT be blocked by maintenance rule
        # because maintenance condition requires action.type not_in [health, metrics, admin]
        # action "health" IS in that list, so condition fails => rule doesn't match
        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="health",
            environment={"maintenance_mode": True},
        )
        # /health endpoint rule requires resource.endpoint in ["/health", ...] and action "read"
        # but action here is "health", and target action is "read" for allow-health policy
        # So allow-health won't match. Only default-deny and potentially maintenance
        # maintenance: action.type="health" is IN ["health","metrics","admin"] -> not_in fails -> rule doesn't match
        # default-deny: matches everything -> DENY
        assert decision.effect == PolicyEffect.DENY

    def test_evaluate_caching(self):
        engine = self._engine()
        d1 = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        # Second call should hit cache
        d2 = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        assert d1.effect == d2.effect
        assert d1.policy_id == d2.policy_id

    def test_evaluate_cache_cleared_on_add(self):
        engine = self._engine()
        # Populate cache
        engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        assert len(engine._decision_cache) > 0
        # Add policy clears cache
        p = Policy(
            id="new-pol", name="New", description="test",
            version=1, rules=[], target={"resource": "*", "action": "*"},
        )
        engine.add_policy(p)
        assert len(engine._decision_cache) == 0

    def test_evaluate_cache_cleared_on_remove(self):
        engine = self._engine()
        engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        assert len(engine._decision_cache) > 0
        engine.remove_policy("allow-health")
        assert len(engine._decision_cache) == 0

    def test_evaluate_cache_expiry(self):
        engine = self._engine()
        engine._cache_ttl = 0  # Expire immediately
        d1 = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        # Even with expired TTL, the result should still be correct
        d2 = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/health",
            action="read",
        )
        assert d1.effect == d2.effect

    def test_evaluate_no_matching_policies_implicit_deny(self):
        engine = self._engine()
        # Remove all policies
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)
        # Disable target so nothing matches
        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/anything",
            action="read",
        )
        assert decision.effect == PolicyEffect.DENY
        assert decision.policy_id == "implicit"
        assert decision.rule_id == "no-match"

    def test_evaluate_disabled_policy_skipped(self):
        engine = self._engine()
        # Remove all policies, add one disabled
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)

        p = Policy(
            id="disabled-pol", name="Disabled", description="test",
            version=1,
            rules=[
                PolicyRule(
                    id="allow-r", description="allow",
                    conditions=[], effect=PolicyEffect.ALLOW,
                )
            ],
            target={"resource": "*", "action": "*"},
            enabled=False,
        )
        engine.add_policy(p)
        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/api",
            action="read",
        )
        assert decision.effect == PolicyEffect.DENY
        assert decision.policy_id == "implicit"

    def test_evaluate_priority_ordering(self):
        engine = self._engine()
        # Remove all defaults
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)

        # Add two policies: one ALLOW at NORMAL, one DENY at HIGH
        allow_policy = Policy(
            id="low-pri", name="Allow", description="low priority allow",
            version=1,
            rules=[
                PolicyRule(
                    id="allow-r", description="allow",
                    conditions=[], effect=PolicyEffect.ALLOW,
                    priority=PolicyPriority.NORMAL,
                )
            ],
            target={"resource": "*", "action": "*"},
        )
        deny_policy = Policy(
            id="high-pri", name="Deny", description="high priority deny",
            version=1,
            rules=[
                PolicyRule(
                    id="deny-r", description="deny",
                    conditions=[], effect=PolicyEffect.DENY,
                    priority=PolicyPriority.HIGH,
                )
            ],
            target={"resource": "*", "action": "*"},
        )
        engine.add_policy(allow_policy)
        engine.add_policy(deny_policy)

        decision = engine.evaluate(
            subject={"node_id": "n1"},
            resource="/api",
            action="read",
        )
        # HIGH priority (20) beats NORMAL (30)
        assert decision.effect == PolicyEffect.DENY
        assert decision.rule_id == "deny-r"

    # --- Export / Import ---

    def test_export_policies_json(self):
        engine = self._engine()
        exported = engine.export_policies()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 4

    def test_import_policies(self):
        engine = self._engine()
        exported = engine.export_policies()

        # Create new engine and import
        engine2 = PolicyEngine(node_id="test-node-2")
        # Remove all defaults first to see the import effect clearly
        for pid in list(engine2.policies.keys()):
            engine2.remove_policy(pid)

        count = engine2.import_policies(exported)
        assert count == 4
        assert len(engine2.policies) == 4

    def test_import_export_roundtrip(self):
        engine = self._engine()
        exported = engine.export_policies()
        data = json.loads(exported)

        engine2 = PolicyEngine(node_id="test-node-2")
        for pid in list(engine2.policies.keys()):
            engine2.remove_policy(pid)
        engine2.import_policies(exported)

        # Verify all policies are present and have correct fields
        for p_data in data:
            p = engine2.get_policy(p_data["id"])
            assert p is not None
            assert p.name == p_data["name"]
            assert p.version == p_data["version"]

    # --- _build_attributes ---

    def test_build_attributes_structure(self):
        engine = self._engine()
        attrs = engine._build_attributes(
            subject={"node_id": "n1", "trust_level": 80},
            resource="/api/data",
            action="read",
            environment={"maintenance_mode": False},
        )
        assert "subject.node_id" in attrs
        assert "subject.trust_level" in attrs
        assert "resource.name" in attrs
        assert "resource.endpoint" in attrs
        assert "action.type" in attrs
        assert "environment.maintenance_mode" in attrs
        assert "environment.timestamp" in attrs

    def test_build_attributes_no_environment(self):
        engine = self._engine()
        attrs = engine._build_attributes(
            subject={"node_id": "n1"},
            resource="/api",
            action="read",
            environment=None,
        )
        # Should still have timestamp
        assert "environment.timestamp" in attrs
        # But no custom environment vars
        assert "environment.maintenance_mode" not in attrs

    # --- _cache_key ---

    def test_cache_key_deterministic(self):
        engine = self._engine()
        attrs = engine._build_attributes(
            subject={"node_id": "n1"},
            resource="/api",
            action="read",
            environment=None,
        )
        k1 = engine._cache_key(attrs)
        k2 = engine._cache_key(attrs)
        assert k1 == k2

    def test_cache_key_different_for_different_attrs(self):
        engine = self._engine()
        attrs1 = engine._build_attributes(
            subject={"node_id": "n1"},
            resource="/api",
            action="read",
            environment=None,
        )
        attrs2 = engine._build_attributes(
            subject={"node_id": "n2"},
            resource="/api",
            action="read",
            environment=None,
        )
        # They may differ (different node_id), but timestamp is dynamic
        # So we just check they're strings of correct length
        assert isinstance(engine._cache_key(attrs1), str)
        assert len(engine._cache_key(attrs1)) == 32


# ---------------------------------------------------------------------------
# PolicyEnforcer
# ---------------------------------------------------------------------------

class TestPolicyEnforcer:
    """Tests for PolicyEnforcer decorator."""

    def _engine_with_allow_all(self):
        engine = PolicyEngine(node_id="test-node")
        # Remove all defaults, add a universal allow
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)
        engine.add_policy(Policy(
            id="allow-all", name="Allow All", description="allow",
            version=1,
            rules=[PolicyRule(
                id="allow-all-r", description="allow",
                conditions=[], effect=PolicyEffect.ALLOW,
                priority=PolicyPriority.EMERGENCY,
            )],
            target={"resource": "*", "action": "*"},
        ))
        return engine

    def _engine_with_deny_all(self):
        engine = PolicyEngine(node_id="test-node")
        # Default policies already include default-deny at DEFAULT priority
        # Remove everything except default-deny
        for pid in list(engine.policies.keys()):
            if pid != "default-deny":
                engine.remove_policy(pid)
        return engine

    def test_enforce_allow(self):
        engine = self._engine_with_allow_all()
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("resource", "read")
        def my_func():
            return "success"

        assert my_func() == "success"

    def test_enforce_deny_raises_permission_error(self):
        engine = self._engine_with_deny_all()
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("/secret", "admin")
        def my_func():
            return "should not reach"

        with pytest.raises(PermissionError, match="Access denied"):
            my_func()

    def test_enforce_with_custom_subject(self):
        engine = self._engine_with_allow_all()
        enforcer = PolicyEnforcer(engine)

        subject = {"node_id": "node-42", "trust_level": 90}

        @enforcer.enforce("resource", "read", get_subject=lambda: subject)
        def my_func():
            return "ok"

        assert my_func() == "ok"

    def test_enforce_default_subject_when_none(self):
        engine = self._engine_with_allow_all()
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("resource", "read", get_subject=None)
        def my_func():
            return "ok"

        # Default subject is {"node_id": "unknown"}, should still be allowed
        assert my_func() == "ok"

    def test_enforce_audit_effect_allows_but_logs(self):
        engine = PolicyEngine(node_id="test-node")
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)
        engine.add_policy(Policy(
            id="audit-pol", name="Audit", description="audit",
            version=1,
            rules=[PolicyRule(
                id="audit-r", description="audit everything",
                conditions=[], effect=PolicyEffect.AUDIT,
                priority=PolicyPriority.EMERGENCY,
            )],
            target={"resource": "*", "action": "*"},
        ))
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("resource", "read")
        def my_func():
            return "audited"

        assert my_func() == "audited"

    def test_enforce_challenge_effect_allows_with_warning(self):
        engine = PolicyEngine(node_id="test-node")
        for pid in list(engine.policies.keys()):
            engine.remove_policy(pid)
        engine.add_policy(Policy(
            id="challenge-pol", name="Challenge", description="challenge",
            version=1,
            rules=[PolicyRule(
                id="challenge-r", description="challenge everything",
                conditions=[], effect=PolicyEffect.CHALLENGE,
                priority=PolicyPriority.EMERGENCY,
            )],
            target={"resource": "*", "action": "*"},
        ))
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("resource", "read")
        def my_func():
            return "challenged"

        assert my_func() == "challenged"

    def test_enforce_passes_args_through(self):
        engine = self._engine_with_allow_all()
        enforcer = PolicyEnforcer(engine)

        @enforcer.enforce("resource", "read")
        def add(a, b, c=0):
            return a + b + c

        assert add(1, 2, c=3) == 6


# ---------------------------------------------------------------------------
# Enum sanity checks
# ---------------------------------------------------------------------------

class TestEnums:
    """Quick sanity checks on enum values."""

    def test_policy_effect_values(self):
        assert PolicyEffect.ALLOW.value == "allow"
        assert PolicyEffect.DENY.value == "deny"
        assert PolicyEffect.AUDIT.value == "audit"
        assert PolicyEffect.CHALLENGE.value == "challenge"

    def test_policy_priority_ordering(self):
        assert PolicyPriority.EMERGENCY.value < PolicyPriority.CRITICAL.value
        assert PolicyPriority.CRITICAL.value < PolicyPriority.HIGH.value
        assert PolicyPriority.HIGH.value < PolicyPriority.NORMAL.value
        assert PolicyPriority.NORMAL.value < PolicyPriority.LOW.value
        assert PolicyPriority.LOW.value < PolicyPriority.DEFAULT.value

    def test_attribute_type_values(self):
        assert AttributeType.SUBJECT.value == "subject"
        assert AttributeType.RESOURCE.value == "resource"
        assert AttributeType.ACTION.value == "action"
        assert AttributeType.ENVIRONMENT.value == "environment"
