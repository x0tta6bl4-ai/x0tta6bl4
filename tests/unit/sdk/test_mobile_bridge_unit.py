"""Unit tests for src.sdk.mobile_bridge."""

from __future__ import annotations

from src.sdk.mobile_bridge import MobileMeshAgent, x0t_mobile_init


def test_mobile_mesh_agent_initial_state():
    agent = MobileMeshAgent(mesh_id="mesh-1", token="tok")
    assert agent.mesh_id == "mesh-1"
    assert agent.token == "tok"
    assert agent.is_running is False
    assert agent.get_status() == {
        "connected": False,
        "pqc_active": True,
        "neighbor_count": 0,
        "battery_mode": "eco",
    }


def test_start_creates_background_thread(monkeypatch):
    captured = {}

    class _FakeThread:
        def __init__(self, target, daemon):
            captured["target"] = target
            captured["daemon"] = daemon
            captured["started"] = False

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("src.sdk.mobile_bridge.threading.Thread", _FakeThread)

    agent = MobileMeshAgent(mesh_id="mesh-1", token="tok")
    rc = agent.start()

    assert rc == 0
    assert agent.is_running is True
    assert captured["target"] == agent._mesh_loop
    assert captured["daemon"] is True
    assert captured["started"] is True


def test_stop_sets_running_false():
    agent = MobileMeshAgent(mesh_id="mesh-1", token="tok")
    agent.is_running = True
    agent.stop()
    assert agent.is_running is False


def test_mesh_loop_updates_status(monkeypatch):
    agent = MobileMeshAgent(mesh_id="mesh-1", token="tok")
    agent.is_running = True

    def _one_tick(_seconds):
        agent.is_running = False

    monkeypatch.setattr("src.sdk.mobile_bridge.time.sleep", _one_tick)
    agent._mesh_loop()

    status = agent.get_status()
    assert status["connected"] is True
    assert status["neighbor_count"] == 2


def test_mobile_init_factory():
    agent = x0t_mobile_init("mesh-x", "token-y")
    assert isinstance(agent, MobileMeshAgent)
    assert agent.mesh_id == "mesh-x"
