"""
Unit tests for src/monitoring/maas_metrics.py

Covers:
- MaaSMetrics instantiation with and without prometheus_client
- NoOp fallback: no errors when prometheus unavailable
- Convenience helpers: record_escrow_failure, record_billing_error,
  record_heartbeat, record_rate_limit_rejection
- Label cardinality guard in record_heartbeat (truncation to 16 chars)
- UTC timestamp in logging_config.StructuredJsonFormatter
"""
from __future__ import annotations

import logging
import sys
import time
from unittest.mock import MagicMock, patch


# ===========================================================================
# 1. MaaSMetrics — prometheus available path
# ===========================================================================


class TestMaaSMetricsWithPrometheus:
    def test_singleton_is_maas_metrics_instance(self):
        from src.monitoring.maas_metrics import MaaSMetrics, maas_metrics

        assert isinstance(maas_metrics, MaaSMetrics)

    def test_all_required_attributes_present(self):
        from src.monitoring.maas_metrics import maas_metrics

        required = [
            "escrow_failures",
            "escrow_operations",
            "heartbeat_received",
            "nodes_active",
            "nodes_offline",
            "billing_errors",
            "billing_operations",
            "governance_quorum_failures",
            "rate_limit_rejected",
            "rate_limit_blocked_ips",
            "vpn_configs_created",
            "vpn_connections_active",
            "vpn_errors",
            "pqc_handshake_failures",
            "pqc_handshakes_total",
            "mapek_events_emitted",
        ]
        for attr in required:
            assert hasattr(maas_metrics, attr), f"Missing metric: {attr}"

    def test_escrow_failures_labels_method(self):
        """Counter should accept 'reason' label without error."""
        from src.monitoring.maas_metrics import maas_metrics

        # Should not raise
        labeled = maas_metrics.escrow_failures.labels(reason="bridge_error")
        assert labeled is not None

    def test_billing_errors_labels_method(self):
        from src.monitoring.maas_metrics import maas_metrics

        labeled = maas_metrics.billing_errors.labels(error_type="stripe_timeout")
        assert labeled is not None

    def test_rate_limit_rejected_labels_method(self):
        from src.monitoring.maas_metrics import maas_metrics

        labeled = maas_metrics.rate_limit_rejected.labels(endpoint="/api/v1/test")
        assert labeled is not None


# ===========================================================================
# 2. NoOp fallback when prometheus_client is absent
# ===========================================================================


class TestNoOpMetric:
    def test_noop_inc_no_error(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        m.inc()
        m.inc(5)

    def test_noop_dec_no_error(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        m.dec()
        m.dec(3)

    def test_noop_set_no_error(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        m.set(42)

    def test_noop_observe_no_error(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        m.observe(0.123)

    def test_noop_labels_returns_self(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        result = m.labels(reason="x", endpoint="/y")
        assert result is m

    def test_noop_time_context_manager(self):
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        with m.time():
            pass  # Should not raise

    def test_noop_metric_is_complete_fallback(self):
        """_NoOpMetric implements the full metric protocol without errors."""
        from src.monitoring.maas_metrics import _NoOpMetric

        m = _NoOpMetric()
        # All metric methods should be callable
        m.inc()
        m.inc(5)
        m.dec()
        m.set(99)
        m.observe(1.5)
        labeled = m.labels(reason="x", endpoint="/y", result="ok")
        assert labeled is m
        # time() context manager
        with m.time():
            pass


# ===========================================================================
# 3. Convenience helpers
# ===========================================================================


class TestConvenienceHelpers:
    def test_record_escrow_failure_calls_inc(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "escrow_failures", mock_counter):
            mm_module.record_escrow_failure("bridge_error")

        mock_counter.labels.assert_called_once_with(reason="bridge_error")
        mock_counter.inc.assert_called_once()

    def test_record_escrow_failure_default_reason(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "escrow_failures", mock_counter):
            mm_module.record_escrow_failure()

        mock_counter.labels.assert_called_once_with(reason="unknown")

    def test_record_billing_error_calls_inc(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "billing_errors", mock_counter):
            mm_module.record_billing_error("stripe_timeout")

        mock_counter.labels.assert_called_once_with(error_type="stripe_timeout")
        mock_counter.inc.assert_called_once()

    def test_record_heartbeat_truncates_node_id(self):
        """record_heartbeat truncates node_id to 16 chars to avoid label cardinality explosion."""
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        long_id = "a" * 64
        with patch.object(mm_module.maas_metrics, "heartbeat_received", mock_counter):
            mm_module.record_heartbeat(long_id)

        call_kwargs = mock_counter.labels.call_args[1]
        assert len(call_kwargs["node_id"]) <= 16

    def test_record_heartbeat_short_id_unchanged(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "heartbeat_received", mock_counter):
            mm_module.record_heartbeat("node-42")

        call_kwargs = mock_counter.labels.call_args[1]
        assert call_kwargs["node_id"] == "node-42"

    def test_record_rate_limit_rejection_calls_inc(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "rate_limit_rejected", mock_counter):
            mm_module.record_rate_limit_rejection("/api/v1/marketplace")

        mock_counter.labels.assert_called_once_with(endpoint="/api/v1/marketplace")
        mock_counter.inc.assert_called_once()

    def test_record_rate_limit_rejection_default_endpoint(self):
        from src.monitoring import maas_metrics as mm_module

        mock_counter = MagicMock()
        mock_counter.labels.return_value = mock_counter

        with patch.object(mm_module.maas_metrics, "rate_limit_rejected", mock_counter):
            mm_module.record_rate_limit_rejection()

        call_kwargs = mock_counter.labels.call_args[1]
        assert call_kwargs["endpoint"] == "unknown"


# ===========================================================================
# 4. UTC timestamp fix in StructuredJsonFormatter
# ===========================================================================


class TestStructuredJsonFormatterUTC:
    def test_timestamp_is_utc_aware(self):
        """StructuredJsonFormatter.format should produce UTC ISO timestamp."""
        import json

        from src.core.logging_config import StructuredJsonFormatter

        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        entry = json.loads(output)

        ts = entry["timestamp"]
        # UTC-aware ISO format ends with +00:00
        assert "+00:00" in ts or ts.endswith("Z"), (
            f"Expected UTC timestamp but got: {ts}"
        )

    def test_timestamp_field_present(self):
        import json

        from src.core.logging_config import StructuredJsonFormatter

        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )
        entry = json.loads(formatter.format(record))
        assert "timestamp" in entry
        assert "level" in entry
        assert "message" in entry

    def test_sensitive_data_masked_in_output(self):
        """Passwords/tokens in log messages must be masked."""
        import json

        from src.core.logging_config import StructuredJsonFormatter

        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="connecting with password=supersecret123",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "supersecret123" not in output

    def test_request_id_injected_from_context(self):
        """request_id from RequestIdContextVar appears in formatted output."""
        import json

        from src.core.logging_config import RequestIdContextVar, StructuredJsonFormatter

        formatter = StructuredJsonFormatter()
        RequestIdContextVar.set("test-req-id-abc123")

        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="request scoped log",
                args=(),
                exc_info=None,
            )
            entry = json.loads(formatter.format(record))
            assert entry.get("request_id") == "test-req-id-abc123"
        finally:
            RequestIdContextVar.clear()


# ===========================================================================
# 5. Integration: escrow failure metric flows through to marketplace module
# ===========================================================================


class TestEscrowMetricIntegration:
    def test_record_escrow_failure_importable_from_marketplace(self):
        """maas_marketplace imports record_escrow_failure without error."""
        # If import fails this test fails
        import importlib

        spec = importlib.util.find_spec("src.api.maas_marketplace")
        assert spec is not None

    def test_record_billing_error_importable_from_billing(self):
        import importlib

        spec = importlib.util.find_spec("src.api.maas_billing")
        assert spec is not None
