"""
Tests for PARL integrations with Federated Learning and MAPE-K.
"""

import sys
from unittest.mock import MagicMock

# Mock optional dependencies before imports
_mocked_modules = {
    'hvac': MagicMock(),
    'hvac.exceptions': MagicMock(),
    'hvac.api': MagicMock(),
    'hvac.api.auth_methods': MagicMock(),
    'hvac.api.auth_methods.Kubernetes': MagicMock(),
    'torch': MagicMock(),
    'torch.nn': MagicMock(),
}

for mod_name, mock_obj in _mocked_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

import pytest
import asyncio


class TestPARLFLIntegration:
    """Test PARL Federated Learning integration."""

    def test_import_parl_fl(self):
        """Test PARL FL integration imports."""
        from src.federated_learning.parl_integration import (
            PARLFederatedOrchestrator,
            PARLFLConfig
        )
        assert PARLFederatedOrchestrator is not None
        assert PARLFLConfig is not None

    def test_parl_fl_config_defaults(self):
        """Test PARL FL config default values."""
        from src.federated_learning.parl_integration import PARLFLConfig

        config = PARLFLConfig()
        assert config.max_workers == 100
        assert config.max_parallel_steps == 1500
        assert config.min_nodes_per_round == 3
        assert config.max_nodes_per_round == 100
        assert config.aggregation_method == "fedavg"

    def test_parl_fl_config_custom(self):
        """Test PARL FL config with custom values."""
        from src.federated_learning.parl_integration import PARLFLConfig

        config = PARLFLConfig(
            max_workers=50,
            max_parallel_steps=500,
            aggregation_method="krum"
        )
        assert config.max_workers == 50
        assert config.max_parallel_steps == 500
        assert config.aggregation_method == "krum"

    @pytest.mark.asyncio
    async def test_parl_fl_orchestrator_init(self):
        """Test PARL FL orchestrator initialization."""
        from src.federated_learning.parl_integration import PARLFederatedOrchestrator

        orchestrator = PARLFederatedOrchestrator()
        assert orchestrator.current_round == 0
        assert orchestrator.global_model == {}
        assert not orchestrator._initialized

    @pytest.mark.asyncio
    async def test_parl_fl_training_round(self):
        """Test executing a training round."""
        from src.federated_learning.parl_integration import PARLFederatedOrchestrator

        orchestrator = PARLFederatedOrchestrator()
        await orchestrator.initialize()

        try:
            nodes = ["node_001", "node_002", "node_003"]
            result = await orchestrator.execute_training_round(nodes)

            assert "round_id" in result
            assert "round_number" in result
            assert result["round_number"] == 1
            assert result["nodes_selected"] == 3
            assert "round_time_ms" in result
            assert "speedup_vs_sequential" in result
        finally:
            await orchestrator.terminate()

    @pytest.mark.asyncio
    async def test_parl_fl_metrics(self):
        """Test PARL FL metrics collection."""
        from src.federated_learning.parl_integration import PARLFederatedOrchestrator

        orchestrator = PARLFederatedOrchestrator()
        await orchestrator.initialize()

        try:
            nodes = ["node_001", "node_002"]
            await orchestrator.execute_training_round(nodes)

            metrics = orchestrator.get_metrics()
            assert metrics["total_rounds"] == 1
            assert metrics["current_round"] == 1
            assert "avg_round_time_ms" in metrics
            assert "parl_enabled" in metrics
        finally:
            await orchestrator.terminate()


class TestPARLMAPEKIntegration:
    """Test PARL MAPE-K integration."""

    def test_import_parl_mapek(self):
        """Test PARL MAPE-K integration imports."""
        from src.core.parl_mapek_integration import (
            PARLMAPEKExecutor,
            MAPEKContext,
            MAPEKPhase
        )
        assert PARLMAPEKExecutor is not None
        assert MAPEKContext is not None
        assert MAPEKPhase is not None

    def test_mapek_phases(self):
        """Test MAPE-K phase enum."""
        from src.core.parl_mapek_integration import MAPEKPhase

        assert MAPEKPhase.MONITOR.value == "monitor"
        assert MAPEKPhase.ANALYZE.value == "analyze"
        assert MAPEKPhase.PLAN.value == "plan"
        assert MAPEKPhase.EXECUTE.value == "execute"
        assert MAPEKPhase.KNOWLEDGE.value == "knowledge"

    def test_mapek_context(self):
        """Test MAPE-K context creation."""
        from src.core.parl_mapek_integration import MAPEKContext, MAPEKPhase

        context = MAPEKContext(
            cycle_id="test_cycle",
            mesh_nodes=["node_1", "node_2", "node_3"]
        )

        assert context.cycle_id == "test_cycle"
        assert len(context.mesh_nodes) == 3
        assert context.current_phase == MAPEKPhase.MONITOR

    @pytest.mark.asyncio
    async def test_parl_mapek_executor_init(self):
        """Test PARL MAPE-K executor initialization."""
        from src.core.parl_mapek_integration import PARLMAPEKExecutor

        executor = PARLMAPEKExecutor()
        assert not executor._initialized
        assert executor.metrics["total_cycles"] == 0

    @pytest.mark.asyncio
    async def test_parl_mapek_cycle(self):
        """Test executing a MAPE-K cycle."""
        from src.core.parl_mapek_integration import (
            PARLMAPEKExecutor,
            MAPEKContext
        )

        executor = PARLMAPEKExecutor()
        await executor.initialize()

        try:
            context = MAPEKContext(
                cycle_id="test_cycle_001",
                mesh_nodes=["node_001", "node_002", "node_003"]
            )

            result = await executor.execute_cycle(context)

            assert result.get("success") is True
            assert "monitor" in result
            assert "analyze" in result
            assert "plan" in result
            assert "execute" in result
            assert "metrics" in result
            assert result["metrics"]["cycle_id"] == "test_cycle_001"
        finally:
            await executor.terminate()

    @pytest.mark.asyncio
    async def test_parl_mapek_metrics(self):
        """Test PARL MAPE-K metrics collection."""
        from src.core.parl_mapek_integration import (
            PARLMAPEKExecutor,
            MAPEKContext
        )

        executor = PARLMAPEKExecutor()
        await executor.initialize()

        try:
            context = MAPEKContext(
                cycle_id="metrics_test",
                mesh_nodes=["node_001"]
            )

            await executor.execute_cycle(context)

            metrics = executor.get_metrics()
            assert metrics["total_cycles"] == 1
            assert "avg_cycle_time_ms" in metrics
            assert "parl_enabled" in metrics
        finally:
            await executor.terminate()

    @pytest.mark.asyncio
    async def test_parl_mapek_knowledge_update(self):
        """Test knowledge base updates."""
        from src.core.parl_mapek_integration import (
            PARLMAPEKExecutor,
            MAPEKContext
        )

        executor = PARLMAPEKExecutor()
        await executor.initialize()

        try:
            # Initial knowledge base should be empty of anomalies
            assert len(executor.knowledge_base["historical_anomalies"]) == 0

            context = MAPEKContext(
                cycle_id="knowledge_test",
                mesh_nodes=["node_001", "node_002"]
            )

            await executor.execute_cycle(context)

            # Knowledge base may have been updated
            assert "historical_anomalies" in executor.knowledge_base
        finally:
            await executor.terminate()


class TestConvenienceFunctions:
    """Test convenience functions for PARL integrations."""

    @pytest.mark.asyncio
    async def test_execute_parallel_fl_round(self):
        """Test convenience function for FL round."""
        from src.federated_learning.parl_integration import execute_parallel_fl_round

        result = await execute_parallel_fl_round(
            node_ids=["node_001", "node_002"],
            training_config={"epochs": 1}
        )

        assert "round_id" in result
        assert result["nodes_selected"] == 2

    @pytest.mark.asyncio
    async def test_execute_mapek_cycle_with_parl(self):
        """Test convenience function for MAPE-K cycle."""
        from src.core.parl_mapek_integration import execute_mapek_cycle_with_parl

        result = await execute_mapek_cycle_with_parl(
            mesh_nodes=["node_001", "node_002"],
            cycle_id="convenience_test"
        )

        assert result.get("success") is True
        assert "metrics" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
