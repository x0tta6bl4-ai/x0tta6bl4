#!/usr/bin/env python3
"""Integration tests for MAPE-K self-healing recovery cycle (#169).

Tests the full detect → analyze → plan → execute → verify cycle.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.self_healing.mape_k import (
    MAPEKAnalyzer,
    MAPEKExecutor,
    MAPEKKnowledge,
    MAPEKMonitor,
    MAPEKPlanner,
)
from src.self_healing.mape_k.manager import SelfHealingManager


@pytest.fixture
def manager():
    """Create a SelfHealingManager with mocked DI and executor."""
    with patch("src.core.di.get_container") as mock_di:
        mock_container = MagicMock()
        mock_container.has.return_value = False
        mock_di.return_value = mock_container
        mgr = SelfHealingManager(node_id="test-node")
        mgr.executor.recovery_executor = MagicMock()
        mgr.executor.use_recovery_executor = True
        mgr.executor.recovery_executor.execute.return_value = True
        yield mgr


@pytest.fixture
def manager_with_event_bus():
    """Create a SelfHealingManager with an event bus."""
    event_bus = MagicMock()
    with patch("src.core.di.get_container") as mock_di:
        mock_container = MagicMock()
        mock_container.has.return_value = False
        mock_di.return_value = mock_container
        mgr = SelfHealingManager(node_id="test-node", event_bus=event_bus)
        mgr.executor.recovery_executor = MagicMock()
        mgr.executor.use_recovery_executor = True
        mgr.executor.recovery_executor.execute.return_value = True
        yield mgr, event_bus


class TestMAPEKRecoveryCycle:
    """Integration tests for the full MAPE-K recovery cycle."""

    def test_full_cycle_detect_analyze_plan_execute(self, manager):
        """Inject high CPU metrics → verify full MAPE-K cycle runs."""
        metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics)

        assert manager._executed_actions_count == 1
        assert len(manager.knowledge.incidents) == 1

    def test_recovery_counter_increments(self, manager):
        """Verify recovery counter increments after healing (with full state reset)."""
        metrics_high = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics_high)
        assert manager._executed_actions_count == 1

        # Reset full state to allow second cycle (simulates new monitoring window)
        manager._in_cooldown = False
        manager._executed_actions_count = 0
        manager.run_cycle(metrics_high)
        assert manager._executed_actions_count == 1

    def test_knowledge_records_cycle(self, manager):
        """Verify knowledge base records the recovery cycle."""
        metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics)

        assert len(manager.knowledge.incidents) == 1
        incident = manager.knowledge.incidents[0]
        assert incident["issue"] is not None
        assert incident["action"] is not None
        assert incident["success"] is True

    def test_normal_metrics_no_recovery(self, manager):
        """Normal metrics should not trigger recovery."""
        metrics = {
            "cpu_percent": 30.0,
            "memory_percent": 40.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics)

        assert manager._executed_actions_count == 0
        assert len(manager.knowledge.incidents) == 0

    def test_cooldown_prevents_double_execution(self, manager):
        """After first recovery, cooldown blocks immediate second recovery."""
        metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics)
        assert manager._executed_actions_count == 1

        manager.run_cycle(metrics)
        assert manager._executed_actions_count == 1

    def test_different_anomaly_types(self, manager):
        """Verify different anomaly types trigger different recovery actions."""
        metrics_cpu = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }
        metrics_mem = {
            "cpu_percent": 30.0,
            "memory_percent": 95.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics_cpu)
        action_cpu = manager.knowledge.incidents[0]["action"]

        # Reset full state to allow second cycle
        manager._in_cooldown = False
        manager._executed_actions_count = 0
        manager.run_cycle(metrics_mem)
        action_mem = manager.knowledge.incidents[1]["action"]

        assert action_cpu != action_mem

    def test_network_loss_triggers_recovery(self, manager):
        """High packet loss should trigger network-related recovery."""
        metrics = {
            "cpu_percent": 30.0,
            "memory_percent": 40.0,
            "packet_loss_percent": 10.0,
        }

        manager.run_cycle(metrics)

        assert manager._executed_actions_count == 1
        incident = manager.knowledge.incidents[0]
        assert "Network" in incident["issue"] or "Loss" in incident["issue"]

    def test_mttr_is_tracked(self, manager):
        """MTTR (Mean Time To Recovery) should be recorded in knowledge."""
        metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics)

        incident = manager.knowledge.incidents[0]
        assert "mttr" in incident
        assert incident["mttr"] >= 0

    def test_multiple_metrics_combined(self, manager):
        """Multiple abnormal metrics should still trigger one recovery cycle."""
        metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 90.0,
            "packet_loss_percent": 8.0,
        }

        manager.run_cycle(metrics)

        assert manager._executed_actions_count == 1
        assert len(manager.knowledge.incidents) == 1

    def test_planner_selects_correct_action(self, manager):
        """Planner should select action based on detected issue."""
        metrics_cpu = {
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics_cpu)

        incident = manager.knowledge.incidents[0]
        assert incident["action"] == "Restart service"

    def test_planner_clear_cache_for_memory(self, manager):
        """Planner should select 'Clear cache' for high memory."""
        metrics_mem = {
            "cpu_percent": 30.0,
            "memory_percent": 95.0,
            "packet_loss_percent": 0.0,
        }

        manager.run_cycle(metrics_mem)

        incident = manager.knowledge.incidents[0]
        assert incident["action"] == "Clear cache"

    def test_planner_switch_route_for_network(self, manager):
        """Planner should select 'Switch route' for network loss."""
        metrics_net = {
            "cpu_percent": 30.0,
            "memory_percent": 40.0,
            "packet_loss_percent": 10.0,
        }

        manager.run_cycle(metrics_net)

        incident = manager.knowledge.incidents[0]
        assert incident["action"] == "Switch route"
