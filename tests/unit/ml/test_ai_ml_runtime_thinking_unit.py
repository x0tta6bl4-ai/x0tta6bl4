import asyncio
import json
from pathlib import Path

import pytest

from src.ai.mesh_ai_router import (
    CloudNode,
    FederatedLearningCoordinator,
    LocalNode,
    MeshAIRouter,
)
from src.federated_learning.production_integration import (
    FLProductionConfig,
    FLProductionManager,
)
from src.ml.integrated_anomaly_analyzer import IntegratedAnomalyAnalyzer
from src.ml.lora.advanced import LoRAIncrementalTrainer, LoRAPerformanceMonitor
from src.ml.mlops import MLOpsManager
from src.ml.production_anomaly_detector import ProductionAnomalyDetector
from src.ml.rag import Document, RAGAnalyzer
from src.optimization.rag_hnsw_optimizer import HNSWPerformanceOptimizer


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert raw_value not in text


@pytest.mark.asyncio
async def test_mesh_ai_router_and_fl_thinking_status_redacts_query_nodes_and_data():
    router = MeshAIRouter()
    router.add_node(
        LocalNode(
            name="local-secret-node",
            latency_ms=10,
            model="local-secret-model",
        )
    )
    router.add_node(
        CloudNode(
            name="cloud-secret-node",
            latency_ms=25,
            provider="cloud-secret-provider",
            api_key="cloud-secret-key",
            model="cloud-secret-model",
        )
    )

    response = await router.route_query("explain private customer query secret")
    assert "private customer query secret" in response

    router_status = router.get_thinking_status()
    assert router_status["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(
        router_status,
        "local-secret-node",
        "local-secret-model",
        "cloud-secret-node",
        "cloud-secret-provider",
        "cloud-secret-key",
        "cloud-secret-model",
        "private customer query secret",
    )

    coordinator = FederatedLearningCoordinator(router)
    await coordinator.run_fl_round(
        {"local-secret-node": ["private training sample secret"]}
    )
    fl_status = coordinator.get_thinking_status()
    assert fl_status["thinking"]["profile"]["role"] == "fl"
    _assert_redacted(
        fl_status,
        "local-secret-node",
        "private training sample secret",
    )


def test_production_anomaly_detector_thinking_status_redacts_metric_labels():
    detector = ProductionAnomalyDetector(sensitivity=1.0, min_history=10)

    for value in range(1, 12):
        detector.record_metric("component-secret", "metric-secret", float(value))
    detector.record_metric("component-secret", "metric-secret", 100.0)
    detector.analyze_component_health("component-secret")

    status = detector.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(status, "component-secret", "metric-secret")


@pytest.mark.asyncio
async def test_mlops_thinking_status_redacts_model_metadata_and_predictions():
    manager = MLOpsManager()
    await manager.register_trained_model(
        name="secret-model",
        version="secret-version",
        model_type="anomaly",
        model_obj="secret-model-object",
        metadata={"description": "secret model description", "framework": "secret-fw"},
    )
    await manager.monitor.update_metrics(
        "secret-model",
        "secret-version",
        [{"score": 0.2, "payload": "secret prediction payload"}],
    )
    await manager.check_model_health("secret-model")

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(
        status,
        "secret-model",
        "secret-version",
        "secret-model-object",
        "secret model description",
        "secret-fw",
        "secret prediction payload",
    )


@pytest.mark.asyncio
async def test_rag_hnsw_optimizer_thinking_status_redacts_queries_and_docs():
    optimizer = HNSWPerformanceOptimizer(max_cache_size=10)

    async def retrieval(query, k=5):
        return [("secret-doc-id", 0.9)]

    results, info = await optimizer.retrieve_with_optimization(
        "secret retrieval query",
        retrieval,
        k=1,
        enable_rewrite=False,
    )

    assert results == [("secret-doc-id", 0.9)]
    assert info["cache_hit"] is False
    status = optimizer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(status, "secret retrieval query", "secret-doc-id")


def test_ai_federated_knowledge_aggregator_redacts_incident_details():
    fl_mod = pytest.importorskip("src.ai.federated_learning")
    aggregator = fl_mod.KnowledgeAggregator()

    aggregator.aggregate_incidents(
        [
            {
                "recovery_action": "secret reboot procedure",
                "success": True,
                "confidence": 0.9,
                "node_id": "secret-node",
            }
        ]
    )

    status = aggregator.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "fl"
    _assert_redacted(status, "secret reboot procedure", "secret-node")


def test_fl_production_manager_thinking_status_redacts_config_and_node_info():
    manager = FLProductionManager(
        FLProductionConfig(
            coordinator_id="secret-coordinator",
            enable_fl=False,
            model_storage_path=Path("/secret/model/path"),
        )
    )
    manager.get_health_status()
    manager.register_participant(
        "secret-node",
        {"ip": "10.0.0.9", "capability": "secret-capability"},
    )

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "fl"
    _assert_redacted(
        status,
        "secret-coordinator",
        "/secret/model/path",
        "secret-node",
        "10.0.0.9",
        "secret-capability",
    )


def test_integrated_anomaly_analyzer_thinking_status_redacts_node_features():
    class _Detector:
        def predict_enhanced(self, **_kwargs):
            return {
                "is_anomaly": False,
                "anomaly_score": 0.2,
                "anomaly_confidence": 0.8,
            }

    analyzer = IntegratedAnomalyAnalyzer(_Detector(), object())
    result = analyzer.process_node_anomaly(
        node_id="secret-node",
        node_features={"secret-feature": 42.0},
        neighbors=[("secret-neighbor", {"secret-neighbor-feature": 1.0})],
        service_id="secret-service",
    )

    assert result.is_anomaly is False
    status = analyzer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    _assert_redacted(
        status,
        "secret-node",
        "secret-feature",
        "secret-neighbor",
        "secret-neighbor-feature",
        "secret-service",
    )


def test_lora_runtime_thinking_status_redacts_checkpoint_and_samples(tmp_path):
    trainer = LoRAIncrementalTrainer(base_model=object(), checkpoint_dir=str(tmp_path))
    assert trainer.save_checkpoint(
        "secret-checkpoint",
        {"secret-state": "secret-value"},
        {"secret-loss": 0.5, "epochs": 1},
    )

    trainer_status = trainer.get_thinking_status()
    assert trainer_status["thinking"]["profile"]["role"] == "development"
    _assert_redacted(
        trainer_status,
        "secret-checkpoint",
        "secret-state",
        "secret-value",
        "secret-loss",
    )

    monitor = LoRAPerformanceMonitor()
    monitor.record_inference(10.0, 256.0, 99.0)
    monitor.record_adapter_overhead(2.5)
    monitor.get_summary()
    monitor_status = monitor.get_thinking_status()
    assert monitor_status["thinking"]["profile"]["role"] == "monitoring"


@pytest.mark.asyncio
async def test_rag_analyzer_thinking_status_redacts_query_content_and_metadata():
    rag = RAGAnalyzer(use_langchain=False, use_hnsw=False)
    await rag.index_knowledge(
        [
            Document(
                id="secret-doc",
                content="secret document content",
                metadata={"tenant": "secret-tenant"},
            )
        ]
    )
    index_status = rag.get_thinking_status()
    _assert_redacted(
        index_status,
        "secret-doc",
        "secret document content",
        "secret-tenant",
    )

    result = await rag.retrieve_context("secret retrieval query", k=1, threshold=-1.0)
    assert len(result.documents) == 1
    retrieve_status = rag.get_thinking_status()
    assert retrieve_status["thinking"]["profile"]["role"] == "documentation"
    _assert_redacted(
        retrieve_status,
        "secret-doc",
        "secret document content",
        "secret-tenant",
        "secret retrieval query",
    )
