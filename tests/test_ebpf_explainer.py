"""
Tests для eBPF Explainer
"""

import pytest

from src.network.ebpf.explainer import EBPFEvent, EBPFEventType, EBPFExplainer


@pytest.fixture
def explainer():
    """Fixture для EBPFExplainer"""
    return EBPFExplainer()


@pytest.fixture
def packet_drop_event():
    """Fixture для packet drop event"""
    return EBPFEvent(
        event_type=EBPFEventType.PACKET_DROP,
        timestamp=1234567890.0,
        node_id="node-001",
        program_id="xdp_counter",
        details={"packet_count": 100, "reason": "rate_limit"},
    )


def test_explain_packet_drop(explainer, packet_drop_event):
    """Test объяснение packet drop события"""
    explanation = explainer.explain_event(packet_drop_event)

    assert "отброшен" in explanation.lower() or "dropped" in explanation.lower()
    assert "Детали" in explanation
    assert len(explanation) > 50  # Должно быть достаточно подробное объяснение


def test_explain_performance(explainer):
    """Test объяснение performance метрик"""
    metrics = {
        "cpu_percent": 1.5,
        "memory_bytes": 50 * 1024 * 1024,  # 50 MB
        "packets_processed": 10000,
        "packet_drops": 5,
    }

    explanation = explainer.explain_performance(metrics)

    assert "CPU" in explanation
    assert "Memory" in explanation
    assert "Packets" in explanation


def test_explain_bottleneck(explainer):
    """Test объяснение bottleneck"""
    analysis = {"type": "cpu", "severity": "high", "location": "xdp_program"}

    explanation = explainer.explain_bottleneck(analysis)

    assert "Bottleneck" in explanation
    assert "CPU" in explanation or "cpu" in explanation
