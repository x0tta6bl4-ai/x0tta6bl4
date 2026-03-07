"""Unit tests for src/api/maas/acl.py."""

from datetime import datetime, timedelta

import pytest

from src.api.maas.acl import (
    ACLEntry,
    ACLEvaluator,
    ACLManager,
    ActionType,
    Effect,
    create_default_policies,
    create_readonly_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    principal="user-1",
    action="read",
    resource="mesh/*",
    effect=Effect.ALLOW,
    conditions=None,
    expires_at=None,
) -> ACLEntry:
    return ACLEntry(
        id="test-acl-id",
        principal=principal,
        action=action,
        resource=resource,
        effect=effect,
        conditions=conditions or {},
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# ACLEntry
# ---------------------------------------------------------------------------


def test_acl_entry_to_dict_and_from_dict_roundtrip():
    entry = _entry()
    d = entry.to_dict()
    restored = ACLEntry.from_dict(d)
    assert restored.id == entry.id
    assert restored.principal == entry.principal
    assert restored.action == entry.action
    assert restored.resource == entry.resource
    assert restored.effect == entry.effect


def test_acl_entry_from_dict_defaults_effect_to_allow():
    d = {
        "id": "x",
        "principal": "u",
        "action": "read",
        "resource": "*",
    }
    entry = ACLEntry.from_dict(d)
    assert entry.effect == Effect.ALLOW


def test_acl_entry_to_dict_expires_at_none_when_not_set():
    entry = _entry()
    assert entry.to_dict()["expires_at"] is None


def test_acl_entry_to_dict_expires_at_is_iso_when_set():
    exp = datetime(2027, 1, 1, 12, 0, 0)
    entry = _entry(expires_at=exp)
    assert entry.to_dict()["expires_at"] == exp.isoformat()


# ---------------------------------------------------------------------------
# ACLEvaluator — default-deny
# ---------------------------------------------------------------------------


def test_evaluator_default_deny_no_policies():
    ev = ACLEvaluator()
    assert ev.evaluate("mesh-1", "user-1", "read", "mesh/data") is False


def test_evaluator_allow_with_matching_policy():
    ev = ACLEvaluator()
    ev.add_policy("mesh-1", _entry(principal="user-1", action="read", resource="mesh/*"))
    assert ev.evaluate("mesh-1", "user-1", "read", "mesh/data") is True


def test_evaluator_deny_overrides_allow():
    ev = ACLEvaluator()
    ev.add_policy("mesh-1", _entry(principal="user-1", action="*", resource="*", effect=Effect.ALLOW))
    ev.add_policy("mesh-1", _entry(principal="user-1", action="delete", resource="*", effect=Effect.DENY))
    assert ev.evaluate("mesh-1", "user-1", "delete", "mesh/data") is False


def test_evaluator_allow_survives_for_other_actions():
    ev = ACLEvaluator()
    ev.add_policy("mesh-1", _entry(principal="user-1", action="*", resource="*", effect=Effect.ALLOW))
    ev.add_policy("mesh-1", _entry(principal="user-1", action="delete", resource="*", effect=Effect.DENY))
    assert ev.evaluate("mesh-1", "user-1", "read", "mesh/data") is True


def test_evaluator_wrong_mesh_returns_deny():
    ev = ACLEvaluator()
    ev.add_policy("mesh-1", _entry(principal="user-1", action="read", resource="*"))
    assert ev.evaluate("mesh-2", "user-1", "read", "*") is False


def test_evaluator_expired_policy_is_skipped():
    past = datetime.utcnow() - timedelta(seconds=1)
    ev = ACLEvaluator()
    ev.add_policy(
        "mesh-1",
        _entry(principal="user-1", action="read", resource="*", expires_at=past),
    )
    assert ev.evaluate("mesh-1", "user-1", "read", "*") is False


def test_evaluator_future_expiry_still_valid():
    future = datetime.utcnow() + timedelta(hours=1)
    ev = ACLEvaluator()
    ev.add_policy(
        "mesh-1",
        _entry(principal="user-1", action="read", resource="*", expires_at=future),
    )
    assert ev.evaluate("mesh-1", "user-1", "read", "*") is True


# ---------------------------------------------------------------------------
# Principal matching
# ---------------------------------------------------------------------------


def test_evaluator_wildcard_principal_matches_anyone():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="*", action="read", resource="*"))
    assert ev.evaluate("m", "any-user", "read", "*") is True


def test_evaluator_exact_principal_does_not_match_other():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="user-1", action="read", resource="*"))
    assert ev.evaluate("m", "user-2", "read", "*") is False


def test_evaluator_group_principal_not_matched_without_lookup():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="group:admins", action="read", resource="*"))
    assert ev.evaluate("m", "user-1", "read", "*") is False


# ---------------------------------------------------------------------------
# Action matching
# ---------------------------------------------------------------------------


def test_evaluator_wildcard_action_matches_any():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="*", resource="*"))
    for act in ("read", "write", "delete", "admin", "deploy"):
        assert ev.evaluate("m", "u", act, "*") is True


def test_evaluator_admin_action_matches_all():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="admin", resource="*"))
    assert ev.evaluate("m", "u", "read", "*") is True
    assert ev.evaluate("m", "u", "delete", "*") is True


def test_evaluator_write_includes_read():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="write", resource="*"))
    assert ev.evaluate("m", "u", "read", "*") is True
    assert ev.evaluate("m", "u", "write", "*") is True


def test_evaluator_read_does_not_include_write():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="*"))
    assert ev.evaluate("m", "u", "write", "*") is False


# ---------------------------------------------------------------------------
# Resource matching
# ---------------------------------------------------------------------------


def test_evaluator_exact_resource_match():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="mesh/abc"))
    assert ev.evaluate("m", "u", "read", "mesh/abc") is True
    assert ev.evaluate("m", "u", "read", "mesh/xyz") is False


def test_evaluator_single_wildcard_segment():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="mesh/*"))
    assert ev.evaluate("m", "u", "read", "mesh/abc") is True
    assert ev.evaluate("m", "u", "read", "mesh/xyz") is True
    assert ev.evaluate("m", "u", "read", "nodes/abc") is False


def test_evaluator_double_wildcard_matches_deeper_path():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="nodes/**"))
    assert ev.evaluate("m", "u", "read", "nodes/x/actions/read") is True


def test_evaluator_global_wildcard_resource():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="*"))
    assert ev.evaluate("m", "u", "read", "anything") is True


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def test_evaluator_ip_range_condition_pass():
    ev = ACLEvaluator()
    ev.add_policy(
        "m",
        _entry(
            principal="u",
            action="read",
            resource="*",
            conditions={"ip_range": {"cidr": "10.0.0.0/8"}},
        ),
    )
    assert ev.evaluate("m", "u", "read", "*", context={"ip": "10.0.0.5"}) is True


def test_evaluator_ip_range_condition_fail():
    ev = ACLEvaluator()
    ev.add_policy(
        "m",
        _entry(
            principal="u",
            action="read",
            resource="*",
            conditions={"ip_range": {"cidr": "10.0.0.0/8"}},
        ),
    )
    assert ev.evaluate("m", "u", "read", "*", context={"ip": "192.168.1.1"}) is False


def test_evaluator_ip_range_missing_ip_fails():
    ev = ACLEvaluator()
    ev.add_policy(
        "m",
        _entry(
            principal="u",
            action="read",
            resource="*",
            conditions={"ip_range": {"cidr": "10.0.0.0/8"}},
        ),
    )
    assert ev.evaluate("m", "u", "read", "*", context={}) is False


def test_evaluator_attributes_condition_pass():
    ev = ACLEvaluator()
    ev.add_policy(
        "m",
        _entry(
            principal="u",
            action="read",
            resource="*",
            conditions={"attributes": {"role": "operator"}},
        ),
    )
    ctx = {"attributes": {"role": "operator"}}
    assert ev.evaluate("m", "u", "read", "*", context=ctx) is True


def test_evaluator_attributes_condition_fail():
    ev = ACLEvaluator()
    ev.add_policy(
        "m",
        _entry(
            principal="u",
            action="read",
            resource="*",
            conditions={"attributes": {"role": "admin"}},
        ),
    )
    ctx = {"attributes": {"role": "viewer"}}
    assert ev.evaluate("m", "u", "read", "*", context=ctx) is False


# ---------------------------------------------------------------------------
# Policy management
# ---------------------------------------------------------------------------


def test_evaluator_remove_policy_returns_true():
    ev = ACLEvaluator()
    entry = _entry()
    ev.add_policy("m", entry)
    assert ev.remove_policy("m", "test-acl-id") is True


def test_evaluator_remove_policy_returns_false_when_not_found():
    ev = ACLEvaluator()
    assert ev.remove_policy("m", "nonexistent") is False


def test_evaluator_remove_policy_stops_access():
    ev = ACLEvaluator()
    entry = _entry(principal="u", action="read", resource="*")
    ev.add_policy("m", entry)
    assert ev.evaluate("m", "u", "read", "*") is True
    ev.remove_policy("m", entry.id)
    assert ev.evaluate("m", "u", "read", "*") is False


def test_evaluator_get_policies_returns_empty_for_unknown_mesh():
    ev = ACLEvaluator()
    assert ev.get_policies("nonexistent") == []


# ---------------------------------------------------------------------------
# ACLManager
# ---------------------------------------------------------------------------


def test_acl_manager_check_access_via_evaluator():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="*"))
    mgr = ACLManager(evaluator=ev)
    assert mgr.check_access("m", "u", "read", "*") is True
    assert mgr.check_access("m", "u", "write", "*") is False


def test_acl_manager_revoke_access():
    ev = ACLEvaluator()
    entry = _entry(principal="u", action="read", resource="*")
    ev.add_policy("m", entry)
    mgr = ACLManager(evaluator=ev)
    assert mgr.revoke_access("m", entry.id) is True
    assert mgr.check_access("m", "u", "read", "*") is False


def test_acl_manager_list_user_permissions():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="u", action="read", resource="*"))
    ev.add_policy("m", _entry(principal="u", action="write", resource="mesh/*"))
    ev.add_policy("m", _entry(principal="other", action="read", resource="*"))
    mgr = ACLManager(evaluator=ev)
    perms = mgr.list_user_permissions("m", "u")
    assert len(perms) == 2
    principals = {p["principal"] for p in perms}
    assert "u" in principals
    assert "other" not in principals


def test_acl_manager_list_permissions_includes_wildcard_entries():
    ev = ACLEvaluator()
    ev.add_policy("m", _entry(principal="*", action="read", resource="*"))
    mgr = ACLManager(evaluator=ev)
    perms = mgr.list_user_permissions("m", "any-user")
    assert len(perms) == 1


# ---------------------------------------------------------------------------
# Predefined policies
# ---------------------------------------------------------------------------


def test_create_default_policies_owner_has_full_access():
    policies = create_default_policies("mesh-1", "owner-42")
    assert len(policies) >= 1
    owner_policy = policies[0]
    assert owner_policy.principal == "owner-42"
    assert owner_policy.action == "*"
    assert owner_policy.resource == "*"
    assert owner_policy.effect == Effect.ALLOW


def test_create_readonly_policy_structure():
    p = create_readonly_policy("mesh-1", "viewer-99", "admin-1")
    assert p.principal == "viewer-99"
    assert p.action == "read"
    assert p.effect == Effect.ALLOW
    assert p.created_by == "admin-1"


def test_create_readonly_policy_ids_are_unique():
    p1 = create_readonly_policy("m", "u", "a")
    p2 = create_readonly_policy("m", "u", "a")
    assert p1.id != p2.id
