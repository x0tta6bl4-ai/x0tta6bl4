"""
Phase 6: Simplified ML Integration Tests

Focused tests for complete ML module integration, production scenarios.
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime
import time

from src.ml.integration import MLEnhancedMAPEK
from src.ml.rag import RAGAnalyzer
from src.ml.lora import LoRAAdapter, LoRAConfig
from src.ml.anomaly import AnomalyDetectionSystem
from src.ml.decision import DecisionEngine, Policy, PolicyPriority
from src.ml.mlops import MLOpsManager


# ========== BASIC ML INTEGRATION TESTS ==========

class TestBasicMLIntegration:
    """Basic ML module integration tests"""
    
    @pytest.mark.asyncio
    async def test_ml_enhanced_mapek_initialization(self):
        """Test MLEnhancedMAPEK initialization"""
        system = MLEnhancedMAPEK()
        assert system is not None
    
    @pytest.mark.asyncio
    async def test_rag_analyzer_creation(self):
        """Test RAG Analyzer creation"""
        rag = RAGAnalyzer()
        assert rag is not None
    
    @pytest.mark.asyncio
    async def test_anomaly_detection_creation(self):
        """Test Anomaly Detection System creation"""
        system = AnomalyDetectionSystem()
        assert system is not None
    
    @pytest.mark.asyncio
    async def test_decision_engine_creation(self):
        """Test Decision Engine creation"""
        engine = DecisionEngine()
        assert engine is not None
    
    @pytest.mark.asyncio
    async def test_mlops_manager_creation(self):
        """Test MLOps Manager creation"""
        manager = MLOpsManager()
        assert manager is not None


# ========== LORA CONFIGURATION TESTS ==========

class TestLoRAConfiguration:
    """LoRA configuration tests"""
    
    def test_lora_config_defaults(self):
        """Test LoRA config with defaults"""
        config = LoRAConfig()
        assert config.r == 8
        assert config.alpha == 32
    
    def test_lora_config_custom(self):
        """Test LoRA config with custom values"""
        config = LoRAConfig(r=4, alpha=16)
        assert config.r == 4
        assert config.alpha == 16
    
    def test_lora_config_target_modules(self):
        """Test LoRA config target modules"""
        config = LoRAConfig(target_modules=["attention"])
        assert config.target_modules == ["attention"]


# ========== RAG SYSTEM TESTS ==========

class TestRAGSystem:
    """RAG system tests"""
    
    @pytest.mark.asyncio
    async def test_rag_retrieval(self):
        """Test RAG retrieval"""
        rag = RAGAnalyzer()
        
        # Try retrieval (may return empty)
        context = await rag.retrieve_context("test query", k=5)
        assert isinstance(context, list)
    
    @pytest.mark.asyncio
    async def test_rag_empty_retrieval(self):
        """Test RAG with no indexed documents"""
        rag = RAGAnalyzer()
        context = await rag.retrieve_context("test", k=10)
        assert isinstance(context, list)


# ========== ANOMALY DETECTION TESTS ==========

class TestAnomalyDetection:
    """Anomaly detection tests"""
    
    @pytest.mark.asyncio
    async def test_anomaly_component_registration(self):
        """Test component registration"""
        system = AnomalyDetectionSystem()
        system.register_component("test_comp", input_dim=16)
        
        # Verify component was registered
        assert "test_comp" in system.components
    
    @pytest.mark.asyncio
    async def test_anomaly_training_basic(self):
        """Test basic anomaly training"""
        system = AnomalyDetectionSystem()
        system.register_component("monitor", input_dim=4)
        
        # Generate training samples
        samples = [np.random.normal(0.5, 0.1, 4) for _ in range(50)]
        
        # Train without error
        await system.train_on_component("monitor", samples)
        assert system.detectors.get("monitor") is not None
    
    @pytest.mark.asyncio
    async def test_anomaly_detection_check(self):
        """Test anomaly detection check"""
        system = AnomalyDetectionSystem()
        system.register_component("test", input_dim=8)
        
        samples = [np.random.randn(8) for _ in range(100)]
        await system.train_on_component("test", samples)
        
        # Check for anomaly
        test_data = np.random.randn(8)
        anomaly, score = await system.check_component("test", test_data)
        
        assert isinstance(score, (float, np.floating))


# ========== DECISION ENGINE TESTS ==========

class TestDecisionEngine:
    """Decision engine tests"""
    
    @pytest.mark.asyncio
    async def test_policy_registration(self):
        """Test policy registration"""
        engine = DecisionEngine()
        policy = Policy("test", "Test Policy", "Test", PolicyPriority.MEDIUM)
        
        engine.ranker.register_policy(policy)
        assert policy in engine.ranker.policies
    
    @pytest.mark.asyncio
    async def test_decision_making(self):
        """Test decision making"""
        engine = DecisionEngine()
        policy = Policy("scale", "Scale", "Scale up", PolicyPriority.HIGH)
        engine.ranker.register_policy(policy)
        
        decision = await engine.decide_on_action(["scale"], {})
        assert "selected_policy" in decision
    
    @pytest.mark.asyncio
    async def test_decision_evaluation(self):
        """Test decision evaluation"""
        engine = DecisionEngine()
        policy = Policy("test", "Test", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)
        
        # Evaluate decision
        await engine.evaluate_decision("test", success=True, reward=0.8, duration_ms=50.0)
        
        stats = engine.get_decision_stats()
        assert stats is not None


# ========== MLOPS TESTS ==========

class TestMLOpsManager:
    """MLOps manager tests"""
    
    @pytest.mark.asyncio
    async def test_model_registration(self):
        """Test model registration"""
        manager = MLOpsManager()
        
        await manager.register_trained_model(
            "test_model",
            "1.0.0",
            "test",
            metadata={"framework": "test"}
        )
        
        # Verify model was registered
        models = manager.registry.get_all_models()
        assert len(models) > 0
    
    @pytest.mark.asyncio
    async def test_model_health_check(self):
        """Test model health check"""
        manager = MLOpsManager()
        
        await manager.register_trained_model(
            "health_test",
            "1.0.0",
            "test"
        )
        
        health = await manager.check_model_health("health_test")
        assert health is not None


# ========== CONCURRENT OPERATIONS TESTS ==========

class TestConcurrentOperations:
    """Concurrent operation tests"""
    
    @pytest.mark.asyncio
    async def test_concurrent_decisions(self):
        """Test concurrent decision making"""
        engine = DecisionEngine()
        policy = Policy("test", "Test", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)
        
        async def make_decision(i):
            return await engine.decide_on_action(["test"], {"index": i})
        
        results = await asyncio.gather(*[make_decision(i) for i in range(10)])
        assert len(results) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_anomaly_checks(self):
        """Test concurrent anomaly checks"""
        system = AnomalyDetectionSystem()
        system.register_component("concurrent", input_dim=8)
        
        samples = [np.random.randn(8) for _ in range(100)]
        await system.train_on_component("concurrent", samples)
        
        async def check_anomaly(i):
            data = np.random.randn(8)
            return await system.check_component("concurrent", data)
        
        results = await asyncio.gather(*[check_anomaly(i) for i in range(10)])
        assert len(results) == 10


# ========== PERFORMANCE TESTS ==========

class TestPerformance:
    """Performance tests"""
    
    @pytest.mark.asyncio
    async def test_decision_latency(self):
        """Test decision making latency"""
        engine = DecisionEngine()
        policy = Policy("latency_test", "Test", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)
        
        times = []
        for i in range(20):
            start = time.time()
            await engine.decide_on_action(["latency_test"], {})
            times.append((time.time() - start) * 1000)
        
        avg_time = np.mean(times)
        max_time = np.max(times)
        
        assert avg_time < 1000  # Should be fast
        assert max_time < 2000
    
    @pytest.mark.asyncio
    async def test_anomaly_detection_latency(self):
        """Test anomaly detection latency"""
        system = AnomalyDetectionSystem()
        system.register_component("perf", input_dim=16)
        
        samples = [np.random.randn(16) for _ in range(100)]
        await system.train_on_component("perf", samples)
        
        times = []
        for i in range(20):
            start = time.time()
            data = np.random.randn(16)
            await system.check_component("perf", data)
            times.append((time.time() - start) * 1000)
        
        avg_time = np.mean(times)
        assert avg_time < 100


# ========== RELIABILITY TESTS ==========

class TestReliability:
    """Reliability tests"""
    
    @pytest.mark.asyncio
    async def test_engine_multiple_iterations(self):
        """Test engine stability over multiple iterations"""
        engine = DecisionEngine()
        policy = Policy("stable", "Stable", "Test", PolicyPriority.MEDIUM)
        engine.ranker.register_policy(policy)
        
        for i in range(50):
            result = await engine.decide_on_action(["stable"], {})
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_anomaly_system_stability(self):
        """Test anomaly system stability"""
        system = AnomalyDetectionSystem()
        system.register_component("stable", input_dim=8)
        
        samples = [np.random.randn(8) for _ in range(100)]
        await system.train_on_component("stable", samples)
        
        for i in range(50):
            data = np.random.randn(8)
            anomaly, score = await system.check_component("stable", data)
            assert isinstance(score, (float, np.floating))


# ========== FIXTURES ==========

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
