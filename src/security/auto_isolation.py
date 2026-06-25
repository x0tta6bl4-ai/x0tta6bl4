"""
Auto-Isolation Module for x0tta6bl4 Mesh.
Automatically isolate compromised or malicious nodes.

Implements:
- Automatic threat response
- Gradual isolation (soft → hard)
- Recovery procedures
- Network quarantine
- Circuit breaker patterns

Zero Trust Principle: Never trust, always verify, limit blast radius.
"""

import logging
import hashlib
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_node_ref(value: object) -> Dict[str, Any]:
    return {"hash": _safe_hash(value), "present": value is not None}


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


class IsolationLevel(Enum):
    """Levels of node isolation."""

    NONE = 0  # Full access
    MONITOR = 1  # Increased monitoring, no restrictions
    RATE_LIMIT = 2  # Rate-limited access
    RESTRICTED = 3  # Limited to essential operations only
    QUARANTINE = 4  # No mesh communication, monitoring only
    BLOCKED = 5  # Complete network block


class IsolationReason(Enum):
    """Reasons for isolation."""

    THREAT_DETECTED = "threat_detected"
    TRUST_DEGRADED = "trust_degraded"
    ANOMALY_DETECTED = "anomaly_detected"
    AUTHENTICATION_FAILURE = "auth_failure"
    PROTOCOL_VIOLATION = "protocol_violation"
    ADMIN_ACTION = "admin_action"
    PEER_CONSENSUS = "peer_consensus"
    RESOURCE_ABUSE = "resource_abuse"


@dataclass
class IsolationRecord:
    """Record of isolation action."""

    node_id: str
    level: IsolationLevel
    reason: IsolationReason
    started_at: float
    expires_at: Optional[float]
    escalation_count: int = 0
    details: str = ""
    auto_recover: bool = True
    recovery_conditions: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if isolation has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "level": self.level.name,
            "reason": self.reason.value,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "escalation_count": self.escalation_count,
            "details": self.details,
            "auto_recover": self.auto_recover,
        }


@dataclass
class IsolationPolicy:
    """Policy for automatic isolation."""

    name: str
    trigger_reason: IsolationReason
    initial_level: IsolationLevel
    escalation_levels: List[IsolationLevel]
    escalation_threshold: int  # Number of violations before escalation
    initial_duration: int  # seconds
    escalation_multiplier: float  # Duration multiplier on escalation
    max_duration: int  # Maximum isolation duration
    auto_recover: bool

    def get_duration(self, escalation_count: int) -> int:
        """Calculate duration based on escalation count."""
        duration = int(
            self.initial_duration * (self.escalation_multiplier**escalation_count)
        )
        return min(duration, self.max_duration)

    def get_level(self, escalation_count: int) -> IsolationLevel:
        """Get isolation level based on escalation count."""
        if escalation_count >= len(self.escalation_levels):
            return self.escalation_levels[-1]
        return self.escalation_levels[escalation_count]


class CircuitBreaker:
    """
    Circuit breaker for node communication.
    Prevents cascade failures by breaking circuits to unhealthy nodes.
    """

    class State(Enum):
        CLOSED = "closed"  # Normal operation
        OPEN = "open"  # Circuit broken, no communication
        HALF_OPEN = "half_open"  # Testing if node recovered

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_successes = 0
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Record successful operation."""
        with self._lock:
            if self.state == self.State.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_requests:
                    self._close()
            else:
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        """Record failed operation."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == self.State.HALF_OPEN:
                self._open()
            elif self.failure_count >= self.failure_threshold:
                self._open()

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        with self._lock:
            if self.state == self.State.CLOSED:
                return True
            elif self.state == self.State.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self._half_open()
                    return True
                return False
            else:  # HALF_OPEN
                return True

    def _open(self) -> None:
        """Open the circuit."""
        self.state = self.State.OPEN
        logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

    def _close(self) -> None:
        """Close the circuit."""
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.half_open_successes = 0
        logger.info("Circuit breaker CLOSED, node recovered")

    def _half_open(self) -> None:
        """Set circuit to half-open for testing."""
        self.state = self.State.HALF_OPEN
        self.half_open_successes = 0
        logger.info("Circuit breaker HALF_OPEN, testing recovery")


class AutoIsolationManager:
    """
    Manages automatic isolation of compromised nodes.
    Implements Zero Trust blast radius limitation.
    """

    # Default isolation policies
    DEFAULT_POLICIES = [
        IsolationPolicy(
            name="threat_response",
            trigger_reason=IsolationReason.THREAT_DETECTED,
            initial_level=IsolationLevel.RESTRICTED,
            escalation_levels=[
                IsolationLevel.RESTRICTED,
                IsolationLevel.QUARANTINE,
                IsolationLevel.BLOCKED,
            ],
            escalation_threshold=2,
            initial_duration=300,  # 5 minutes
            escalation_multiplier=4.0,
            max_duration=86400,  # 24 hours
            auto_recover=True,
        ),
        IsolationPolicy(
            name="trust_degradation",
            trigger_reason=IsolationReason.TRUST_DEGRADED,
            initial_level=IsolationLevel.RATE_LIMIT,
            escalation_levels=[
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED,
                IsolationLevel.QUARANTINE,
            ],
            escalation_threshold=3,
            initial_duration=600,  # 10 minutes
            escalation_multiplier=2.0,
            max_duration=43200,  # 12 hours
            auto_recover=True,
        ),
        IsolationPolicy(
            name="auth_failure",
            trigger_reason=IsolationReason.AUTHENTICATION_FAILURE,
            initial_level=IsolationLevel.RATE_LIMIT,
            escalation_levels=[
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED,
                IsolationLevel.BLOCKED,
            ],
            escalation_threshold=5,
            initial_duration=60,  # 1 minute
            escalation_multiplier=3.0,
            max_duration=3600,  # 1 hour
            auto_recover=True,
        ),
        IsolationPolicy(
            name="anomaly_detection",
            trigger_reason=IsolationReason.ANOMALY_DETECTED,
            initial_level=IsolationLevel.MONITOR,
            escalation_levels=[
                IsolationLevel.MONITOR,
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED,
            ],
            escalation_threshold=3,
            initial_duration=120,  # 2 minutes
            escalation_multiplier=2.0,
            max_duration=7200,  # 2 hours
            auto_recover=True,
        ),
        IsolationPolicy(
            name="protocol_violation",
            trigger_reason=IsolationReason.PROTOCOL_VIOLATION,
            initial_level=IsolationLevel.QUARANTINE,
            escalation_levels=[IsolationLevel.QUARANTINE, IsolationLevel.BLOCKED],
            escalation_threshold=1,
            initial_duration=3600,  # 1 hour
            escalation_multiplier=4.0,
            max_duration=604800,  # 1 week
            auto_recover=False,
        ),
    ]

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.isolated_nodes: Dict[str, IsolationRecord] = {}
        self.policies: Dict[IsolationReason, IsolationPolicy] = {
            p.trigger_reason: p for p in self.DEFAULT_POLICIES
        }
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)
        self.violation_counts: Dict[str, Dict[IsolationReason, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[str, IsolationLevel], None]] = []
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"auto-isolation-manager:{_safe_hash(node_id)}",
            role="security",
            capabilities=("zero-trust", "healing", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "auto_isolation_manager_init",
                "goal": "Initialize zero-trust isolation decisions",
                "signals": {
                    "node": _safe_node_ref(node_id),
                    "policy_count": len(self.policies),
                },
                "safety_boundary": (
                    "Do not expose raw node ids, IP addresses, or incident details "
                    "in isolation thinking context."
                ),
            }
        )
        
        # Zero-Trust XDP Enforcement
        try:
            from src.network.ebpf.quarantine_manager import QuarantineManager
            self._quarantine = QuarantineManager()
            self.register_callback(self._enforce_network_isolation)
        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error(f"XDP Quarantine enforcement not available: {e}")
            self._quarantine = None

        logger.info(f"AutoIsolationManager initialized for {node_id}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_node_identifiers": True,
                    "redact_network_addresses": True,
                    "redact_incident_details": True,
                    "preserve_zero_trust_policy": True,
                },
                "safety_boundary": (
                    "Use only hashes, isolation levels, reasons, counters, and "
                    "boolean flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def _enforce_network_isolation(self, node_id: str, level: IsolationLevel) -> None:
        """Bridge between logic and kernel-level enforcement."""
        if not self._quarantine:
            return

        # We need the IP address of the node.
        # In a real system, we'd resolve node_id to IP via discovery service.
        # For this implementation, we assume node_id is the IP for simplicity
        # or it can be resolved.
        # 
        # NOTE: This assumes node_id format is IP address. For UUID/hostname formats,
        # a proper resolution service should be implemented.
        ip_address = node_id
        
        # Validate IP format for logging/warning purposes
        import ipaddress
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            logger.warning(
                f"Node ID '{node_id}' does not appear to be a valid IP address. "
                f"Using as-is for quarantine. Consider implementing node-to-IP resolution."
            )
        
        if level in [IsolationLevel.QUARANTINE, IsolationLevel.BLOCKED]:
            self._quarantine.block_node(ip_address, level=level.value)
        elif level == IsolationLevel.NONE:
            self._quarantine.unblock_node(ip_address)


    def register_callback(
        self, callback: Callable[[str, IsolationLevel], None]
    ) -> None:
        """Register callback for isolation events."""
        self._callbacks.append(callback)
        self._record_thinking(
            "auto_isolation_callback_registered",
            "Register isolation event callback",
            {"callback_count": len(self._callbacks)},
        )

    def _notify_callbacks(self, node_id: str, level: IsolationLevel) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(node_id, level)
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                logger.error(f"Callback error: {e}")

    def isolate(
        self,
        node_id: str,
        reason: IsolationReason,
        details: str = "",
        level_override: Optional[IsolationLevel] = None,
        duration_override: Optional[int] = None,
    ) -> IsolationRecord:
        """
        Isolate a node.

        Args:
            node_id: Node to isolate
            reason: Reason for isolation
            details: Additional details
            level_override: Override policy level
            duration_override: Override policy duration

        Returns:
            IsolationRecord
        """
        with self._lock:
            # Get or create violation count
            self.violation_counts[node_id][reason] += 1
            violation_count = self.violation_counts[node_id][reason]

            # Get policy
            policy = self.policies.get(reason)

            # Check if already isolated
            existing = self.isolated_nodes.get(node_id)
            if existing and not existing.is_expired():
                # Escalate if same reason
                if existing.reason == reason:
                    return self._escalate(node_id, existing, violation_count)

            # Determine level and duration
            if level_override:
                level = level_override
            elif policy:
                escalation_count = violation_count // policy.escalation_threshold
                level = policy.get_level(escalation_count)
            else:
                level = IsolationLevel.RESTRICTED

            if duration_override:
                duration = duration_override
            elif policy:
                escalation_count = violation_count // policy.escalation_threshold
                duration = policy.get_duration(escalation_count)
            else:
                duration = 300

            now = time.time()
            record = IsolationRecord(
                node_id=node_id,
                level=level,
                reason=reason,
                started_at=now,
                expires_at=now + duration,
                escalation_count=0,
                details=details,
                auto_recover=policy.auto_recover if policy else True,
            )

            self.isolated_nodes[node_id] = record
            self._notify_callbacks(node_id, level)

            logger.warning(
                f"Isolated node {node_id}: level={level.name}, "
                f"reason={reason.value}, duration={duration}s"
            )
            self._record_thinking(
                "auto_isolation_node_isolated",
                "Select isolation level and duration for node",
                {
                    "node": _safe_node_ref(node_id),
                    "reason": reason.value,
                    "level": level.name,
                    "violation_count_bucket": _safe_count_bucket(violation_count),
                    "policy_found": policy is not None,
                    "level_override": level_override is not None,
                    "duration_override": duration_override is not None,
                    "duration_bucket": _safe_count_bucket(duration),
                    "details_hash": _safe_hash(details) if details else None,
                    "isolated_count_bucket": _safe_count_bucket(
                        len(self.isolated_nodes)
                    ),
                },
            )

            return record

    def _escalate(
        self, node_id: str, current: IsolationRecord, violation_count: int
    ) -> IsolationRecord:
        """Escalate existing isolation."""
        policy = self.policies.get(current.reason)

        if not policy:
            return current

        escalation_count = current.escalation_count + 1
        new_level = policy.get_level(escalation_count)
        new_duration = policy.get_duration(escalation_count)

        now = time.time()
        current.level = new_level
        current.escalation_count = escalation_count
        current.expires_at = now + new_duration
        current.auto_recover = policy.auto_recover

        self._notify_callbacks(node_id, new_level)

        logger.warning(
            f"Escalated isolation for {node_id}: "
            f"level={new_level.name}, escalation={escalation_count}"
        )
        self._record_thinking(
            "auto_isolation_escalated",
            "Escalate existing node isolation",
            {
                "node": _safe_node_ref(node_id),
                "reason": current.reason.value,
                "level": new_level.name,
                "violation_count_bucket": _safe_count_bucket(violation_count),
                "escalation_count_bucket": _safe_count_bucket(escalation_count),
                "duration_bucket": _safe_count_bucket(new_duration),
            },
        )

        return current

    def release(self, node_id: str, force: bool = False) -> bool:
        """
        Release node from isolation.

        Args:
            node_id: Node to release
            force: Force release even if not auto_recover

        Returns:
            True if released
        """
        with self._lock:
            if node_id not in self.isolated_nodes:
                self._record_thinking(
                    "auto_isolation_release_missing",
                    "Reject release for non-isolated node",
                    {"node": _safe_node_ref(node_id), "force": force},
                )
                return False

            record = self.isolated_nodes[node_id]

            if not record.auto_recover and not force:
                self._record_thinking(
                    "auto_isolation_release_rejected",
                    "Reject non-forced release for manual isolation",
                    {
                        "node": _safe_node_ref(node_id),
                        "level": record.level.name,
                        "reason": record.reason.value,
                        "force": force,
                    },
                )
                logger.warning(
                    f"Cannot auto-release {node_id}, manual release required"
                )
                return False

            del self.isolated_nodes[node_id]
            self._notify_callbacks(node_id, IsolationLevel.NONE)

            # Reset circuit breaker
            if node_id in self.circuit_breakers:
                self.circuit_breakers[node_id]._close()

            logger.info(f"Released node {node_id} from isolation")
            self._record_thinking(
                "auto_isolation_released",
                "Release node from isolation",
                {
                    "node": _safe_node_ref(node_id),
                    "force": force,
                    "remaining_isolated_bucket": _safe_count_bucket(
                        len(self.isolated_nodes)
                    ),
                },
            )
            return True

    def get_isolation_level(self, node_id: str) -> IsolationLevel:
        """Get current isolation level for node."""
        with self._lock:
            if node_id not in self.isolated_nodes:
                self._record_thinking(
                    "auto_isolation_level_checked",
                    "Check node isolation level",
                    {"node": _safe_node_ref(node_id), "level": IsolationLevel.NONE.name},
                )
                return IsolationLevel.NONE

            record = self.isolated_nodes[node_id]

            if record.is_expired():
                if record.auto_recover:
                    self.release(node_id)
                    self._record_thinking(
                        "auto_isolation_level_auto_recovered",
                        "Auto-release expired isolation before level check",
                        {"node": _safe_node_ref(node_id)},
                    )
                    return IsolationLevel.NONE

            self._record_thinking(
                "auto_isolation_level_checked",
                "Check node isolation level",
                {
                    "node": _safe_node_ref(node_id),
                    "level": record.level.name,
                    "reason": record.reason.value,
                },
            )
            return record.level

    def is_allowed(self, node_id: str, operation: str = "default") -> Tuple[bool, str]:
        """
        Check if operation is allowed for node.

        Args:
            node_id: Node requesting operation
            operation: Operation type

        Returns:
            (allowed, reason)
        """
        level = self.get_isolation_level(node_id)

        # Check circuit breaker
        cb = self.circuit_breakers[node_id]
        if not cb.allow_request():
            self._record_thinking(
                "auto_isolation_operation_denied_circuit",
                "Deny operation because circuit breaker is open",
                {"node": _safe_node_ref(node_id), "operation_hash": _safe_hash(operation)},
            )
            return False, "Circuit breaker open"

        # Level-based access control
        if level == IsolationLevel.NONE:
            allowed, reason = True, "OK"
        elif level == IsolationLevel.MONITOR:
            allowed, reason = True, "Monitored"
        elif level == IsolationLevel.RATE_LIMIT:
            # Would implement actual rate limiting here
            allowed, reason = True, "Rate limited"
        elif level == IsolationLevel.RESTRICTED:
            # Only essential operations
            essential = ["health", "heartbeat", "auth"]
            if operation in essential:
                allowed, reason = True, "Restricted - essential only"
            else:
                allowed, reason = False, f"Restricted - {operation} not allowed"
        elif level == IsolationLevel.QUARANTINE:
            if operation == "health":
                allowed, reason = True, "Quarantine - health only"
            else:
                allowed, reason = False, "Quarantine - blocked"
        else:  # BLOCKED
            allowed, reason = False, "Blocked"

        self._record_thinking(
            "auto_isolation_operation_checked",
            "Evaluate operation against isolation level",
            {
                "node": _safe_node_ref(node_id),
                "operation_hash": _safe_hash(operation),
                "level": level.name,
                "allowed": allowed,
                "decision_reason_hash": _safe_hash(reason),
            },
        )
        return allowed, reason

    def record_success(self, node_id: str) -> None:
        """Record successful operation for circuit breaker."""
        self.circuit_breakers[node_id].record_success()
        self._record_thinking(
            "auto_isolation_circuit_success",
            "Record successful node operation for circuit breaker",
            {"node": _safe_node_ref(node_id)},
        )

    def record_failure(self, node_id: str) -> None:
        """Record failed operation for circuit breaker."""
        self.circuit_breakers[node_id].record_failure()
        cb = self.circuit_breakers[node_id]
        self._record_thinking(
            "auto_isolation_circuit_failure",
            "Record failed node operation for circuit breaker",
            {
                "node": _safe_node_ref(node_id),
                "state": cb.state.value,
                "failure_count_bucket": _safe_count_bucket(cb.failure_count),
            },
        )

    def cleanup_expired(self) -> int:
        """Cleanup expired isolation records."""
        with self._lock:
            expired = []
            for node_id, record in self.isolated_nodes.items():
                if record.is_expired() and record.auto_recover:
                    expired.append(node_id)

            for node_id in expired:
                self.release(node_id)

            self._record_thinking(
                "auto_isolation_expired_cleaned",
                "Clean up expired auto-recoverable isolations",
                {"expired_count": len(expired)},
            )
            return len(expired)

    def get_isolated_nodes(self) -> List[Dict[str, Any]]:
        """Get all isolated nodes."""
        with self._lock:
            return [
                record.to_dict()
                for record in self.isolated_nodes.values()
                if not record.is_expired()
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Get isolation statistics."""
        with self._lock:
            by_level = defaultdict(int)
            by_reason = defaultdict(int)

            for record in self.isolated_nodes.values():
                if not record.is_expired():
                    by_level[record.level.name] += 1
                    by_reason[record.reason.value] += 1

            open_breakers = sum(
                1
                for cb in self.circuit_breakers.values()
                if cb.state != CircuitBreaker.State.CLOSED
            )

            stats = {
                "total_isolated": len(
                    [r for r in self.isolated_nodes.values() if not r.is_expired()]
                ),
                "by_level": dict(by_level),
                "by_reason": dict(by_reason),
                "open_circuit_breakers": open_breakers,
                "total_circuit_breakers": len(self.circuit_breakers),
            }
            self._record_thinking(
                "auto_isolation_stats_collected",
                "Collect isolation and circuit breaker statistics",
                {
                    "total_isolated_bucket": _safe_count_bucket(
                        stats["total_isolated"]
                    ),
                    "by_level": stats["by_level"],
                    "by_reason": stats["by_reason"],
                    "open_circuit_breakers": open_breakers,
                    "total_circuit_breakers": len(self.circuit_breakers),
                },
            )
            return stats


class QuarantineZone:
    """
    Network quarantine zone for isolated nodes.
    Provides limited sandbox environment for observation.
    """

    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.nodes: Set[str] = set()
        self.allowed_peers: Set[str] = set()
        self.max_bandwidth: int = 1024  # bytes/sec
        self.allowed_operations: Set[str] = {"health", "metrics"}
        self._lock = threading.Lock()
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"quarantine-zone:{_safe_hash(zone_id)}",
            role="security",
            capabilities=("zero-trust", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "quarantine_zone_init",
                "goal": "Initialize quarantine communication policy",
                "signals": {
                    "zone": {"hash": _safe_hash(zone_id), "present": True},
                    "allowed_operation_count": len(self.allowed_operations),
                    "max_bandwidth_bucket": _safe_count_bucket(self.max_bandwidth),
                },
                "safety_boundary": (
                    "Do not expose raw zone ids or node ids in quarantine thinking "
                    "context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_zone_identifier": True,
                    "redact_node_identifiers": True,
                    "preserve_quarantine_policy": True,
                },
                "safety_boundary": (
                    "Use hashes, counts, operation names, and boolean decisions only."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def add_node(self, node_id: str) -> None:
        """Add node to quarantine zone."""
        with self._lock:
            self.nodes.add(node_id)
            self._record_thinking(
                "quarantine_zone_node_added",
                "Add node to quarantine zone",
                {
                    "node": _safe_node_ref(node_id),
                    "node_count_bucket": _safe_count_bucket(len(self.nodes)),
                },
            )
            logger.info(f"Node {node_id} added to quarantine zone {self.zone_id}")

    def remove_node(self, node_id: str) -> None:
        """Remove node from quarantine zone."""
        with self._lock:
            self.nodes.discard(node_id)
            self._record_thinking(
                "quarantine_zone_node_removed",
                "Remove node from quarantine zone",
                {
                    "node": _safe_node_ref(node_id),
                    "node_count_bucket": _safe_count_bucket(len(self.nodes)),
                },
            )
            logger.info(f"Node {node_id} removed from quarantine zone {self.zone_id}")

    def is_quarantined(self, node_id: str) -> bool:
        """Check if node is quarantined."""
        return node_id in self.nodes

    def can_communicate(self, source: str, target: str) -> bool:
        """Check if communication is allowed in quarantine."""
        if source not in self.nodes and target not in self.nodes:
            allowed = True  # Neither quarantined
        elif source in self.nodes and target in self.nodes:
            allowed = True  # Both quarantined, can communicate
        elif target in self.allowed_peers or source in self.allowed_peers:
            allowed = True
        else:
            allowed = False

        self._record_thinking(
            "quarantine_zone_communication_checked",
            "Evaluate quarantine communication rule",
            {
                "source": _safe_node_ref(source),
                "target": _safe_node_ref(target),
                "source_quarantined": source in self.nodes,
                "target_quarantined": target in self.nodes,
                "allowed": allowed,
            },
        )
        return allowed

    def is_operation_allowed(self, operation: str) -> bool:
        """Check if operation is allowed in quarantine."""
        allowed = operation in self.allowed_operations
        self._record_thinking(
            "quarantine_zone_operation_checked",
            "Evaluate quarantine operation rule",
            {
                "operation": operation,
                "allowed": allowed,
                "allowed_operation_count": len(self.allowed_operations),
            },
        )
        return allowed
