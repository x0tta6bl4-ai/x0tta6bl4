"""
AnomalyConsensusManager — Delphi-consensus for session isolation decisions.

Wraps PBFTNode to provide cross-node verification before executing
potentially destructive healing actions (session isolation, key rotation).

Usage:
    manager = AnomalyConsensusManager(
        node_id="node-a",
        peers={"node-b", "node-c", "node-d"},
        f=1,
    )

    # Before isolating, ask peers to verify
    approved, result = await manager.request_consensus(
        session_id="abc123",
        anomaly_type="high_failure_rate",
        severity="high",
        evidence={"failure_rate": 0.15, "total_packets": 1000},
    )

    if approved:
        await isolate()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from src.coordination.events import EventBus, EventType
from src.swarm.pbft import PBFTNode, PBFTRequest

logger = logging.getLogger(__name__)

SERVICE_AGENT = "anomaly-consensus"
CONSENSUS_CLAIM_BOUNDARY = (
    "Anomaly consensus event only. It records local peer verification state "
    "and does not prove network-wide agreement, dataplane delivery, or "
    "production readiness by itself."
)

# Registry for in-process PBFT message routing
_node_registry: Dict[str, "AnomalyConsensusManager"] = {}


def _register_node(manager: "AnomalyConsensusManager") -> None:
    _node_registry[manager.node_id] = manager


def _unregister_node(node_id: str) -> None:
    _node_registry.pop(node_id, None)


@dataclass
class AnomalyEvidence:
    """Evidence about a session anomaly to be verified by peer nodes.

    Fields:
        session_id: The session being evaluated
        anomaly_type: Type (high_failure_rate, expired, anomaly_storm, etc.)
        severity: low/medium/high/critical
        failure_rate: Ratio of failed verifications (0.0-1.0)
        total_packets: Total packets observed
        observed_by: Node that detected the anomaly
        timestamp: When the anomaly was observed
        local_health_score: Optional local health score (0.0-1.0)
        extra: Additional context
    """

    session_id: str
    anomaly_type: str
    severity: str
    failure_rate: float = 0.0
    total_packets: int = 0
    observed_by: str = ""
    timestamp: float = field(default_factory=time.time)
    local_health_score: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "failure_rate": self.failure_rate,
            "total_packets": self.total_packets,
            "observed_by": self.observed_by,
            "timestamp": self.timestamp,
            "local_health_score": self.local_health_score,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AnomalyEvidence:
        return cls(
            session_id=data.get("session_id", ""),
            anomaly_type=data.get("anomaly_type", ""),
            severity=data.get("severity", "low"),
            failure_rate=data.get("failure_rate", 0.0),
            total_packets=data.get("total_packets", 0),
            observed_by=data.get("observed_by", ""),
            timestamp=data.get("timestamp", time.time()),
            local_health_score=data.get("local_health_score"),
            extra=data.get("extra", {}),
        )


@dataclass
class ConsensusVerdict:
    """Result of consensus-based anomaly verification.

    Fields:
        approved: True if peers agree action is needed
        reason: Summary of the decision
        peer_count: How many peers participated
        approvals: Number of peers that approved
        rejections: Number of peers that rejected
        duration_ms: Time taken for consensus
    """

    approved: bool
    reason: str = ""
    peer_count: int = 0
    approvals: int = 0
    rejections: int = 0
    duration_ms: float = 0.0


class AnomalyConsensusManager:
    """Manages cross-node consensus verification for anomaly decisions.

    Uses PBFT for Byzantine fault-tolerant agreement among mesh nodes.
    Before the healer isolates a session, this manager asks peer nodes
    to independently verify the anomaly evidence.

    In single-node mode (f=0 or only peers=set()), auto-approves since
    there are no peers to disagree. In multi-node mode, requires
    2f+1 commits per PBFT protocol.

    For in-process use (same Python process), an internal routing table
    connects PBFTNode instances directly. For production, replace
    with ConsensusTransport or gRPC.
    """

    def __init__(
        self,
        node_id: str,
        peers: Optional[Set[str]] = None,
        f: int = 0,
        event_bus: Optional[EventBus] = None,
        project_root: str = ".",
        consensus_timeout: float = 15.0,
        auto_approve: bool = False,
        local_health_fn: Optional[Callable[[], float]] = None,
    ):
        """
        Args:
            node_id: This node's identifier
            peers: Set of peer node IDs (empty for single-node)
            f: Max Byzantine nodes to tolerate (0 = auto-approve)
            event_bus: Shared EventBus for events
            project_root: Project root for EventBus
            consensus_timeout: Max seconds to wait for consensus
            auto_approve: If True, always approve (bypass PBFT)
            local_health_fn: Optional callback returning local health score (0-1)
        """
        self.node_id = node_id
        self.peers = peers or set()
        self.f = f
        self.project_root = project_root
        self.consensus_timeout = consensus_timeout
        self.auto_approve = auto_approve or (f == 0 and not self.peers)
        self.local_health_fn = local_health_fn

        self.event_bus = event_bus

        # In single-node / auto-approve mode, skip PBFT entirely
        self._pbft_node: Optional[PBFTNode] = None
        if not self.auto_approve:
            self._init_pbft()

        # Register for in-process routing
        _register_node(self)

    def _init_pbft(self) -> None:
        """Initialize PBFT node with in-process transport."""
        all_peers = self.peers | {self.node_id}
        self._pbft_node = PBFTNode(
            node_id=self.node_id,
            peers=self.peers,
            f=self.f,
            event_bus=self.event_bus,
            event_project_root=self.project_root,
            source_agent=f"{SERVICE_AGENT}:{self.node_id}",
        )
        self._pbft_node.set_callbacks(
            on_execute=self._evaluate_anomaly,
            send_message=self._route_message,
        )

    def _route_message(self, target_id: str, message: Dict[str, Any]) -> None:
        """Route PBFT message to target node via in-process registry."""
        if target_id == self.node_id:
            # Local message
            if self._pbft_node:
                self._pbft_node.receive_message(message)
            return
        target = _node_registry.get(target_id)
        if target and target._pbft_node:
            target._pbft_node.receive_message(message)
        else:
            logger.warning(
                "Consensus peer %s not found in registry (simulating timeout)", target_id
            )

    def _evaluate_anomaly(self, operation: Any) -> Dict[str, Any]:
        """PBFT execution callback — evaluate anomaly evidence locally.

        Each peer independently judges whether the anomaly is real.
        Returns dict with 'approved' bool and 'reason' str.
        """
        if isinstance(operation, str):
            try:
                data = json.loads(operation)
            except (json.JSONDecodeError, TypeError, ValueError):
                return {"approved": False, "reason": "invalid operation format"}
        elif isinstance(operation, dict):
            data = operation
        else:
            return {"approved": False, "reason": f"unexpected type: {type(operation).__name__}"}

        evidence = AnomalyEvidence.from_dict(data)

        # Decision logic — peers independently evaluate
        reasons = []

        # 1. Critical severity always triggers action
        if evidence.severity == "critical":
            reasons.append("critical severity confirmed by peer")
            return {"approved": True, "reason": "; ".join(reasons)}

        # 2. High failure rate (>10%) is suspicious
        if evidence.failure_rate > 0.10 and evidence.total_packets > 50:
            reasons.append(f"failure_rate={evidence.failure_rate:.2%} exceeds 10% threshold")
            return {"approved": True, "reason": "; ".join(reasons)}

        # 3. Check local health — if this peer is also unhealthy, agree
        if self.local_health_fn:
            local_score = self.local_health_fn()
            if local_score is not None and local_score < 0.5:
                reasons.append(f"local health score {local_score:.2f} confirms degradation")
                return {"approved": True, "reason": "; ".join(reasons)}

        # 4. Insufficient evidence — reject
        if evidence.total_packets < 20:
            reasons.append("insufficient sample size")
            return {"approved": False, "reason": "; ".join(reasons)}

        # 5. Medium severity with moderate failure — cautious approve
        if evidence.severity == "high" and evidence.failure_rate > 0.05:
            reasons.append("high severity with elevated failure rate")
            return {"approved": True, "reason": "; ".join(reasons)}

        # Default: reject — not enough evidence
        reasons.append(f"insufficient evidence (severity={evidence.severity}, "
                       f"failure_rate={evidence.failure_rate:.2f})")
        return {"approved": False, "reason": "; ".join(reasons)}

    async def request_consensus(
        self,
        session_id: str,
        anomaly_type: str,
        severity: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> ConsensusVerdict:
        """Request peer consensus before acting on an anomaly.

        Args:
            session_id: Session being evaluated
            anomaly_type: Type of anomaly detected
            severity: Severity level
            evidence: Dict with failure_rate, total_packets, etc.

        Returns:
            ConsensusVerdict with approval decision
        """
        start = time.monotonic()

        # Auto-approve mode (single node or f=0 with no peers)
        if self.auto_approve:
            elapsed = (time.monotonic() - start) * 1000
            return ConsensusVerdict(
                approved=True,
                reason="auto-approve (single-node mode)",
                peer_count=0,
                approvals=0,
                rejections=0,
                duration_ms=elapsed,
            )

        # Build evidence payload
        ev = AnomalyEvidence(
            session_id=session_id,
            anomaly_type=anomaly_type,
            severity=severity,
            failure_rate=(evidence or {}).get("failure_rate", 0.0),
            total_packets=(evidence or {}).get("total_packets", 0),
            observed_by=self.node_id,
            local_health_score=self.local_health_fn() if self.local_health_fn else None,
            extra={k: v for k, v in (evidence or {}).items()
                   if k not in ("failure_rate", "total_packets")},
        )

        if self._pbft_node is None:
            elapsed = (time.monotonic() - start) * 1000
            return ConsensusVerdict(
                approved=False,
                reason="PBFT node not initialized",
                duration_ms=elapsed,
            )

        try:
            # Submit to PBFT with timeout
            success, pbft_result = await asyncio.wait_for(
                self._pbft_node.request(ev.to_dict()),
                timeout=self.consensus_timeout,
            )

            elapsed = (time.monotonic() - start) * 1000

            if not success:
                return ConsensusVerdict(
                    approved=False,
                    reason="PBFT consensus failed or timed out",
                    duration_ms=elapsed,
                )

            # Extract result from PBFT execution
            if isinstance(pbft_result, dict):
                approved = pbft_result.get("approved", False)
                reason = pbft_result.get("reason", "")
            elif pbft_result is None:
                approved = False
                reason = "no PBFT execution result"
            else:
                approved = bool(pbft_result)
                reason = str(pbft_result)

            return ConsensusVerdict(
                approved=approved,
                reason=reason,
                peer_count=len(self.peers),
                approvals=1 if approved else 0,
                rejections=0 if approved else 1,
                duration_ms=elapsed,
            )

        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            logger.warning("Consensus timeout for session %s after %.0fms",
                           session_id[:8], elapsed)
            return ConsensusVerdict(
                approved=False,
                reason=f"consensus timeout ({self.consensus_timeout}s)",
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Consensus error for session %s: %s", session_id[:8], exc)
            return ConsensusVerdict(
                approved=False,
                reason=f"consensus error: {exc}",
                duration_ms=elapsed,
            )

    def get_status(self) -> Dict[str, Any]:
        """Return current consensus manager state."""
        return {
            "node_id": self.node_id,
            "peers": sorted(self.peers),
            "f": self.f,
            "auto_approve": self.auto_approve,
            "registered_peers": sorted(_node_registry.keys()),
            "pbft_initialized": self._pbft_node is not None,
        }

    def close(self) -> None:
        """Clean up — unregister from routing table."""
        _unregister_node(self.node_id)
