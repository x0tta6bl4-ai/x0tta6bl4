"""
MeshShield: Quarantine Engine for Compromised Nodes

Isolates malicious or compromised nodes from the mesh network.
Target MTTR: < 6 seconds from detection to isolation.

Architecture:
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Detection  │────►│  Analysis   │────►│ Quarantine  │
    │  (eBPF)     │     │  (ML/Rules) │     │  (Firewall) │
    └─────────────┘     └─────────────┘     └─────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
      Anomaly Score      Threat Level        Isolation
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels."""

    NONE = 0
    LOW = 1  # Suspicious activity, monitor
    MEDIUM = 2  # Confirmed anomaly, warn
    HIGH = 3  # Active threat, isolate
    CRITICAL = 4  # Immediate danger, block + alert


class QuarantineReason(Enum):
    """Reasons for node quarantine."""

    ANOMALY_SCORE = "anomaly_score_exceeded"
    REPLAY_ATTACK = "token_replay_detected"
    CERTIFICATE_INVALID = "certificate_validation_failed"
    BEHAVIOR_DEVIATION = "behavior_deviation"
    MANUAL = "manual_quarantine"
    DAO_VOTE = "dao_governance_decision"


@dataclass
class ThreatIndicator:
    """Indicator of compromise or suspicious activity."""

    node_id: str
    indicator_type: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    details: str = ""


@dataclass
class QuarantineRecord:
    """Record of a quarantined node."""

    node_id: str
    reason: QuarantineReason
    threat_level: ThreatLevel
    quarantined_at: datetime
    expires_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    indicators: List[ThreatIndicator] = field(default_factory=list)


class MeshShield:
    """
    Quarantine engine for mesh network security.

    Features:
    - Real-time threat detection integration
    - Automatic isolation of compromised nodes
    - Graduated response based on threat level
    - DAO-governed release mechanism
    - Audit trail for all actions

    Usage:
        shield = MeshShield()

        # Report suspicious activity
        shield.report_indicator(ThreatIndicator(
            node_id="node-123",
            indicator_type="anomaly_score",
            value=0.95
        ))

        # Check if node is quarantined
        if shield.is_quarantined("node-123"):
            print("Node is isolated")

        # Release after investigation
        shield.release_node("node-123", "false_positive")
    """

    # Thresholds for automatic quarantine
    ANOMALY_THRESHOLD = 0.85
    REPLAY_THRESHOLD = 3  # attempts
    CERT_FAILURE_THRESHOLD = 2

    # Quarantine durations by threat level
    QUARANTINE_DURATION = {
        ThreatLevel.LOW: timedelta(minutes=15),
        ThreatLevel.MEDIUM: timedelta(hours=1),
        ThreatLevel.HIGH: timedelta(hours=24),
        ThreatLevel.CRITICAL: None,  # Indefinite, requires manual release
    }

    def __init__(self):
        self._quarantined: Dict[str, QuarantineRecord] = {}
        self._indicators: Dict[str, List[ThreatIndicator]] = {}
        self._blocked_ips: Set[str] = set()
        self._event_handlers: List[Callable] = []
        self._metrics = {
            "quarantines_total": 0,
            "releases_total": 0,
            "false_positives": 0,
            "mttr_sum": 0.0,
            "mttr_count": 0,
        }

    def report_indicator(self, indicator: ThreatIndicator) -> Optional[ThreatLevel]:
        """
        Report a threat indicator for a node.

        Returns the resulting threat level if quarantine was triggered.
        """
        node_id = indicator.node_id

        # Store indicator
        if node_id not in self._indicators:
            self._indicators[node_id] = []
        self._indicators[node_id].append(indicator)

        # Analyze threat level
        threat_level = self._analyze_threat(node_id)

        # Auto-quarantine if threshold exceeded
        if threat_level.value >= ThreatLevel.HIGH.value:
            reason = self._determine_reason(indicator)
            self.quarantine_node(node_id, reason, threat_level)
            return threat_level

        return None

    def _analyze_threat(self, node_id: str) -> ThreatLevel:
        """Analyze accumulated indicators to determine threat level."""
        indicators = self._indicators.get(node_id, [])

        if not indicators:
            return ThreatLevel.NONE

        # Recent indicators (last 5 minutes)
        cutoff = datetime.now() - timedelta(minutes=5)
        recent = [i for i in indicators if i.timestamp > cutoff]

        # Count by type
        anomaly_scores = [
            i.value for i in recent if i.indicator_type == "anomaly_score"
        ]
        replay_count = len([i for i in recent if i.indicator_type == "replay_attack"])
        cert_failures = len([i for i in recent if i.indicator_type == "cert_failure"])

        # Determine threat level
        if replay_count >= self.REPLAY_THRESHOLD:
            return ThreatLevel.CRITICAL

        if cert_failures >= self.CERT_FAILURE_THRESHOLD:
            return ThreatLevel.HIGH

        if anomaly_scores:
            max_score = max(anomaly_scores)
            if max_score >= 0.95:
                return ThreatLevel.CRITICAL
            elif max_score >= self.ANOMALY_THRESHOLD:
                return ThreatLevel.HIGH
            elif max_score >= 0.7:
                return ThreatLevel.MEDIUM
            elif max_score >= 0.5:
                return ThreatLevel.LOW

        return ThreatLevel.NONE

    def _determine_reason(self, indicator: ThreatIndicator) -> QuarantineReason:
        """Determine quarantine reason from indicator."""
        type_to_reason = {
            "anomaly_score": QuarantineReason.ANOMALY_SCORE,
            "replay_attack": QuarantineReason.REPLAY_ATTACK,
            "cert_failure": QuarantineReason.CERTIFICATE_INVALID,
            "behavior": QuarantineReason.BEHAVIOR_DEVIATION,
        }
        return type_to_reason.get(
            indicator.indicator_type, QuarantineReason.ANOMALY_SCORE
        )

    def quarantine_node(
        self,
        node_id: str,
        reason: QuarantineReason,
        threat_level: ThreatLevel = ThreatLevel.HIGH,
    ) -> QuarantineRecord:
        """
        Quarantine a node immediately.

        Actions:
        1. Block all traffic from/to node
        2. Revoke certificates
        3. Notify DAO
        4. Log for audit
        """
        now = datetime.now()
        duration = self.QUARANTINE_DURATION.get(threat_level)
        expires_at = now + duration if duration else None

        record = QuarantineRecord(
            node_id=node_id,
            reason=reason,
            threat_level=threat_level,
            quarantined_at=now,
            expires_at=expires_at,
            indicators=self._indicators.get(node_id, [])[-10:],  # Last 10
        )

        self._quarantined[node_id] = record
        self._metrics["quarantines_total"] += 1

        # Trigger event handlers (e.g., firewall rules, notifications)
        self._emit_event("quarantine", record)

        logger.warning(
            f"🛡️ QUARANTINED: {node_id} | Reason: {reason.value} | "
            f"Level: {threat_level.name} | Expires: {expires_at or 'INDEFINITE'}"
        )

        return record

    def release_node(
        self, node_id: str, reason: str = "investigation_complete"
    ) -> bool:
        """
        Release a node from quarantine.

        Returns True if node was quarantined and is now released.
        """
        if node_id not in self._quarantined:
            return False

        record = self._quarantined[node_id]
        record.released_at = datetime.now()

        # Calculate MTTR
        mttr = (record.released_at - record.quarantined_at).total_seconds()
        self._metrics["mttr_sum"] += mttr
        self._metrics["mttr_count"] += 1
        self._metrics["releases_total"] += 1

        if reason == "false_positive":
            self._metrics["false_positives"] += 1

        del self._quarantined[node_id]

        # Clear indicators
        self._indicators.pop(node_id, None)

        self._emit_event("release", {"node_id": node_id, "reason": reason})

        logger.info(f"✅ RELEASED: {node_id} | Reason: {reason} | MTTR: {mttr:.2f}s")

        return True

    def is_quarantined(self, node_id: str) -> bool:
        """Check if a node is currently quarantined."""
        if node_id not in self._quarantined:
            return False

        record = self._quarantined[node_id]

        # Check expiration
        if record.expires_at and datetime.now() > record.expires_at:
            self.release_node(node_id, "expired")
            return False

        return True

    def get_quarantine_record(self, node_id: str) -> Optional[QuarantineRecord]:
        """Get quarantine details for a node."""
        return self._quarantined.get(node_id)

    def list_quarantined(self) -> List[QuarantineRecord]:
        """List all currently quarantined nodes."""
        # Clean up expired
        now = datetime.now()
        expired = [
            nid
            for nid, r in self._quarantined.items()
            if r.expires_at and now > r.expires_at
        ]
        for nid in expired:
            self.release_node(nid, "expired")

        return list(self._quarantined.values())

    def on_event(self, handler: Callable):
        """Register event handler for quarantine/release events."""
        self._event_handlers.append(handler)

    def _emit_event(self, event_type: str, data):
        """Emit event to all handlers."""
        for handler in self._event_handlers:
            try:
                handler(event_type, data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def get_metrics(self) -> Dict:
        """Get shield metrics for monitoring."""
        avg_mttr = (
            self._metrics["mttr_sum"] / self._metrics["mttr_count"]
            if self._metrics["mttr_count"] > 0
            else 0
        )
        return {
            "quarantined_nodes": len(self._quarantined),
            "quarantines_total": self._metrics["quarantines_total"],
            "releases_total": self._metrics["releases_total"],
            "false_positive_rate": (
                self._metrics["false_positives"] / self._metrics["releases_total"]
                if self._metrics["releases_total"] > 0
                else 0
            ),
            "avg_mttr_seconds": avg_mttr,
        }


# Global instance
mesh_shield = MeshShield()
