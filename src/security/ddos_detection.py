"""
DDoS Detection System

Provides DDoS attack detection, rate limiting, traffic analysis,
and automated mitigation.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DDoSType(Enum):
    """Types of DDoS attacks"""

    VOLUMETRIC = "volumetric"  # High traffic volume
    PROTOCOL = "protocol"  # Protocol-level attacks (SYN flood, etc.)
    APPLICATION = "application"  # Application-layer attacks
    SLOWLORIS = "slowloris"  # Slow HTTP attacks
    UDP_FLOOD = "udp_flood"  # UDP flood
    ICMP_FLOOD = "icmp_flood"  # ICMP flood


class AttackSeverity(Enum):
    """Attack severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DDoSAlert:
    """DDoS attack alert"""

    alert_id: str
    attack_type: DDoSType
    severity: AttackSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_ips: List[str] = field(default_factory=list)
    target_ip: Optional[str] = None
    target_port: Optional[int] = None
    traffic_rate: float = 0.0  # packets/second
    bandwidth: float = 0.0  # Mbps
    description: str = ""
    mitigation_applied: bool = False
    mitigation_action: Optional[str] = None


@dataclass
class TrafficBaseline:
    """Traffic baseline for anomaly detection"""

    avg_packets_per_second: float = 0.0
    avg_bandwidth_mbps: float = 0.0
    avg_connections: int = 0
    peak_packets_per_second: float = 0.0
    peak_bandwidth_mbps: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class DDoSDetector:
    """
    DDoS attack detection system.

    Provides:
    - Real-time traffic analysis
    - Attack pattern detection
    - Rate limiting
    - Automated mitigation
    """

    def __init__(
        self,
        detection_window: int = 60,  # seconds
        threshold_multiplier: float = 3.0,  # 3x baseline = attack
    ):
        """
        Initialize DDoS detector.

        Args:
            detection_window: Time window for analysis (seconds)
            threshold_multiplier: Multiplier for baseline threshold
        """
        self.detection_window = detection_window
        self.threshold_multiplier = threshold_multiplier

        # Traffic tracking
        # Keep enough samples to represent high-rate bursts across the full
        # detection window.
        self.traffic_history: deque = deque(maxlen=10000)
        self.ip_traffic: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.port_traffic: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))

        # Baselines
        self.baseline = TrafficBaseline()
        self.baseline_learning = True
        self.baseline_samples = 0

        # Alerts
        self.alerts: List[DDoSAlert] = []

        # Rate limiting
        self.rate_limits: Dict[str, Tuple[float, int]] = {}  # ip -> (last_reset, count)
        self.blocked_ips: set = set()

        logger.info("DDoSDetector initialized")

    def analyze_traffic(
        self,
        source_ip: str,
        target_ip: str,
        target_port: int,
        packet_size: int,
        protocol: str = "tcp",
    ) -> Optional[DDoSAlert]:
        """
        Analyze traffic and detect DDoS attacks.

        Args:
            source_ip: Source IP address
            target_ip: Target IP address
            target_port: Target port
            packet_size: Packet size in bytes
            protocol: Protocol (tcp, udp, icmp)

        Returns:
            DDoSAlert if attack detected, None otherwise
        """
        now = time.time()
        timestamp = datetime.utcnow()

        # Record traffic
        self.traffic_history.append(
            {
                "timestamp": now,
                "source_ip": source_ip,
                "target_ip": target_ip,
                "target_port": target_port,
                "packet_size": packet_size,
                "protocol": protocol,
            }
        )

        # Track per-IP traffic
        self.ip_traffic[source_ip].append(
            {"timestamp": now, "packet_size": packet_size}
        )

        # Track per-port traffic
        self.port_traffic[target_port].append(
            {"timestamp": now, "packet_size": packet_size}
        )

        # Update baseline during learning phase
        if self.baseline_learning:
            self._update_baseline()
            return None

        # Detect attacks
        alert = self._detect_attack(source_ip, target_ip, target_port, protocol)

        if alert:
            self.alerts.append(alert)
            logger.warning(
                f"🚨 DDoS attack detected: {alert.attack_type.value} "
                f"(severity: {alert.severity.value}, rate: {alert.traffic_rate:.1f} pps)"
            )

            # Apply mitigation
            if not alert.mitigation_applied:
                self._apply_mitigation(alert)

        return alert

    def _update_baseline(self):
        """Update traffic baseline"""
        if len(self.traffic_history) < 100:
            return

        # Calculate averages over detection window
        cutoff_time = time.time() - self.detection_window

        recent_traffic = [
            t for t in self.traffic_history if t["timestamp"] > cutoff_time
        ]

        if not recent_traffic:
            return

        # Calculate metrics
        total_packets = len(recent_traffic)
        total_bytes = sum(t["packet_size"] for t in recent_traffic)
        duration = self.detection_window

        packets_per_second = total_packets / duration
        bandwidth_mbps = (total_bytes * 8) / (duration * 1_000_000)  # Convert to Mbps

        # Update baseline (exponential moving average)
        alpha = 0.1
        self.baseline.avg_packets_per_second = (
            alpha * packets_per_second
            + (1 - alpha) * self.baseline.avg_packets_per_second
        )
        self.baseline.avg_bandwidth_mbps = (
            alpha * bandwidth_mbps + (1 - alpha) * self.baseline.avg_bandwidth_mbps
        )

        # Update peaks
        if packets_per_second > self.baseline.peak_packets_per_second:
            self.baseline.peak_packets_per_second = packets_per_second
        if bandwidth_mbps > self.baseline.peak_bandwidth_mbps:
            self.baseline.peak_bandwidth_mbps = bandwidth_mbps

        self.baseline_samples += 1
        self.baseline.last_updated = datetime.utcnow()

        # End learning phase after sufficient samples
        if self.baseline_samples >= 10:
            self.baseline_learning = False
            logger.info("Traffic baseline learning completed")

    def _detect_attack(
        self, source_ip: str, target_ip: str, target_port: int, protocol: str
    ) -> Optional[DDoSAlert]:
        """Detect DDoS attack"""
        now = time.time()
        cutoff_time = now - self.detection_window

        # Calculate current traffic rate
        recent_traffic = [
            t for t in self.traffic_history if t["timestamp"] > cutoff_time
        ]

        if not recent_traffic:
            return None

        current_rate = len(recent_traffic) / self.detection_window
        current_bandwidth = (
            sum(t["packet_size"] for t in recent_traffic)
            * 8
            / (self.detection_window * 1_000_000)
        )

        # Check against baseline
        threshold_rate = (
            self.baseline.avg_packets_per_second * self.threshold_multiplier
        )
        threshold_bandwidth = (
            self.baseline.avg_bandwidth_mbps * self.threshold_multiplier
        )

        if current_rate < threshold_rate and current_bandwidth < threshold_bandwidth:
            return None

        # Determine attack type
        attack_type = self._classify_attack(protocol, target_port, recent_traffic)

        # Determine severity
        severity = self._determine_severity(current_rate, threshold_rate)

        # Get source IPs
        source_ips = list(set(t["source_ip"] for t in recent_traffic))

        alert_id = f"ddos-{attack_type.value}-{int(now)}"
        alert = DDoSAlert(
            alert_id=alert_id,
            attack_type=attack_type,
            severity=severity,
            source_ips=source_ips,
            target_ip=target_ip,
            target_port=target_port,
            traffic_rate=current_rate,
            bandwidth=current_bandwidth,
            description=f"{attack_type.value} attack detected",
        )

        return alert

    def _classify_attack(
        self, protocol: str, target_port: int, recent_traffic: List[Dict[str, Any]]
    ) -> DDoSType:
        """Classify attack type"""
        # Check for UDP flood
        if protocol == "udp":
            return DDoSType.UDP_FLOOD

        # Check for ICMP flood
        if protocol == "icmp":
            return DDoSType.ICMP_FLOOD

        # Check for application-layer (HTTP)
        if target_port in [80, 443, 8080]:
            # Check for slowloris pattern (many connections, small packets)
            avg_packet_size = sum(t["packet_size"] for t in recent_traffic) / len(
                recent_traffic
            )
            if avg_packet_size < 100:  # Small packets
                return DDoSType.SLOWLORIS
            return DDoSType.APPLICATION

        # Default to volumetric
        return DDoSType.VOLUMETRIC

    def _determine_severity(
        self, current_rate: float, threshold_rate: float
    ) -> AttackSeverity:
        """Determine attack severity"""
        ratio = current_rate / threshold_rate if threshold_rate > 0 else 0

        if ratio >= 10.0:
            return AttackSeverity.CRITICAL
        elif ratio >= 5.0:
            return AttackSeverity.HIGH
        elif ratio >= 3.0:
            return AttackSeverity.MEDIUM
        else:
            return AttackSeverity.LOW

    def _apply_mitigation(self, alert: DDoSAlert):
        """Apply mitigation for detected attack"""
        # Block source IPs
        for source_ip in alert.source_ips[:10]:  # Limit to top 10
            self.blocked_ips.add(source_ip)
            logger.info(f"Blocked IP: {source_ip}")

        alert.mitigation_applied = True
        alert.mitigation_action = "ip_blocking"

        # Additional mitigations based on attack type
        if alert.attack_type == DDoSType.SLOWLORIS:
            # Rate limit connections
            alert.mitigation_action = "rate_limiting"
        elif alert.attack_type in [DDoSType.UDP_FLOOD, DDoSType.ICMP_FLOOD]:
            # Filter protocol
            alert.mitigation_action = "protocol_filtering"

    def is_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips

    def unblock_ip(self, ip: str):
        """Unblock an IP address"""
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            logger.info(f"Unblocked IP: {ip}")

    def get_statistics(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get DDoS detection statistics"""
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.utcnow()

        filtered_alerts = [
            a for a in self.alerts if start_time <= a.timestamp <= end_time
        ]

        by_type = {}
        by_severity = {}

        for alert in filtered_alerts:
            attack_type = alert.attack_type.value
            by_type[attack_type] = by_type.get(attack_type, 0) + 1

            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "total_alerts": len(filtered_alerts),
            "by_type": by_type,
            "by_severity": by_severity,
            "blocked_ips": len(self.blocked_ips),
            "baseline": {
                "avg_packets_per_second": self.baseline.avg_packets_per_second,
                "avg_bandwidth_mbps": self.baseline.avg_bandwidth_mbps,
                "learning": self.baseline_learning,
            },
        }
