"""
Phase 6: Comprehensive ML Integration Tests

Tests for complete ML module integration, production scenarios, and edge cases.
"""

import asyncio
import time
from datetime import datetime

import numpy as np
import pytest

from src.ml.anomaly import AnomalyDetectionSystem
from src.ml.decision import DecisionEngine, Policy, PolicyPriority
from src.ml.integration import MLEnhancedMAPEK
from src.ml.lora import LoRAAdapter, LoRAConfig
from src.ml.mlops import MLOpsManager
from src.ml.rag import Document, RAGAnalyzer

# ========== INTEGRATION TEST SUITE ==========


class TestMLIntegrationComplete:
    """Complete ML module integration tests"""

    @pytest.mark.asyncio
    async def test_full_autonomic_loop_iteration(self):
        """Test complete autonomic loop with all ML modules"""
        system = MLEnhancedMAPEK()

        metrics = {"cpu": 0.5, "memory": 0.6, "latency_ms": 45, "request_count": 1000}

        result = await system.autonomic_loop_iteration(
            metrics, ["scale_up", "optimize_config", "restart_component"]
        )

        assert "monitoring" in result
        assert "analysis" in result
        assert "planning" in result
        assert "execution" in result
        assert "knowledge_update" in result
        assert "overall_success" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_rag_anomaly_integration(self):
        """Test RAG + Anomaly Detection integration"""
        rag = RAGAnalyzer()
        anomaly_system = AnomalyDetectionSystem()

        # Index knowledge
        docs = [
            Document(id="1", content="High CPU usage recovery procedure", metadata={}),
            Document(id="2", content="Memory leak detection and fix", metadata={}),
            Document(id="3", content="Latency optimization techniques", metadata={}),
        ]
        await rag.index_knowledge(docs)

        # Setup anomaly detection
        anomaly_system.register_component("monitor", input_dim=4)
        normal_samples = [np.random.normal(0.5, 0.1, 4) for _ in range(100)]
        await anomaly_system.train_on_component("monitor", normal_samples)

        # Test anomalous metrics
        anomalous = np.array([3.0, 3.0, 3.0, 3.0])
        anomaly, score = await anomaly_system.check_component("monitor", anomalous)

        assert anomaly is not None

        # Retrieve context for anomaly
        context = await rag.retrieve_context("high CPU recovery", k=2)
        assert isinstance(context, list)

    @pytest.mark.asyncio
    async def test_decision_lora_integration(self):
        """Test Decision Making + LoRA integration"""
        engine = DecisionEngine()
        lora = LoRAAdapter(LoRAConfig(r=4))

        # Setup policies
        policies = [
            Policy(
                "scale",
                "Scale Up",
                "Add replicas",
                PolicyPriority.HIGH,
                success_rate=0.8,
            ),
            Policy(
                "optimize",
                "Optimize",
                "Tune config",
                PolicyPriority.MEDIUM,
                success_rate=0.7,
            ),
            Policy(
                "restart",
                "Restart",
                "Restart service",
                PolicyPriority.CRITICAL,
                success_rate=0.6,
            ),
        ]

        for p in policies:
            engine.ranker.register_policy(p)

        # Make decision
        decision = await engine.decide_on_action(
            ["scale", "optimize", "restart"], {"cpu": 0.85}
        )

        assert "selected_policy" in decision
        selected = decision["selected_policy"]

        # Setup LoRA adaptation
        lora.add_layer(selected, input_dim=64, output_dim=32)
        input_data = np.random.randn(64)
        base_output = np.random.randn(32)

        adapted = await lora.adapt_output(selected, input_data, base_output)
        assert adapted.shape == base_output.shape

    @pytest.mark.asyncio
    async def test_mlops_monitoring_integration(self):
        """Test MLOps + Performance Monitoring integration"""
        manager = MLOpsManager()

        # Register model
        await manager.register_trained_model(
            "test_model", "1.0.0", "test", metadata={"framework": "custom"}
        )

        # Simulate predictions
        predictions = [
            {"score": 0.92},
            {"score": 0.88},
            {"score": 0.85},
        ]

        alert = await manager.monitor.update_metrics("test_model", "1.0.0", predictions)

        health = await manager.check_model_health("test_model")
        assert "model" in health

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling across modules"""
        system = MLEnhancedMAPEK()

        # Test with empty metrics
        result = await system.autonomic_loop_iteration({}, [])
        assert result is not None

        # Test with invalid actions
        result = await system.autonomic_loop_iteration(
            {"cpu": 0.5}, ["nonexistent_action"]
        )
        assert result is not None


# ========== SCENARIO-BASED TESTS ==========


class TestProductionScenarios:
    """Production scenario tests"""

    @pytest.mark.asyncio
    async def test_scenario_high_cpu_spike(self):
        """Scenario: Sudden CPU spike detection and recovery"""
        system = MLEnhancedMAPEK()

        # Normal operation
        for i in range(5):
            metrics = {"cpu": 0.3 + np.random.random() * 0.1}
            result = await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize", "restart"]
            )
            assert result["overall_success"]

        # CPU spike
        spike_metrics = {"cpu": 0.95}
        result = await system.autonomic_loop_iteration(
            spike_metrics, ["scale_up", "optimize", "restart"]
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_scenario_cascading_failures(self):
        """Scenario: Multiple component failures"""
        system = MLEnhancedMAPEK()

        # Simulate cascading issues
        issues = [
            {"cpu": 0.9, "memory": 0.85, "latency": 500},
            {"cpu": 0.92, "memory": 0.87, "latency": 550},
            {"cpu": 0.88, "memory": 0.9, "latency": 480},
        ]

        for metrics in issues:
            result = await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize", "restart"]
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_scenario_learning_improvement(self):
        """Scenario: Decision quality improves over time"""
        engine = DecisionEngine()

        policy = Policy("test", "Test", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)

        # Initial decision
        decision1 = await engine.decide_on_action(["test"], {})

        # Record successful outcomes
        for i in range(10):
            await engine.evaluate_decision(
                "test",
                success=True,
                reward=0.8 + np.random.random() * 0.1,
                duration_ms=45.0,
            )

        # Get stats
        stats = engine.get_decision_stats()
        assert stats["total_decisions"] >= 1


# ========== CONCURRENT OPERATION TESTS ==========


class TestConcurrentOperations:
    """Tests for concurrent ML operations"""

    @pytest.mark.asyncio
    async def test_concurrent_ml_loops(self):
        """Test 10 concurrent autonomic loops"""
        system = MLEnhancedMAPEK()

        async def run_loop(i):
            metrics = {
                "cpu": 0.3 + np.random.random() * 0.3,
                "memory": 0.4 + np.random.random() * 0.2,
            }
            return await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize"]
            )

        results = await asyncio.gather(*[run_loop(i) for i in range(10)])
        assert len(results) == 10
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_anomaly_detection(self):
        """Test concurrent anomaly detection on multiple components"""
        system = AnomalyDetectionSystem()

        components = ["analyzer", "planner", "executor"]

        for comp in components:
            system.register_component(comp, input_dim=16)
            samples = [np.random.randn(16) for _ in range(100)]
            await system.train_on_component(comp, samples)

        async def check_anomaly(comp, i):
            data = np.random.randn(16)
            return await system.check_component(comp, data)

        tasks = [check_anomaly(comp, i) for comp in components for i in range(5)]

        results = await asyncio.gather(*tasks)
        assert len(results) == 15


# ========== PERFORMANCE VALIDATION TESTS ==========


class TestPerformanceValidation:
    """Performance and resource validation"""

    @pytest.mark.asyncio
    async def test_loop_latency_under_load(self):
        """Test autonomic loop latency under simulated load"""
        system = MLEnhancedMAPEK()

        latencies = []

        for i in range(20):
            metrics = {
                "cpu": 0.5 + np.random.random() * 0.2,
                "memory": 0.6 + np.random.random() * 0.15,
            }

            start = time.time()
            await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize", "restart"]
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            latencies.append(elapsed)

        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        p95_latency = np.percentile(latencies, 95)

        assert avg_latency < 200  # Average should be < 200ms
        assert max_latency < 500  # Max should be < 500ms
        assert p95_latency < 300  # P95 should be < 300ms

    @pytest.mark.asyncio
    async def test_memory_stability(self):
        """Test memory usage stability over many iterations"""
        system = MLEnhancedMAPEK()

        # Run many iterations
        for i in range(50):
            metrics = {
                "cpu": 0.3 + np.random.random() * 0.4,
                "memory": 0.4 + np.random.random() * 0.3,
            }

            await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize", "restart"]
            )

        # Memory should not grow unbounded
        # This is a basic check - real memory profiling would be needed
        stats = system.get_ml_statistics()
        assert stats is not None

    @pytest.mark.asyncio
    async def test_throughput_benchmark(self):
        """Benchmark system throughput"""
        system = MLEnhancedMAPEK()

        start = time.time()
        iterations = 100

        for i in range(iterations):
            await system.autonomic_loop_iteration(
                {"cpu": 0.5, "memory": 0.6}, ["scale_up", "optimize"]
            )

        elapsed = time.time() - start
        throughput = iterations / elapsed

        assert throughput > 10  # At least 10 loops/second


# ========== EDGE CASE TESTS ==========


class TestEdgeCases:
    """Edge case and boundary condition tests"""

    @pytest.mark.asyncio
    async def test_extreme_metric_values(self):
        """Test with extreme metric values"""
        system = MLEnhancedMAPEK()

        extreme_metrics = [
            {"cpu": 0.0, "memory": 0.0},  # Minimum
            {"cpu": 1.0, "memory": 1.0},  # Maximum
            {"cpu": 0.5, "memory": 0.5, "latency": 10000},  # High latency
        ]

        for metrics in extreme_metrics:
            result = await system.autonomic_loop_iteration(
                metrics, ["scale_up", "optimize"]
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_empty_knowledge_base(self):
        """Test RAG with empty knowledge base"""
        rag = RAGAnalyzer()

        # No indexing
        context = await rag.retrieve_context("test", k=5)
        assert isinstance(context, list)

    @pytest.mark.asyncio
    async def test_single_policy_available(self):
        """Test decision making with only one policy"""
        engine = DecisionEngine()

        policy = Policy("only_one", "Only Policy", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)

        decision = await engine.decide_on_action(["only_one"], {})
        assert decision["selected_policy"] == "only_one"

    @pytest.mark.asyncio
    async def test_anomaly_detection_no_training(self):
        """Test anomaly detection without training"""
        system = AnomalyDetectionSystem()
        system.register_component("test", input_dim=16)

        # Try detection without training
        data = np.random.randn(16)
        anomaly, score = await system.check_component("test", data)

        # Should still return something
        assert isinstance(score, float)


# ========== RELIABILITY TESTS ==========


class TestReliability:
    """Reliability and stability tests"""

    @pytest.mark.asyncio
    async def test_recovery_from_anomaly_detection(self):
        """Test system recovery after anomaly detection"""
        system = MLEnhancedMAPEK()

        # Normal operation
        normal = {"cpu": 0.3}
        result1 = await system.autonomic_loop_iteration(normal, ["scale_up"])

        # Anomalous
        anomalous = {"cpu": 0.95}
        result2 = await system.autonomic_loop_iteration(anomalous, ["scale_up"])

        # Recovery to normal
        normal_again = {"cpu": 0.35}
        result3 = await system.autonomic_loop_iteration(normal_again, ["scale_up"])

        assert result3 is not None

    @pytest.mark.asyncio
    async def test_policy_recovery_after_failure(self):
        """Test policy still functions after failed execution"""
        engine = DecisionEngine()

        policy = Policy("test", "Test", "Test", PolicyPriority.MEDIUM, success_rate=0.5)
        engine.ranker.register_policy(policy)

        # Record failures
        for i in range(5):
            await engine.evaluate_decision("test", False, 0.0, 50.0)

        # Policy should still be available
        decision = await engine.decide_on_action(["test"], {})
        assert decision["selected_policy"] == "test"


# ========== Fixtures ==========


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
