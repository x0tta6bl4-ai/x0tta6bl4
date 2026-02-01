"""
Reputation Scoring System for Domains and Proxies.

Implements:
- Domain reputation tracking with exponential decay
- Proxy trust scoring
- Block detection and recovery
- Anomaly detection for unusual patterns
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class ReputationLevel(Enum):
    """Reputation levels for domains and proxies."""
    EXCELLENT = (0.9, 1.0)
    GOOD = (0.7, 0.9)
    FAIR = (0.5, 0.7)
    POOR = (0.3, 0.5)
    BAD = (0.0, 0.3)
    UNKNOWN = (0.0, 0.0)
    
    def __init__(self, min_score: float, max_score: float):
        self.min_score = min_score
        self.max_score = max_score
    
    @classmethod
    def from_score(cls, score: float) -> "ReputationLevel":
        """Get reputation level from score."""
        for level in cls:
            if level != cls.UNKNOWN and level.min_score <= score <= level.max_score:
                return level
        return cls.UNKNOWN


@dataclass
class ReputationEvent:
    """Single reputation event."""
    timestamp: float
    success: bool
    latency_ms: float
    proxy_id: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainReputation:
    """Comprehensive domain reputation tracking."""
    domain: str
    score: float = 0.5
    events: List[ReputationEvent] = field(default_factory=list)
    block_events: int = 0
    success_streak: int = 0
    failure_streak: int = 0
    last_access: float = field(default_factory=time.time)
    first_seen: float = field(default_factory=time.time)
    
    # Exponential decay parameters
    decay_factor: float = 0.95  # Decay per day
    success_boost: float = 0.05
    failure_penalty: float = 0.1
    block_penalty: float = 0.3
    
    def record_event(self, event: ReputationEvent):
        """Record a new reputation event."""
        self.events.append(event)
        self.last_access = event.timestamp
        
        # Apply decay based on time since last event
        time_diff_days = (event.timestamp - self.last_access) / 86400
        self.score *= (self.decay_factor ** time_diff_days)
        
        if event.success:
            self.success_streak += 1
            self.failure_streak = 0
            
            # Boost score for success
            boost = self.success_boost * (1 + self.success_streak * 0.1)
            self.score = min(1.0, self.score + boost)
        else:
            self.failure_streak += 1
            self.success_streak = 0
            
            # Penalize for failure
            penalty = self.failure_penalty * (1 + self.failure_streak * 0.2)
            
            # Additional penalty for blocks
            if event.error_type in ("blocked", "captcha", "rate_limited"):
                penalty += self.block_penalty
                self.block_events += 1
            
            self.score = max(0.0, self.score - penalty)
        
        # Keep only recent events (last 100)
        if len(self.events) > 100:
            self.events = self.events[-100:]
    
    def get_level(self) -> ReputationLevel:
        """Get current reputation level."""
        return ReputationLevel.from_score(self.score)
    
    def is_trusted(self, threshold: float = 0.5) -> bool:
        """Check if domain is trusted."""
        return self.score >= threshold
    
    def get_success_rate(self, window: int = 20) -> float:
        """Calculate recent success rate."""
        recent = self.events[-window:] if len(self.events) >= window else self.events
        if not recent:
            return 0.5
        successes = sum(1 for e in recent if e.success)
        return successes / len(recent)
    
    def get_avg_latency(self, window: int = 20) -> float:
        """Calculate average latency."""
        recent = self.events[-window:] if len(self.events) >= window else self.events
        if not recent:
            return 0.0
        return statistics.mean(e.latency_ms for e in recent)
    
    def get_risk_score(self) -> float:
        """
        Calculate risk score (0-1, higher = riskier).
        
        Factors:
        - Low reputation score
        - High block rate
        - Recent failures
        """
        risk = 0.0
        
        # Reputation-based risk
        risk += (1 - self.score) * 0.4
        
        # Block-based risk
        total_events = len(self.events)
        if total_events > 0:
            block_rate = self.block_events / total_events
            risk += block_rate * 0.3
        
        # Recent failure streak
        risk += min(0.3, self.failure_streak * 0.1)
        
        return min(1.0, risk)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain": self.domain,
            "score": round(self.score, 3),
            "level": self.get_level().name,
            "success_rate": round(self.get_success_rate(), 3),
            "avg_latency_ms": round(self.get_avg_latency(), 2),
            "risk_score": round(self.get_risk_score(), 3),
            "block_events": self.block_events,
            "success_streak": self.success_streak,
            "failure_streak": self.failure_streak,
            "total_events": len(self.events),
            "last_access": self.last_access,
            "first_seen": self.first_seen
        }


@dataclass
class ProxyTrustScore:
    """Trust scoring for individual proxies."""
    proxy_id: str
    trust_score: float = 0.5
    reliability_score: float = 0.5
    performance_score: float = 0.5
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    
    latency_history: List[float] = field(default_factory=list)
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    
    def record_result(
        self,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None
    ):
        """Record request result."""
        self.total_requests += 1
        self.last_used = time.time()
        self.latency_history.append(latency_ms)
        
        # Keep only last 100 latency samples
        if len(self.latency_history) > 100:
            self.latency_history = self.latency_history[-100:]
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error_type:
                self.error_types[error_type] += 1
                if error_type in ("blocked", "banned"):
                    self.blocked_requests += 1
        
        # Update scores
        self._update_reliability()
        self._update_performance()
        self._update_trust()
    
    def _update_reliability(self):
        """Update reliability score based on success rate."""
        if self.total_requests < 5:
            return  # Insufficient data
        
        success_rate = self.successful_requests / self.total_requests
        
        # Penalize for blocks
        block_rate = self.blocked_requests / self.total_requests if self.total_requests > 0 else 0
        
        self.reliability_score = max(0.0, success_rate - block_rate * 0.5)
    
    def _update_performance(self):
        """Update performance score based on latency."""
        if not self.latency_history:
            return
        
        avg_latency = statistics.mean(self.latency_history[-20:])
        
        # Score based on latency tiers
        if avg_latency < 100:
            self.performance_score = 1.0
        elif avg_latency < 300:
            self.performance_score = 0.9
        elif avg_latency < 500:
            self.performance_score = 0.7
        elif avg_latency < 1000:
            self.performance_score = 0.5
        else:
            self.performance_score = max(0.0, 1.0 - (avg_latency / 2000))
    
    def _update_trust(self):
        """Update overall trust score."""
        # Weighted combination
        self.trust_score = (
            self.reliability_score * 0.6 +
            self.performance_score * 0.4
        )
    
    def get_error_breakdown(self) -> Dict[str, int]:
        """Get breakdown of error types."""
        return dict(self.error_types)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proxy_id": self.proxy_id,
            "trust_score": round(self.trust_score, 3),
            "reliability_score": round(self.reliability_score, 3),
            "performance_score": round(self.performance_score, 3),
            "total_requests": self.total_requests,
            "success_rate": round(
                self.successful_requests / self.total_requests, 3
            ) if self.total_requests > 0 else 0,
            "avg_latency_ms": round(
                statistics.mean(self.latency_history[-20:]), 2
            ) if self.latency_history else 0,
            "error_breakdown": self.get_error_breakdown()
        }


class ReputationScoringSystem:
    """
    Centralized reputation scoring system.
    """
    
    def __init__(self):
        self.domain_reputations: Dict[str, DomainReputation] = {}
        self.proxy_trust_scores: Dict[str, ProxyTrustScore] = {}
        self._lock = asyncio.Lock()
    
    async def record_domain_event(
        self,
        domain: str,
        success: bool,
        latency_ms: float,
        proxy_id: Optional[str] = None,
        error_type: Optional[str] = None
    ):
        """Record an event for a domain."""
        async with self._lock:
            if domain not in self.domain_reputations:
                self.domain_reputations[domain] = DomainReputation(domain=domain)
            
            event = ReputationEvent(
                timestamp=time.time(),
                success=success,
                latency_ms=latency_ms,
                proxy_id=proxy_id,
                error_type=error_type
            )
            
            self.domain_reputations[domain].record_event(event)
    
    async def record_proxy_result(
        self,
        proxy_id: str,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None
    ):
        """Record a result for a proxy."""
        async with self._lock:
            if proxy_id not in self.proxy_trust_scores:
                self.proxy_trust_scores[proxy_id] = ProxyTrustScore(proxy_id=proxy_id)
            
            self.proxy_trust_scores[proxy_id].record_result(
                success=success,
                latency_ms=latency_ms,
                error_type=error_type
            )
    
    def get_domain_reputation(self, domain: str) -> Optional[DomainReputation]:
        """Get reputation for a domain."""
        return self.domain_reputations.get(domain)
    
    def get_proxy_trust(self, proxy_id: str) -> Optional[ProxyTrustScore]:
        """Get trust score for a proxy."""
        return self.proxy_trust_scores.get(proxy_id)
    
    def get_high_risk_domains(self, threshold: float = 0.5) -> List[DomainReputation]:
        """Get domains with high risk scores."""
        return [
            rep for rep in self.domain_reputations.values()
            if rep.get_risk_score() >= threshold
        ]
    
    def get_trusted_proxies(self, min_trust: float = 0.6) -> List[ProxyTrustScore]:
        """Get proxies with high trust scores."""
        return [
            score for score in self.proxy_trust_scores.values()
            if score.trust_score >= min_trust
        ]
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Generate system recommendations."""
        recommendations = []
        
        # Check for problematic domains
        high_risk = self.get_high_risk_domains()
        for domain in high_risk[:5]:  # Top 5
            recommendations.append({
                "type": "high_risk_domain",
                "severity": "high",
                "domain": domain.domain,
                "risk_score": round(domain.get_risk_score(), 3),
                "recommendation": "Consider using residential proxies or rotating more frequently"
            })
        
        # Check for untrusted proxies
        untrusted = [
            score for score in self.proxy_trust_scores.values()
            if score.trust_score < 0.3 and score.total_requests > 10
        ]
        for proxy in untrusted[:5]:
            recommendations.append({
                "type": "untrusted_proxy",
                "severity": "medium",
                "proxy_id": proxy.proxy_id,
                "trust_score": round(proxy.trust_score, 3),
                "recommendation": "Consider removing or investigating this proxy"
            })
        
        return recommendations
    
    def export_stats(self) -> Dict[str, Any]:
        """Export comprehensive statistics."""
        return {
            "domains": {
                "total": len(self.domain_reputations),
                "by_level": {
                    level.name: sum(
                        1 for d in self.domain_reputations.values()
                        if d.get_level() == level
                    )
                    for level in ReputationLevel
                },
                "high_risk": len(self.get_high_risk_domains())
            },
            "proxies": {
                "total": len(self.proxy_trust_scores),
                "trusted": len(self.get_trusted_proxies()),
                "avg_trust_score": round(
                    statistics.mean(
                        s.trust_score for s in self.proxy_trust_scores.values()
                    ), 3
                ) if self.proxy_trust_scores else 0
            },
            "recommendations": self.get_recommendations()
        }
