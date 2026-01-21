"""
Intrusion Detection System (IDS)

Provides network and host-based intrusion detection, behavioral analysis,
and incident response.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class IntrusionType(Enum):
    """Types of intrusions"""
    NETWORK_INTRUSION = "network_intrusion"
    HOST_INTRUSION = "host_intrusion"
    APPLICATION_INTRUSION = "application_intrusion"
    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    MALWARE_INFECTION = "malware_infection"


class IntrusionSeverity(Enum):
    """Intrusion severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IntrusionAlert:
    """Represents an intrusion detection alert"""
    alert_id: str
    intrusion_type: IntrusionType
    severity: IntrusionSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    node_id: Optional[str] = None
    description: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: str = "alert"  # alert, investigating, confirmed, false_positive
    response_action: Optional[str] = None


class IntrusionDetectionSystem:
    """
    Intrusion Detection System for network and host-based detection.
    
    Provides:
    - Network intrusion detection
    - Host-based detection
    - Behavioral analysis
    - Incident response
    """
    
    def __init__(self):
        self.alerts: List[IntrusionAlert] = []
        self.behavioral_baselines: Dict[str, Dict[str, Any]] = {}  # node_id -> baseline
        self.detection_rules: List[Dict[str, Any]] = []
        
        # Thresholds
        self.anomaly_threshold = 0.75
        self.confidence_threshold = 0.65
        
        # Initialize default rules
        self._initialize_default_rules()
        
        logger.info("IntrusionDetectionSystem initialized")
    
    def _initialize_default_rules(self):
        """Initialize default detection rules"""
        self.detection_rules = [
            {
                "name": "Port Scan Detection",
                "pattern": "multiple_ports",
                "threshold": 10,
                "severity": IntrusionSeverity.MEDIUM
            },
            {
                "name": "Brute Force Detection",
                "pattern": "failed_auth",
                "threshold": 5,
                "severity": IntrusionSeverity.HIGH
            },
            {
                "name": "Unusual Traffic Pattern",
                "pattern": "traffic_anomaly",
                "threshold": 0.8,
                "severity": IntrusionSeverity.MEDIUM
            },
            {
                "name": "Data Exfiltration",
                "pattern": "large_data_transfer",
                "threshold": 1000,  # MB
                "severity": IntrusionSeverity.CRITICAL
            }
        ]
    
    def detect_intrusion(
        self,
        intrusion_type: IntrusionType,
        indicators: Dict[str, Any],
        source_ip: Optional[str] = None,
        target_ip: Optional[str] = None,
        node_id: Optional[str] = None,
        description: str = ""
    ) -> Optional[IntrusionAlert]:
        """
        Detect an intrusion.
        
        Args:
            intrusion_type: Type of intrusion
            indicators: Intrusion indicators
            source_ip: Source IP address
            target_ip: Target IP address
            node_id: Node identifier
            description: Alert description
        
        Returns:
            IntrusionAlert if detected, None otherwise
        """
        # Calculate confidence
        confidence = self._calculate_confidence(intrusion_type, indicators, node_id)
        
        if confidence < self.confidence_threshold:
            logger.debug(f"Intrusion {intrusion_type.value} confidence too low: {confidence}")
            return None
        
        # Determine severity
        severity = self._determine_severity(intrusion_type, indicators, confidence)
        
        # Create alert
        alert_id = f"ids-alert-{intrusion_type.value}-{time.time()}"
        alert = IntrusionAlert(
            alert_id=alert_id,
            intrusion_type=intrusion_type,
            severity=severity,
            source_ip=source_ip,
            target_ip=target_ip,
            node_id=node_id,
            description=description,
            indicators=indicators,
            confidence=confidence
        )
        
        self.alerts.append(alert)
        
        logger.warning(
            f"🚨 Intrusion detected: {intrusion_type.value} "
            f"(severity: {severity.value}, confidence: {confidence:.2f})"
        )
        
        return alert
    
    def _calculate_confidence(
        self,
        intrusion_type: IntrusionType,
        indicators: Dict[str, Any],
        node_id: Optional[str]
    ) -> float:
        """Calculate intrusion confidence"""
        confidence = 0.5  # Base confidence
        
        # Check against behavioral baseline
        if node_id and node_id in self.behavioral_baselines:
            baseline = self.behavioral_baselines[node_id]
            anomaly_score = self._compare_to_baseline(indicators, baseline)
            confidence += anomaly_score * 0.3
        
        # Boost confidence based on indicators
        if indicators.get("known_attack_pattern", False):
            confidence += 0.2
        if indicators.get("multiple_indicators", False):
            confidence += 0.1
        if indicators.get("correlation_score", 0) > 0.7:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _compare_to_baseline(
        self,
        indicators: Dict[str, Any],
        baseline: Dict[str, Any]
    ) -> float:
        """Compare indicators to behavioral baseline"""
        anomaly_score = 0.0
        
        # Compare traffic patterns
        if "traffic_volume" in indicators and "avg_traffic" in baseline:
            ratio = indicators["traffic_volume"] / baseline["avg_traffic"]
            if ratio > 2.0 or ratio < 0.5:
                anomaly_score += 0.3
        
        # Compare connection patterns
        if "connections" in indicators and "avg_connections" in baseline:
            ratio = indicators["connections"] / baseline["avg_connections"]
            if ratio > 3.0:
                anomaly_score += 0.2
        
        return min(1.0, anomaly_score)
    
    def _determine_severity(
        self,
        intrusion_type: IntrusionType,
        indicators: Dict[str, Any],
        confidence: float
    ) -> IntrusionSeverity:
        """Determine intrusion severity"""
        # Critical intrusions
        if intrusion_type == IntrusionType.DATA_BREACH:
            if confidence > 0.8:
                return IntrusionSeverity.CRITICAL
        
        # High severity
        if intrusion_type in [IntrusionType.UNAUTHORIZED_ACCESS, IntrusionType.MALWARE_INFECTION]:
            if confidence > 0.7:
                return IntrusionSeverity.HIGH
        
        # Medium severity
        if confidence > 0.65:
            return IntrusionSeverity.MEDIUM
        
        return IntrusionSeverity.LOW
    
    def update_behavioral_baseline(
        self,
        node_id: str,
        metrics: Dict[str, Any]
    ):
        """
        Update behavioral baseline for a node.
        
        Args:
            node_id: Node identifier
            metrics: Current metrics
        """
        if node_id not in self.behavioral_baselines:
            self.behavioral_baselines[node_id] = {
                "avg_traffic": metrics.get("traffic_volume", 0),
                "avg_connections": metrics.get("connections", 0),
                "last_updated": datetime.utcnow()
            }
        else:
            baseline = self.behavioral_baselines[node_id]
            # Exponential moving average
            alpha = 0.1
            baseline["avg_traffic"] = (
                alpha * metrics.get("traffic_volume", 0) +
                (1 - alpha) * baseline["avg_traffic"]
            )
            baseline["avg_connections"] = (
                alpha * metrics.get("connections", 0) +
                (1 - alpha) * baseline["avg_connections"]
            )
            baseline["last_updated"] = datetime.utcnow()
    
    def get_alerts(
        self,
        intrusion_type: Optional[IntrusionType] = None,
        severity: Optional[IntrusionSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[IntrusionAlert]:
        """
        Get intrusion alerts with filtering.
        
        Args:
            intrusion_type: Filter by type
            severity: Filter by severity
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum results
        
        Returns:
            List of alerts
        """
        results = []
        
        for alert in self.alerts:
            if intrusion_type and alert.intrusion_type != intrusion_type:
                continue
            if severity and alert.severity != severity:
                continue
            if start_time and alert.timestamp < start_time:
                continue
            if end_time and alert.timestamp > end_time:
                continue
            
            results.append(alert)
            
            if len(results) >= limit:
                break
        
        return results
    
    def respond_to_intrusion(
        self,
        alert_id: str,
        action: str
    ) -> bool:
        """
        Respond to intrusion with automated action.
        
        Args:
            alert_id: Alert identifier
            action: Response action
        
        Returns:
            True if responded successfully
        """
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.status = "confirmed"
                alert.response_action = action
                logger.info(f"Intrusion {alert_id} responded with action: {action}")
                return True
        
        return False
    
    def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get intrusion detection statistics.
        
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
        
        alerts = self.get_alerts(start_time=start_time, end_time=end_time, limit=10000)
        
        by_type = {}
        by_severity = {}
        by_status = {}
        
        for alert in alerts:
            # By type
            intrusion_type = alert.intrusion_type.value
            by_type[intrusion_type] = by_type.get(intrusion_type, 0) + 1
            
            # By severity
            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # By status
            status = alert.status
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "total_alerts": len(alerts),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status
        }

