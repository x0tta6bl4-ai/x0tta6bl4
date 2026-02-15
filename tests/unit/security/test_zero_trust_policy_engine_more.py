from datetime import datetime, timedelta

import pytest

from src.security.zero_trust.policy_engine import (PolicyAction,
                                                   PolicyCondition,
                                                   PolicyEngine, PolicyRule)


def test_match_pattern_exact_and_wildcard_and_prefix():
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)

    assert engine._match_pattern("spiffe://d/w/a", "spiffe://d/w/a") is True
    assert engine._match_pattern("spiffe://d/w/a", "spiffe://d/w/*") is True
    assert engine._match_pattern("spiffe://d/w/api-v1", "spiffe://d/w/api*") is True
    assert engine._match_pattern("spiffe://d/w/a", "spiffe://x/*") is False


def test_time_window_spans_midnight(monkeypatch):
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, 1, 0, 0)

    monkeypatch.setattr("src.security.zero_trust.policy_engine.datetime", _FakeDT)

    assert engine._check_time_window({"start": "23:00", "end": "02:00"}) is True


def test_time_window_invalid_format_defaults_allow():
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    assert engine._check_time_window({"start": "BAD", "end": "WORSE"}) is True


def test_rate_limit_blocks(monkeypatch):
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)

    # Freeze time so all requests fall within the same 1-minute window
    base = datetime(2026, 1, 1, 12, 0, 0)

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return base

    monkeypatch.setattr("src.security.zero_trust.policy_engine.datetime", _FakeDT)

    peer = "spiffe://t/workload/user-1"
    rl = {"requests_per_minute": 2}

    assert engine._check_rate_limit(peer, rl) is True
    assert engine._check_rate_limit(peer, rl) is True
    assert engine._check_rate_limit(peer, rl) is False


def test_evaluate_opa_policy_takes_precedence(monkeypatch):
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=True)

    rule = PolicyRule(
        rule_id="opa-rule",
        name="OPA",
        action=PolicyAction.ALLOW,
        spiffe_id_pattern="spiffe://t/workload/*",
        allowed_resources=["r1"],
        priority=999,
        opa_policy="package x0tta6bl4.policy\n default allow=false",
    )
    engine.add_rule(rule)

    class _Resp:
        status_code = 200

        def json(self):
            return {"result": False}

    def _post(url, json, timeout):
        return _Resp()

    monkeypatch.setattr("src.security.zero_trust.policy_engine.requests.post", _post)

    decision = engine.evaluate("spiffe://t/workload/u", resource="r1")
    assert decision.allowed is False
    assert decision.audit_log is True
    assert "OPA" in (decision.reason or "")


def test_audit_log_trim_to_1000(monkeypatch):
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    engine.remove_rule("default_allow")

    for i in range(1100):
        engine.evaluate(peer_spiffe_id=f"spiffe://t/workload/u{i}", resource="r")

    assert len(engine.audit_log) == 1000
