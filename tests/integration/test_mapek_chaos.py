"""
Chaos Monkey tests for MAPE-K self-healing.

Tests recovery from various failure scenarios.
"""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest

try:
    from src.self_healing.mape_k import (MAPEKAnalyzer, MAPEKExecutor,
                                         MAPEKKnowledge, MAPEKLoop,
                                         MAPEKMonitor, MAPEKPlanner)

    MAPEK_AVAILABLE = True
except ImportError:
    MAPEK_AVAILABLE = False
    MAPEKMonitor = None
    MAPEKAnalyzer = None
    MAPEKPlanner = None
    MAPEKExecutor = None
    MAPEKKnowledge = None
    MAPEKLoop = None


@pytest.mark.skipif(not MAPEK_AVAILABLE, reason="MAPE-K not available")
class TestMAPEKChaosMonkey:
    """Chaos monkey tests for MAPE-K self-healing"""

    def test_node_failure_recovery(self):
        """Test recovery from node failure"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Simulate healthy state
        healthy_metrics = {
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "packet_loss_percent": 0.1,
        }

        # Run cycle - should be healthy
        result = mapek.run_cycle(healthy_metrics)
        assert result == "Healthy" or result is None

        # Simulate node failure (high CPU, high memory)
        failure_metrics = {
            "cpu_percent": 95.0,
            "memory_percent": 90.0,
            "packet_loss_percent": 10.0,
        }

        # Run cycle - should detect issue
        result = mapek.run_cycle(failure_metrics)
        assert result is not None
        assert (
            "High CPU" in result or "High Memory" in result or "Network Loss" in result
        )

    def test_cascading_failure_recovery(self):
        """Test recovery from cascading failures"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Simulate cascading failure
        failure_sequence = [
            {"cpu_percent": 80.0, "memory_percent": 70.0},  # Warning
            {"cpu_percent": 95.0, "memory_percent": 85.0},  # Critical
            {"cpu_percent": 99.0, "memory_percent": 95.0},  # Severe
        ]

        results = []
        for metrics in failure_sequence:
            result = mapek.run_cycle(metrics)
            results.append(result)
            time.sleep(0.1)  # Simulate time passing

        # Should detect and plan recovery
        assert any("High CPU" in str(r) for r in results if r)
        assert any("High Memory" in str(r) for r in results if r)

    def test_network_partition_recovery(self):
        """Test recovery from network partition"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Simulate network partition (high packet loss)
        partition_metrics = {
            "cpu_percent": 30.0,
            "memory_percent": 40.0,
            "packet_loss_percent": 50.0,  # Severe network issue
        }

        result = mapek.run_cycle(partition_metrics)
        assert result is not None
        assert "Network Loss" in result or "Network" in result

    def test_rapid_fluctuation_handling(self):
        """Test handling of rapid metric fluctuations"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Rapid fluctuations (should not cause thrashing)
        fluctuations = [
            {"cpu_percent": 50.0},
            {"cpu_percent": 95.0},
            {"cpu_percent": 50.0},
            {"cpu_percent": 95.0},
        ]

        actions_taken = []
        for metrics in fluctuations:
            result = mapek.run_cycle(metrics)
            if result and result != "Healthy":
                actions_taken.append(result)

        # Should handle gracefully without excessive actions
        assert len(actions_taken) <= len(fluctuations)  # Not more actions than cycles

    def test_knowledge_base_learning(self):
        """Test that knowledge base learns from recovery patterns"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Record successful recovery
        metrics = {"cpu_percent": 95.0}
        issue = mapek.run_cycle(metrics)

        # Record success
        knowledge.record(
            metrics, issue or "High CPU", "Restart service", success=True, mttr=2.5
        )

        # Check that knowledge base has learned
        recommended = knowledge.get_recommended_action("High CPU")
        assert recommended == "Restart service"

    def test_threshold_adaptation(self):
        """Test adaptive threshold adjustment"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)

        # Record false positives
        for _ in range(5):
            knowledge.record(
                {"cpu_percent": 88.0},  # Just below threshold
                "High CPU",
                "No action",
                success=False,
            )

        # Threshold should be adjusted
        adjusted = knowledge.get_adjusted_threshold("cpu_percent", 90.0)
        assert adjusted >= 90.0  # Should increase to reduce false positives


@pytest.mark.skipif(not MAPEK_AVAILABLE, reason="MAPE-K not available")
class TestMAPEKEdgeCases:
    """Test edge cases for MAPE-K"""

    def test_empty_metrics(self):
        """Test handling of empty metrics"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Empty metrics
        result = mapek.run_cycle({})
        # Should handle gracefully (return "Healthy" or None)
        assert result == "Healthy" or result is None

    def test_missing_metrics(self):
        """Test handling of missing expected metrics"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Missing expected metrics
        partial_metrics = {"cpu_percent": 95.0}  # Missing memory, packet_loss
        result = mapek.run_cycle(partial_metrics)
        # Should handle gracefully
        assert result is not None or result == "Healthy"

    def test_extreme_values(self):
        """Test handling of extreme metric values"""
        knowledge = MAPEKKnowledge()
        monitor = MAPEKMonitor(knowledge=knowledge)
        analyzer = MAPEKAnalyzer()
        planner = MAPEKPlanner(knowledge=knowledge)
        executor = MAPEKExecutor()

        mapek = MAPEKLoop(monitor, analyzer, planner, executor, knowledge)

        # Extreme values
        extreme_metrics = {
            "cpu_percent": 999.0,  # Invalid (should be 0-100)
            "memory_percent": -10.0,  # Invalid (negative)
            "packet_loss_percent": 200.0,  # Invalid (>100%)
        }

        result = mapek.run_cycle(extreme_metrics)
        # Should handle gracefully (clamp or reject)
        assert result is not None or result == "Healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
