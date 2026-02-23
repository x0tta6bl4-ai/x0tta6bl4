"""Unit tests for src.agents.security_audit_agent."""

from __future__ import annotations

import pytest

from src.agents.security_audit_agent import SecurityAuditAgent


def test_run_audit_emits_expected_log_messages(monkeypatch, caplog):
    monkeypatch.setattr("src.agents.security_audit_agent.time.sleep", lambda _seconds: None)
    agent = SecurityAuditAgent()

    with caplog.at_level("INFO"):
        agent.run_audit()

    assert any("Initiating system security audit" in msg for msg in caplog.messages)
    assert any("SBOM generated" in msg for msg in caplog.messages)
    assert any("PQC Rotation status: OK" in msg for msg in caplog.messages)
    assert any("Zero-Trust Identity" in msg for msg in caplog.messages)


def test_run_invokes_audit_loop_once_when_sleep_interrupts(monkeypatch):
    agent = SecurityAuditAgent()
    calls = {"audit": 0}

    def _audit():
        calls["audit"] += 1

    def _sleep(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(agent, "run_audit", _audit)
    monkeypatch.setattr("src.agents.security_audit_agent.time.sleep", _sleep)

    with pytest.raises(KeyboardInterrupt):
        agent.run()

    assert calls["audit"] == 1
