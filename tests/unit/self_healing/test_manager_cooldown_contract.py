"""Timed recovery suppression without live backend operations."""
from unittest.mock import patch

import pytest

from src.self_healing.mape_k.manager import SelfHealingManager


@pytest.mark.parametrize("result", [True, False])
def test_cooldown_expires_while_anomaly_persists(result):
    now = [100.0]
    manager = SelfHealingManager(node_id="authoritative-node", action_cooldown_seconds=60,
                                 clock=lambda: now[0])
    with (patch.object(manager.monitor, "check", return_value=True),
          patch.object(manager.analyzer, "analyze", return_value="High CPU"),
          patch.object(manager.planner, "plan", return_value="Restart service"),
          patch.object(manager.executor, "execute", return_value=result) as execute):
        manager.run_cycle({"node_id": "untrusted-metric-node"})
        now[0] = 159.9
        assert manager.recovery_start_times == {}
        assert manager.recovery_events == {}
        manager.run_cycle({})
        assert execute.call_count == 1
        now[0] = 160.0
        manager.run_cycle({})
        assert execute.call_count == 2
        execute.assert_called_with("Restart service", {"node_id": "authoritative-node"})
    assert manager.get_feedback_stats()["oscillation_blocks"] == 1


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
def test_invalid_cooldown_rejected(duration):
    with pytest.raises(ValueError, match="finite and non-negative"):
        SelfHealingManager(action_cooldown_seconds=duration)


def test_backend_exception_still_throttles_next_attempt():
    manager = SelfHealingManager(clock=lambda: 100.0)
    with (patch.object(manager.monitor, "check", return_value=True),
          patch.object(manager.analyzer, "analyze", return_value="High CPU"),
          patch.object(manager.planner, "plan", return_value="Restart service"),
          patch.object(manager.executor, "execute", side_effect=RuntimeError("backend")) as execute):
        with pytest.raises(RuntimeError, match="backend"):
            manager.run_cycle({})
        assert manager.recovery_start_times == {}
        assert manager.recovery_events == {}
        manager.run_cycle({})
        assert execute.call_count == 1


def test_zero_cooldown_allows_next_cycle():
    manager = SelfHealingManager(action_cooldown_seconds=0, clock=lambda: 100.0)
    with (patch.object(manager.monitor, "check", return_value=True),
          patch.object(manager.analyzer, "analyze", return_value="High CPU"),
          patch.object(manager.planner, "plan", return_value="Restart service"),
          patch.object(manager.executor, "execute", return_value=False) as execute):
        manager.run_cycle({})
        manager.run_cycle({})
        assert execute.call_count == 2
