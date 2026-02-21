"""Unit tests for PQC-MAPE-K Integration."""
import os
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.pqc_mapek_integration import (
    PQCAnomalyType,
    PQCAnomaly,
    PQCPrometheusMetrics,
    PQCMAPEKIntegration,
    start_pqc_monitoring_thread,
)


class TestPQCAnomalyType:
    def test_values(self):
        assert PQCAnomalyType.VERIFICATION_FAILED.value == "verification_failed"
        assert PQCAnomalyType.UNKNOWN_PUBKEY.value == "unknown_pubkey"
        assert PQCAnomalyType.SESSION_EXPIRED.value == "session_expired"
        assert PQCAnomalyType.HIGH_FAILURE_RATE.value == "high_failure_rate"
        assert PQCAnomalyType.REPLAY_ATTACK.value == "replay_attack"


class TestPQCAnomaly:
    def test_defaults(self):
        a = PQCAnomaly(anomaly_type=PQCAnomalyType.VERIFICATION_FAILED, session_id="s1")
        assert a.anomaly_type == PQCAnomalyType.VERIFICATION_FAILED
        assert a.session_id == "s1"
        assert a.severity == "medium"
        assert a.pubkey_id is None
        assert isinstance(a.timestamp, float)
        assert isinstance(a.details, dict)

    def test_custom(self):
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.REPLAY_ATTACK,
            session_id="s2",
            pubkey_id="pk1",
            severity="critical",
            details={"ip": "1.2.3.4"},
        )
        assert a.pubkey_id == "pk1"
        assert a.severity == "critical"
        assert a.details["ip"] == "1.2.3.4"


class TestPQCPrometheusMetrics:
    def test_disabled_metrics(self):
        m = PQCPrometheusMetrics.__new__(PQCPrometheusMetrics)
        m._enabled = False
        # All methods should be no-ops
        m.record_verification(True, 0.01)
        m.record_anomaly(PQCAnomalyType.VERIFICATION_FAILED)
        m.record_event_received()
        m.update_session_count(5)
        m.update_pubkey_count(3)
        m.update_rates(0.9, 0.1)


class TestPQCMAPEKIntegrationInit:
    def test_default_init(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        assert integ.daemon is None
        assert integ.metrics._enabled is False
        assert integ.consecutive_failures == 0
        assert integ.anomaly_history == []

    def test_custom_thresholds(self):
        integ = PQCMAPEKIntegration(
            thresholds={"max_failure_rate": 0.2},
            enable_metrics=False,
        )
        assert integ.thresholds["max_failure_rate"] == 0.2
        # Defaults should still be present
        assert integ.thresholds["consecutive_failures_alert"] == 5

    def test_with_daemon(self):
        daemon = MagicMock()
        integ = PQCMAPEKIntegration(pqc_daemon=daemon, enable_metrics=False)
        assert integ.daemon is daemon

    def test_with_custom_metrics(self):
        metrics = MagicMock()
        integ = PQCMAPEKIntegration(metrics=metrics)
        assert integ.metrics is metrics


class TestCallbacks:
    def test_set_alert_callback(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        cb = MagicMock()
        integ.set_mapek_alert_callback(cb)
        assert integ._mapek_alert_callback is cb

    def test_set_action_callback(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        cb = MagicMock()
        integ.set_mapek_action_callback(cb)
        assert integ._mapek_action_callback is cb


class TestHandleDaemonAnomaly:
    def test_unknown_pubkey(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.handle_daemon_anomaly("unknown_pubkey", {
            "session_id": "abc123",
            "pubkey_id": "pk456",
        })
        assert len(integ.anomaly_history) == 1
        assert integ.anomaly_history[0].anomaly_type == PQCAnomalyType.UNKNOWN_PUBKEY

    def test_verification_failed(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.handle_daemon_anomaly("verification_failed", {"session_id": "s1"})
        assert integ.consecutive_failures == 1

    def test_unknown_event_type_defaults_to_verification_failed(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.handle_daemon_anomaly("weird_event", {"session_id": "s1"})
        assert integ.anomaly_history[0].anomaly_type == PQCAnomalyType.VERIFICATION_FAILED


class TestProcessAnomaly:
    def test_trims_old_history(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        old = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="old",
            timestamp=time.time() - 7200,  # 2 hours ago
        )
        integ.anomaly_history.append(old)
        integ._process_anomaly(PQCAnomaly(
            anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY, session_id="new"
        ))
        # Old entry should be trimmed
        assert all(a.session_id != "old" for a in integ.anomaly_history)

    def test_consecutive_failures_reset_on_non_verification(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.consecutive_failures = 3
        integ._process_anomaly(PQCAnomaly(
            anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY, session_id="s1"
        ))
        assert integ.consecutive_failures == 0


class TestShouldEscalate:
    def test_high_severity(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="s1", severity="high"
        )
        assert integ._should_escalate(a) is True

    def test_consecutive_failures(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.consecutive_failures = 5
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="s1", severity="medium"
        )
        assert integ._should_escalate(a) is True

    def test_no_escalation(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY,
            session_id="s1", severity="medium"
        )
        assert integ._should_escalate(a) is False

    def test_failure_rate_escalation(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        now = time.time()
        # Add many recent verifications
        integ._recent_verifications = [(now, False)] * 20
        # Add many failure anomalies
        for _ in range(5):
            integ.anomaly_history.append(PQCAnomaly(
                anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
                session_id="s1", timestamp=now
            ))
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="s1", severity="medium"
        )
        assert integ._should_escalate(a) is True


class TestEscalateToMapek:
    def test_calls_alert_callback(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        alert_cb = MagicMock()
        integ.set_mapek_alert_callback(alert_cb)
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="s1"
        )
        integ._escalate_to_mapek(a)
        alert_cb.assert_called_once_with(a)

    def test_calls_action_callback(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        action_cb = MagicMock()
        integ.set_mapek_action_callback(action_cb)
        a = PQCAnomaly(
            anomaly_type=PQCAnomalyType.VERIFICATION_FAILED,
            session_id="s1"
        )
        integ._escalate_to_mapek(a)
        assert action_cb.called
        assert action_cb.call_args[0][0] == "invalidate_session"


class TestSuggestRemediation:
    def test_verification_failed(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        a = PQCAnomaly(anomaly_type=PQCAnomalyType.VERIFICATION_FAILED, session_id="s1")
        actions = integ._suggest_remediation(a)
        assert any(a["type"] == "invalidate_session" for a in actions)

    def test_verification_failed_with_consecutive(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.consecutive_failures = 5
        a = PQCAnomaly(anomaly_type=PQCAnomalyType.VERIFICATION_FAILED, session_id="s1")
        actions = integ._suggest_remediation(a)
        assert any(a["type"] == "rotate_keys" for a in actions)

    def test_unknown_pubkey(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        a = PQCAnomaly(anomaly_type=PQCAnomalyType.UNKNOWN_PUBKEY, session_id="s1", pubkey_id="pk1")
        actions = integ._suggest_remediation(a)
        assert any(a["type"] == "request_key_registration" for a in actions)

    def test_replay_attack(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        a = PQCAnomaly(anomaly_type=PQCAnomalyType.REPLAY_ATTACK, session_id="s1")
        actions = integ._suggest_remediation(a)
        assert any(a["type"] == "block_session" for a in actions)
        assert any(a["type"] == "alert_security" for a in actions)


class TestRecordVerification:
    def test_success(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.record_verification(True, 0.01)
        assert len(integ._recent_verifications) == 1

    def test_failure_triggers_rate_check(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        # Record many failures to trigger high failure rate
        for _ in range(20):
            integ.record_verification(False)
        # Should have generated a HIGH_FAILURE_RATE anomaly
        assert any(
            a.anomaly_type == PQCAnomalyType.HIGH_FAILURE_RATE
            for a in integ.anomaly_history
        )

    def test_success_resets_consecutive(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.consecutive_failures = 3
        integ.record_verification(True)
        assert integ.consecutive_failures == 0

    def test_trims_window(self):
        integ = PQCMAPEKIntegration(
            thresholds={"anomaly_window_seconds": 1},
            enable_metrics=False,
        )
        integ._recent_verifications = [(time.time() - 10, True)]
        integ.record_verification(True)
        # Old entry outside 1s window should be trimmed
        assert len(integ._recent_verifications) == 1


class TestGetMetricsForMapek:
    def test_no_daemon(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        assert integ.get_metrics_for_mapek() == {}

    def test_with_daemon(self):
        daemon = MagicMock()
        daemon.get_stats.return_value = {
            "events_received": 100,
            "verifications_success": 90,
            "verifications_failed": 10,
            "unknown_pubkey": 2,
            "active_sessions": 5,
            "registered_pubkeys": 3,
        }
        integ = PQCMAPEKIntegration(pqc_daemon=daemon, enable_metrics=False)
        m = integ.get_metrics_for_mapek()
        assert m["pqc_events_received"] == 100
        assert m["pqc_success_rate"] == 0.9
        assert m["pqc_failure_rate"] == 0.1


class TestSyncDaemonMetrics:
    def test_no_daemon(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.sync_daemon_metrics()  # Should not raise

    def test_with_daemon(self):
        daemon = MagicMock()
        daemon.get_stats.return_value = {"active_sessions": 5, "registered_pubkeys": 3}
        metrics = MagicMock()
        metrics._enabled = True
        integ = PQCMAPEKIntegration(pqc_daemon=daemon, metrics=metrics)
        integ.sync_daemon_metrics()
        metrics.update_session_count.assert_called_once_with(5)
        metrics.update_pubkey_count.assert_called_once_with(3)


class TestUpdateThresholdsFromDAO:
    def test_update_existing(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.update_thresholds_from_dao({"max_failure_rate": 0.2})
        assert integ.thresholds["max_failure_rate"] == 0.2

    def test_ignore_unknown(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.update_thresholds_from_dao({"unknown_key": 999})
        assert "unknown_key" not in integ.thresholds


class TestStartMonitoringThread:
    def test_starts_and_stops(self):
        integ = PQCMAPEKIntegration(enable_metrics=False)
        integ.daemon = MagicMock()
        integ.daemon.get_stats.return_value = {}
        stop = threading.Event()
        t = start_pqc_monitoring_thread(integ, interval=0.05, stop_event=stop)
        time.sleep(0.15)
        stop.set()
        t.join(timeout=1)
        assert not t.is_alive()
