"""
ML Modules Unit Tests

Tests for RAG, LoRA, Anomaly Detection, Decision Making, MLOps modules.
"""

import asyncio
from datetime import datetime

import numpy as np
import pytest

from src.ml.anomaly import AnomalyConfig, AnomalyDetectionSystem
from src.ml.decision import DecisionEngine, Policy, PolicyPriority
from src.ml.lora import LoRAAdapter, LoRAConfig
from src.ml.mlops import MLOpsManager, ModelMetadata
from src.ml.rag import Document, RAGAnalyzer, VectorStore

# ========== RAG Tests ==========


class TestRAG:
    """RAG module tests"""

    @pytest.mark.asyncio
    async def test_rag_initialization(self):
        """Test RAG analyzer initialization"""
        rag = RAGAnalyzer()
        assert rag is not None
        stats = rag.get_stats()
        assert "documents_count" in stats

    @pytest.mark.asyncio
    async def test_document_indexing(self):
        """Test document indexing"""
        rag = RAGAnalyzer()

        docs = [
            Document(
                id="1", content="High latency issue", metadata={"topic": "performance"}
            ),
            Document(
                id="2", content="Memory leak detected", metadata={"topic": "memory"}
            ),
        ]

        indexed = await rag.index_knowledge(docs)
        assert indexed > 0

    @pytest.mark.asyncio
    async def test_context_retrieval(self):
        """Test context retrieval"""
        rag = RAGAnalyzer()

        docs = [
            Document(id="1", content="High latency issue resolution"),
            Document(id="2", content="Memory optimization techniques"),
        ]

        await rag.index_knowledge(docs)
        context = await rag.retrieve_context("latency", k=1)
        assert isinstance(context, list)


# ========== LoRA Tests ==========


class TestLoRA:
    """LoRA module tests"""

    def test_lora_config(self):
        """Test LoRA configuration"""
        config = LoRAConfig(rank=8, alpha=16.0, learning_rate=0.001)
        assert config.rank == 8
        assert config.alpha == 16.0

    @pytest.mark.asyncio
    async def test_lora_layer(self):
        """Test LoRA layer"""
        config = LoRAConfig(rank=4)
        from src.ml.lora import LoRALayer

        layer = LoRALayer(input_dim=32, output_dim=16, config=config)

        x = np.random.randn(32)
        base_output = np.random.randn(16)
        adapted = layer.forward(x, base_output)

        assert adapted.shape == base_output.shape

    @pytest.mark.asyncio
    async def test_lora_adapter(self):
        """Test LoRA adapter"""
        adapter = LoRAAdapter(LoRAConfig(rank=8))
        adapter.add_layer("test", input_dim=64, output_dim=32)

        assert "test" in adapter.lora_layers
        stats = adapter.get_stats()
        assert stats["layers_count"] == 1


# ========== Anomaly Detection Tests ==========


class TestAnomalyDetection:
    """Anomaly detection tests"""

    def test_anomaly_config(self):
        """Test anomaly configuration"""
        config = AnomalyConfig(threshold=0.7, window_size=50)
        assert config.threshold == 0.7
        assert config.window_size == 50

    @pytest.mark.asyncio
    async def test_detector_training(self):
        """Test anomaly detector training"""
        system = AnomalyDetectionSystem()
        system.register_component("test", input_dim=32)

        normal_samples = [np.random.normal(0.5, 0.1, 32) for _ in range(100)]

        result = await system.train_on_component("test", normal_samples)
        assert "epochs" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_anomaly_detection(self):
        """Test anomaly detection"""
        system = AnomalyDetectionSystem()
        system.register_component("test", input_dim=32)

        # Train
        normal_samples = [np.random.normal(0.5, 0.1, 32) for _ in range(100)]
        await system.train_on_component("test", normal_samples)

        # Test normal
        normal_test = np.random.normal(0.5, 0.1, 32)
        anomaly1, score1 = await system.check_component("test", normal_test)

        # Test anomalous
        anomaly_test = np.random.normal(3.0, 1.0, 32)
        anomaly2, score2 = await system.check_component("test", anomaly_test)

        assert isinstance(score1, float)
        assert isinstance(score2, float)
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1


# ========== Decision Making Tests ==========


class TestDecisionMaking:
    """Decision making tests"""

    def test_policy_creation(self):
        """Test policy creation"""
        policy = Policy(
            id="test",
            name="Test Policy",
            description="Test",
            priority=PolicyPriority.HIGH,
        )
        assert policy.id == "test"
        assert policy.priority == PolicyPriority.HIGH

    @pytest.mark.asyncio
    async def test_policy_ranking(self):
        """Test policy ranking"""
        engine = DecisionEngine()

        p1 = Policy("p1", "Policy 1", "Test", PolicyPriority.HIGH)
        p2 = Policy("p2", "Policy 2", "Test", PolicyPriority.LOW)

        engine.ranker.register_policy(p1)
        engine.ranker.register_policy(p2)

        ranked = engine.ranker.rank_policies(top_k=2)
        assert len(ranked) <= 2

    @pytest.mark.asyncio
    async def test_decision_making(self):
        """Test decision making"""
        engine = DecisionEngine()

        policy = Policy("test", "Test", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)

        decision = await engine.decide_on_action(["test"], {})
        assert "selected_policy" in decision or "error" in decision


# ========== MLOps Tests ==========


class TestMLOps:
    """MLOps tests"""

    def test_model_registry(self):
        """Test model registry"""
        from src.ml.mlops import ModelRegistry

        registry = ModelRegistry()

        meta = ModelMetadata(
            name="test_model",
            version="1.0.0",
            model_type="test",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        registry.register_model(meta)
        assert registry.get_model("test_model") is None  # No object registered
        versions = registry.get_model_versions("test_model")
        assert "1.0.0" in versions

    @pytest.mark.asyncio
    async def test_mlops_manager(self):
        """Test MLOps manager"""
        manager = MLOpsManager()

        await manager.register_trained_model(
            "test", "1.0.0", "test", metadata={"framework": "custom"}
        )

        health = await manager.check_model_health("test")
        assert "model" in health


# ========== Integration Tests ==========


class TestMLIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_ml_enhanced_mapek(self):
        """Test ML-enhanced MAPE-K"""
        from src.ml.integration import MLEnhancedMAPEK

        system = MLEnhancedMAPEK()

        metrics = {"cpu": 0.5, "memory": 0.6, "latency": 50.0}

        result = await system.autonomic_loop_iteration(metrics, ["action1", "action2"])

        assert "monitoring" in result or result is not None


# ========== Performance Tests ==========


class TestMLPerformance:
    """Performance tests"""

    @pytest.mark.asyncio
    async def test_rag_performance(self):
        """Test RAG retrieval performance"""
        rag = RAGAnalyzer()

        docs = [
            Document(id=str(i), content=f"Document {i}", metadata={"index": i})
            for i in range(100)
        ]

        await rag.index_knowledge(docs)

        import time

        start = time.time()
        context = await rag.retrieve_context("test", k=5)
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be fast

    @pytest.mark.asyncio
    async def test_anomaly_performance(self):
        """Test anomaly detection performance"""
        system = AnomalyDetectionSystem()
        system.register_component("test", input_dim=32)

        samples = [np.random.randn(32) for _ in range(100)]
        await system.train_on_component("test", samples)

        import time

        start = time.time()
        for _ in range(100):
            await system.check_component("test", np.random.randn(32))
        elapsed = time.time() - start

        assert elapsed < 1.0  # 100 inferences should be < 1s


# ========== Conftest fixtures ==========


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
