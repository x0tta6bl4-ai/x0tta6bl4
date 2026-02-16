import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""
Unit tests for Threat Detection System.
Tests: init, detect different threat types, confidence calculation, severity mapping,
threat intelligence, filtering, mitigation, statistics.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.security.threat_detection import (Threat, ThreatDetector,
                                           ThreatSeverity, ThreatType)

# ===========================================================================
# Tests: Enums and Dataclass
# ===========================================================================


class TestEnumsAndDataclass:
    """Tests for ThreatType, ThreatSeverity, and Threat dataclass."""

    def test_threat_type_values(self):
        assert ThreatType.MALICIOUS_TRAFFIC.value == "malicious_traffic"
        assert ThreatType.UNAUTHORIZED_ACCESS.value == "unauthorized_access"
        assert ThreatType.DATA_EXFILTRATION.value == "data_exfiltration"
        assert ThreatType.DENIAL_OF_SERVICE.value == "denial_of_service"
        assert ThreatType.PRIVILEGE_ESCALATION.value == "privilege_escalation"
        assert ThreatType.MALWARE.value == "malware"
        assert ThreatType.SUSPICIOUS_BEHAVIOR.value == "suspicious_behavior"

    def test_threat_severity_values(self):
        assert ThreatSeverity.LOW.value == "low"
        assert ThreatSeverity.MEDIUM.value == "medium"
        assert ThreatSeverity.HIGH.value == "high"
        assert ThreatSeverity.CRITICAL.value == "critical"

    def test_threat_dataclass_defaults(self):
        t = Threat(
            threat_id="t1",
            threat_type=ThreatType.MALWARE,
            severity=ThreatSeverity.HIGH,
        )
        assert t.threat_id == "t1"
        assert t.source_ip is None
        assert t.target_ip is None
        assert t.node_id is None
        assert t.description == ""
        assert t.indicators == {}
        assert t.confidence == 0.0
        assert t.status == "detected"
        assert t.mitigation_action is None

    def test_threat_dataclass_full(self):
        t = Threat(
            threat_id="t2",
            threat_type=ThreatType.UNAUTHORIZED_ACCESS,
            severity=ThreatSeverity.CRITICAL,
            source_ip="1.2.3.4",
            target_ip="5.6.7.8",
            node_id="node-1",
            description="brute force",
            indicators={"failed_attempts": 100},
            confidence=0.95,
            status="mitigated",
            mitigation_action="block_ip",
        )
        assert t.source_ip == "1.2.3.4"
        assert t.confidence == 0.95
        assert t.status == "mitigated"


# ===========================================================================
# Tests: Initialization
# ===========================================================================


class TestThreatDetectorInit:
    """Tests for ThreatDetector initialization."""

    def test_defaults(self):
        td = ThreatDetector()
        assert td.detected_threats == []
        assert td.threat_patterns == {}
        assert td.threat_intelligence == {}
        assert td.anomaly_threshold == 0.7
        assert td.confidence_threshold == 0.6


# ===========================================================================
# Tests: Confidence Calculation
# ===========================================================================


class TestConfidenceCalculation:
    """Tests for _calculate_confidence."""

    def test_base_confidence_malware(self):
        td = ThreatDetector()
        c = td._calculate_confidence(ThreatType.MALWARE, {})
        assert c == 0.8

    def test_base_confidence_suspicious_behavior(self):
        td = ThreatDetector()
        c = td._calculate_confidence(ThreatType.SUSPICIOUS_BEHAVIOR, {})
        assert c == 0.4

    def test_base_confidence_malicious_traffic(self):
        td = ThreatDetector()
        c = td._calculate_confidence(ThreatType.MALICIOUS_TRAFFIC, {})
        assert c == 0.5

    def test_boost_failed_attempts(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {"failed_attempts": 10},
        )
        assert c == pytest.approx(0.6)

    def test_boost_unusual_pattern(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {"unusual_pattern": True},
        )
        assert c == pytest.approx(0.6)

    def test_boost_known_malicious(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {"known_malicious": True},
        )
        assert c == pytest.approx(0.7)

    def test_boost_anomaly_score(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {"anomaly_score": 0.9},
        )
        assert c == pytest.approx(0.6)

    def test_multiple_boosts(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {
                "failed_attempts": 10,
                "unusual_pattern": True,
                "known_malicious": True,
                "anomaly_score": 0.9,
            },
        )
        # 0.5 + 0.1 + 0.1 + 0.2 + 0.1 = 1.0
        assert c == pytest.approx(1.0)

    def test_confidence_capped_at_1(self):
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALWARE,  # base 0.8
            {
                "failed_attempts": 10,
                "unusual_pattern": True,
                "known_malicious": True,
                "anomaly_score": 0.9,
            },
        )
        assert c == pytest.approx(1.0)

    def test_failed_attempts_below_threshold(self):
        """failed_attempts <= 5 should not boost."""
        td = ThreatDetector()
        c = td._calculate_confidence(
            ThreatType.MALICIOUS_TRAFFIC,
            {"failed_attempts": 5},
        )
        assert c == pytest.approx(0.5)


# ===========================================================================
# Tests: Severity Determination
# ===========================================================================


class TestSeverityDetermination:
    """Tests for _determine_severity."""

    def test_critical_data_exfiltration(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.DATA_EXFILTRATION, {}, 0.9)
        assert s == ThreatSeverity.CRITICAL

    def test_critical_privilege_escalation(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.PRIVILEGE_ESCALATION, {}, 0.85)
        assert s == ThreatSeverity.CRITICAL

    def test_not_critical_if_low_confidence(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.DATA_EXFILTRATION, {}, 0.65)
        assert s == ThreatSeverity.MEDIUM

    def test_high_unauthorized_access(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.UNAUTHORIZED_ACCESS, {}, 0.75)
        assert s == ThreatSeverity.HIGH

    def test_high_denial_of_service(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.DENIAL_OF_SERVICE, {}, 0.8)
        assert s == ThreatSeverity.HIGH

    def test_medium_generic(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.MALWARE, {}, 0.65)
        assert s == ThreatSeverity.MEDIUM

    def test_low_severity(self):
        td = ThreatDetector()
        s = td._determine_severity(ThreatType.SUSPICIOUS_BEHAVIOR, {}, 0.5)
        assert s == ThreatSeverity.LOW


# ===========================================================================
# Tests: Detect Threat
# ===========================================================================


class TestDetectThreat:
    """Tests for detect_threat."""

    def test_detect_returns_threat_above_threshold(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            threat_type=ThreatType.MALWARE,
            indicators={"known_malicious": True},
            source_ip="1.2.3.4",
            description="test malware",
        )
        assert threat is not None
        assert isinstance(threat, Threat)
        assert threat.threat_type == ThreatType.MALWARE
        assert threat.source_ip == "1.2.3.4"
        assert threat.description == "test malware"
        assert threat.confidence >= td.confidence_threshold

    def test_detect_returns_none_below_threshold(self):
        td = ThreatDetector()
        # SUSPICIOUS_BEHAVIOR has base 0.4, below default threshold 0.6
        threat = td.detect_threat(
            threat_type=ThreatType.SUSPICIOUS_BEHAVIOR,
            indicators={},
        )
        assert threat is None

    def test_detect_appends_to_list(self):
        td = ThreatDetector()
        td.detect_threat(
            threat_type=ThreatType.UNAUTHORIZED_ACCESS,
            indicators={"failed_attempts": 10},
        )
        assert len(td.detected_threats) == 1

    def test_detect_multiple_threats(self):
        td = ThreatDetector()
        td.detect_threat(ThreatType.MALWARE, {"known_malicious": True})
        td.detect_threat(ThreatType.DENIAL_OF_SERVICE, {"failed_attempts": 20})
        assert len(td.detected_threats) == 2

    def test_detect_with_node_id(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            threat_type=ThreatType.MALWARE,
            indicators={},
            node_id="node-42",
        )
        assert threat.node_id == "node-42"

    def test_threat_id_format(self):
        td = ThreatDetector()
        with patch(
            "src.security.threat_detection.time.time", return_value=1234567890.0
        ):
            threat = td.detect_threat(
                threat_type=ThreatType.MALWARE,
                indicators={},
            )
        assert threat.threat_id == "threat-malware-1234567890.0"

    def test_threat_intel_boosts_confidence(self):
        td = ThreatDetector()
        td.add_threat_intelligence("1.2.3.4", {"reputation": "malicious"})
        threat = td.detect_threat(
            threat_type=ThreatType.UNAUTHORIZED_ACCESS,
            indicators={},
            source_ip="1.2.3.4",
        )
        # Base for UNAUTHORIZED_ACCESS is 0.6, + 0.2 from intel = 0.8
        assert threat is not None
        assert threat.confidence >= 0.8

    def test_threat_intel_added_to_indicators(self):
        td = ThreatDetector()
        td.add_threat_intelligence("1.2.3.4", {"reputation": "malicious"})
        threat = td.detect_threat(
            threat_type=ThreatType.MALWARE,
            indicators={"test": True},
            source_ip="1.2.3.4",
        )
        assert "source_intel" in threat.indicators


# ===========================================================================
# Tests: Threat Intelligence
# ===========================================================================


class TestThreatIntelligence:
    """Tests for add_threat_intelligence and _check_threat_intelligence."""

    def test_add_and_retrieve(self):
        td = ThreatDetector()
        td.add_threat_intelligence("1.2.3.4", {"category": "botnet"})
        assert "1.2.3.4" in td.threat_intelligence
        assert td.threat_intelligence["1.2.3.4"]["category"] == "botnet"

    def test_check_source_ip(self):
        td = ThreatDetector()
        td.add_threat_intelligence("10.0.0.1", {"score": 90})
        result = td._check_threat_intelligence("10.0.0.1", None)
        assert result is not None
        assert "source_intel" in result

    def test_check_target_ip(self):
        td = ThreatDetector()
        td.add_threat_intelligence("10.0.0.2", {"score": 80})
        result = td._check_threat_intelligence(None, "10.0.0.2")
        assert result is not None
        assert "target_intel" in result

    def test_check_both_ips(self):
        td = ThreatDetector()
        td.add_threat_intelligence("10.0.0.1", {"score": 90})
        td.add_threat_intelligence("10.0.0.2", {"score": 80})
        result = td._check_threat_intelligence("10.0.0.1", "10.0.0.2")
        assert "source_intel" in result
        assert "target_intel" in result

    def test_check_no_match(self):
        td = ThreatDetector()
        result = td._check_threat_intelligence("1.1.1.1", "2.2.2.2")
        assert result is None

    def test_check_none_ips(self):
        td = ThreatDetector()
        result = td._check_threat_intelligence(None, None)
        assert result is None

    def test_overwrite_intelligence(self):
        td = ThreatDetector()
        td.add_threat_intelligence("1.2.3.4", {"v": 1})
        td.add_threat_intelligence("1.2.3.4", {"v": 2})
        assert td.threat_intelligence["1.2.3.4"]["v"] == 2


# ===========================================================================
# Tests: Get Threats (Filtering)
# ===========================================================================


class TestGetThreats:
    """Tests for get_threats with various filters."""

    def _populate(self, td: ThreatDetector):
        """Add a set of threats with different types and severities."""
        now = datetime.utcnow()
        td.detected_threats = [
            Threat(
                threat_id="t1",
                threat_type=ThreatType.MALWARE,
                severity=ThreatSeverity.HIGH,
                timestamp=now,
            ),
            Threat(
                threat_id="t2",
                threat_type=ThreatType.DENIAL_OF_SERVICE,
                severity=ThreatSeverity.MEDIUM,
                timestamp=now,
            ),
            Threat(
                threat_id="t3",
                threat_type=ThreatType.MALWARE,
                severity=ThreatSeverity.CRITICAL,
                timestamp=now,
            ),
            Threat(
                threat_id="t4",
                threat_type=ThreatType.UNAUTHORIZED_ACCESS,
                severity=ThreatSeverity.LOW,
                timestamp=now - timedelta(days=2),
            ),
        ]

    def test_get_all(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats()
        assert len(threats) == 4

    def test_filter_by_type(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats(threat_type=ThreatType.MALWARE)
        assert len(threats) == 2
        assert all(t.threat_type == ThreatType.MALWARE for t in threats)

    def test_filter_by_severity(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats(severity=ThreatSeverity.HIGH)
        assert len(threats) == 1
        assert threats[0].threat_id == "t1"

    def test_filter_by_start_time(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats(start_time=datetime.utcnow() - timedelta(hours=1))
        # t4 is 2 days old, so should be excluded
        assert len(threats) == 3

    def test_filter_by_end_time(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats(end_time=datetime.utcnow() - timedelta(days=1))
        # Only t4 is old enough
        assert len(threats) == 1
        assert threats[0].threat_id == "t4"

    def test_filter_combined(self):
        td = ThreatDetector()
        self._populate(td)
        now = datetime.utcnow()
        threats = td.get_threats(
            threat_type=ThreatType.MALWARE,
            severity=ThreatSeverity.HIGH,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert len(threats) == 1
        assert threats[0].threat_id == "t1"

    def test_limit(self):
        td = ThreatDetector()
        self._populate(td)
        threats = td.get_threats(limit=2)
        assert len(threats) == 2

    def test_empty_list(self):
        td = ThreatDetector()
        threats = td.get_threats()
        assert threats == []


# ===========================================================================
# Tests: Mitigate Threat
# ===========================================================================


class TestMitigateThreat:
    """Tests for mitigate_threat."""

    def test_mitigate_existing(self):
        td = ThreatDetector()
        td.detected_threats.append(
            Threat(
                threat_id="t-100",
                threat_type=ThreatType.MALWARE,
                severity=ThreatSeverity.HIGH,
            )
        )
        result = td.mitigate_threat("t-100", "quarantine")
        assert result is True
        assert td.detected_threats[0].status == "mitigated"
        assert td.detected_threats[0].mitigation_action == "quarantine"

    def test_mitigate_nonexistent(self):
        td = ThreatDetector()
        result = td.mitigate_threat("does-not-exist", "block")
        assert result is False

    def test_mitigate_idempotent(self):
        td = ThreatDetector()
        td.detected_threats.append(
            Threat(
                threat_id="t-200",
                threat_type=ThreatType.DENIAL_OF_SERVICE,
                severity=ThreatSeverity.MEDIUM,
            )
        )
        td.mitigate_threat("t-200", "rate_limit")
        td.mitigate_threat("t-200", "block_ip")
        # Second call overwrites the action
        assert td.detected_threats[0].mitigation_action == "block_ip"


# ===========================================================================
# Tests: Statistics
# ===========================================================================


class TestThreatStatistics:
    """Tests for get_threat_statistics."""

    def test_empty_statistics(self):
        td = ThreatDetector()
        stats = td.get_threat_statistics()
        assert stats["total_threats"] == 0
        assert stats["by_type"] == {}
        assert stats["by_severity"] == {}
        assert stats["by_status"] == {}

    def test_statistics_with_threats(self):
        td = ThreatDetector()
        now = datetime.utcnow()
        td.detected_threats = [
            Threat("t1", ThreatType.MALWARE, ThreatSeverity.HIGH, timestamp=now),
            Threat("t2", ThreatType.MALWARE, ThreatSeverity.CRITICAL, timestamp=now),
            Threat(
                "t3",
                ThreatType.DENIAL_OF_SERVICE,
                ThreatSeverity.MEDIUM,
                timestamp=now,
                status="mitigated",
            ),
        ]
        stats = td.get_threat_statistics(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert stats["total_threats"] == 3
        assert stats["by_type"]["malware"] == 2
        assert stats["by_type"]["denial_of_service"] == 1
        assert stats["by_severity"]["high"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["medium"] == 1
        assert stats["by_status"]["detected"] == 2
        assert stats["by_status"]["mitigated"] == 1

    def test_statistics_default_time_range(self):
        td = ThreatDetector()
        now = datetime.utcnow()
        td.detected_threats.append(
            Threat("t1", ThreatType.MALWARE, ThreatSeverity.HIGH, timestamp=now)
        )
        stats = td.get_threat_statistics()
        assert stats["total_threats"] == 1
        assert "period" in stats
        assert "start" in stats["period"]
        assert "end" in stats["period"]

    def test_statistics_filters_old_threats(self):
        td = ThreatDetector()
        now = datetime.utcnow()
        td.detected_threats = [
            Threat(
                "old",
                ThreatType.MALWARE,
                ThreatSeverity.LOW,
                timestamp=now - timedelta(days=30),
            ),
            Threat("new", ThreatType.MALWARE, ThreatSeverity.LOW, timestamp=now),
        ]
        stats = td.get_threat_statistics(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert stats["total_threats"] == 1


# ===========================================================================
# Tests: Different Threat Types Detection
# ===========================================================================


class TestDifferentThreatTypes:
    """Test detection of each threat type."""

    def test_malicious_traffic(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.MALICIOUS_TRAFFIC,
            {"failed_attempts": 10, "unusual_pattern": True},
        )
        assert threat is not None
        assert threat.threat_type == ThreatType.MALICIOUS_TRAFFIC

    def test_unauthorized_access(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.UNAUTHORIZED_ACCESS,
            {"failed_attempts": 10},
        )
        assert threat is not None
        assert threat.threat_type == ThreatType.UNAUTHORIZED_ACCESS

    def test_data_exfiltration(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.DATA_EXFILTRATION,
            {},
        )
        assert threat is not None
        assert threat.threat_type == ThreatType.DATA_EXFILTRATION

    def test_denial_of_service(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.DENIAL_OF_SERVICE,
            {},
        )
        assert threat is not None
        assert threat.threat_type == ThreatType.DENIAL_OF_SERVICE

    def test_privilege_escalation(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.PRIVILEGE_ESCALATION,
            {},
        )
        assert threat is not None

    def test_malware(self):
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.MALWARE,
            {},
        )
        assert threat is not None
        assert threat.confidence == pytest.approx(0.8)

    def test_suspicious_behavior_rejected(self):
        """SUSPICIOUS_BEHAVIOR base confidence (0.4) is below threshold (0.6)."""
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.SUSPICIOUS_BEHAVIOR,
            {},
        )
        assert threat is None

    def test_suspicious_behavior_with_boosts(self):
        """SUSPICIOUS_BEHAVIOR can pass threshold with sufficient indicators."""
        td = ThreatDetector()
        threat = td.detect_threat(
            ThreatType.SUSPICIOUS_BEHAVIOR,
            {"failed_attempts": 10, "unusual_pattern": True, "known_malicious": True},
        )
        # 0.4 + 0.1 + 0.1 + 0.2 = 0.8, above threshold
        assert threat is not None
        assert threat.confidence >= 0.8
