"""
Continuous Verification Module for x0tta6bl4 Mesh Zero Trust.
Never trust, always verify - continuously.

Implements:
- Session re-validation
- Behavioral analysis
- Anomaly-based re-authentication
- Risk scoring
- Adaptive verification frequency

Zero Trust Principle: Trust is never implicit and must be continuously earned.
"""
import time
import logging
import threading
import hashlib
import statistics
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class VerificationResult(Enum):
    """Result of verification check."""
    PASSED = "passed"
    FAILED = "failed"
    DEGRADED = "degraded"  # Passed with warnings
    PENDING = "pending"
    SKIPPED = "skipped"


class RiskLevel(Enum):
    """Risk assessment levels."""
    MINIMAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class VerificationType(Enum):
    """Types of verification checks."""
    IDENTITY = "identity"
    DEVICE = "device"
    BEHAVIOR = "behavior"
    NETWORK = "network"
    CREDENTIAL = "credential"
    SESSION = "session"
    RESOURCE = "resource"


@dataclass
class VerificationCheck:
    """Single verification check result."""
    check_id: str
    type: VerificationType
    result: VerificationResult
    score: float  # 0.0 - 1.0
    details: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "type": self.type.value,
            "result": self.result.value,
            "score": self.score,
            "details": self.details,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms
        }


@dataclass
class Session:
    """User/node session with continuous verification state."""
    session_id: str
    entity_id: str  # Node ID or user ID
    created_at: float
    last_verified_at: float
    last_activity_at: float
    verification_count: int = 0
    failed_verifications: int = 0
    risk_score: float = 0.0
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "entity_id": self.entity_id,
            "created_at": self.created_at,
            "last_verified_at": self.last_verified_at,
            "last_activity_at": self.last_activity_at,
            "verification_count": self.verification_count,
            "failed_verifications": self.failed_verifications,
            "risk_score": self.risk_score,
            "is_active": self.is_active
        }


@dataclass
class BehaviorProfile:
    """Behavioral profile for anomaly detection."""
    entity_id: str
    # Activity patterns
    typical_hours: Set[int] = field(default_factory=set)  # Hours of day
    typical_actions: Dict[str, int] = field(default_factory=dict)  # Action frequencies
    typical_resources: Set[str] = field(default_factory=set)
    avg_request_rate: float = 0.0  # Requests per minute
    avg_session_duration: float = 0.0  # Minutes
    # Statistical baselines
    request_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    action_sequence: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update(self, action: str, resource: str, timestamp: float) -> None:
        """Update profile with new activity."""
        hour = int((timestamp % 86400) / 3600)
        self.typical_hours.add(hour)
        self.typical_actions[action] = self.typical_actions.get(action, 0) + 1
        self.typical_resources.add(resource)
        self.request_times.append(timestamp)
        self.action_sequence.append(action)
        
        # Update request rate
        if len(self.request_times) >= 2:
            time_span = self.request_times[-1] - self.request_times[0]
            if time_span > 0:
                self.avg_request_rate = len(self.request_times) / (time_span / 60)


class VerificationStrategy(ABC):
    """Abstract base for verification strategies."""
    
    @abstractmethod
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        """Perform verification check."""
        pass


class IdentityVerificationStrategy(VerificationStrategy):
    """Verify entity identity."""
    
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        start = time.time()
        
        # Check if identity claims are still valid
        entity_id = session.entity_id
        claimed_id = context.get("claimed_id", entity_id)
        
        if entity_id != claimed_id:
            return VerificationCheck(
                check_id=f"identity-{session.session_id}",
                type=VerificationType.IDENTITY,
                result=VerificationResult.FAILED,
                score=0.0,
                details=f"Identity mismatch: {entity_id} vs {claimed_id}",
                duration_ms=(time.time() - start) * 1000
            )
        
        # Check DID validity if present
        did = context.get("did")
        if did and not did.startswith("did:"):
            return VerificationCheck(
                check_id=f"identity-{session.session_id}",
                type=VerificationType.IDENTITY,
                result=VerificationResult.FAILED,
                score=0.0,
                details="Invalid DID format",
                duration_ms=(time.time() - start) * 1000
            )
        
        return VerificationCheck(
            check_id=f"identity-{session.session_id}",
            type=VerificationType.IDENTITY,
            result=VerificationResult.PASSED,
            score=1.0,
            details="Identity verified",
            duration_ms=(time.time() - start) * 1000
        )


class DeviceVerificationStrategy(VerificationStrategy):
    """Verify device attestation."""
    
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        start = time.time()
        
        device_fingerprint = context.get("device_fingerprint")
        original_fingerprint = session.metadata.get("device_fingerprint")
        
        if original_fingerprint and device_fingerprint != original_fingerprint:
            return VerificationCheck(
                check_id=f"device-{session.session_id}",
                type=VerificationType.DEVICE,
                result=VerificationResult.FAILED,
                score=0.0,
                details="Device fingerprint changed",
                duration_ms=(time.time() - start) * 1000
            )
        
        # Check device trust level
        trust_level = context.get("device_trust_level", 50)
        if trust_level < 30:
            return VerificationCheck(
                check_id=f"device-{session.session_id}",
                type=VerificationType.DEVICE,
                result=VerificationResult.DEGRADED,
                score=trust_level / 100,
                details=f"Low device trust: {trust_level}",
                duration_ms=(time.time() - start) * 1000
            )
        
        return VerificationCheck(
            check_id=f"device-{session.session_id}",
            type=VerificationType.DEVICE,
            result=VerificationResult.PASSED,
            score=trust_level / 100,
            details="Device verified",
            duration_ms=(time.time() - start) * 1000
        )


class BehaviorVerificationStrategy(VerificationStrategy):
    """Verify behavioral patterns for anomalies."""
    
    def __init__(self):
        self.profiles: Dict[str, BehaviorProfile] = {}
    
    def get_profile(self, entity_id: str) -> BehaviorProfile:
        """Get or create behavior profile."""
        if entity_id not in self.profiles:
            self.profiles[entity_id] = BehaviorProfile(entity_id=entity_id)
        return self.profiles[entity_id]
    
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        start = time.time()
        profile = self.get_profile(session.entity_id)
        
        anomalies = []
        score = 1.0
        
        # Check time of day
        current_hour = int((time.time() % 86400) / 3600)
        if profile.typical_hours and current_hour not in profile.typical_hours:
            anomalies.append(f"Unusual hour: {current_hour}")
            score -= 0.2
        
        # Check action frequency
        action = context.get("action", "unknown")
        if profile.typical_actions:
            total_actions = sum(profile.typical_actions.values())
            action_freq = profile.typical_actions.get(action, 0) / total_actions if total_actions > 0 else 0
            if action_freq < 0.01 and total_actions > 100:
                anomalies.append(f"Rare action: {action}")
                score -= 0.15
        
        # Check request rate
        current_rate = context.get("request_rate", 0)
        if profile.avg_request_rate > 0 and current_rate > profile.avg_request_rate * 5:
            anomalies.append(f"High request rate: {current_rate:.1f}/min vs avg {profile.avg_request_rate:.1f}")
            score -= 0.3
        
        # Check resource access
        resource = context.get("resource", "")
        if profile.typical_resources and resource not in profile.typical_resources:
            if len(profile.typical_resources) > 10:  # Only flag if we have enough data
                anomalies.append(f"New resource access: {resource}")
                score -= 0.1
        
        # Update profile
        profile.update(action, resource, time.time())
        
        score = max(0.0, score)
        
        if score < 0.5:
            result = VerificationResult.FAILED
        elif score < 0.8:
            result = VerificationResult.DEGRADED
        else:
            result = VerificationResult.PASSED
        
        return VerificationCheck(
            check_id=f"behavior-{session.session_id}",
            type=VerificationType.BEHAVIOR,
            result=result,
            score=score,
            details="; ".join(anomalies) if anomalies else "Behavior normal",
            duration_ms=(time.time() - start) * 1000
        )


class NetworkVerificationStrategy(VerificationStrategy):
    """Verify network context."""
    
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        start = time.time()
        anomalies = []
        score = 1.0
        
        # Check source IP consistency
        current_ip = context.get("source_ip")
        original_ip = session.metadata.get("source_ip")
        
        if original_ip and current_ip and current_ip != original_ip:
            # IP change could be legitimate (mobile, VPN) but flag it
            anomalies.append(f"IP changed: {original_ip} -> {current_ip}")
            score -= 0.2
        
        # Check network location
        current_country = context.get("country")
        original_country = session.metadata.get("country")
        
        if original_country and current_country and current_country != original_country:
            anomalies.append(f"Country changed: {original_country} -> {current_country}")
            score -= 0.3
        
        # Check for known malicious indicators
        is_tor = context.get("is_tor", False)
        is_proxy = context.get("is_proxy", False)
        
        if is_tor:
            anomalies.append("Tor exit node detected")
            score -= 0.1  # Not necessarily bad, just note it
        
        if is_proxy:
            anomalies.append("Proxy detected")
            score -= 0.1
        
        score = max(0.0, score)
        
        if score < 0.5:
            result = VerificationResult.FAILED
        elif score < 0.8:
            result = VerificationResult.DEGRADED
        else:
            result = VerificationResult.PASSED
        
        return VerificationCheck(
            check_id=f"network-{session.session_id}",
            type=VerificationType.NETWORK,
            result=result,
            score=score,
            details="; ".join(anomalies) if anomalies else "Network context normal",
            duration_ms=(time.time() - start) * 1000
        )


class SessionVerificationStrategy(VerificationStrategy):
    """Verify session validity and freshness."""
    
    def __init__(self, max_idle_minutes: int = 30, max_age_hours: int = 24):
        self.max_idle = max_idle_minutes * 60
        self.max_age = max_age_hours * 3600
    
    def verify(self, session: Session, context: Dict[str, Any]) -> VerificationCheck:
        start = time.time()
        now = time.time()
        
        # Check session age
        session_age = now - session.created_at
        if session_age > self.max_age:
            return VerificationCheck(
                check_id=f"session-{session.session_id}",
                type=VerificationType.SESSION,
                result=VerificationResult.FAILED,
                score=0.0,
                details=f"Session expired (age: {session_age/3600:.1f}h)",
                duration_ms=(time.time() - start) * 1000
            )
        
        # Check idle time
        idle_time = now - session.last_activity_at
        if idle_time > self.max_idle:
            return VerificationCheck(
                check_id=f"session-{session.session_id}",
                type=VerificationType.SESSION,
                result=VerificationResult.FAILED,
                score=0.0,
                details=f"Session idle too long ({idle_time/60:.1f}min)",
                duration_ms=(time.time() - start) * 1000
            )
        
        # Check failure rate
        if session.verification_count > 0:
            failure_rate = session.failed_verifications / session.verification_count
            if failure_rate > 0.3:
                return VerificationCheck(
                    check_id=f"session-{session.session_id}",
                    type=VerificationType.SESSION,
                    result=VerificationResult.DEGRADED,
                    score=1.0 - failure_rate,
                    details=f"High failure rate: {failure_rate:.1%}",
                    duration_ms=(time.time() - start) * 1000
                )
        
        # Calculate freshness score
        age_score = max(0, 1 - (session_age / self.max_age))
        idle_score = max(0, 1 - (idle_time / self.max_idle))
        score = (age_score + idle_score) / 2
        
        return VerificationCheck(
            check_id=f"session-{session.session_id}",
            type=VerificationType.SESSION,
            result=VerificationResult.PASSED,
            score=score,
            details=f"Session valid (age: {session_age/60:.1f}min, idle: {idle_time/60:.1f}min)",
            duration_ms=(time.time() - start) * 1000
        )


class ContinuousVerificationEngine:
    """
    Core engine for continuous verification.
    Orchestrates multiple verification strategies.
    """
    
    def __init__(
        self,
        node_id: str,
        base_interval_seconds: int = 60,
        max_interval_seconds: int = 300
    ):
        self.node_id = node_id
        self.base_interval = base_interval_seconds
        self.max_interval = max_interval_seconds
        
        self.sessions: Dict[str, Session] = {}
        self.strategies: Dict[VerificationType, VerificationStrategy] = {
            VerificationType.IDENTITY: IdentityVerificationStrategy(),
            VerificationType.DEVICE: DeviceVerificationStrategy(),
            VerificationType.BEHAVIOR: BehaviorVerificationStrategy(),
            VerificationType.NETWORK: NetworkVerificationStrategy(),
            VerificationType.SESSION: SessionVerificationStrategy(),
        }
        
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[Session, List[VerificationCheck]], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info(f"ContinuousVerificationEngine initialized for {node_id}")
    
    def register_callback(
        self,
        callback: Callable[[Session, List[VerificationCheck]], None]
    ) -> None:
        """Register callback for verification events."""
        self._callbacks.append(callback)
    
    def create_session(
        self,
        entity_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Session:
        """Create new session for entity."""
        session_id = hashlib.sha256(
            f"{entity_id}:{time.time()}:{self.node_id}".encode()
        ).hexdigest()[:32]
        
        now = time.time()
        session = Session(
            session_id=session_id,
            entity_id=entity_id,
            created_at=now,
            last_verified_at=now,
            last_activity_at=now,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.sessions[session_id] = session
        
        logger.info(f"Created session {session_id} for {entity_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def terminate_session(self, session_id: str) -> bool:
        """Terminate a session."""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].is_active = False
                logger.info(f"Terminated session {session_id}")
                return True
            return False
    
    def verify_session(
        self,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        check_types: Optional[List[VerificationType]] = None
    ) -> Tuple[bool, List[VerificationCheck], float]:
        """
        Verify a session with all applicable strategies.
        
        Args:
            session_id: Session to verify
            context: Additional context for verification
            check_types: Specific checks to run (None = all)
            
        Returns:
            (passed, checks, aggregate_score)
        """
        session = self.sessions.get(session_id)
        if not session:
            return False, [], 0.0
        
        if not session.is_active:
            return False, [], 0.0
        
        context = context or {}
        checks = []
        
        # Determine which checks to run
        types_to_check = check_types or list(self.strategies.keys())
        
        # Run verification strategies
        for vtype in types_to_check:
            if vtype in self.strategies:
                try:
                    check = self.strategies[vtype].verify(session, context)
                    checks.append(check)
                except Exception as e:
                    logger.error(f"Verification error for {vtype}: {e}")
                    checks.append(VerificationCheck(
                        check_id=f"{vtype.value}-error",
                        type=vtype,
                        result=VerificationResult.FAILED,
                        score=0.0,
                        details=f"Error: {e}"
                    ))
        
        # Calculate aggregate score
        if checks:
            aggregate_score = statistics.mean(c.score for c in checks)
        else:
            aggregate_score = 0.0
        
        # Update session
        session.last_verified_at = time.time()
        session.verification_count += 1
        
        # Determine overall result
        failed_checks = [c for c in checks if c.result == VerificationResult.FAILED]
        if failed_checks:
            session.failed_verifications += 1
            passed = False
        else:
            passed = True
        
        # Update risk score
        session.risk_score = 1.0 - aggregate_score
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(session, checks)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        return passed, checks, aggregate_score
    
    def record_activity(self, session_id: str) -> None:
        """Record activity for session."""
        session = self.sessions.get(session_id)
        if session:
            session.last_activity_at = time.time()
    
    def get_verification_interval(self, session: Session) -> int:
        """
        Get adaptive verification interval based on risk.
        Higher risk = more frequent verification.
        """
        if session.risk_score > 0.7:
            return self.base_interval  # High risk: frequent checks
        elif session.risk_score > 0.4:
            return self.base_interval * 2  # Medium risk
        else:
            return self.max_interval  # Low risk: less frequent
    
    def should_verify(self, session: Session) -> bool:
        """Check if session should be verified now."""
        interval = self.get_verification_interval(session)
        time_since_last = time.time() - session.last_verified_at
        return time_since_last >= interval
    
    def start_background_verification(self) -> None:
        """Start background verification thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._verification_loop, daemon=True)
        self._thread.start()
        logger.info("Background verification started")
    
    def stop_background_verification(self) -> None:
        """Stop background verification thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Background verification stopped")
    
    def _verification_loop(self) -> None:
        """Background verification loop."""
        while self._running:
            try:
                with self._lock:
                    sessions_to_verify = [
                        s for s in self.sessions.values()
                        if s.is_active and self.should_verify(s)
                    ]
                
                for session in sessions_to_verify:
                    try:
                        passed, checks, score = self.verify_session(session.session_id)
                        
                        if not passed:
                            logger.warning(
                                f"Session {session.session_id} failed verification: "
                                f"score={score:.2f}"
                            )
                    except Exception as e:
                        logger.error(f"Error verifying session {session.session_id}: {e}")
                
                # Clean up inactive sessions
                self._cleanup_sessions()
                
            except Exception as e:
                logger.error(f"Error in verification loop: {e}")
            
            time.sleep(10)  # Check every 10 seconds
    
    def _cleanup_sessions(self) -> None:
        """Clean up expired/inactive sessions."""
        with self._lock:
            now = time.time()
            max_age = 24 * 3600  # 24 hours
            
            expired = [
                sid for sid, s in self.sessions.items()
                if not s.is_active or (now - s.last_activity_at) > max_age
            ]
            
            for sid in expired:
                del self.sessions[sid]
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        with self._lock:
            active = sum(1 for s in self.sessions.values() if s.is_active)
            high_risk = sum(1 for s in self.sessions.values() if s.risk_score > 0.7)
            
            return {
                "total_sessions": len(self.sessions),
                "active_sessions": active,
                "high_risk_sessions": high_risk,
                "background_running": self._running,
                "base_interval": self.base_interval,
                "max_interval": self.max_interval
            }
