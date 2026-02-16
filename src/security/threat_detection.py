"""
Threat Detection

Provides anomaly detection for security threats, threat intelligence integration,
and automated response.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ThreatType(Enum):
    """Types of security threats"""

    MALICIOUS_TRAFFIC = "malicious_traffic"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    DENIAL_OF_SERVICE = "denial_of_service"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MALWARE = "malware"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"


class ThreatSeverity(Enum):
    """Threat severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Threat:
    """Represents a detected threat"""

    threat_id: str
    threat_type: ThreatType
    severity: ThreatSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    node_id: Optional[str] = None
    description: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0-1.0
    status: str = "detected"  # detected, investigating, mitigated, false_positive
    mitigation_action: Optional[str] = None


class ThreatDetector:
    """
    Detects security threats using anomaly detection and threat intelligence.

    Provides:
    - Anomaly detection for security
    - Threat intelligence integration
    - Automated response
    - Threat reporting
    """

    def __init__(self):
        self.detected_threats: List[Threat] = []
        self.threat_patterns: Dict[ThreatType, List[Dict[str, Any]]] = {}
        self.threat_intelligence: Dict[str, Any] = {}  # IP/domain -> threat info

        # Thresholds
        self.anomaly_threshold = 0.7
        self.confidence_threshold = 0.6

        logger.info("ThreatDetector initialized")

    def detect_threat(
        self,
        threat_type: ThreatType,
        indicators: Dict[str, Any],
        source_ip: Optional[str] = None,
        target_ip: Optional[str] = None,
        node_id: Optional[str] = None,
        description: str = "",
    ) -> Optional[Threat]:
        """
        Detect a security threat.

        Args:
            threat_type: Type of threat
            indicators: Threat indicators
            source_ip: Source IP address
            target_ip: Target IP address
            node_id: Node identifier
            description: Threat description

        Returns:
            Threat object if detected, None otherwise
        """
        # Calculate confidence
        confidence = self._calculate_confidence(threat_type, indicators)

        if confidence < self.confidence_threshold:
            logger.debug(f"Threat {threat_type.value} confidence too low: {confidence}")
            return None

        # Determine severity
        severity = self._determine_severity(threat_type, indicators, confidence)

        # Check threat intelligence
        threat_intel = self._check_threat_intelligence(source_ip, target_ip)
        if threat_intel:
            confidence = min(1.0, confidence + 0.2)  # Boost confidence
            indicators.update(threat_intel)

        # Create threat
        threat_id = f"threat-{threat_type.value}-{time.time()}"
        threat = Threat(
            threat_id=threat_id,
            threat_type=threat_type,
            severity=severity,
            source_ip=source_ip,
            target_ip=target_ip,
            node_id=node_id,
            description=description,
            indicators=indicators,
            confidence=confidence,
        )

        self.detected_threats.append(threat)

        logger.warning(
            f"🚨 Threat detected: {threat_type.value} "
            f"(severity: {severity.value}, confidence: {confidence:.2f})"
        )

        return threat

    def _calculate_confidence(
        self, threat_type: ThreatType, indicators: Dict[str, Any]
    ) -> float:
        """
        Calculate threat confidence based on indicators.

        Args:
            threat_type: Type of threat
            indicators: Threat indicators

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 0.0

        # Base confidence by threat type
        base_confidence = {
            ThreatType.MALICIOUS_TRAFFIC: 0.5,
            ThreatType.UNAUTHORIZED_ACCESS: 0.6,
            ThreatType.DATA_EXFILTRATION: 0.7,
            ThreatType.DENIAL_OF_SERVICE: 0.6,
            ThreatType.PRIVILEGE_ESCALATION: 0.7,
            ThreatType.MALWARE: 0.8,
            ThreatType.SUSPICIOUS_BEHAVIOR: 0.4,
        }

        confidence = base_confidence.get(threat_type, 0.5)

        # Boost confidence based on indicators
        if indicators.get("failed_attempts", 0) > 5:
            confidence += 0.1
        if indicators.get("unusual_pattern", False):
            confidence += 0.1
        if indicators.get("known_malicious", False):
            confidence += 0.2
        if indicators.get("anomaly_score", 0) > self.anomaly_threshold:
            confidence += 0.1

        return min(1.0, confidence)

    def _determine_severity(
        self, threat_type: ThreatType, indicators: Dict[str, Any], confidence: float
    ) -> ThreatSeverity:
        """Determine threat severity"""
        # Critical threats
        if threat_type in [
            ThreatType.DATA_EXFILTRATION,
            ThreatType.PRIVILEGE_ESCALATION,
        ]:
            if confidence > 0.8:
                return ThreatSeverity.CRITICAL

        # High severity
        if threat_type in [
            ThreatType.UNAUTHORIZED_ACCESS,
            ThreatType.DENIAL_OF_SERVICE,
        ]:
            if confidence > 0.7:
                return ThreatSeverity.HIGH

        # Medium severity
        if confidence > 0.6:
            return ThreatSeverity.MEDIUM

        return ThreatSeverity.LOW

    def _check_threat_intelligence(
        self, source_ip: Optional[str], target_ip: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Check threat intelligence for IP addresses.

        Args:
            source_ip: Source IP
            target_ip: Target IP

        Returns:
            Threat intelligence data if found
        """
        intel = {}

        if source_ip and source_ip in self.threat_intelligence:
            intel["source_intel"] = self.threat_intelligence[source_ip]

        if target_ip and target_ip in self.threat_intelligence:
            intel["target_intel"] = self.threat_intelligence[target_ip]

        return intel if intel else None

    def add_threat_intelligence(
        self, identifier: str, threat_info: Dict[str, Any]  # IP or domain
    ):
        """
        Add threat intelligence data.

        Args:
            identifier: IP address or domain
            threat_info: Threat information
        """
        self.threat_intelligence[identifier] = threat_info
        logger.info(f"Added threat intelligence for {identifier}")

    def get_threats(
        self,
        threat_type: Optional[ThreatType] = None,
        severity: Optional[ThreatSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Threat]:
        """
        Get detected threats with filtering.

        Args:
            threat_type: Filter by threat type
            severity: Filter by severity
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum results

        Returns:
            List of threats
        """
        results = []

        for threat in self.detected_threats:
            if threat_type and threat.threat_type != threat_type:
                continue
            if severity and threat.severity != severity:
                continue
            if start_time and threat.timestamp < start_time:
                continue
            if end_time and threat.timestamp > end_time:
                continue

            results.append(threat)

            if len(results) >= limit:
                break

        return results

    def mitigate_threat(self, threat_id: str, action: str) -> bool:
        """
        Mitigate a threat with automated action.

        Args:
            threat_id: Threat identifier
            action: Mitigation action

        Returns:
            True if mitigated successfully
        """
        for threat in self.detected_threats:
            if threat.threat_id == threat_id:
                threat.status = "mitigated"
                threat.mitigation_action = action
                logger.info(f"Threat {threat_id} mitigated with action: {action}")
                return True

        return False

    def get_threat_statistics(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get threat statistics.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            Statistics dictionary
        """
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.utcnow()

        threats = self.get_threats(
            start_time=start_time, end_time=end_time, limit=10000
        )

        by_type = {}
        by_severity = {}
        by_status = {}

        for threat in threats:
            # By type
            threat_type = threat.threat_type.value
            by_type[threat_type] = by_type.get(threat_type, 0) + 1

            # By severity
            severity = threat.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # By status
            status = threat.status
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "total_threats": len(threats),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
        }
