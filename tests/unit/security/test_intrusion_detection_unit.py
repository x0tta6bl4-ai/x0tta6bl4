"""
Unit tests for IntrusionDetectionSystem.

Tests cover initialization, confidence calculation, severity determination,
behavioral baselines, alert filtering, incident response, and statistics.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.security.intrusion_detection import (IntrusionAlert,
                                              IntrusionDetectionSystem,
                                              IntrusionSeverity, IntrusionType)


class TestIntrusionAlert:
    """Tests for the IntrusionAlert dataclass."""

    def test_alert_defaults(self):
        alert = IntrusionAlert(
            alert_id="test-001",
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            severity=IntrusionSeverity.LOW,
        )
        assert alert.alert_id == "test-001"
        assert alert.intrusion_type == IntrusionType.NETWORK_INTRUSION
        assert alert.severity == IntrusionSeverity.LOW
        assert isinstance(alert.timestamp, datetime)
        assert alert.source_ip is None
        assert alert.target_ip is None
        assert alert.node_id is None
        assert alert.description == ""
        assert alert.indicators == {}
        assert alert.confidence == 0.0
        assert alert.status == "alert"
        assert alert.response_action is None

    def test_alert_with_all_fields(self):
        ts = datetime(2026, 1, 1)
        alert = IntrusionAlert(
            alert_id="test-002",
            intrusion_type=IntrusionType.DATA_BREACH,
            severity=IntrusionSeverity.CRITICAL,
            timestamp=ts,
            source_ip="10.0.0.1",
            target_ip="10.0.0.2",
            node_id="node-1",
            description="Data exfiltration detected",
            indicators={"known_attack_pattern": True},
            confidence=0.95,
            status="confirmed",
            response_action="isolate_node",
        )
        assert alert.timestamp == ts
        assert alert.source_ip == "10.0.0.1"
        assert alert.target_ip == "10.0.0.2"
        assert alert.node_id == "node-1"
        assert alert.description == "Data exfiltration detected"
        assert alert.indicators == {"known_attack_pattern": True}
        assert alert.confidence == 0.95
        assert alert.status == "confirmed"
        assert alert.response_action == "isolate_node"


class TestIntrusionDetectionSystem:
    """Tests for the IntrusionDetectionSystem class."""

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    def test_default_initialization(self):
        ids = IntrusionDetectionSystem()
        assert ids.alerts == []
        assert ids.behavioral_baselines == {}
        assert len(ids.detection_rules) == 4
        assert ids.anomaly_threshold == 0.75
        assert ids.confidence_threshold == 0.65

    def test_default_rules_content(self):
        ids = IntrusionDetectionSystem()
        rule_names = [r["name"] for r in ids.detection_rules]
        assert "Port Scan Detection" in rule_names
        assert "Brute Force Detection" in rule_names
        assert "Unusual Traffic Pattern" in rule_names
        assert "Data Exfiltration" in rule_names

    # ------------------------------------------------------------------ #
    # detect_intrusion - confidence below threshold returns None
    # ------------------------------------------------------------------ #

    def test_detect_intrusion_low_confidence_returns_none(self):
        """Base confidence is 0.5 with no boosting indicators -- below 0.65 threshold."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={},
            source_ip="10.0.0.1",
            target_ip="10.0.0.2",
        )
        assert result is None
        assert len(ids.alerts) == 0

    def test_detect_intrusion_just_below_threshold_returns_none(self):
        """known_attack_pattern alone gives 0.5 + 0.2 = 0.7, but without it only 0.6."""
        ids = IntrusionDetectionSystem()
        # Only multiple_indicators: 0.5 + 0.1 = 0.6 < 0.65
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"multiple_indicators": True},
        )
        assert result is None

    # ------------------------------------------------------------------ #
    # detect_intrusion - reaching threshold returns alert
    # ------------------------------------------------------------------ #

    def test_detect_intrusion_known_attack_pattern_reaches_threshold(self):
        """known_attack_pattern: 0.5 + 0.2 = 0.7 >= 0.65."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
            source_ip="192.168.1.100",
            target_ip="192.168.1.1",
            node_id="node-a",
            description="Port scan detected",
        )
        assert result is not None
        assert isinstance(result, IntrusionAlert)
        assert result.intrusion_type == IntrusionType.NETWORK_INTRUSION
        assert result.confidence == 0.7
        assert result.source_ip == "192.168.1.100"
        assert result.target_ip == "192.168.1.1"
        assert result.node_id == "node-a"
        assert result.description == "Port scan detected"
        assert result.status == "alert"
        assert len(ids.alerts) == 1

    def test_detect_intrusion_known_pattern_plus_multiple_indicators(self):
        """known_attack_pattern + multiple_indicators: 0.5 + 0.2 + 0.1 = ~0.8."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
            },
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.8)

    def test_detect_intrusion_all_indicator_boosts(self):
        """All boosts: 0.5 + 0.2 + 0.1 + 0.1 = 0.9."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
                "correlation_score": 0.85,
            },
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.9)

    def test_detect_intrusion_confidence_capped_at_one(self):
        """Confidence should never exceed 1.0."""
        ids = IntrusionDetectionSystem()
        # Set up a baseline that will cause anomaly boost
        ids.behavioral_baselines["node-x"] = {
            "avg_traffic": 100,
            "avg_connections": 10,
            "last_updated": datetime.utcnow(),
        }
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
                "correlation_score": 0.9,
                "traffic_volume": 500,  # 5x baseline => +0.3 anomaly
                "connections": 100,  # 10x baseline => +0.2 anomaly
            },
            node_id="node-x",
        )
        assert result is not None
        assert result.confidence <= 1.0

    # ------------------------------------------------------------------ #
    # Severity determination
    # ------------------------------------------------------------------ #

    def test_severity_data_breach_high_confidence_is_critical(self):
        """DATA_BREACH with confidence > 0.8 should be CRITICAL."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.DATA_BREACH,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
                "correlation_score": 0.85,
            },
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.9)
        assert result.severity == IntrusionSeverity.CRITICAL

    def test_severity_data_breach_moderate_confidence_is_medium(self):
        """DATA_BREACH with confidence 0.7 (not > 0.8) falls through to MEDIUM."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.DATA_BREACH,
            indicators={"known_attack_pattern": True},
        )
        assert result is not None
        assert result.confidence == 0.7
        assert result.severity == IntrusionSeverity.MEDIUM

    def test_severity_unauthorized_access_high_confidence_is_high(self):
        """UNAUTHORIZED_ACCESS with confidence > 0.7 should be HIGH."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.UNAUTHORIZED_ACCESS,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
            },
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.8)
        assert result.severity == IntrusionSeverity.HIGH

    def test_severity_malware_high_confidence_is_high(self):
        """MALWARE_INFECTION with confidence > 0.7 should be HIGH."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.MALWARE_INFECTION,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
            },
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.8)
        assert result.severity == IntrusionSeverity.HIGH

    def test_severity_network_intrusion_moderate_confidence_is_medium(self):
        """NETWORK_INTRUSION with confidence > 0.65 should be MEDIUM."""
        ids = IntrusionDetectionSystem()
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        assert result is not None
        assert result.confidence == 0.7
        assert result.severity == IntrusionSeverity.MEDIUM

    def test_severity_low_when_confidence_at_boundary(self):
        """_determine_severity returns LOW when confidence <= 0.65."""
        ids = IntrusionDetectionSystem()
        severity = ids._determine_severity(
            IntrusionType.NETWORK_INTRUSION,
            {},
            0.65,
        )
        # confidence > 0.65 is the condition, so 0.65 exactly => LOW
        assert severity == IntrusionSeverity.LOW

    # ------------------------------------------------------------------ #
    # Behavioral baseline
    # ------------------------------------------------------------------ #

    def test_update_behavioral_baseline_creates_new(self):
        ids = IntrusionDetectionSystem()
        ids.update_behavioral_baseline(
            "node-1",
            {
                "traffic_volume": 1000,
                "connections": 50,
            },
        )
        assert "node-1" in ids.behavioral_baselines
        baseline = ids.behavioral_baselines["node-1"]
        assert baseline["avg_traffic"] == 1000
        assert baseline["avg_connections"] == 50
        assert "last_updated" in baseline

    def test_update_behavioral_baseline_ema_update(self):
        """Second update applies exponential moving average with alpha=0.1."""
        ids = IntrusionDetectionSystem()
        ids.update_behavioral_baseline(
            "node-1",
            {
                "traffic_volume": 1000,
                "connections": 50,
            },
        )
        ids.update_behavioral_baseline(
            "node-1",
            {
                "traffic_volume": 2000,
                "connections": 100,
            },
        )
        baseline = ids.behavioral_baselines["node-1"]
        # EMA: alpha * new + (1-alpha) * old
        expected_traffic = 0.1 * 2000 + 0.9 * 1000  # 1100
        expected_connections = 0.1 * 100 + 0.9 * 50  # 55
        assert baseline["avg_traffic"] == pytest.approx(expected_traffic)
        assert baseline["avg_connections"] == pytest.approx(expected_connections)

    def test_update_behavioral_baseline_missing_metrics(self):
        """Missing metric keys default to 0."""
        ids = IntrusionDetectionSystem()
        ids.update_behavioral_baseline("node-1", {})
        baseline = ids.behavioral_baselines["node-1"]
        assert baseline["avg_traffic"] == 0
        assert baseline["avg_connections"] == 0

    # ------------------------------------------------------------------ #
    # Behavioral baseline anomaly boosts confidence
    # ------------------------------------------------------------------ #

    def test_detect_intrusion_with_baseline_anomaly_boosts_confidence(self):
        """Traffic anomaly vs baseline should add to confidence via _compare_to_baseline."""
        ids = IntrusionDetectionSystem()
        ids.behavioral_baselines["node-1"] = {
            "avg_traffic": 100,
            "avg_connections": 10,
            "last_updated": datetime.utcnow(),
        }
        # traffic_volume 300 / avg 100 = 3.0 (> 2.0 => +0.3)
        # No connections anomaly
        # Base 0.5 + anomaly 0.3*0.3 = 0.59 -- still below threshold
        # Add known_attack_pattern for +0.2 => 0.79
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={
                "traffic_volume": 300,
                "known_attack_pattern": True,
            },
            node_id="node-1",
        )
        assert result is not None
        # 0.5 + (0.3 * 0.3) + 0.2 = 0.79
        assert result.confidence == pytest.approx(0.79)

    def test_detect_intrusion_with_both_traffic_and_connection_anomaly(self):
        """Both traffic and connection anomalies should stack."""
        ids = IntrusionDetectionSystem()
        ids.behavioral_baselines["node-1"] = {
            "avg_traffic": 100,
            "avg_connections": 10,
            "last_updated": datetime.utcnow(),
        }
        # traffic 500/100 = 5.0 > 2.0 => anomaly += 0.3
        # connections 40/10 = 4.0 > 3.0 => anomaly += 0.2
        # anomaly total = 0.5, confidence += 0.5 * 0.3 = 0.15
        # base 0.5 + 0.15 = 0.65 -- still not >= 0.65 threshold (< means below)
        # Actually 0.65 < 0.65 is False, so it passes the threshold check
        result = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={
                "traffic_volume": 500,
                "connections": 40,
            },
            node_id="node-1",
        )
        assert result is not None
        assert result.confidence == pytest.approx(0.65)

    def test_compare_to_baseline_no_anomaly(self):
        """Normal traffic ratios should not boost anomaly score."""
        ids = IntrusionDetectionSystem()
        anomaly = ids._compare_to_baseline(
            {"traffic_volume": 120, "connections": 12},
            {"avg_traffic": 100, "avg_connections": 10},
        )
        # 120/100 = 1.2 (not > 2.0 or < 0.5)
        # 12/10 = 1.2 (not > 3.0)
        assert anomaly == 0.0

    def test_compare_to_baseline_low_traffic_also_anomalous(self):
        """Traffic ratio < 0.5 is also flagged as anomalous."""
        ids = IntrusionDetectionSystem()
        anomaly = ids._compare_to_baseline(
            {"traffic_volume": 30},
            {"avg_traffic": 100, "avg_connections": 10},
        )
        # 30/100 = 0.3 < 0.5 => +0.3
        assert anomaly == pytest.approx(0.3)

    # ------------------------------------------------------------------ #
    # get_alerts filtering
    # ------------------------------------------------------------------ #

    def _create_ids_with_alerts(self):
        """Helper to create an IDS with several alerts for filtering tests."""
        ids = IntrusionDetectionSystem()
        # Alert 1: NETWORK_INTRUSION, MEDIUM
        ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        # Alert 2: DATA_BREACH, CRITICAL
        ids.detect_intrusion(
            intrusion_type=IntrusionType.DATA_BREACH,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
                "correlation_score": 0.85,
            },
        )
        # Alert 3: UNAUTHORIZED_ACCESS, HIGH
        ids.detect_intrusion(
            intrusion_type=IntrusionType.UNAUTHORIZED_ACCESS,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
            },
        )
        return ids

    def test_get_alerts_no_filter(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts()
        assert len(alerts) == 3

    def test_get_alerts_filter_by_type(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts(intrusion_type=IntrusionType.DATA_BREACH)
        assert len(alerts) == 1
        assert alerts[0].intrusion_type == IntrusionType.DATA_BREACH

    def test_get_alerts_filter_by_severity(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts(severity=IntrusionSeverity.HIGH)
        assert len(alerts) == 1
        assert alerts[0].severity == IntrusionSeverity.HIGH

    def test_get_alerts_filter_by_type_and_severity(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            severity=IntrusionSeverity.MEDIUM,
        )
        assert len(alerts) == 1

    def test_get_alerts_filter_no_match(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts(severity=IntrusionSeverity.LOW)
        assert len(alerts) == 0

    def test_get_alerts_limit(self):
        ids = self._create_ids_with_alerts()
        alerts = ids.get_alerts(limit=2)
        assert len(alerts) == 2

    def test_get_alerts_filter_by_time(self):
        ids = IntrusionDetectionSystem()
        ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        now = datetime.utcnow()
        # Filter with start_time in the future should exclude current alerts
        alerts = ids.get_alerts(start_time=now + timedelta(hours=1))
        assert len(alerts) == 0
        # Filter with end_time in the past should exclude current alerts
        alerts = ids.get_alerts(end_time=now - timedelta(hours=1))
        assert len(alerts) == 0
        # Filter with a window that includes now
        alerts = ids.get_alerts(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert len(alerts) == 1

    # ------------------------------------------------------------------ #
    # respond_to_intrusion
    # ------------------------------------------------------------------ #

    def test_respond_to_intrusion_sets_status_and_action(self):
        ids = IntrusionDetectionSystem()
        alert = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        assert alert is not None

        result = ids.respond_to_intrusion(alert.alert_id, "block_ip")
        assert result is True
        assert alert.status == "confirmed"
        assert alert.response_action == "block_ip"

    def test_respond_to_intrusion_unknown_alert_returns_false(self):
        ids = IntrusionDetectionSystem()
        result = ids.respond_to_intrusion("nonexistent-id", "block_ip")
        assert result is False

    def test_respond_to_intrusion_updates_correct_alert(self):
        """When multiple alerts exist, only the targeted one is updated."""
        ids = IntrusionDetectionSystem()
        alert1 = ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        alert2 = ids.detect_intrusion(
            intrusion_type=IntrusionType.DATA_BREACH,
            indicators={
                "known_attack_pattern": True,
                "multiple_indicators": True,
                "correlation_score": 0.85,
            },
        )
        assert alert1 is not None
        assert alert2 is not None

        ids.respond_to_intrusion(alert2.alert_id, "isolate_node")
        assert alert1.status == "alert"
        assert alert1.response_action is None
        assert alert2.status == "confirmed"
        assert alert2.response_action == "isolate_node"

    # ------------------------------------------------------------------ #
    # get_statistics
    # ------------------------------------------------------------------ #

    def test_get_statistics_empty(self):
        ids = IntrusionDetectionSystem()
        stats = ids.get_statistics()
        assert stats["total_alerts"] == 0
        assert stats["by_type"] == {}
        assert stats["by_severity"] == {}
        assert stats["by_status"] == {}
        assert "period" in stats
        assert "start" in stats["period"]
        assert "end" in stats["period"]

    def test_get_statistics_counts(self):
        ids = self._create_ids_with_alerts()
        stats = ids.get_statistics()
        assert stats["total_alerts"] == 3

        assert stats["by_type"]["network_intrusion"] == 1
        assert stats["by_type"]["data_breach"] == 1
        assert stats["by_type"]["unauthorized_access"] == 1

        assert stats["by_severity"]["medium"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["high"] == 1

        assert stats["by_status"]["alert"] == 3

    def test_get_statistics_after_response(self):
        ids = self._create_ids_with_alerts()
        alert = ids.alerts[0]
        ids.respond_to_intrusion(alert.alert_id, "block_ip")
        stats = ids.get_statistics()
        assert stats["by_status"]["confirmed"] == 1
        assert stats["by_status"]["alert"] == 2

    def test_get_statistics_respects_time_window(self):
        ids = IntrusionDetectionSystem()
        ids.detect_intrusion(
            intrusion_type=IntrusionType.NETWORK_INTRUSION,
            indicators={"known_attack_pattern": True},
        )
        # Query for a time window entirely in the past
        past_start = datetime.utcnow() - timedelta(days=10)
        past_end = datetime.utcnow() - timedelta(days=9)
        stats = ids.get_statistics(start_time=past_start, end_time=past_end)
        assert stats["total_alerts"] == 0

    # ------------------------------------------------------------------ #
    # Enum values
    # ------------------------------------------------------------------ #

    def test_intrusion_type_values(self):
        assert IntrusionType.NETWORK_INTRUSION.value == "network_intrusion"
        assert IntrusionType.HOST_INTRUSION.value == "host_intrusion"
        assert IntrusionType.APPLICATION_INTRUSION.value == "application_intrusion"
        assert IntrusionType.DATA_BREACH.value == "data_breach"
        assert IntrusionType.UNAUTHORIZED_ACCESS.value == "unauthorized_access"
        assert IntrusionType.MALWARE_INFECTION.value == "malware_infection"

    def test_intrusion_severity_values(self):
        assert IntrusionSeverity.LOW.value == "low"
        assert IntrusionSeverity.MEDIUM.value == "medium"
        assert IntrusionSeverity.HIGH.value == "high"
        assert IntrusionSeverity.CRITICAL.value == "critical"
