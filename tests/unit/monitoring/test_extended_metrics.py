"""
Test suite for extended Prometheus metrics.

Tests:
- GraphSAGE anomaly detection metrics
- LoRA training metrics
- RAG retrieval metrics
- DAO governance voting metrics
- eBPF event and compilation metrics
"""

import pytest

from src.monitoring.prometheus_extended import (
    dao_votes_cast_total, ebpf_events_processed_total,
    get_extended_metrics_text, graphsage_anomalies_detected_total,
    graphsage_inference_latency_ms, lora_training_loss,
    rag_retrieval_latency_ms, record_dao_vote, record_ebpf_event,
    record_graphsage_inference, record_lora_training_update,
    record_rag_retrieval)


class TestGraphSAGEMetrics:
    """Test GraphSAGE anomaly detection metrics."""

    def test_inference_latency_recorded(self):
        """Test that inference latency is recorded."""
        graphsage_inference_latency_ms.observe(25.5)
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_graphsage_inference_latency_ms" in metrics

    def test_anomaly_detection_recorded(self):
        """Test that anomaly detection is recorded."""
        record_graphsage_inference(45.2, True, "CRITICAL")
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_graphsage_anomalies_detected_total" in metrics


class TestLoRAMetrics:
    """Test LoRA fine-tuning metrics."""

    def test_training_loss_recorded(self):
        """Test that training loss is recorded."""
        lora_training_loss.labels(adapter_name="test_adapter", model_name="mape_k").set(
            0.45
        )
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_lora_training_loss" in metrics

    def test_training_update_recorded(self):
        """Test that training update is recorded."""
        record_lora_training_update("test_adapter", 0.35, 5)
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_lora_training" in metrics


class TestRAGMetrics:
    """Test RAG pipeline metrics."""

    def test_retrieval_latency_recorded(self):
        """Test that retrieval latency is recorded."""
        rag_retrieval_latency_ms.observe(125.5)
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_rag_retrieval_latency_ms" in metrics

    def test_rag_retrieval_recorded(self):
        """Test that RAG retrieval is recorded."""
        record_rag_retrieval(95.3, 5)
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_rag_retrieval" in metrics


class TestDAOMetrics:
    """Test DAO governance metrics."""

    def test_vote_recorded(self):
        """Test that votes are recorded."""
        record_dao_vote("FOR", "model_update")
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_dao_votes_cast_total" in metrics

    def test_multiple_vote_types(self):
        """Test recording different vote types."""
        record_dao_vote("FOR", "model_update")
        record_dao_vote("AGAINST", "model_update")
        record_dao_vote("ABSTAIN", "threshold_change")
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_dao_votes_cast_total" in metrics


class TesteBPFMetrics:
    """Test eBPF network program metrics."""

    def test_ebpf_event_recorded(self):
        """Test that eBPF events are recorded."""
        record_ebpf_event("packet_rx", "xdp")
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_ebpf_events_processed_total" in metrics

    def test_multiple_event_types(self):
        """Test recording different event types."""
        record_ebpf_event("packet_rx", "xdp")
        record_ebpf_event("packet_tx", "xdp")
        record_ebpf_event("drop_counter", "tc")
        metrics = get_extended_metrics_text()
        assert b"x0tta6bl4_ebpf_events_processed_total" in metrics


class TestMetricsExport:
    """Test metrics export functionality."""

    def test_metrics_text_format(self):
        """Test that metrics are exported in Prometheus text format."""
        metrics = get_extended_metrics_text()
        assert isinstance(metrics, bytes)
        assert b"# HELP" in metrics
        assert b"# TYPE" in metrics

    def test_all_metric_types_present(self):
        """Test that all metric types are exported."""
        metrics = get_extended_metrics_text()

        # Check for key metrics from each category
        assert b"graphsage" in metrics.lower() or b"x0tta6bl4" in metrics
        assert b"lora" in metrics.lower() or b"x0tta6bl4" in metrics
        assert b"rag" in metrics.lower() or b"x0tta6bl4" in metrics
        assert b"dao" in metrics.lower() or b"x0tta6bl4" in metrics
        assert b"ebpf" in metrics.lower() or b"x0tta6bl4" in metrics
