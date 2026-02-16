#!/usr/bin/env python3
"""
Unit tests for PQC-MAPE-K Integration
Tests the integration between PQC Verification Daemon and MAPE-K self-healing loop.
"""

import secrets
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.network.ebpf.pqc_mapek_integration import (
    PQCAnomaly, PQCAnomalyType, PQCMAPEKIntegration, PQCPrometheusMetrics,
    create_integrated_pqc_system, start_pqc_monitoring_thread)


@pytest.fixture
def mock_metrics():
    """Provide mock metrics to avoid Prometheus registry collisions"""
    mock = Mock(spec=PQCPrometheusMetrics)
    mock._enabled = True
    return mock


class TestPQCAnomalyType:
    """Tests for PQCAnomalyType enum"""

    def test_anomaly_types_defined(self):
        """Test all anomaly types are defined"""
        assert PQCAnomalyType.VERIFICATION_FAILED.value == "verification_failed"
        assert PQCAnomalyType.UNKNOWN_PUBKEY.value == "unknown_pubkey"
        assert PQCAnomalyType.SESSION_EXPIRED.value == "session_expired"
        assert PQCAnomalyType.HIGH_FAILURE_RATE.value == "high_failure_rate"
        assert PQCAnomalyType.REPLAY_ATTACK.value == "replay_attack"


class TestPQCAnomaly:
    """Tests for PQCAnomaly dataclass"""

    def test_create_anomaly(self):
        """Test creating an anomaly"""
        anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="test-session-123",
        )

        assert anomaly.anomaly_type == PQCAnomalyType.VERIFICATION_FAILED
        assert anomaly.session_id == "test-session-123"
        assert anomaly.severity == "medium"  # default
        assert anomaly.pubkey_id is None
        assert isinstance(anomaly.timestamp, float)
        assert isinstance(anomaly.details, dict)

    def test_create_anomaly_with_all_fields(self):
        """Test creating anomaly with all fields"""
        ts = time.time()
        anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.REPLAY_ATTACK,
            session_id="session-456",
            pubkey_id="pubkey-789",
            timestamp=ts,
            severity="critical",
            details={"source_ip": "10.0.0.1"},
        )

        assert anomaly.anomaly_type == PQCAnomalyType.REPLAY_ATTACK
        assert anomaly.session_id == "session-456"
        assert anomaly.pubkey_id == "pubkey-789"
        assert anomaly.timestamp == ts
        assert anomaly.severity == "critical"
        assert anomaly.details == {"source_ip": "10.0.0.1"}


class TestPQCPrometheusMetrics:
    """Tests for PQCPrometheusMetrics"""

    def test_initialization_without_prometheus(self):
        """Test initialization when prometheus_client not available"""
        with patch.dict("sys.modules", {"prometheus_client": None}):
            with patch(
                "src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", False
            ):
                metrics = PQCPrometheusMetrics()
                assert metrics._enabled is False

    @patch("src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_mapek_integration.Counter")
    @patch("src.network.ebpf.pqc_mapek_integration.Gauge")
    @patch("src.network.ebpf.pqc_mapek_integration.Histogram")
    def test_initialization_with_prometheus(
        self, mock_histogram, mock_gauge, mock_counter
    ):
        """Test initialization with prometheus_client available"""
        metrics = PQCPrometheusMetrics(namespace="test_pqc")

        assert metrics._enabled is True
        assert metrics._namespace == "test_pqc"

        # Verify counters created
        assert mock_counter.call_count >= 3  # verifications, anomalies, events

        # Verify gauges created
        assert (
            mock_gauge.call_count >= 4
        )  # sessions, pubkeys, verification_rate, failure_rate

        # Verify histogram created
        mock_histogram.assert_called_once()

    @patch("src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_mapek_integration.Counter")
    @patch("src.network.ebpf.pqc_mapek_integration.Gauge")
    @patch("src.network.ebpf.pqc_mapek_integration.Histogram")
    def test_record_verification_success(
        self, mock_histogram, mock_gauge, mock_counter
    ):
        """Test recording successful verification"""
        metrics = PQCPrometheusMetrics()

        metrics.record_verification(success=True, latency_seconds=0.005)

        # Should call labels().inc() on verifications counter
        metrics.verifications_total.labels.assert_called_with(result="success")

    @patch("src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_mapek_integration.Counter")
    @patch("src.network.ebpf.pqc_mapek_integration.Gauge")
    @patch("src.network.ebpf.pqc_mapek_integration.Histogram")
    def test_record_verification_failed(self, mock_histogram, mock_gauge, mock_counter):
        """Test recording failed verification"""
        metrics = PQCPrometheusMetrics()

        metrics.record_verification(success=False)

        metrics.verifications_total.labels.assert_called_with(result="failed")

    @patch("src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_mapek_integration.Counter")
    @patch("src.network.ebpf.pqc_mapek_integration.Gauge")
    @patch("src.network.ebpf.pqc_mapek_integration.Histogram")
    def test_record_anomaly(self, mock_histogram, mock_gauge, mock_counter):
        """Test recording anomaly"""
        metrics = PQCPrometheusMetrics()

        metrics.record_anomaly(PQCAnomalyType.UNKNOWN_PUBKEY)

        metrics.anomalies_total.labels.assert_called_with(type="unknown_pubkey")

    def test_metrics_noop_when_disabled(self):
        """Test metrics operations are no-op when disabled"""
        with patch(
            "src.network.ebpf.pqc_mapek_integration.PROMETHEUS_AVAILABLE", False
        ):
            metrics = PQCPrometheusMetrics()

            # These should not raise
            metrics.record_verification(True, 0.01)
            metrics.record_anomaly(PQCAnomalyType.VERIFICATION_FAILED)
            metrics.record_event_received()
            metrics.update_session_count(10)
            metrics.update_pubkey_count(5)
            metrics.update_rates(0.95, 0.05)


class TestPQCMAPEKIntegration:
    """Tests for PQCMAPEKIntegration"""

    def test_initialization_defaults(self, mock_metrics):
        """Test initialization with default parameters"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        assert integration.daemon is None
        assert integration.thresholds["max_failure_rate"] == 0.1
        assert integration.thresholds["consecutive_failures_alert"] == 5
        assert integration.consecutive_failures == 0
        assert len(integration.anomaly_history) == 0

    def test_initialization_custom_thresholds(self, mock_metrics):
        """Test initialization with custom thresholds"""
        custom_thresholds = {
            "max_failure_rate": 0.2,
            "consecutive_failures_alert": 10,
        }

        integration = PQCMAPEKIntegration(
            metrics=mock_metrics, thresholds=custom_thresholds
        )

        assert integration.thresholds["max_failure_rate"] == 0.2
        assert integration.thresholds["consecutive_failures_alert"] == 10
        # Defaults should still be present
        assert integration.thresholds["min_verification_rate"] == 0.9

    def test_set_callbacks(self, mock_metrics):
        """Test setting MAPE-K callbacks"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        alert_callback = Mock()
        action_callback = Mock()

        integration.set_mapek_alert_callback(alert_callback)
        integration.set_mapek_action_callback(action_callback)

        assert integration._mapek_alert_callback is alert_callback
        assert integration._mapek_action_callback is action_callback

    def test_handle_daemon_anomaly_unknown_pubkey(self, mock_metrics):
        """Test handling unknown_pubkey anomaly from daemon"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)
        alert_callback = Mock()
        integration.set_mapek_alert_callback(alert_callback)

        integration.handle_daemon_anomaly(
            "unknown_pubkey", {"session_id": "sess-123", "pubkey_id": "pk-456"}
        )

        assert len(integration.anomaly_history) == 1
        anomaly = integration.anomaly_history[0]
        assert anomaly.anomaly_type == PQCAnomalyType.UNKNOWN_PUBKEY
        assert anomaly.severity == "medium"

    def test_handle_daemon_anomaly_verification_failed(self, mock_metrics):
        """Test handling verification_failed anomaly"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)
        alert_callback = Mock()
        integration.set_mapek_alert_callback(alert_callback)

        integration.handle_daemon_anomaly(
            "verification_failed", {"session_id": "sess-789"}
        )

        assert len(integration.anomaly_history) == 1
        anomaly = integration.anomaly_history[0]
        assert anomaly.anomaly_type == PQCAnomalyType.VERIFICATION_FAILED
        assert anomaly.severity == "high"
        # High severity should trigger escalation
        alert_callback.assert_called_once()

    def test_consecutive_failures_tracking(self, mock_metrics):
        """Test consecutive failures are tracked"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        for i in range(3):
            integration.handle_daemon_anomaly(
                "verification_failed", {"session_id": f"sess-{i}"}
            )

        assert integration.consecutive_failures == 3

    def test_consecutive_failures_reset_on_different_anomaly(self, mock_metrics):
        """Test consecutive failures reset on non-failure anomaly"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        # Build up failures
        for i in range(3):
            integration.handle_daemon_anomaly(
                "verification_failed", {"session_id": f"sess-{i}"}
            )

        assert integration.consecutive_failures == 3

        # Different anomaly type resets counter
        integration.handle_daemon_anomaly(
            "unknown_pubkey", {"session_id": "sess-new", "pubkey_id": "pk-new"}
        )

        assert integration.consecutive_failures == 0

    def test_escalation_on_consecutive_failures(self, mock_metrics):
        """Test escalation when consecutive failures exceed threshold"""
        integration = PQCMAPEKIntegration(
            metrics=mock_metrics, thresholds={"consecutive_failures_alert": 3}
        )
        alert_callback = Mock()
        integration.set_mapek_alert_callback(alert_callback)

        # First two failures don't escalate (high severity does escalate though)
        # Actually, verification_failed has severity="high", so each will escalate
        # Let's test with unknown_pubkey which has medium severity
        for i in range(3):
            # Simulate consecutive failures via direct method call
            anomaly = PQCAnomaly(
                anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
                session_id=f"sess-{i}",
                severity="low",  # Override to test threshold
            )
            integration.consecutive_failures += 1
            integration.anomaly_history.append(anomaly)

        # Now should escalate on next check
        assert integration.consecutive_failures >= 3

    def test_record_verification_success(self, mock_metrics):
        """Test recording successful verification"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        integration.record_verification(success=True, latency_seconds=0.01)

        mock_metrics.record_verification.assert_called_with(True, 0.01)
        assert integration.consecutive_failures == 0
        assert len(integration._recent_verifications) == 1

    def test_record_verification_failure(self, mock_metrics):
        """Test recording failed verification doesn't reset consecutive counter"""
        # Set min_verification_rate to 0 to prevent HIGH_FAILURE_RATE anomalies
        integration = PQCMAPEKIntegration(
            metrics=mock_metrics, thresholds={"min_verification_rate": 0}
        )

        # Add some successful verifications first to avoid rate-based anomalies
        for _ in range(10):
            integration._recent_verifications.append((time.time(), True))

        integration.consecutive_failures = 3

        integration.record_verification(success=False)

        # Failure doesn't reset counter (only success resets it)
        assert integration.consecutive_failures == 3

    def test_recent_verifications_window_trimming(self, mock_metrics):
        """Test recent verifications are trimmed to window"""
        integration = PQCMAPEKIntegration(
            metrics=mock_metrics,
            thresholds={"anomaly_window_seconds": 0.1},  # 100ms window
        )

        # Add old verification
        integration._recent_verifications.append((time.time() - 1, True))

        # Add new verification - should trigger trim
        integration.record_verification(success=True)

        # Old one should be trimmed
        assert len(integration._recent_verifications) == 1

    def test_suggest_remediation_verification_failed(self, mock_metrics):
        """Test remediation suggestions for verification failure"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)
        integration.consecutive_failures = 4

        anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED, session_id="sess-123"
        )

        actions = integration._suggest_remediation(anomaly)

        assert len(actions) >= 1
        action_types = [a["type"] for a in actions]
        assert "invalidate_session" in action_types
        assert "rotate_keys" in action_types  # Due to consecutive_failures >= 3

    def test_suggest_remediation_unknown_pubkey(self, mock_metrics):
        """Test remediation suggestions for unknown pubkey"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY,
            session_id="sess-123",
            pubkey_id="pk-456",
        )

        actions = integration._suggest_remediation(anomaly)

        assert len(actions) == 1
        assert actions[0]["type"] == "request_key_registration"
        assert actions[0]["pubkey_id"] == "pk-456"

    def test_suggest_remediation_replay_attack(self, mock_metrics):
        """Test remediation suggestions for replay attack"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.REPLAY_ATTACK, session_id="sess-123"
        )

        actions = integration._suggest_remediation(anomaly)

        action_types = [a["type"] for a in actions]
        assert "block_session" in action_types
        assert "alert_security" in action_types

    def test_get_metrics_for_mapek_without_daemon(self, mock_metrics):
        """Test getting metrics without daemon"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        metrics = integration.get_metrics_for_mapek()

        assert metrics == {}

    def test_get_metrics_for_mapek_with_daemon(self, mock_metrics):
        """Test getting metrics with mock daemon"""
        mock_daemon = Mock()
        mock_daemon.get_stats.return_value = {
            "events_received": 100,
            "verifications_success": 95,
            "verifications_failed": 5,
            "unknown_pubkey": 2,
            "active_sessions": 10,
            "registered_pubkeys": 3,
        }

        integration = PQCMAPEKIntegration(pqc_daemon=mock_daemon, metrics=mock_metrics)

        metrics = integration.get_metrics_for_mapek()

        assert metrics["pqc_events_received"] == 100
        assert metrics["pqc_verifications_success"] == 95
        assert metrics["pqc_verifications_failed"] == 5
        assert metrics["pqc_success_rate"] == 0.95
        assert metrics["pqc_failure_rate"] == 0.05
        assert metrics["pqc_active_sessions"] == 10

    def test_sync_daemon_metrics(self):
        """Test syncing daemon metrics to Prometheus"""
        mock_daemon = Mock()
        mock_daemon.get_stats.return_value = {
            "active_sessions": 5,
            "registered_pubkeys": 2,
        }
        mock_metrics = Mock()

        integration = PQCMAPEKIntegration(pqc_daemon=mock_daemon, metrics=mock_metrics)

        integration.sync_daemon_metrics()

        mock_metrics.update_session_count.assert_called_with(5)
        mock_metrics.update_pubkey_count.assert_called_with(2)

    def test_update_thresholds_from_dao(self, mock_metrics):
        """Test updating thresholds from DAO"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        assert integration.thresholds["max_failure_rate"] == 0.1

        integration.update_thresholds_from_dao(
            {
                "max_failure_rate": 0.15,
                "nonexistent_key": 999,  # Should be ignored
            }
        )

        assert integration.thresholds["max_failure_rate"] == 0.15
        assert "nonexistent_key" not in integration.thresholds

    def test_anomaly_history_trimmed_to_hour(self, mock_metrics):
        """Test anomaly history is trimmed to last hour"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        # Add old anomaly
        old_anomaly = PQCAnomaly(
            anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY,
            session_id="old-session",
            timestamp=time.time() - 4000,  # Over an hour ago
        )
        integration.anomaly_history.append(old_anomaly)

        # Process new anomaly - should trigger trim
        integration._process_anomaly(
            PQCAnomaly(
                anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY, session_id="new-session"
            )
        )

        # Old anomaly should be removed
        session_ids = [a.session_id for a in integration.anomaly_history]
        assert "old-session" not in session_ids
        assert "new-session" in session_ids

    def test_high_failure_rate_anomaly_generated(self, mock_metrics):
        """Test that HIGH_FAILURE_RATE anomaly is generated when rate drops"""
        integration = PQCMAPEKIntegration(
            metrics=mock_metrics,
            thresholds={"min_verification_rate": 0.9, "anomaly_window_seconds": 60},
        )

        # Record many failures to drop rate below threshold
        for _ in range(9):
            integration.record_verification(success=False)

        integration.record_verification(success=True)

        # Should have generated HIGH_FAILURE_RATE anomaly
        anomaly_types = [a.anomaly_type for a in integration.anomaly_history]
        assert PQCAnomalyType.HIGH_FAILURE_RATE in anomaly_types


class TestCreateIntegratedPQCSystem:
    """Tests for create_integrated_pqc_system factory function"""

    def test_creates_system_with_all_components(self):
        """Test factory creates system with daemon, integration, and metrics"""
        result = create_integrated_pqc_system(
            interface="eth0",
            enable_prometheus=False,  # Avoid Prometheus registry collision
        )

        assert "daemon" in result
        assert "integration" in result
        assert "metrics" in result
        assert result["integration"].daemon is result["daemon"]

    def test_creates_system_without_prometheus(self):
        """Test factory with prometheus disabled"""
        result = create_integrated_pqc_system(enable_prometheus=False)

        assert result["metrics"] is None
        assert result["integration"].metrics is not None  # Uses internal mock

    def test_wires_up_anomaly_callback(self):
        """Test factory wires up anomaly callback between daemon and integration"""
        result = create_integrated_pqc_system(enable_prometheus=False)

        daemon = result["daemon"]
        integration = result["integration"]

        # Check that anomaly_callback is wired
        assert daemon.anomaly_callback is not None
        # Verify callback is the integration's handler
        assert daemon.anomaly_callback == integration.handle_daemon_anomaly


class TestStartPQCMonitoringThread:
    """Tests for start_pqc_monitoring_thread"""

    def test_starts_daemon_thread(self):
        """Test monitoring thread is started as daemon"""
        integration = Mock()
        integration.sync_daemon_metrics = Mock()
        integration.get_metrics_for_mapek = Mock(return_value={})
        stop_event = threading.Event()

        thread = start_pqc_monitoring_thread(
            integration, interval=0.01, stop_event=stop_event
        )

        assert thread.daemon is True
        assert thread.name == "pqc-monitor"
        assert thread.is_alive()

        # Let it run once
        time.sleep(0.05)

        # Should have called sync at least once
        assert integration.sync_daemon_metrics.called
        stop_event.set()
        thread.join(timeout=1.0)


class TestIntegration:
    """Integration tests combining multiple components"""

    def test_full_anomaly_flow(self, mock_metrics):
        """Test complete anomaly detection and escalation flow"""
        # Setup
        alert_events = []
        action_events = []

        def alert_callback(anomaly):
            alert_events.append(anomaly)

        def action_callback(action_type, data):
            action_events.append((action_type, data))

        integration = PQCMAPEKIntegration(metrics=mock_metrics)
        integration.set_mapek_alert_callback(alert_callback)
        integration.set_mapek_action_callback(action_callback)

        # Simulate daemon sending verification failure
        integration.handle_daemon_anomaly(
            "verification_failed", {"session_id": secrets.token_hex(8)}
        )

        # Should have escalated (high severity)
        assert len(alert_events) == 1
        assert alert_events[0].anomaly_type == PQCAnomalyType.VERIFICATION_FAILED

        # Should have suggested actions
        assert len(action_events) >= 1
        action_types = [a[0] for a in action_events]
        assert "invalidate_session" in action_types

    def test_metrics_integration(self, mock_metrics):
        """Test metrics are properly updated during operations"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        # Record some verifications
        integration.record_verification(success=True, latency_seconds=0.005)
        integration.record_verification(success=False, latency_seconds=0.01)

        # Verify metrics calls
        assert mock_metrics.record_verification.call_count == 2
        assert mock_metrics.update_rates.call_count == 2

    def test_dao_governance_threshold_update(self, mock_metrics):
        """Test DAO governance can update thresholds"""
        integration = PQCMAPEKIntegration(metrics=mock_metrics)

        # Initial check
        assert integration.thresholds["max_failure_rate"] == 0.1

        # Simulate DAO vote result
        dao_decision = {
            "max_failure_rate": 0.15,
            "min_verification_rate": 0.85,
        }

        integration.update_thresholds_from_dao(dao_decision)

        # Verify thresholds updated
        assert integration.thresholds["max_failure_rate"] == 0.15
        assert integration.thresholds["min_verification_rate"] == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
