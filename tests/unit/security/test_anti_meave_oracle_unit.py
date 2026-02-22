"""Unit tests for src.security.anti_meave_oracle."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.security.anti_meave_oracle import (
    AntiMeaveOracle,
    Capability,
    CapabilityType,
    ThreatLevel,
    get_oracle,
    set_oracle,
)


def _read_capability(
    name: str = "read-cap",
    max_nodes: int = 5,
    max_pct: float = 1.0,
    expires_at: float | None = None,
) -> Capability:
    return Capability(
        name=name,
        capability_type=CapabilityType.READ,
        max_affected_nodes=max_nodes,
        max_affected_percentage=max_pct,
        expires_at=expires_at,
    )


def test_capability_expiry_and_scope_checks():
    cap = _read_capability(max_nodes=2, max_pct=0.5)
    assert cap.is_expired() is False
    assert cap.is_valid() is True
    assert cap.can_affect_nodes(2, 10) is True
    assert cap.can_affect_nodes(3, 10) is False
    assert cap.can_affect_nodes(2, 3) is False

    expired = _read_capability(expires_at=time.time() - 1)
    assert expired.is_expired() is True
    assert expired.is_valid() is False


@pytest.mark.asyncio
async def test_register_agent_rejects_invalid_capability():
    oracle = AntiMeaveOracle()
    expired = _read_capability(expires_at=time.time() - 1)

    assert await oracle.register_agent("a1", "swarm-1", [expired]) is False
    assert oracle.get_metrics()["agents_registered"] == 0


@pytest.mark.asyncio
async def test_validate_action_success_records_metrics_and_audit():
    oracle = AntiMeaveOracle(network_size=100, max_nodes_per_agent=10)
    cap = _read_capability(name="read", max_nodes=5, max_pct=1.0)
    assert await oracle.register_agent("a1", "swarm-1", [cap]) is True

    allowed = await oracle.validate_action("a1", "read", ["n1", "n2"])
    assert allowed is True

    profile = oracle.get_agent_profile("a1")
    assert profile is not None
    assert profile.actions_taken == 1
    assert profile.nodes_affected == {"n1", "n2"}
    assert oracle.get_metrics()["actions_validated"] == 1

    events = [e["event"] for e in oracle.get_audit_log(agent_id="a1", limit=10)]
    assert "agent_registered" in events
    assert "action_validated" in events


@pytest.mark.asyncio
async def test_validate_action_rejects_unknown_agent():
    oracle = AntiMeaveOracle()
    allowed = await oracle.validate_action("missing", "read", ["n1"])
    assert allowed is False
    assert oracle.get_metrics()["actions_rejected"] == 1


@pytest.mark.asyncio
async def test_validate_action_scope_violation_creates_high_alert():
    oracle = AntiMeaveOracle(network_size=100)
    cap = _read_capability(name="read", max_nodes=1, max_pct=1.0)
    assert await oracle.register_agent("a1", "swarm-1", [cap]) is True

    allowed = await oracle.validate_action("a1", "read", ["n1", "n2"])
    assert allowed is False

    alerts = oracle.get_alerts(agent_id="a1")
    assert len(alerts) == 1
    assert alerts[0].threat_level is ThreatLevel.HIGH
    assert "Scope violation" in alerts[0].description


@pytest.mark.asyncio
async def test_rate_limit_violation_creates_medium_alert():
    oracle = AntiMeaveOracle(max_agent_actions_per_minute=1)
    cap = _read_capability(name="read", max_nodes=3, max_pct=1.0)
    assert await oracle.register_agent("a1", "swarm-1", [cap]) is True

    assert await oracle.validate_action("a1", "read", ["n1"]) is True
    assert await oracle.validate_action("a1", "read", ["n2"]) is False

    alerts = oracle.get_alerts(agent_id="a1")
    assert len(alerts) == 1
    assert alerts[0].threat_level is ThreatLevel.MEDIUM
    assert "Rate limit exceeded" in alerts[0].description


@pytest.mark.asyncio
async def test_detect_threats_autosuspends_without_deadlock():
    oracle = AntiMeaveOracle(network_size=10, anomaly_threshold=0.2, auto_suspend=True)
    cap = _read_capability(name="read", max_nodes=10, max_pct=1.0)
    assert await oracle.register_agent("a1", "swarm-1", [cap]) is True

    profile = oracle.get_agent_profile("a1")
    assert profile is not None
    profile.actions_taken = 50
    profile.nodes_affected.update({"n1", "n2", "n3"})

    threats = await asyncio.wait_for(oracle.detect_threats(), timeout=1.0)
    assert len(threats) == 1
    assert threats[0].threat_level is ThreatLevel.HIGH
    assert oracle.get_agent_profile("a1").is_suspended is True


@pytest.mark.asyncio
async def test_resolve_alert_and_shutdown():
    oracle = AntiMeaveOracle(network_size=100)
    cap = _read_capability(name="read", max_nodes=1, max_pct=1.0)
    assert await oracle.register_agent("a1", "swarm-1", [cap]) is True

    assert await oracle.validate_action("a1", "read", ["n1", "n2"]) is False
    alerts = oracle.get_alerts(agent_id="a1", unresolved_only=True)
    assert len(alerts) == 1

    assert await oracle.resolve_alert(alerts[0].alert_id) is True
    assert oracle.get_alerts(agent_id="a1", unresolved_only=True) == []

    assert await oracle.shutdown() is None
    assert oracle.get_metrics()["active_agents"] == 0


def test_oracle_singleton_set_and_get():
    custom = AntiMeaveOracle(network_size=7)
    set_oracle(custom)
    assert get_oracle() is custom
