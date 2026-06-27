"""Tests for IntegratedMAPEKCycle.run_cycle (async) and MAPEKMonitor.check dict API."""
import pytest
from src.self_healing.mape_k import MAPEKMonitor
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle


class TestMAPEKMonitorCheckDict:
    """MAPEKMonitor.check now returns a dict (not a bool)."""

    def setup_method(self):
        self.monitor = MAPEKMonitor()

    def test_check_healthy_returns_dict(self):
        result = self.monitor.check({"cpu_percent": 30, "memory_percent": 40, "packet_loss_percent": 1})
        assert isinstance(result, dict)
        assert "anomaly_detected" in result
        assert "scaling_recommended" in result
        assert result["anomaly_detected"] is False

    def test_check_high_cpu_detects_anomaly(self):
        result = self.monitor.check({"cpu_percent": 95, "memory_percent": 30})
        assert result["anomaly_detected"] is True
        assert result["issue"] == "High CPU"

    def test_check_high_memory_detects_anomaly(self):
        result = self.monitor.check({"cpu_percent": 20, "memory_percent": 90})
        assert result["anomaly_detected"] is True
        assert result["issue"] == "High Memory"

    def test_check_healthy_issue_label(self):
        result = self.monitor.check({"cpu_percent": 10, "memory_percent": 20})
        assert result["issue"] == "Healthy"


@pytest.mark.asyncio
class TestIntegratedMAPEKRunCycle:
    """IntegratedMAPEKCycle.run_cycle is async."""

    async def test_healthy_metrics_no_anomaly(self):
        cycle = IntegratedMAPEKCycle()
        metrics = {"node_id": "test-node", "cpu_percent": 30, "memory_percent": 40, "packet_loss_percent": 0.5}
        result = await cycle.run_cycle(metrics)
        assert isinstance(result, dict)
        assert result["anomaly_detected"] is False
        assert "cycle_id" in result

    async def test_high_cpu_triggers_analyze(self):
        cycle = IntegratedMAPEKCycle()
        metrics = {"node_id": "test-node", "cpu_percent": 95, "memory_percent": 40}
        result = await cycle.run_cycle(metrics)
        assert result["anomaly_detected"] is True

    async def test_result_contains_timestamp(self):
        cycle = IntegratedMAPEKCycle()
        result = await cycle.run_cycle({"node_id": "n", "cpu_percent": 10})
        assert "timestamp" in result

    async def test_scaling_recommended_field_present(self):
        cycle = IntegratedMAPEKCycle()
        result = await cycle.run_cycle({"node_id": "n", "cpu_percent": 50})
        assert "scaling_recommended" in result
