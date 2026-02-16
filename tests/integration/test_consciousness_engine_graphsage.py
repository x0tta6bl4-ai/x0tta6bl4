import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


# --- Mock GraphSAGE Anomaly Detector for deterministic results ---
class MockGraphSAGEAnomalyDetectorInTest:
    def predict(self, node_id, node_features, neighbors):
        latency = node_features.get("latency", 0.0)
        if latency > 100.0:
            return MagicMock(
                is_anomaly=True,
                anomaly_score=0.9,
                confidence=0.95,
                node_id=node_id,
                features=node_features,
                inference_time_ms=1.0,
            )
        else:
            return MagicMock(
                is_anomaly=False,
                anomaly_score=0.518,
                confidence=0.99,
                node_id=node_id,
                features=node_features,
                inference_time_ms=1.0,
            )

    @property
    def is_trained(self):
        return True  # Assume trained for mock


import src.ml.graphsage_anomaly_detector  # Import the module first


@pytest.mark.asyncio
@patch(
    "src.core.consciousness.create_graphsage_detector_for_mapek"
)  # Patch the function in the module where it's looked up
async def test_consciousness_engine_graphsage_anomaly_detection(
    mock_create_graphsage_detector_for_mapek_func,
):
    # Configure the mock to return instances of our MockGraphSAGEAnomalyDetectorInTest
    mock_create_graphsage_detector_for_mapek_func.return_value = (
        MockGraphSAGEAnomalyDetectorInTest()
    )

    # --- Now import ConsciousnessEngine and other related modules (after patch) ---
    from src.core.consciousness import (PHI, ConsciousnessEngine,
                                        ConsciousnessMetrics,
                                        ConsciousnessState)

    """
    Тест: ConsciousnessEngine должен корректно определять состояние
    при аномалиях, предсказанных GraphSAGE.
    """

    # 1. Инициализация ConsciousnessEngine с моком GraphSAGE
    # ConsciousnessEngine теперь будет использовать наш mock_create_graphsage_detector_for_mapek
    engine = ConsciousnessEngine(enable_advanced_metrics=True)

    # Debug prints
    print(
        f"\nDEBUG: Initializing ConsciousnessEngine with graphsage_detector: {engine.graphsage_detector}"
    )
    print(f"DEBUG: type(engine.graphsage_detector): {type(engine.graphsage_detector)}")
    print(
        f"DEBUG: engine.graphsage_detector.predict type: {type(engine.graphsage_detector.predict)}"
    )

    # 2. Симуляция нормальных метрик
    normal_metrics = {
        "node_id": "node-1",
        "cpu_percent": 50.0,
        "memory_percent": 40.0,
        "latency_ms": 50.0,
        "packet_loss": 0.1,
        "mesh_connectivity": 5,
    }

    metrics_normal = engine.get_consciousness_metrics(normal_metrics)

    assert metrics_normal.state == ConsciousnessState.HARMONIC
    assert metrics_normal.phi_ratio > 1.0  # Should be harmonic or euphoric
    assert metrics_normal.phi_ratio < PHI * 1.05  # Should be close to PHI

    # 3. Симуляция аномальных метрик (высокая latency)
    anomaly_metrics = {
        "node_id": "node-1",
        "cpu_percent": 80.0,
        "memory_percent": 70.0,
        "latency_ms": 150.0,  # High latency
        "packet_loss": 5.0,
        "mesh_connectivity": 3,
    }

    metrics_anomaly = engine.get_consciousness_metrics(anomaly_metrics)

    # Debug prints for anomaly
    anomaly_pred = engine.graphsage_detector.predict(
        anomaly_metrics["node_id"], anomaly_metrics, []
    )
    print(
        f"DEBUG ANOMALY: anomaly_prediction.anomaly_score: {anomaly_pred.anomaly_score}"
    )
    print(f"DEBUG ANOMALY: metrics_anomaly.phi_ratio: {metrics_anomaly.phi_ratio}")
    print(f"DEBUG ANOMALY: metrics_anomaly.state: {metrics_anomaly.state}")

    # Test expects phi_ratio < 1.0 and state CONTEMPLATIVE/MYSTICAL
    assert metrics_anomaly.state in [
        ConsciousnessState.CONTEMPLATIVE,
        ConsciousnessState.MYSTICAL,
    ]
    assert metrics_anomaly.phi_ratio < 1.0

    # Дополнительная проверка на восстановление (если GraphSAGE предскажет нормальное)
    # Симуляция восстановления после аномалии
    recovery_metrics = {
        "node_id": "node-1",
        "cpu_percent": 45.0,
        "memory_percent": 35.0,
        "latency_ms": 60.0,
        "packet_loss": 0.5,
        "mesh_connectivity": 7,
    }

    metrics_recovery = engine.get_consciousness_metrics(recovery_metrics)
    assert metrics_recovery.state == ConsciousnessState.HARMONIC
    assert metrics_recovery.phi_ratio > 1.0
