import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""
Unit tests for DDoS Detection System.
Tests: init defaults, traffic analysis (normal vs attack), blocking/unblocking,
severity classification, statistics, baseline learning, volumetric/protocol/application attacks.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.security.ddos_detection import (AttackSeverity, DDoSAlert,
                                         DDoSDetector, DDoSType,
                                         TrafficBaseline)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fill_baseline(detector: DDoSDetector, n_packets: int = 120, pps_rate: float = 1.0):
    """
    Feed enough packets through *learning mode* so the baseline is established.
    Each packet is spaced 1/pps_rate seconds apart.  We mock time so that
    all packets fall within the detection window.
    """
    base_time = 1_000_000.0
    base_dt = datetime(2025, 6, 1, 12, 0, 0)

    for i in range(n_packets):
        current_time = base_time + (i / pps_rate)
        current_dt = base_dt + timedelta(seconds=i / pps_rate)
        with (
            patch("src.security.ddos_detection.time.time", return_value=current_time),
            patch("src.security.ddos_detection.datetime") as mock_dt,
        ):
            mock_dt.utcnow.return_value = current_dt
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            detector.analyze_traffic(
                source_ip="10.0.0.1",
                target_ip="10.0.0.100",
                target_port=8080,
                packet_size=500,
                protocol="tcp",
            )

    # After enough samples the learning phase should have ended
    assert not detector.baseline_learning, (
        f"Baseline still learning after {n_packets} packets "
        f"(samples={detector.baseline_samples})"
    )


# ===========================================================================
# Tests: Initialization
# ===========================================================================


class TestDDoSDetectorInit:
    """Tests for DDoSDetector initialization."""

    def test_default_values(self):
        detector = DDoSDetector()
        assert detector.detection_window == 60
        assert detector.threshold_multiplier == 3.0
        assert detector.baseline_learning is True
        assert detector.baseline_samples == 0
        assert len(detector.alerts) == 0
        assert len(detector.blocked_ips) == 0

    def test_custom_values(self):
        detector = DDoSDetector(detection_window=120, threshold_multiplier=5.0)
        assert detector.detection_window == 120
        assert detector.threshold_multiplier == 5.0

    def test_baseline_defaults(self):
        detector = DDoSDetector()
        assert detector.baseline.avg_packets_per_second == 0.0
        assert detector.baseline.avg_bandwidth_mbps == 0.0
        assert detector.baseline.peak_packets_per_second == 0.0


# ===========================================================================
# Tests: Enums and Dataclasses
# ===========================================================================


class TestEnumsAndDataclasses:
    """Tests for DDoSType, AttackSeverity, DDoSAlert, TrafficBaseline."""

    def test_ddos_type_values(self):
        assert DDoSType.VOLUMETRIC.value == "volumetric"
        assert DDoSType.PROTOCOL.value == "protocol"
        assert DDoSType.APPLICATION.value == "application"
        assert DDoSType.SLOWLORIS.value == "slowloris"
        assert DDoSType.UDP_FLOOD.value == "udp_flood"
        assert DDoSType.ICMP_FLOOD.value == "icmp_flood"

    def test_attack_severity_values(self):
        assert AttackSeverity.LOW.value == "low"
        assert AttackSeverity.MEDIUM.value == "medium"
        assert AttackSeverity.HIGH.value == "high"
        assert AttackSeverity.CRITICAL.value == "critical"

    def test_ddos_alert_defaults(self):
        alert = DDoSAlert(
            alert_id="test-1",
            attack_type=DDoSType.VOLUMETRIC,
            severity=AttackSeverity.HIGH,
        )
        assert alert.alert_id == "test-1"
        assert alert.source_ips == []
        assert alert.target_ip is None
        assert alert.target_port is None
        assert alert.traffic_rate == 0.0
        assert alert.bandwidth == 0.0
        assert alert.description == ""
        assert alert.mitigation_applied is False
        assert alert.mitigation_action is None

    def test_traffic_baseline_defaults(self):
        bl = TrafficBaseline()
        assert bl.avg_packets_per_second == 0.0
        assert bl.avg_bandwidth_mbps == 0.0
        assert bl.avg_connections == 0
        assert bl.peak_packets_per_second == 0.0
        assert bl.peak_bandwidth_mbps == 0.0


# ===========================================================================
# Tests: Baseline Learning
# ===========================================================================


class TestBaselineLearning:
    """Tests for the baseline learning phase."""

    def test_returns_none_during_learning(self):
        detector = DDoSDetector()
        result = detector.analyze_traffic(
            source_ip="10.0.0.1",
            target_ip="10.0.0.100",
            target_port=80,
            packet_size=500,
        )
        assert result is None
        assert detector.baseline_learning is True

    def test_no_update_with_few_samples(self):
        """Baseline should not update when < 100 traffic history entries."""
        detector = DDoSDetector()
        for _ in range(50):
            detector.analyze_traffic(
                source_ip="10.0.0.1",
                target_ip="10.0.0.100",
                target_port=80,
                packet_size=500,
            )
        assert detector.baseline_learning is True
        assert detector.baseline_samples == 0

    def test_learning_completes_after_enough_samples(self):
        detector = DDoSDetector(detection_window=200)
        _fill_baseline(detector, n_packets=200, pps_rate=2.0)
        assert not detector.baseline_learning
        assert detector.baseline_samples >= 10
        assert detector.baseline.avg_packets_per_second > 0

    def test_baseline_peak_tracking(self):
        detector = DDoSDetector(detection_window=200)
        _fill_baseline(detector, n_packets=200, pps_rate=2.0)
        assert detector.baseline.peak_packets_per_second > 0


# ===========================================================================
# Tests: Traffic Analysis - Normal vs Attack
# ===========================================================================


class TestTrafficAnalysis:
    """Tests for analyze_traffic under normal and attack conditions."""

    def _make_detector_past_baseline(self):
        """Create a detector that is past baseline learning with known baseline."""
        detector = DDoSDetector(detection_window=60, threshold_multiplier=3.0)
        detector.baseline_learning = False
        detector.baseline.avg_packets_per_second = 10.0
        detector.baseline.avg_bandwidth_mbps = 0.01
        return detector

    def test_normal_traffic_no_alert(self):
        """Traffic below threshold should not trigger an alert."""
        detector = self._make_detector_past_baseline()
        base_time = 2_000_000.0
        base_dt = datetime(2025, 7, 1, 12, 0, 0)

        # Send 10 packets in 60s window => 10/60 ~= 0.17 pps, well below threshold (30 pps)
        for i in range(10):
            t = base_time + i * 6  # 6s apart
            dt = base_dt + timedelta(seconds=i * 6)
            with (
                patch("src.security.ddos_detection.time.time", return_value=t),
                patch("src.security.ddos_detection.datetime") as mock_dt,
            ):
                mock_dt.utcnow.return_value = dt
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                result = detector.analyze_traffic(
                    source_ip="10.0.0.1",
                    target_ip="10.0.0.100",
                    target_port=80,
                    packet_size=500,
                )
        assert result is None
        assert len(detector.alerts) == 0

    def test_high_rate_triggers_alert(self):
        """Traffic well above threshold should trigger an alert."""
        detector = self._make_detector_past_baseline()
        base_time = 3_000_000.0
        base_dt = datetime(2025, 7, 1, 14, 0, 0)

        # Send 500 packets in < 1 second => ~500/60 = 8.3 pps in window
        # Actually we need rate > 30 pps (3x baseline of 10)
        # Send 2000 packets all at "now" so rate = 2000/60 ~= 33 pps
        alert = None
        for i in range(2000):
            t = base_time + i * 0.001  # clustered in ~2s
            dt = base_dt + timedelta(seconds=i * 0.001)
            with (
                patch("src.security.ddos_detection.time.time", return_value=t),
                patch("src.security.ddos_detection.datetime") as mock_dt,
            ):
                mock_dt.utcnow.return_value = dt
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                result = detector.analyze_traffic(
                    source_ip="192.168.1.100",
                    target_ip="10.0.0.100",
                    target_port=9999,
                    packet_size=1000,
                    protocol="tcp",
                )
                if result is not None:
                    alert = result

        assert alert is not None
        assert isinstance(alert, DDoSAlert)
        assert alert.attack_type == DDoSType.VOLUMETRIC  # port 9999, tcp
        assert len(detector.alerts) > 0

    def test_traffic_records_in_history(self):
        detector = DDoSDetector()
        detector.analyze_traffic("1.1.1.1", "2.2.2.2", 80, 100)
        assert len(detector.traffic_history) == 1
        assert detector.traffic_history[0]["source_ip"] == "1.1.1.1"

    def test_ip_traffic_tracked(self):
        detector = DDoSDetector()
        detector.analyze_traffic("5.5.5.5", "2.2.2.2", 80, 200)
        assert "5.5.5.5" in detector.ip_traffic
        assert len(detector.ip_traffic["5.5.5.5"]) == 1

    def test_port_traffic_tracked(self):
        detector = DDoSDetector()
        detector.analyze_traffic("5.5.5.5", "2.2.2.2", 443, 200)
        assert 443 in detector.port_traffic
        assert len(detector.port_traffic[443]) == 1


# ===========================================================================
# Tests: Attack Classification
# ===========================================================================


class TestAttackClassification:
    """Tests for _classify_attack (indirectly via analyze_traffic)."""

    def _detector_with_attack(
        self, protocol, target_port, packet_size=1000, n_packets=2000
    ):
        """Build a detector and push enough attack traffic to trigger an alert."""
        detector = DDoSDetector(detection_window=60, threshold_multiplier=3.0)
        detector.baseline_learning = False
        detector.baseline.avg_packets_per_second = 10.0
        detector.baseline.avg_bandwidth_mbps = 0.01

        base_time = 4_000_000.0
        base_dt = datetime(2025, 8, 1, 0, 0, 0)
        alert = None
        for i in range(n_packets):
            t = base_time + i * 0.001
            dt = base_dt + timedelta(seconds=i * 0.001)
            with (
                patch("src.security.ddos_detection.time.time", return_value=t),
                patch("src.security.ddos_detection.datetime") as mock_dt,
            ):
                mock_dt.utcnow.return_value = dt
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                result = detector.analyze_traffic(
                    source_ip="192.168.1.50",
                    target_ip="10.0.0.100",
                    target_port=target_port,
                    packet_size=packet_size,
                    protocol=protocol,
                )
                if result is not None:
                    alert = result
        return detector, alert

    def test_udp_flood(self):
        _, alert = self._detector_with_attack("udp", 53)
        assert alert is not None
        assert alert.attack_type == DDoSType.UDP_FLOOD

    def test_icmp_flood(self):
        _, alert = self._detector_with_attack("icmp", 0)
        assert alert is not None
        assert alert.attack_type == DDoSType.ICMP_FLOOD

    def test_application_layer(self):
        _, alert = self._detector_with_attack("tcp", 80, packet_size=1000)
        assert alert is not None
        assert alert.attack_type == DDoSType.APPLICATION

    def test_slowloris(self):
        """Small packets on HTTP port should be classified as slowloris."""
        _, alert = self._detector_with_attack("tcp", 443, packet_size=50)
        assert alert is not None
        assert alert.attack_type == DDoSType.SLOWLORIS

    def test_volumetric_non_http_tcp(self):
        _, alert = self._detector_with_attack("tcp", 9999, packet_size=1000)
        assert alert is not None
        assert alert.attack_type == DDoSType.VOLUMETRIC

    def test_application_on_8080(self):
        """Port 8080 should be treated as application layer."""
        _, alert = self._detector_with_attack("tcp", 8080, packet_size=1000)
        assert alert is not None
        assert alert.attack_type == DDoSType.APPLICATION


# ===========================================================================
# Tests: Severity Classification
# ===========================================================================


class TestSeverityClassification:
    """Tests for _determine_severity."""

    def test_critical_severity(self):
        detector = DDoSDetector()
        severity = detector._determine_severity(100.0, 10.0)
        assert severity == AttackSeverity.CRITICAL

    def test_high_severity(self):
        detector = DDoSDetector()
        severity = detector._determine_severity(60.0, 10.0)
        assert severity == AttackSeverity.HIGH

    def test_medium_severity(self):
        detector = DDoSDetector()
        severity = detector._determine_severity(35.0, 10.0)
        assert severity == AttackSeverity.MEDIUM

    def test_low_severity(self):
        detector = DDoSDetector()
        severity = detector._determine_severity(15.0, 10.0)
        assert severity == AttackSeverity.LOW

    def test_zero_threshold_returns_low(self):
        """If threshold_rate is 0, ratio is 0 -> LOW."""
        detector = DDoSDetector()
        severity = detector._determine_severity(100.0, 0.0)
        assert severity == AttackSeverity.LOW


# ===========================================================================
# Tests: Blocking / Unblocking
# ===========================================================================


class TestBlocking:
    """Tests for is_blocked and unblock_ip."""

    def test_is_blocked_false_by_default(self):
        detector = DDoSDetector()
        assert detector.is_blocked("1.2.3.4") is False

    def test_blocked_after_adding(self):
        detector = DDoSDetector()
        detector.blocked_ips.add("1.2.3.4")
        assert detector.is_blocked("1.2.3.4") is True

    def test_unblock_ip(self):
        detector = DDoSDetector()
        detector.blocked_ips.add("1.2.3.4")
        detector.unblock_ip("1.2.3.4")
        assert detector.is_blocked("1.2.3.4") is False

    def test_unblock_ip_not_present(self):
        """Unblocking an IP that is not blocked should not raise."""
        detector = DDoSDetector()
        detector.unblock_ip("9.9.9.9")  # no error
        assert not detector.is_blocked("9.9.9.9")

    def test_mitigation_blocks_source_ips(self):
        """When an alert is generated, source IPs should be blocked."""
        detector = DDoSDetector(detection_window=60, threshold_multiplier=3.0)
        detector.baseline_learning = False
        detector.baseline.avg_packets_per_second = 10.0
        detector.baseline.avg_bandwidth_mbps = 0.01

        base_time = 5_000_000.0
        base_dt = datetime(2025, 9, 1, 0, 0, 0)
        for i in range(2000):
            t = base_time + i * 0.001
            dt = base_dt + timedelta(seconds=i * 0.001)
            with (
                patch("src.security.ddos_detection.time.time", return_value=t),
                patch("src.security.ddos_detection.datetime") as mock_dt,
            ):
                mock_dt.utcnow.return_value = dt
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                detector.analyze_traffic(
                    "192.168.1.50", "10.0.0.100", 9999, 1000, "tcp"
                )

        assert detector.is_blocked("192.168.1.50")


# ===========================================================================
# Tests: Mitigation
# ===========================================================================


class TestMitigation:
    """Tests for _apply_mitigation side effects."""

    def test_slowloris_mitigation_action(self):
        alert = DDoSAlert(
            alert_id="test-sl",
            attack_type=DDoSType.SLOWLORIS,
            severity=AttackSeverity.HIGH,
            source_ips=["10.0.0.5"],
        )
        detector = DDoSDetector()
        detector._apply_mitigation(alert)
        assert alert.mitigation_applied is True
        assert alert.mitigation_action == "rate_limiting"

    def test_udp_flood_mitigation_action(self):
        alert = DDoSAlert(
            alert_id="test-uf",
            attack_type=DDoSType.UDP_FLOOD,
            severity=AttackSeverity.HIGH,
            source_ips=["10.0.0.6"],
        )
        detector = DDoSDetector()
        detector._apply_mitigation(alert)
        assert alert.mitigation_action == "protocol_filtering"

    def test_icmp_flood_mitigation_action(self):
        alert = DDoSAlert(
            alert_id="test-if",
            attack_type=DDoSType.ICMP_FLOOD,
            severity=AttackSeverity.MEDIUM,
            source_ips=["10.0.0.7"],
        )
        detector = DDoSDetector()
        detector._apply_mitigation(alert)
        assert alert.mitigation_action == "protocol_filtering"

    def test_volumetric_mitigation_action(self):
        alert = DDoSAlert(
            alert_id="test-vol",
            attack_type=DDoSType.VOLUMETRIC,
            severity=AttackSeverity.HIGH,
            source_ips=["10.0.0.8"],
        )
        detector = DDoSDetector()
        detector._apply_mitigation(alert)
        assert alert.mitigation_action == "ip_blocking"

    def test_mitigation_limits_to_10_ips(self):
        ips = [f"10.0.0.{i}" for i in range(20)]
        alert = DDoSAlert(
            alert_id="test-many",
            attack_type=DDoSType.VOLUMETRIC,
            severity=AttackSeverity.CRITICAL,
            source_ips=ips,
        )
        detector = DDoSDetector()
        detector._apply_mitigation(alert)
        assert len(detector.blocked_ips) == 10


# ===========================================================================
# Tests: Statistics
# ===========================================================================


class TestStatistics:
    """Tests for get_statistics."""

    def test_empty_statistics(self):
        detector = DDoSDetector()
        stats = detector.get_statistics()
        assert stats["total_alerts"] == 0
        assert stats["by_type"] == {}
        assert stats["by_severity"] == {}
        assert stats["blocked_ips"] == 0
        assert stats["baseline"]["learning"] is True

    def test_statistics_with_alerts(self):
        detector = DDoSDetector()
        now = datetime.utcnow()
        detector.alerts.append(
            DDoSAlert(
                alert_id="a1",
                attack_type=DDoSType.VOLUMETRIC,
                severity=AttackSeverity.HIGH,
                timestamp=now,
            )
        )
        detector.alerts.append(
            DDoSAlert(
                alert_id="a2",
                attack_type=DDoSType.VOLUMETRIC,
                severity=AttackSeverity.CRITICAL,
                timestamp=now,
            )
        )
        detector.alerts.append(
            DDoSAlert(
                alert_id="a3",
                attack_type=DDoSType.UDP_FLOOD,
                severity=AttackSeverity.HIGH,
                timestamp=now,
            )
        )
        detector.blocked_ips = {"1.1.1.1", "2.2.2.2"}

        stats = detector.get_statistics(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert stats["total_alerts"] == 3
        assert stats["by_type"]["volumetric"] == 2
        assert stats["by_type"]["udp_flood"] == 1
        assert stats["by_severity"]["high"] == 2
        assert stats["by_severity"]["critical"] == 1
        assert stats["blocked_ips"] == 2

    def test_statistics_filters_by_time(self):
        detector = DDoSDetector()
        old = datetime(2020, 1, 1)
        recent = datetime.utcnow()

        detector.alerts.append(
            DDoSAlert(
                alert_id="old1",
                attack_type=DDoSType.VOLUMETRIC,
                severity=AttackSeverity.LOW,
                timestamp=old,
            )
        )
        detector.alerts.append(
            DDoSAlert(
                alert_id="new1",
                attack_type=DDoSType.VOLUMETRIC,
                severity=AttackSeverity.LOW,
                timestamp=recent,
            )
        )

        stats = detector.get_statistics(
            start_time=recent - timedelta(hours=1),
            end_time=recent + timedelta(hours=1),
        )
        assert stats["total_alerts"] == 1

    def test_statistics_default_time_range(self):
        """When no time range given, defaults to last 24h."""
        detector = DDoSDetector()
        now = datetime.utcnow()
        detector.alerts.append(
            DDoSAlert(
                alert_id="a1",
                attack_type=DDoSType.APPLICATION,
                severity=AttackSeverity.MEDIUM,
                timestamp=now,
            )
        )
        stats = detector.get_statistics()
        assert stats["total_alerts"] == 1
        assert "period" in stats
        assert "start" in stats["period"]
        assert "end" in stats["period"]

    def test_statistics_baseline_info(self):
        detector = DDoSDetector()
        detector.baseline.avg_packets_per_second = 42.0
        detector.baseline.avg_bandwidth_mbps = 1.5
        stats = detector.get_statistics()
        assert stats["baseline"]["avg_packets_per_second"] == 42.0
        assert stats["baseline"]["avg_bandwidth_mbps"] == 1.5
