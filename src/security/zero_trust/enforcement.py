"""
Enhanced Zero Trust Enforcement

Production-ready Zero Trust enforcement with:
- Continuous verification
- Adaptive trust scoring
- Real-time policy enforcement
- Threat-based isolation
- Audit logging
"""
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Import existing components
try:
    from ..zero_trust.policy_engine import PolicyEngine, PolicyDecision, get_policy_engine
    from ..zero_trust import ZeroTrustValidator
    from ..auto_isolation import AutoIsolationManager, IsolationLevel
    from ..continuous_verification import ContinuousVerificationEngine
    ZERO_TRUST_AVAILABLE = True
except ImportError:
    ZERO_TRUST_AVAILABLE = False
    PolicyEngine = None  # type: ignore
    ZeroTrustValidator = None  # type: ignore
    AutoIsolationManager = None  # type: ignore
    ContinuousVerificationEngine = None  # type: ignore


class TrustScore(Enum):
    """Trust score levels"""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    TRUSTED = 4


@dataclass
class EnforcementResult:
    """Result of Zero Trust enforcement"""
    allowed: bool
    trust_score: TrustScore
    policy_decision: Optional[PolicyDecision] = None
    verification_result: Optional[Any] = None
    isolation_level: Optional[IsolationLevel] = None
    reason: Optional[str] = None


class ZeroTrustEnforcer:
    """
    Enhanced Zero Trust Enforcement Engine.
    
    Provides production-ready Zero Trust enforcement with:
    - Continuous verification
    - Adaptive trust scoring
    - Real-time policy enforcement
    - Threat-based isolation
    """
    
    def __init__(self):
        if not ZERO_TRUST_AVAILABLE:
            logger.warning("Zero Trust components not available")
            self.policy_engine = None
            self.validator = None
            self.isolation_manager = None
            self.verification_engine = None
        else:
            self.policy_engine = get_policy_engine()
            self.validator = ZeroTrustValidator()
            self.isolation_manager = AutoIsolationManager() if AutoIsolationManager else None
            self.verification_engine = ContinuousVerificationEngine() if ContinuousVerificationEngine else None
        
        # Trust score tracking
        self.trust_scores: Dict[str, float] = {}  # spiffe_id -> score (0.0-1.0)
        self.trust_history: Dict[str, List[float]] = {}  # spiffe_id -> [scores]
        
        # Enforcement statistics
        self.enforcement_stats = {
            "total_requests": 0,
            "allowed": 0,
            "denied": 0,
            "isolated": 0
        }
        
        logger.info("Zero Trust Enforcer initialized")
    
    def enforce(
        self,
        peer_spiffe_id: str,
        resource: Optional[str] = None,
        action: Optional[str] = None
    ) -> EnforcementResult:
        """
        Enforce Zero Trust policy for a peer request.
        
        Args:
            peer_spiffe_id: SPIFFE ID of the peer
            resource: Resource being accessed
            action: Action being performed
        
        Returns:
            EnforcementResult with allow/deny decision
        """
        self.enforcement_stats["total_requests"] += 1
        
        # 1. Check if peer is isolated
        if self.isolation_manager:
            isolation = self.isolation_manager.get_isolation_status(peer_spiffe_id)
            if isolation and isolation.level.value >= IsolationLevel.QUARANTINED.value:
                self.enforcement_stats["denied"] += 1
                return EnforcementResult(
                    allowed=False,
                    trust_score=TrustScore.UNTRUSTED,
                    isolation_level=isolation.level,
                    reason=f"Peer is isolated: {isolation.reason}"
                )
        
        # 2. Validate SPIFFE identity
        if self.validator:
            try:
                is_valid = self.validator.validate_connection(peer_spiffe_id)
                if not is_valid:
                    self.enforcement_stats["denied"] += 1
                    return EnforcementResult(
                        allowed=False,
                        trust_score=TrustScore.UNTRUSTED,
                        reason="SPIFFE identity validation failed"
                    )
            except Exception as e:
                logger.error(f"SPIFFE validation error: {e}")
                self.enforcement_stats["denied"] += 1
                return EnforcementResult(
                    allowed=False,
                    trust_score=TrustScore.UNTRUSTED,
                    reason=f"Validation error: {str(e)}"
                )
        
        # 3. Evaluate policy
        policy_decision = None
        if self.policy_engine:
            policy_decision = self.policy_engine.evaluate(
                peer_spiffe_id=peer_spiffe_id,
                resource=resource
            )
            
            if not policy_decision.allowed:
                self.enforcement_stats["denied"] += 1
                return EnforcementResult(
                    allowed=False,
                    trust_score=TrustScore.LOW,
                    policy_decision=policy_decision,
                    reason=policy_decision.reason
                )
        
        # 4. Continuous verification (if enabled)
        verification_result = None
        if self.verification_engine:
            try:
                verification_result = self.verification_engine.verify(peer_spiffe_id)
                if verification_result and not verification_result.verified:
                    # Lower trust score but don't deny immediately
                    self._update_trust_score(peer_spiffe_id, -0.1)
            except Exception as e:
                logger.warning(f"Verification error: {e}")
        
        # 5. Calculate trust score
        trust_score = self._calculate_trust_score(peer_spiffe_id)
        
        # 6. Adaptive enforcement based on trust score
        if trust_score == TrustScore.UNTRUSTED:
            # Isolate untrusted peers
            if self.isolation_manager:
                self.isolation_manager.isolate(
                    peer_spiffe_id=peer_spiffe_id,
                    level=IsolationLevel.QUARANTINED,
                    reason="Untrusted trust score"
                )
            self.enforcement_stats["denied"] += 1
            self.enforcement_stats["isolated"] += 1
            return EnforcementResult(
                allowed=False,
                trust_score=trust_score,
                policy_decision=policy_decision,
                verification_result=verification_result,
                isolation_level=IsolationLevel.QUARANTINED,
                reason="Untrusted trust score"
            )
        
        # 7. Allow with appropriate trust level
        self.enforcement_stats["allowed"] += 1
        self._update_trust_score(peer_spiffe_id, 0.05)  # Reward successful access
        
        return EnforcementResult(
            allowed=True,
            trust_score=trust_score,
            policy_decision=policy_decision,
            verification_result=verification_result,
            reason="Access granted"
        )
    
    def _calculate_trust_score(self, peer_spiffe_id: str) -> TrustScore:
        """Calculate trust score for peer"""
        # Get current score
        current_score = self.trust_scores.get(peer_spiffe_id, 0.5)  # Default medium
        
        # Consider history
        history = self.trust_history.get(peer_spiffe_id, [])
        if history:
            avg_score = sum(history[-10:]) / len(history[-10:])  # Last 10 scores
            current_score = (current_score * 0.7) + (avg_score * 0.3)  # Weighted average
        
        # Map to TrustScore enum
        if current_score < 0.2:
            return TrustScore.UNTRUSTED
        elif current_score < 0.4:
            return TrustScore.LOW
        elif current_score < 0.7:
            return TrustScore.MEDIUM
        elif current_score < 0.9:
            return TrustScore.HIGH
        else:
            return TrustScore.TRUSTED
    
    def _update_trust_score(self, peer_spiffe_id: str, delta: float):
        """Update trust score for peer"""
        current_score = self.trust_scores.get(peer_spiffe_id, 0.5)
        new_score = max(0.0, min(1.0, current_score + delta))
        self.trust_scores[peer_spiffe_id] = new_score
        
        # Update history
        if peer_spiffe_id not in self.trust_history:
            self.trust_history[peer_spiffe_id] = []
        self.trust_history[peer_spiffe_id].append(new_score)
        
        # Keep only last 100 scores
        if len(self.trust_history[peer_spiffe_id]) > 100:
            self.trust_history[peer_spiffe_id] = self.trust_history[peer_spiffe_id][-100:]
    
    def get_enforcement_stats(self) -> Dict[str, Any]:
        """Get enforcement statistics"""
        total = self.enforcement_stats["total_requests"]
        if total == 0:
            return {
                **self.enforcement_stats,
                "allow_rate": 0.0,
                "deny_rate": 0.0
            }
        
        return {
            **self.enforcement_stats,
            "allow_rate": self.enforcement_stats["allowed"] / total,
            "deny_rate": self.enforcement_stats["denied"] / total,
            "isolation_rate": self.enforcement_stats["isolated"] / total,
            "tracked_peers": len(self.trust_scores)
        }


# Global instance
_zero_trust_enforcer: Optional[ZeroTrustEnforcer] = None


def get_zero_trust_enforcer() -> ZeroTrustEnforcer:
    """Get global Zero Trust Enforcer instance"""
    global _zero_trust_enforcer
    if _zero_trust_enforcer is None:
        _zero_trust_enforcer = ZeroTrustEnforcer()
    return _zero_trust_enforcer

