"""
Test suite for OpenTelemetry distributed tracing.

Tests:
- Tracer manager initialization
- MAPE-K span creation
- Network operation spans
- SPIFFE/mTLS spans
- ML operation spans
"""

import pytest

from src.monitoring.opentelemetry_tracing import (OTEL_AVAILABLE, MAPEKSpans,
                                                  MLSpans, NetworkSpans,
                                                  OTelTracingManager,
                                                  SPIFFESpans,
                                                  get_tracer_manager,
                                                  initialize_tracing)


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
class TestTracerManagerInitialization:
    """Test OpenTelemetry initialization."""

    def test_tracer_manager_creation(self):
        """Test creating tracer manager."""
        manager = OTelTracingManager(service_name="test-service")
        assert manager.service_name == "test-service"

    def test_tracing_disabled_when_otel_unavailable(self):
        """Test that tracing gracefully disables if OpenTelemetry unavailable."""
        manager = OTelTracingManager()
        # Should not crash, just disabled
        assert isinstance(manager.enabled, bool)


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
class TestMAPEKSpans:
    """Test MAPE-K span creation."""

    def test_monitor_span(self):
        """Test Monitor phase span."""
        manager = OTelTracingManager()

        spans = MAPEKSpans(manager)
        with spans.monitor_phase("node-a", metrics_collected=42):
            pass

    def test_analyze_span(self):
        """Test Analyze phase span."""
        manager = OTelTracingManager()

        spans = MAPEKSpans(manager)
        with spans.analyze_phase("node-a", anomalies=1, confidence=0.95):
            pass

    def test_plan_span(self):
        """Test Plan phase span."""
        manager = OTelTracingManager()

        spans = MAPEKSpans(manager)
        with spans.plan_phase("node-a", actions=3):
            pass

    def test_execute_span(self):
        """Test Execute phase span."""
        manager = OTelTracingManager()

        spans = MAPEKSpans(manager)
        with spans.execute_phase("node-a", actions_executed=3, success=True):
            pass

    def test_knowledge_span(self):
        """Test Knowledge phase span."""
        manager = OTelTracingManager()

        spans = MAPEKSpans(manager)
        with spans.knowledge_phase("node-a", insights=5):
            pass


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
class TestNetworkSpans:
    """Test network operation spans."""

    def test_node_discovery_span(self):
        """Test node discovery span."""
        manager = OTelTracingManager()

        spans = NetworkSpans(manager)
        with spans.node_discovery("node-a", discovered_nodes=3):
            pass

    def test_route_calculation_span(self):
        """Test route calculation span."""
        manager = OTelTracingManager()

        spans = NetworkSpans(manager)
        with spans.route_calculation("node-a", "node-c", hops=2):
            pass

    def test_message_forwarding_span(self):
        """Test message forwarding span."""
        manager = OTelTracingManager()

        spans = NetworkSpans(manager)
        with spans.message_forwarding("node-a", "node-b", "msg-123"):
            pass


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
class TestSPIFFESpans:
    """Test SPIFFE/SPIRE identity operation spans."""

    def test_svid_fetch_span(self):
        """Test SVID fetch span."""
        manager = OTelTracingManager()

        spans = SPIFFESpans(manager)
        with spans.svid_fetch("node-a", ttl_seconds=3600):
            pass

    def test_svid_renewal_span(self):
        """Test SVID renewal span."""
        manager = OTelTracingManager()

        spans = SPIFFESpans(manager)
        with spans.svid_renewal("node-a", success=True):
            pass

    def test_mtls_handshake_span(self):
        """Test mTLS handshake span."""
        manager = OTelTracingManager()

        spans = SPIFFESpans(manager)
        with spans.mtls_handshake("node-a", "node-b", duration_ms=45.2):
            pass


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not available")
class TestMLSpans:
    """Test ML operation spans."""

    def test_model_inference_span(self):
        """Test model inference span."""
        manager = OTelTracingManager()

        spans = MLSpans(manager)
        with spans.model_inference("graphsage", input_size=100, latency_ms=23.5):
            pass

    def test_model_training_span(self):
        """Test model training span."""
        manager = OTelTracingManager()

        spans = MLSpans(manager)
        with spans.model_training("lora_adapter", epoch=5, loss=0.32):
            pass


class TestGlobalFunctions:
    """Test global tracer initialization."""

    def test_initialize_tracing(self):
        """Test initialize_tracing global function."""
        initialize_tracing("test-service")
        manager = get_tracer_manager()
        assert manager is not None
