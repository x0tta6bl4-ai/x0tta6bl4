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
import time
import logging
import threading
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class IsolationLevel(Enum):
    """Levels of node isolation."""
    NONE = 0           # Full access
    MONITOR = 1        # Increased monitoring, no restrictions
    RATE_LIMIT = 2     # Rate-limited access
    RESTRICTED = 3     # Limited to essential operations only
    QUARANTINE = 4     # No mesh communication, monitoring only
    BLOCKED = 5        # Complete network block


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
            "auto_recover": self.auto_recover
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
        duration = int(self.initial_duration * (self.escalation_multiplier ** escalation_count))
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
        CLOSED = "closed"      # Normal operation
        OPEN = "open"          # Circuit broken, no communication
        HALF_OPEN = "half_open"  # Testing if node recovered
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3
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
                IsolationLevel.BLOCKED
            ],
            escalation_threshold=2,
            initial_duration=300,  # 5 minutes
            escalation_multiplier=4.0,
            max_duration=86400,  # 24 hours
            auto_recover=True
        ),
        IsolationPolicy(
            name="trust_degradation",
            trigger_reason=IsolationReason.TRUST_DEGRADED,
            initial_level=IsolationLevel.RATE_LIMIT,
            escalation_levels=[
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED,
                IsolationLevel.QUARANTINE
            ],
            escalation_threshold=3,
            initial_duration=600,  # 10 minutes
            escalation_multiplier=2.0,
            max_duration=43200,  # 12 hours
            auto_recover=True
        ),
        IsolationPolicy(
            name="auth_failure",
            trigger_reason=IsolationReason.AUTHENTICATION_FAILURE,
            initial_level=IsolationLevel.RATE_LIMIT,
            escalation_levels=[
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED,
                IsolationLevel.BLOCKED
            ],
            escalation_threshold=5,
            initial_duration=60,  # 1 minute
            escalation_multiplier=3.0,
            max_duration=3600,  # 1 hour
            auto_recover=True
        ),
        IsolationPolicy(
            name="anomaly_detection",
            trigger_reason=IsolationReason.ANOMALY_DETECTED,
            initial_level=IsolationLevel.MONITOR,
            escalation_levels=[
                IsolationLevel.MONITOR,
                IsolationLevel.RATE_LIMIT,
                IsolationLevel.RESTRICTED
            ],
            escalation_threshold=3,
            initial_duration=120,  # 2 minutes
            escalation_multiplier=2.0,
            max_duration=7200,  # 2 hours
            auto_recover=True
        ),
        IsolationPolicy(
            name="protocol_violation",
            trigger_reason=IsolationReason.PROTOCOL_VIOLATION,
            initial_level=IsolationLevel.QUARANTINE,
            escalation_levels=[
                IsolationLevel.QUARANTINE,
                IsolationLevel.BLOCKED
            ],
            escalation_threshold=1,
            initial_duration=3600,  # 1 hour
            escalation_multiplier=4.0,
            max_duration=604800,  # 1 week
            auto_recover=False
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
        
        logger.info(f"AutoIsolationManager initialized for {node_id}")
    
    def register_callback(self, callback: Callable[[str, IsolationLevel], None]) -> None:
        """Register callback for isolation events."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, node_id: str, level: IsolationLevel) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(node_id, level)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def isolate(
        self,
        node_id: str,
        reason: IsolationReason,
        details: str = "",
        level_override: Optional[IsolationLevel] = None,
        duration_override: Optional[int] = None
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
                auto_recover=policy.auto_recover if policy else True
            )
            
            self.isolated_nodes[node_id] = record
            self._notify_callbacks(node_id, level)
            
            logger.warning(
                f"Isolated node {node_id}: level={level.name}, "
                f"reason={reason.value}, duration={duration}s"
            )
            
            return record
    
    def _escalate(
        self,
        node_id: str,
        current: IsolationRecord,
        violation_count: int
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
                return False
            
            record = self.isolated_nodes[node_id]
            
            if not record.auto_recover and not force:
                logger.warning(f"Cannot auto-release {node_id}, manual release required")
                return False
            
            del self.isolated_nodes[node_id]
            self._notify_callbacks(node_id, IsolationLevel.NONE)
            
            # Reset circuit breaker
            if node_id in self.circuit_breakers:
                self.circuit_breakers[node_id]._close()
            
            logger.info(f"Released node {node_id} from isolation")
            return True
    
    def get_isolation_level(self, node_id: str) -> IsolationLevel:
        """Get current isolation level for node."""
        with self._lock:
            if node_id not in self.isolated_nodes:
                return IsolationLevel.NONE
            
            record = self.isolated_nodes[node_id]
            
            if record.is_expired():
                if record.auto_recover:
                    self.release(node_id)
                    return IsolationLevel.NONE
            
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
            return False, "Circuit breaker open"
        
        # Level-based access control
        if level == IsolationLevel.NONE:
            return True, "OK"
        elif level == IsolationLevel.MONITOR:
            return True, "Monitored"
        elif level == IsolationLevel.RATE_LIMIT:
            # Would implement actual rate limiting here
            return True, "Rate limited"
        elif level == IsolationLevel.RESTRICTED:
            # Only essential operations
            essential = ["health", "heartbeat", "auth"]
            if operation in essential:
                return True, "Restricted - essential only"
            return False, f"Restricted - {operation} not allowed"
        elif level == IsolationLevel.QUARANTINE:
            if operation == "health":
                return True, "Quarantine - health only"
            return False, "Quarantine - blocked"
        else:  # BLOCKED
            return False, "Blocked"
    
    def record_success(self, node_id: str) -> None:
        """Record successful operation for circuit breaker."""
        self.circuit_breakers[node_id].record_success()
    
    def record_failure(self, node_id: str) -> None:
        """Record failed operation for circuit breaker."""
        self.circuit_breakers[node_id].record_failure()
    
    def cleanup_expired(self) -> int:
        """Cleanup expired isolation records."""
        with self._lock:
            expired = []
            for node_id, record in self.isolated_nodes.items():
                if record.is_expired() and record.auto_recover:
                    expired.append(node_id)
            
            for node_id in expired:
                self.release(node_id)
            
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
                1 for cb in self.circuit_breakers.values()
                if cb.state != CircuitBreaker.State.CLOSED
            )
            
            return {
                "total_isolated": len([r for r in self.isolated_nodes.values() if not r.is_expired()]),
                "by_level": dict(by_level),
                "by_reason": dict(by_reason),
                "open_circuit_breakers": open_breakers,
                "total_circuit_breakers": len(self.circuit_breakers)
            }


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
    
    def add_node(self, node_id: str) -> None:
        """Add node to quarantine zone."""
        with self._lock:
            self.nodes.add(node_id)
            logger.info(f"Node {node_id} added to quarantine zone {self.zone_id}")
    
    def remove_node(self, node_id: str) -> None:
        """Remove node from quarantine zone."""
        with self._lock:
            self.nodes.discard(node_id)
            logger.info(f"Node {node_id} removed from quarantine zone {self.zone_id}")
    
    def is_quarantined(self, node_id: str) -> bool:
        """Check if node is quarantined."""
        return node_id in self.nodes
    
    def can_communicate(self, source: str, target: str) -> bool:
        """Check if communication is allowed in quarantine."""
        if source not in self.nodes and target not in self.nodes:
            return True  # Neither quarantined
        
        if source in self.nodes and target in self.nodes:
            return True  # Both quarantined, can communicate
        
        # One quarantined, one not
        if target in self.allowed_peers or source in self.allowed_peers:
            return True
        
        return False
    
    def is_operation_allowed(self, operation: str) -> bool:
        """Check if operation is allowed in quarantine."""
        return operation in self.allowed_operations
