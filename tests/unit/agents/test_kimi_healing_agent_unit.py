from __future__ import annotations

from src.agents.kimi_healing_agent import KimiHealingAgent


def test_high_latency_maps_to_update_config_action():
    agent = KimiHealingAgent()
    actions = agent.analyze_and_heal({"type": "high_latency"}, "node-a")

    assert len(actions) == 1
    assert actions[0].action == "update_config"
    assert actions[0].params.get("force_reconnect") is True


def test_ddos_maps_to_valid_playbook_action():
    agent = KimiHealingAgent()
    actions = agent.analyze_and_heal({"type": "ddos_suspected"}, "node-b")

    assert len(actions) == 1
    assert actions[0].action == "ban_peer"
    assert actions[0].params.get("reason") == "ddos_suspected"


def test_unknown_anomaly_uses_restart_fallback():
    agent = KimiHealingAgent()
    actions = agent.analyze_and_heal({"type": "something_else"}, "node-c")

    assert len(actions) == 1
    assert actions[0].action == "restart"
    assert actions[0].params.get("reason") == "unknown_anomaly"

