import asyncio
from unittest.mock import Mock

import pytest

from src.self_healing.mape_k import (MAPEKExecutor, MAPEKKnowledge,
                                     MAPEKMonitor, MAPEKPlanner,
                                     SelfHealingManager)


def test_knowledge_threshold_adjustment_success_and_failure(monkeypatch):
    k = MAPEKKnowledge()

    k.record(
        metrics={"cpu_percent": 90.0},
        issue="High CPU",
        action="Restart service",
        success=True,
    )
    t1 = k.get_adjusted_threshold("cpu_percent", 100.0)
    assert t1 > 0

    k.record(
        metrics={"cpu_percent": 90.0},
        issue="High CPU",
        action="Restart service",
        success=False,
    )
    t2 = k.get_adjusted_threshold("cpu_percent", 100.0)
    assert t2 != t1


def test_knowledge_recommended_action_prefers_lower_mttr():
    k = MAPEKKnowledge()

    k.record(
        metrics={}, issue="High CPU", action="Restart service", success=True, mttr=10.0
    )
    k.record(
        metrics={}, issue="High CPU", action="Restart service", success=True, mttr=12.0
    )
    k.record(metrics={}, issue="High CPU", action="Scale up", success=True, mttr=3.0)

    assert k.get_recommended_action("High CPU") == "Scale up"
    assert k.get_average_mttr("High CPU") == pytest.approx((10.0 + 12.0 + 3.0) / 3.0)


def test_knowledge_storage_adapter_sync_paths():
    storage = Mock()
    storage.record_incident_sync = Mock()
    storage.search_patterns_sync = Mock(
        return_value=[{"action": "Restart service", "mttr": 1.0}]
    )

    k = MAPEKKnowledge(knowledge_storage=storage)
    k.record(
        metrics={"cpu_percent": 95},
        issue="High CPU",
        action="Restart service",
        success=True,
        mttr=1.0,
    )

    storage.record_incident_sync.assert_called_once()
    patterns = k.get_successful_patterns("High CPU")
    assert patterns and patterns[0]["mttr"] == 1.0


def test_monitor_uses_threshold_manager_over_default():
    tm = Mock()
    tm.get_threshold = Mock(side_effect=lambda name, default: 1.0)

    mon = MAPEKMonitor(knowledge=None, threshold_manager=tm)
    assert mon.check({"cpu_percent": 2.0}) is True


def test_planner_uses_knowledge_recommended_action():
    k = MAPEKKnowledge()
    k.record(
        metrics={}, issue="High CPU", action="Custom Action", success=True, mttr=1.0
    )

    p = MAPEKPlanner(knowledge=k)
    assert p.plan("High CPU") == "Custom Action"


def test_executor_uses_recovery_executor_execute(monkeypatch):
    ex = MAPEKExecutor()

    fake = Mock()
    fake.execute = Mock(return_value=True)
    ex.recovery_executor = fake
    ex.use_recovery_executor = True

    assert ex.execute("Restart service", {"service_name": "x"}) is True
    fake.execute.assert_called_once()


def test_self_healing_manager_applies_dao_proposals_on_startup():
    tm = Mock()
    tm.get_threshold = Mock(side_effect=lambda name, default: default)
    tm.check_and_apply_dao_proposals = Mock(return_value=2)

    m = SelfHealingManager(threshold_manager=tm)
    tm.check_and_apply_dao_proposals.assert_called_once()
    assert m.threshold_manager is tm
