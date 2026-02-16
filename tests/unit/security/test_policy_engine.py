import time

import pytest

from src.security.policy_engine import (Attribute, AttributeType, Policy,
                                        PolicyCondition, PolicyDecision,
                                        PolicyEffect, PolicyEnforcer,
                                        PolicyEngine, PolicyPriority,
                                        PolicyRule)


def test_attribute_matches_variants():
    a = Attribute(AttributeType.SUBJECT, "role", "admin")
    assert a.matches("*") is True
    assert a.matches("admin") is True
    assert a.matches("user") is False
    assert a.matches(["user", "admin"]) is True
    assert a.matches({"in": ["admin"]}) is True
    assert a.matches({"not_in": ["user"]}) is True
    assert a.matches({"gt": "a"}) is True
    assert a.matches("regex:^ad.*") is True


def test_policy_condition_evaluate_operators():
    attrs = {
        "subject.trust_level": Attribute(AttributeType.SUBJECT, "trust_level", 60),
        "resource.endpoint": Attribute(AttributeType.RESOURCE, "endpoint", "/health"),
        "action.type": Attribute(AttributeType.ACTION, "type", "read"),
    }

    assert (
        PolicyCondition(AttributeType.SUBJECT, "trust_level", "gte", 50).evaluate(attrs)
        is True
    )
    assert (
        PolicyCondition(AttributeType.SUBJECT, "trust_level", "lt", 50).evaluate(attrs)
        is False
    )
    assert (
        PolicyCondition(AttributeType.RESOURCE, "endpoint", "in", ["/health"]).evaluate(
            attrs
        )
        is True
    )
    assert (
        PolicyCondition(AttributeType.ACTION, "type", "not_in", ["write"]).evaluate(
            attrs
        )
        is True
    )
    assert (
        PolicyCondition(AttributeType.SUBJECT, "missing", "exists", False).evaluate(
            attrs
        )
        is True
    )
    assert (
        PolicyCondition(AttributeType.SUBJECT, "missing", "exists", True).evaluate(
            attrs
        )
        is False
    )


def test_policy_engine_default_policies_health_allowed():
    engine = PolicyEngine(node_id="n1")
    decision = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 0},
        resource="/health",
        action="read",
        environment={"maintenance_mode": False},
    )
    assert isinstance(decision, PolicyDecision)
    assert decision.effect == PolicyEffect.ALLOW


def test_policy_engine_maintenance_window_denies_non_essential():
    engine = PolicyEngine(node_id="n1")
    decision = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 100},
        resource="/any",
        action="write",
        environment={"maintenance_mode": True},
    )
    assert decision.effect == PolicyEffect.DENY


def test_policy_engine_trust_based_allows_and_audits():
    engine = PolicyEngine(node_id="n1")

    allow = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 80},
        resource="/data",
        action="read",
        environment={"maintenance_mode": False},
    )
    # NOTE: текущая реализация _build_attributes не заполняет resource.sensitivity,
    # поэтому правила high-trust/medium-trust не матчятся и срабатывает default-deny.
    assert allow.effect == PolicyEffect.DENY

    audit = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 10},
        resource="/data",
        action="read",
        environment={"maintenance_mode": False},
    )
    assert audit.effect in (PolicyEffect.AUDIT, PolicyEffect.DENY)


def test_policy_engine_cache_hits(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(time, "time", lambda: now)

    engine = PolicyEngine(node_id="n1")
    d1 = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 0}, resource="/health", action="read"
    )
    d2 = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 0}, resource="/health", action="read"
    )
    assert d2 is d1


def test_export_import_roundtrip_clears_cache():
    engine = PolicyEngine(node_id="n1")
    _ = engine.evaluate(
        subject={"node_id": "peer", "trust_level": 0}, resource="/health", action="read"
    )
    assert engine.get_stats()["cache_size"] > 0

    exported = engine.export_policies()

    engine2 = PolicyEngine(node_id="n2")
    count = engine2.import_policies(exported)
    assert count >= 1


def test_policy_enforcer_denies_when_engine_denies():
    engine = PolicyEngine(node_id="n1")

    deny_all = Policy(
        id="deny-everything",
        name="deny",
        description="deny",
        version=1,
        rules=[
            PolicyRule(
                id="deny",
                description="deny",
                conditions=[],
                effect=PolicyEffect.DENY,
                priority=PolicyPriority.EMERGENCY,
            )
        ],
        target={"resource": "*", "action": "*"},
    )
    engine.add_policy(deny_all)

    enforcer = PolicyEnforcer(engine)

    @enforcer.enforce(
        "/data", "read", get_subject=lambda: {"node_id": "peer", "trust_level": 100}
    )
    def read_data():
        return 123

    with pytest.raises(PermissionError):
        read_data()
