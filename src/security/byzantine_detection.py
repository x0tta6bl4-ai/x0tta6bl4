"""
Byzantine Attacks Detection

Provides detection of Byzantine (malicious) nodes in distributed systems,
consensus validation, node reputation tracking, and automated isolation.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ByzantineBehavior(Enum):
    """Types of Byzantine behaviors"""

    INCONSISTENT_STATE = "inconsistent_state"  # Different state to different nodes
    DOUBLE_SPEND = "double_spend"  # Attempting to spend same resource twice
    LIE_ABOUT_STATE = "lie_about_state"  # Reporting false state
    SELECTIVE_MESSAGE_DROP = "selective_message_drop"  # Dropping specific messages
    MESSAGE_DELAY = "message_delay"  # Deliberately delaying messages
    CONSENSUS_VIOLATION = "consensus_violation"  # Violating consensus protocol
    MALICIOUS_AGGREGATION = "malicious_aggregation"  # Sending malicious FL updates


class ByzantineSeverity(Enum):
    """Byzantine behavior severity"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ByzantineAlert:
    """Byzantine behavior alert"""

    alert_id: str
    node_id: str
    behavior_type: ByzantineBehavior
    severity: ByzantineSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0-1.0
    consensus_round: Optional[int] = None
    reported_by: List[str] = field(default_factory=list)  # Nodes that reported
    isolation_applied: bool = False
    isolation_action: Optional[str] = None


@dataclass
class NodeReputation:
    """Node reputation tracking"""

    node_id: str
    reputation_score: float = 1.0  # 0.0-1.0
    total_interactions: int = 0
    successful_interactions: int = 0
    byzantine_violations: int = 0
    last_violation: Optional[datetime] = None
    trust_level: str = "trusted"  # trusted, suspicious, untrusted, banned
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def update_reputation(self, success: bool):
        """Update reputation based on interaction"""
        self.total_interactions += 1
        if success:
            self.successful_interactions += 1

        # Calculate reputation score
        if self.total_interactions > 0:
            self.reputation_score = (
                self.successful_interactions / self.total_interactions
            ) * (
                0.9**self.byzantine_violations
            )  # Exponential decay on violations

        # Update trust level
        if self.reputation_score >= 0.8:
            self.trust_level = "trusted"
        elif self.reputation_score >= 0.5:
            self.trust_level = "suspicious"
        elif self.reputation_score >= 0.2:
            self.trust_level = "untrusted"
        else:
            self.trust_level = "banned"

        self.last_updated = datetime.utcnow()


class ByzantineDetector:
    """
    Detects Byzantine (malicious) nodes in distributed systems.

    Provides:
    - Byzantine behavior detection
    - Consensus validation
    - Node reputation tracking
    - Automated isolation
    """

    def __init__(
        self,
        min_evidence_nodes: int = 2,  # Minimum nodes reporting same issue
        reputation_threshold: float = 0.3,  # Below this = byzantine
        consensus_tolerance: int = 1,  # Maximum byzantine nodes tolerated
    ):
        """
        Initialize Byzantine detector.

        Args:
            min_evidence_nodes: Minimum nodes needed to confirm byzantine behavior
            reputation_threshold: Reputation threshold for byzantine classification
            consensus_tolerance: Maximum byzantine nodes tolerated (for BFT)
        """
        self.min_evidence_nodes = min_evidence_nodes
        self.reputation_threshold = reputation_threshold
        self.consensus_tolerance = consensus_tolerance

        # Node tracking
        self.node_reputations: Dict[str, NodeReputation] = {}
        self.consensus_history: Dict[int, Dict[str, Any]] = (
            {}
        )  # round -> consensus data
        self.state_claims: Dict[str, Dict[str, Any]] = {}  # node_id -> state claims

        # Alerts
        self.alerts: List[ByzantineAlert] = []
        self.isolated_nodes: set = set()

        logger.info("ByzantineDetector initialized")

    def detect_byzantine_behavior(
        self,
        node_id: str,
        behavior_type: ByzantineBehavior,
        evidence: Dict[str, Any],
        reported_by: Optional[str] = None,
        consensus_round: Optional[int] = None,
    ) -> Optional[ByzantineAlert]:
        """
        Detect Byzantine behavior.

        Args:
            node_id: Suspected node ID
            behavior_type: Type of behavior
            evidence: Evidence of behavior
            reported_by: Node that reported this
            consensus_round: Consensus round number

        Returns:
            ByzantineAlert if confirmed, None otherwise
        """
        # Get or create node reputation
        if node_id not in self.node_reputations:
            self.node_reputations[node_id] = NodeReputation(node_id=node_id)

        reputation = self.node_reputations[node_id]

        # Check if already isolated
        if node_id in self.isolated_nodes:
            logger.debug(f"Node {node_id} already isolated")
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(
            node_id, behavior_type, evidence, reputation, reported_by
        )

        if confidence < 0.6:  # Minimum confidence threshold
            logger.debug(f"Byzantine behavior confidence too low: {confidence}")
            return None

        # Determine severity
        severity = self._determine_severity(behavior_type, evidence, confidence)

        # Create alert
        alert_id = f"byzantine-{node_id}-{int(time.time())}"
        alert = ByzantineAlert(
            alert_id=alert_id,
            node_id=node_id,
            behavior_type=behavior_type,
            severity=severity,
            evidence=evidence,
            confidence=confidence,
            consensus_round=consensus_round,
            reported_by=[reported_by] if reported_by else [],
        )

        # Check if multiple nodes report same issue
        if reported_by:
            # Find other reports for same node/behavior
            similar_alerts = [
                a
                for a in self.alerts
                if a.node_id == node_id
                and a.behavior_type == behavior_type
                and (time.time() - a.timestamp.timestamp()) < 300  # Within 5 minutes
            ]

            if len(similar_alerts) >= self.min_evidence_nodes - 1:
                # Multiple confirmations - high confidence
                alert.confidence = min(1.0, confidence + 0.3)
                alert.reported_by = [
                    a.reported_by[0] for a in similar_alerts if a.reported_by
                ] + [reported_by]

        self.alerts.append(alert)

        # Update reputation
        reputation.byzantine_violations += 1
        reputation.last_violation = datetime.utcnow()
        reputation.update_reputation(success=False)

        # Apply isolation if severe
        if severity in [ByzantineSeverity.HIGH, ByzantineSeverity.CRITICAL]:
            self._apply_isolation(alert)

        logger.warning(
            f"🚨 Byzantine behavior detected: {node_id} - {behavior_type.value} "
            f"(severity: {severity.value}, confidence: {confidence:.2f})"
        )

        return alert

    def _calculate_confidence(
        self,
        node_id: str,
        behavior_type: ByzantineBehavior,
        evidence: Dict[str, Any],
        reputation: NodeReputation,
        reported_by: Optional[str],
    ) -> float:
        """Calculate detection confidence"""
        confidence = 0.5  # Base confidence

        # Adjust based on reputation
        if reputation.reputation_score < self.reputation_threshold:
            confidence += 0.2  # Low reputation = higher suspicion

        # Adjust based on behavior type
        high_confidence_behaviors = [
            ByzantineBehavior.DOUBLE_SPEND,
            ByzantineBehavior.CONSENSUS_VIOLATION,
            ByzantineBehavior.MALICIOUS_AGGREGATION,
        ]
        if behavior_type in high_confidence_behaviors:
            confidence += 0.2

        # Adjust based on evidence quality
        if evidence.get("direct_proof", False):
            confidence += 0.1
        if evidence.get("multiple_witnesses", False):
            confidence += 0.1

        # Adjust based on reporter reputation
        if reported_by and reported_by in self.node_reputations:
            reporter_reputation = self.node_reputations[reported_by]
            if reporter_reputation.reputation_score > 0.8:
                confidence += 0.1  # Trusted reporter

        return min(1.0, confidence)

    def _determine_severity(
        self,
        behavior_type: ByzantineBehavior,
        evidence: Dict[str, Any],
        confidence: float,
    ) -> ByzantineSeverity:
        """Determine severity"""
        critical_behaviors = [
            ByzantineBehavior.DOUBLE_SPEND,
            ByzantineBehavior.CONSENSUS_VIOLATION,
            ByzantineBehavior.MALICIOUS_AGGREGATION,
        ]

        if behavior_type in critical_behaviors and confidence > 0.8:
            return ByzantineSeverity.CRITICAL

        if behavior_type in critical_behaviors or confidence > 0.7:
            return ByzantineSeverity.HIGH

        if confidence > 0.6:
            return ByzantineSeverity.MEDIUM

        return ByzantineSeverity.LOW

    def validate_consensus(
        self,
        consensus_round: int,
        node_id: str,
        proposed_value: Any,
        received_values: Dict[str, Any],
    ) -> Tuple[bool, Optional[ByzantineAlert]]:
        """
        Validate consensus round for Byzantine behavior.

        Args:
            consensus_round: Consensus round number
            node_id: Node proposing value
            proposed_value: Proposed value
            received_values: Values received from other nodes

        Returns:
            (is_valid, alert_if_byzantine)
        """
        # Store consensus data
        self.consensus_history[consensus_round] = {
            "proposer": node_id,
            "proposed_value": proposed_value,
            "received_values": received_values,
            "timestamp": datetime.utcnow(),
        }

        # Check for inconsistent values
        value_counts = {}
        for other_node, value in received_values.items():
            if value not in value_counts:
                value_counts[value] = []
            value_counts[value].append(other_node)

        # If majority agrees on different value, proposer might be byzantine
        if len(value_counts) > 1:
            # Find majority value
            majority_value = max(value_counts.items(), key=lambda x: len(x[1]))[0]

            if proposed_value != majority_value:
                # Proposer disagrees with majority - potential byzantine
                alert = self.detect_byzantine_behavior(
                    node_id=node_id,
                    behavior_type=ByzantineBehavior.CONSENSUS_VIOLATION,
                    evidence={
                        "proposed_value": proposed_value,
                        "majority_value": majority_value,
                        "consensus_round": consensus_round,
                        "value_distribution": {
                            str(k): len(v) for k, v in value_counts.items()
                        },
                    },
                    consensus_round=consensus_round,
                )
                return False, alert

        return True, None

    def _apply_isolation(self, alert: ByzantineAlert):
        """Apply isolation to Byzantine node"""
        if alert.node_id in self.isolated_nodes:
            return

        self.isolated_nodes.add(alert.node_id)
        alert.isolation_applied = True
        alert.isolation_action = "network_isolation"

        logger.warning(f"Isolated Byzantine node: {alert.node_id}")

    def release_isolation(self, node_id: str) -> bool:
        """
        Release isolation for a node.

        Args:
            node_id: Node ID to release

        Returns:
            True if released successfully
        """
        if node_id not in self.isolated_nodes:
            return False

        self.isolated_nodes.remove(node_id)
        logger.info(f"Released isolation for node: {node_id}")
        return True

    def get_node_reputation(self, node_id: str) -> Optional[NodeReputation]:
        """Get node reputation"""
        return self.node_reputations.get(node_id)

    def get_statistics(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get Byzantine detection statistics"""
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.utcnow()

        filtered_alerts = [
            a for a in self.alerts if start_time <= a.timestamp <= end_time
        ]

        by_behavior = {}
        by_severity = {}
        by_trust_level = {}

        for alert in filtered_alerts:
            behavior = alert.behavior_type.value
            by_behavior[behavior] = by_behavior.get(behavior, 0) + 1

            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        for reputation in self.node_reputations.values():
            trust_level = reputation.trust_level
            by_trust_level[trust_level] = by_trust_level.get(trust_level, 0) + 1

        return {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "total_alerts": len(filtered_alerts),
            "by_behavior": by_behavior,
            "by_severity": by_severity,
            "isolated_nodes": len(self.isolated_nodes),
            "node_reputations": {
                "total": len(self.node_reputations),
                "by_trust_level": by_trust_level,
            },
        }
