import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from libx0t.core.mape_k_loop import MAPEKLoop
from libx0t.core.consciousness import ConsciousnessMetrics, ConsciousnessState

class TestMAPEKLoop:
    @pytest.fixture
    def loop(self):
        consciousness = MagicMock()
        mesh = MagicMock()
        prometheus = MagicMock()
        zero_trust = MagicMock()
        dao_logger = AsyncMock()
        
        # Setup default mock returns
        mesh.get_statistics = AsyncMock(return_value={
            "active_peers": 5,
            "avg_latency_ms": 50,
            "packet_loss_percent": 0.01,
            "mttr_minutes": 3.0
        })
        zero_trust.get_validation_stats.return_value = {"success_rate": 0.98}
        
        consciousness.get_consciousness_metrics.return_value = ConsciousnessMetrics(
            phi_ratio=1.618, state=ConsciousnessState.HARMONIC,
            frequency_alignment=1.0, entropy=0.0, harmony_index=1.0, mesh_health=1.0, timestamp=0
        )
        
        return MAPEKLoop(
            consciousness_engine=consciousness,
            mesh_manager=mesh,
            prometheus=prometheus,
            zero_trust=zero_trust,
            dao_logger=dao_logger
        )

    @pytest.mark.asyncio
    async def test_monitor(self, loop):
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_mem:
            mock_mem.return_value.percent = 60.0
            
            metrics = await loop._monitor()
            
            assert metrics['cpu_percent'] == 50.0
            assert metrics['memory_percent'] == 60.0
            assert metrics['mesh_connectivity'] == 5
            loop.mesh.get_statistics.assert_called_once()
            loop.zero_trust.get_validation_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze(self, loop):
        raw_metrics = {"cpu": 10}
        metrics = await loop._analyze(raw_metrics)
        
        loop.consciousness.get_consciousness_metrics.assert_called_with(
            raw_metrics, swarm_risk_penalty=0.0
        )
        assert isinstance(metrics, ConsciousnessMetrics)

    def test_plan(self, loop):
        metrics = ConsciousnessMetrics(
            phi_ratio=1.618, state=ConsciousnessState.HARMONIC,
            frequency_alignment=1.0, entropy=0.0, harmony_index=1.0, mesh_health=1.0, timestamp=0
        )
        
        loop.consciousness.get_operational_directive.return_value = {
            "monitoring_interval_sec": 60,
            "route_preference": "balanced"
        }
        loop.consciousness.get_trend_analysis.return_value = {"trend": "stable"}
        
        directives = loop._plan(metrics)
        
        assert directives["monitoring_interval_sec"] == 60
        assert directives["trend"] == {"trend": "stable"}

    @pytest.mark.asyncio
    async def test_execute_route_preference(self, loop):
        directives = {"route_preference": "performance"}
        loop.mesh.set_route_preference = AsyncMock(return_value=True)
        
        actions = await loop._execute(directives)
        
        loop.mesh.set_route_preference.assert_called_with("performance")
        assert "route_preference=performance" in actions

    @pytest.mark.asyncio
    async def test_execute_aggressive_healing(self, loop):
        directives = {"enable_aggressive_healing": True}
        # set_route_preference is called first in _execute, so it must be awaitable
        loop.mesh.set_route_preference = AsyncMock(return_value=True)
        loop.mesh.trigger_aggressive_healing = AsyncMock(return_value=2)
        
        actions = await loop._execute(directives)
        
        loop.mesh.trigger_aggressive_healing.assert_called_once()
        assert "aggressive_healing=2_nodes" in actions

    @pytest.mark.asyncio
    async def test_knowledge(self, loop):
        metrics = ConsciousnessMetrics(
            phi_ratio=1.618, state=ConsciousnessState.HARMONIC,
            frequency_alignment=1.0, entropy=0.0, harmony_index=1.0, mesh_health=1.0, timestamp=0
        )
        directives = {"message": "All good"}
        actions = ["action1"]
        
        await loop._knowledge(metrics, directives, actions)
        
        # Check prometheus export
        assert loop.prometheus.set_gauge.call_count > 0
        
        # Check history update
        assert len(loop.state_history) == 1
        assert loop.state_history[0].metrics == metrics

    @pytest.mark.asyncio
    async def test_execute_cycle(self, loop):
        # Mock metrics object that has to_prometheus_format
        mock_metrics = MagicMock(spec=ConsciousnessMetrics)
        mock_metrics.state = ConsciousnessState.HARMONIC
        mock_metrics.phi_ratio = 1.618
        mock_metrics.to_prometheus_format.return_value = {}
        
        # Mock all internal steps to verify flow without side effects
        loop._monitor = AsyncMock(return_value={"raw": 1})
        loop._analyze = AsyncMock(return_value=mock_metrics)
        loop._plan = MagicMock(return_value={"monitoring_interval_sec": 30})
        loop._execute = AsyncMock(return_value=["action"])
        # We need _knowledge to run to verify end of cycle stuff
        # But _knowledge calls to_prometheus_format on the result of _analyze (mock_metrics)
        
        # Mock _knowledge if we want to skip its logic
        loop._knowledge = AsyncMock()
        
        # Also need to mock get_system_thought if cycle_count logic triggers
        loop.consciousness.get_system_thought.return_value = "Thought"

        await loop._execute_cycle()
        
        loop._monitor.assert_called_once()
        loop._analyze.assert_called_once_with={"raw": 1}
        loop._plan.assert_called_once_with(mock_metrics)
        loop._execute.assert_called_once_with({"monitoring_interval_sec": 30})
        loop._knowledge.assert_called_once()
        
        # interval should update
        assert loop.loop_interval == 30
