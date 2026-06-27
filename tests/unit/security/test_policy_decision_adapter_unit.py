from src.security.policy_decision_adapter import (
    policy_allowed,
    policy_reason,
    policy_rules,
)
from src.security.policy_engine import (
    PolicyDecision as ABACPolicyDecision,
    PolicyEffect,
)
from src.security.zero_trust.policy_engine import (
    PolicyAction,
    PolicyDecision as ZeroTrustPolicyDecision,
)


def test_adapter_blocks_abac_deny_decision_even_when_dataclass_is_truthy():
    decision = ABACPolicyDecision(
        effect=PolicyEffect.DENY,
        policy_id="default-deny",
        rule_id="deny-all",
        reason="Default deny rule",
        attributes_evaluated=4,
        evaluation_time_ms=1.2,
    )

    assert bool(decision) is True
    assert policy_allowed(decision) is False
    assert policy_reason(decision) == "Default deny rule"
    assert policy_rules(decision) == ["deny-all"]


def test_adapter_allows_abac_audit_but_blocks_challenge_until_handled():
    audit_decision = ABACPolicyDecision(
        effect=PolicyEffect.AUDIT,
        policy_id="trust-based-access",
        rule_id="low-trust-audit",
        reason="Low trust nodes require audit logging",
        attributes_evaluated=3,
        evaluation_time_ms=0.4,
    )
    challenge_decision = ABACPolicyDecision(
        effect=PolicyEffect.CHALLENGE,
        policy_id="challenge-policy",
        rule_id="challenge-rule",
        reason="Additional verification required",
        attributes_evaluated=3,
        evaluation_time_ms=0.4,
    )

    assert policy_allowed(audit_decision) is True
    assert policy_allowed(challenge_decision) is False


def test_adapter_preserves_zero_trust_decision_semantics():
    allow = ZeroTrustPolicyDecision(
        allowed=True,
        action=PolicyAction.ALLOW,
        matched_rules=["allow-rule"],
        reason="matched allow",
    )
    deny = ZeroTrustPolicyDecision(
        allowed=False,
        action=PolicyAction.DENY,
        matched_rules=["deny-rule"],
        reason="matched deny",
    )

    assert policy_allowed(allow) is True
    assert policy_rules(allow) == ["allow-rule"]
    assert policy_allowed(deny) is False
    assert policy_reason(deny) == "matched deny"


def test_adapter_normalizes_dict_decision_shapes():
    assert policy_allowed({"effect": "deny", "rule_id": "r1"}) is False
    assert policy_rules({"effect": "deny", "rule_id": "r1"}) == ["r1"]
    assert policy_allowed({"action": "audit", "matched_rules": ["r2"]}) is True
    assert policy_rules({"action": "audit", "matched_rules": ["r2"]}) == ["r2"]
