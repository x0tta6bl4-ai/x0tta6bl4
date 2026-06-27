"""
Tests для GraphSAGE Observe Mode
"""

import pytest

from src.ml.graphsage_anomaly_detector import AnomalyPrediction
from src.ml.graphsage_observe_mode import (DetectorMode,
                                           GraphSAGEObserveMode)


@pytest.fixture
def observe_detector():
    """Fixture для observe mode detector"""
    return GraphSAGEObserveMode(
        mode=DetectorMode.OBSERVE, threshold=0.95, confidence_required=0.90
    )


def test_observe_mode_initialization(observe_detector):
    """Test инициализация observe mode"""
    assert observe_detector.mode == DetectorMode.OBSERVE
    assert observe_detector.threshold == 0.95
    assert observe_detector.confidence_required == 0.90


def test_detect_anomaly_observe_mode(observe_detector):
    """Test обнаружение аномалии в observe mode"""
    graph_data = {
        "nodes": [{"id": "node-001", "cpu": 95.0}],
        "edges": [],
        "cpu_percent": 95.0,
        "memory_percent": 80.0,
    }

    event = observe_detector.detect(graph_data, "node-001")

    # В observe mode событие должно быть залогировано, но не заблокировано
    if event:
        assert event.mode == DetectorMode.OBSERVE
        assert event.action_taken is None  # Нет действий в observe mode
        assert event.claim_gate["observe_mode_passive"] is True
        assert event.claim_gate["local_model_score_claim_allowed"] is True
        assert event.claim_gate["live_intrusion_detection_claim_allowed"] is False
        assert event.claim_gate["production_security_coverage_claim_allowed"] is False


def test_get_stats(observe_detector):
    """Test получение статистики"""
    stats = observe_detector.get_stats()

    assert "total_detections" in stats
    assert "mode" in stats
    assert stats["mode"] == "observe"
    assert "claim_boundary" in stats


def test_observe_mode_claim_gate_uses_observe_threshold(monkeypatch, observe_detector):
    """Observe mode reports local score only and keeps broad security claims blocked."""
    monkeypatch.setattr(observe_detector, "_save_event_for_analysis", lambda _event: None)
    observe_detector.detector.predict = lambda **_kwargs: AnomalyPrediction(
        is_anomaly=True,
        anomaly_score=0.96,
        confidence=0.95,
        node_id="node-claim",
        features={"cpu_percent": 99.0},
        inference_time_ms=0.1,
    )

    event = observe_detector.detect({"cpu_percent": 99.0}, "node-claim")

    assert event is not None
    assert event.claim_gate["source"] == "graphsage_observe_mode"
    assert event.claim_gate["threshold"] == observe_detector.threshold
    assert event.claim_gate["local_anomaly_threshold_exceeded"] is True
    assert event.claim_gate["autonomous_block_claim_allowed"] is False
    assert event.action_taken is None


def test_migrate_to_warn_mode(observe_detector):
    """Test миграция к warn mode"""
    observe_detector.migrate_to_warn_mode()

    assert observe_detector.mode == DetectorMode.WARN


def test_migrate_to_block_mode_requires_validation(observe_detector):
    """Test что миграция к block mode требует валидации"""
    # Без validation данных миграция не должна произойти
    observe_detector.migrate_to_block_mode()

    # Должен остаться в текущем режиме (observe или warn)
    assert observe_detector.mode in [DetectorMode.OBSERVE, DetectorMode.WARN]
