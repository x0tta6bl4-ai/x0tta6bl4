"""Unit tests for src/core/mape_k_loop.py — MAPE-K autonomic loop."""
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from dataclasses import dataclass
from enum import Enum


# Mock consciousness types before importing the module
class _FakeState(Enum):
    AWAKENED = "AWAKENED"
    CONTEMPLATIVE = "CONTEMPLATIVE"
    EUPHORIC = "EUPHORIC"
    MYSTICAL = "MYSTICAL"


@dataclass
class _FakeMetrics:
    state: _FakeState = _FakeState.AWAKENED
    phi_ratio: float = 0.618

    def to_prometheus_format(self):
        return {"phi_ratio": self.phi_ratio, "state_value": 1.0}


# Patch heavy imports before loading the module under test
_PATCHES = {
    "src.core.consciousness.ConsciousnessEngine": MagicMock,
    "src.core.consciousness.ConsciousnessMetrics": _FakeMetrics,
    "src.monitoring.prometheus_client.PrometheusExporter": MagicMock,
    "src.mesh.network_manager.MeshNetworkManager": MagicMock,
    "src.security.zero_trust.ZeroTrustValidator": MagicMock,
    "src.dao.ipfs_logger.DAOAuditLogger": MagicMock,
}


@pytest.fixture
def loop():
    """Create a MAPEKLoop with all dependencies mocked."""
    with patch.dict("sys.modules", {}):  # don't pollute
        pass

    with patch("src.core.mape_k_loop.ConsciousnessEngine"), \
         patch("src.core.mape_k_loop.MeshNetworkManager"), \
         patch("src.core.mape_k_loop.PrometheusExporter"), \
         patch("src.core.mape_k_loop.ZeroTrustValidator"), \
         patch("src.core.mape_k_loop.DAOAuditLogger"):
        from src.core.mape_k_loop import MAPEKLoop

    consciousness = MagicMock()
    mesh = MagicMock()
    prometheus = MagicMock()
    zero_trust = MagicMock()
    dao_logger = AsyncMock()

    # Default mock returns
    mesh.get_statistics = AsyncMock(return_value={
        "active_peers": 5,
        "avg_latency_ms": 50,
        "packet_loss_percent": 0.01,
        "mttr_minutes": 3.0,
    })
    mesh.set_route_preference = AsyncMock(return_value=True)
    mesh.trigger_aggressive_healing = AsyncMock(return_value=3)
    mesh.trigger_preemptive_checks = AsyncMock()
    zero_trust.get_validation_stats.return_value = {"success_rate": 0.98}

    consciousness.get_consciousness_metrics.return_value = _FakeMetrics()
    consciousness.get_operational_directive.return_value = {
        "route_preference": "balanced",
        "monitoring_interval_sec": 30,
        "message": "All good",
    }
    consciousness.get_trend_analysis.return_value = {"trend": "stable"}

    mk = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        dao_logger=dao_logger,
    )
    return mk


class TestInit:
    def test_default_attributes(self, loop):
        assert loop.running is False
        assert loop.loop_interval == 60
        assert loop.state_history == []
        assert loop.action_dispatcher is None

    def test_action_dispatcher_param(self, loop):
        from src.dao.governance import ActionDispatcher
        loop2_dispatcher = ActionDispatcher()

        with patch("src.core.mape_k_loop.ConsciousnessEngine"), \
             patch("src.core.mape_k_loop.MeshNetworkManager"), \
             patch("src.core.mape_k_loop.PrometheusExporter"), \
             patch("src.core.mape_k_loop.ZeroTrustValidator"):
            from src.core.mape_k_loop import MAPEKLoop
            mk = MAPEKLoop(
                consciousness_engine=MagicMock(),
                mesh_manager=MagicMock(),
                prometheus=MagicMock(),
                zero_trust=MagicMock(),
                action_dispatcher=loop2_dispatcher,
            )
        assert mk.action_dispatcher is loop2_dispatcher


class TestMonitorPhase:
    @pytest.mark.asyncio
    async def test_monitor_returns_metrics(self, loop):
        metrics = await loop._monitor()
        assert "cpu_percent" in metrics
        assert "latency_ms" in metrics
        assert "mesh_connectivity" in metrics
        assert "zero_trust_success_rate" in metrics
        assert metrics["mesh_connectivity"] == 5

    @pytest.mark.asyncio
    async def test_monitor_psutil_fallback(self, loop):
        """When psutil is missing, fallback values are used."""
        with patch.dict("sys.modules", {"psutil": None}):
            metrics = await loop._monitor()
        assert metrics["cpu_percent"] == 50.0
        assert metrics["memory_percent"] == 50.0


class TestAnalyzePhase:
    def test_analyze_calls_consciousness(self, loop):
        raw = {"cpu_percent": 80.0}
        result = loop._analyze(raw)
        loop.consciousness.get_consciousness_metrics.assert_called_once_with(raw)
        assert isinstance(result, _FakeMetrics)


class TestPlanPhase:
    def test_plan_returns_directives(self, loop):
        metrics = _FakeMetrics()
        directives = loop._plan(metrics)
        assert "route_preference" in directives
        assert "trend" in directives

    def test_plan_preemptive_on_degrading(self, loop):
        metrics = _FakeMetrics(state=_FakeState.CONTEMPLATIVE)
        loop.consciousness.get_trend_analysis.return_value = {"trend": "degrading"}
        directives = loop._plan(metrics)
        assert directives.get("preemptive_healing") is True


class TestExecutePhase:
    @pytest.mark.asyncio
    async def test_execute_route_preference(self, loop):
        directives = {"route_preference": "low_latency"}
        actions = await loop._execute(directives)
        loop.mesh.set_route_preference.assert_called_once_with("low_latency")
        assert "route_preference=low_latency" in actions

    @pytest.mark.asyncio
    async def test_execute_aggressive_healing(self, loop):
        directives = {"enable_aggressive_healing": True}
        actions = await loop._execute(directives)
        loop.mesh.trigger_aggressive_healing.assert_called_once()
        assert any("aggressive_healing" in a for a in actions)

    @pytest.mark.asyncio
    async def test_execute_preemptive_healing(self, loop):
        directives = {"preemptive_healing": True}
        actions = await loop._execute(directives)
        loop.mesh.trigger_preemptive_checks.assert_called_once()
        assert "preemptive_healing_initiated" in actions

    @pytest.mark.asyncio
    async def test_execute_dao_actions(self, loop):
        from src.dao.governance import ActionDispatcher
        loop.action_dispatcher = ActionDispatcher()
        directives = {
            "dao_actions": [
                {"type": "restart_node", "node_id": "node-5"},
                {"type": "rotate_keys", "scope": "all"},
            ]
        }
        actions = await loop._execute(directives)
        dao_actions = [a for a in actions if a.startswith("dao:")]
        assert len(dao_actions) == 2
        assert all("OK" in a for a in dao_actions)

    @pytest.mark.asyncio
    async def test_execute_no_dispatcher_skips_dao(self, loop):
        """Without action_dispatcher, dao_actions are ignored."""
        directives = {"dao_actions": [{"type": "restart_node", "node_id": "x"}]}
        actions = await loop._execute(directives)
        assert not any("dao:" in a for a in actions)


class TestKnowledgePhase:
    @pytest.mark.asyncio
    async def test_knowledge_exports_prometheus(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": "test"}
        await loop._knowledge(metrics, directives, ["action1"])
        loop.prometheus.set_gauge.assert_called()

    @pytest.mark.asyncio
    async def test_knowledge_stores_state(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        await loop._knowledge(metrics, directives, [])
        assert len(loop.state_history) == 1

    @pytest.mark.asyncio
    async def test_knowledge_trims_history(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        # Pre-fill history to just under limit
        loop.state_history = [MagicMock()] * 10000
        await loop._knowledge(metrics, directives, [])
        assert len(loop.state_history) == 10000  # trimmed after exceeding

    @pytest.mark.asyncio
    async def test_knowledge_logs_dao_for_euphoric(self, loop):
        metrics = _FakeMetrics(state=_FakeState.EUPHORIC)
        directives = {"message": "peak"}
        loop.dao_logger.log_consciousness_event = AsyncMock(return_value="cid-1")
        await loop._knowledge(metrics, directives, [])
        loop.dao_logger.log_consciousness_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_knowledge_raw_metrics_exported(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        raw = {"latency_ms": 120, "cpu_percent": 88, "packet_loss": 0.05}
        await loop._knowledge(metrics, directives, [], raw)
        # Should export mapped gauges
        calls = [c[0] for c in loop.prometheus.set_gauge.call_args_list]
        gauge_names = [c[0] for c in calls]
        assert "mesh_latency_ms" in gauge_names
        assert "system_cpu_percent" in gauge_names


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_execute_cycle(self, loop):
        await loop._execute_cycle()
        # Verify all phases called
        loop.consciousness.get_consciousness_metrics.assert_called_once()
        loop.consciousness.get_operational_directive.assert_called_once()
        assert len(loop.state_history) == 1
        assert loop.loop_interval == 30  # updated from directives


class TestStartStop:
    @pytest.mark.asyncio
    async def test_stop_sets_flag(self, loop):
        await loop.stop()
        assert loop.running is False
