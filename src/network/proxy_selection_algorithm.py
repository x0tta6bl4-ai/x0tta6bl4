"""
Advanced Proxy Selection Algorithm with ML-based scoring.

Implements:
- Weighted scoring based on latency, success rate, and reputation
- Predictive proxy selection using historical performance
- Adaptive load balancing
- Anti-pattern detection and avoidance
"""
import asyncio
import logging
import random
import secrets
import time
from typing import List, Optional, Dict, Any, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import statistics

from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Proxy selection strategies."""
    WEIGHTED_SCORE = "weighted_score"
    LOWEST_LATENCY = "lowest_latency"
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    PREDICTIVE = "predictive"
    GEOGRAPHIC = "geographic"


@dataclass
class ProxyMetrics:
    """Historical metrics for proxy performance prediction."""
    proxy_id: str
    latency_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    success_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    timestamp_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    
    def add_sample(self, latency_ms: float, success: bool):
        """Add a new performance sample."""
        self.latency_history.append(latency_ms)
        self.success_history.append(1.0 if success else 0.0)
        self.timestamp_history.append(time.time())
    
    def get_success_rate(self, window: int = 20) -> float:
        """Calculate success rate over recent window."""
        if not self.success_history:
            return 0.5  # Neutral default
        recent = list(self.success_history)[-window:]
        return sum(recent) / len(recent)
    
    def get_avg_latency(self, window: int = 20) -> float:
        """Calculate average latency over recent window."""
        if not self.latency_history:
            return 1000.0  # High default
        recent = list(self.latency_history)[-window:]
        return statistics.mean(recent) if recent else 1000.0
    
    def get_latency_trend(self) -> float:
        """Calculate latency trend (negative = improving)."""
        if len(self.latency_history) < 10:
            return 0.0
        
        recent = list(self.latency_history)[-10:]
        older = list(self.latency_history)[-20:-10]
        
        if not older:
            return 0.0
        
        return statistics.mean(recent) - statistics.mean(older)
    
    def get_stability_score(self) -> float:
        """Calculate stability based on latency variance."""
        if len(self.latency_history) < 5:
            return 0.5
        
        recent = list(self.latency_history)[-20:]
        if len(recent) < 2:
            return 0.5
        
        try:
            variance = statistics.variance(recent)
            # Lower variance = higher stability
            return max(0.0, 1.0 - (variance / 10000))
        except statistics.StatisticsError:
            return 0.5


@dataclass
class DomainProfile:
    """Profile for domain-specific proxy optimization."""
    domain: str
    preferred_regions: List[str] = field(default_factory=list)
    blocked_proxies: set = field(default_factory=set)
    optimal_proxy_scores: Dict[str, float] = field(default_factory=dict)
    last_optimized: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Ensure mutable defaults are instance-specific."""
        if not isinstance(self.preferred_regions, list):
            object.__setattr__(self, 'preferred_regions', list(self.preferred_regions))
        if not isinstance(self.blocked_proxies, set):
            object.__setattr__(self, 'blocked_proxies', set(self.blocked_proxies))
        if not isinstance(self.optimal_proxy_scores, dict):
            object.__setattr__(self, 'optimal_proxy_scores', dict(self.optimal_proxy_scores))
    
    def mark_blocked(self, proxy_id: str):
        """Mark a proxy as blocked for this domain."""
        self.blocked_proxies.add(proxy_id)
        if proxy_id in self.optimal_proxy_scores:
            del self.optimal_proxy_scores[proxy_id]
    
    def update_score(self, proxy_id: str, score: float):
        """Update proxy score for this domain."""
        self.optimal_proxy_scores[proxy_id] = score
        self.last_optimized = time.time()


class ProxySelectionAlgorithm:
    """
    Advanced proxy selection with ML-inspired scoring.
    """
    
    def __init__(
        self,
        default_strategy: SelectionStrategy = SelectionStrategy.WEIGHTED_SCORE,
        latency_weight: float = 0.3,
        success_weight: float = 0.4,
        stability_weight: float = 0.2,
        geographic_weight: float = 0.1
    ):
        self.default_strategy = default_strategy
        self.latency_weight = latency_weight
        self.success_weight = success_weight
        self.stability_weight = stability_weight
        self.geographic_weight = geographic_weight
        
        # Metrics storage
        self.proxy_metrics: Dict[str, ProxyMetrics] = {}
        self.domain_profiles: Dict[str, DomainProfile] = {}
        
        # Round-robin state
        self._rr_index = 0
        self._rr_lock = asyncio.Lock()
        
        # Pattern detection
        self._selection_history: deque = deque(maxlen=1000)
        self._pattern_weights: Dict[str, float] = {}
    
    def _get_metrics(self, proxy: ProxyEndpoint) -> ProxyMetrics:
        """Get or create metrics for a proxy."""
        if proxy.id not in self.proxy_metrics:
            self.proxy_metrics[proxy.id] = ProxyMetrics(proxy_id=proxy.id)
        return self.proxy_metrics[proxy.id]
    
    def _get_domain_profile(self, domain: str) -> DomainProfile:
        """Get or create domain profile."""
        if domain not in self.domain_profiles:
            self.domain_profiles[domain] = DomainProfile(domain=domain)
        return self.domain_profiles[domain]
    
    def calculate_proxy_score(
        self,
        proxy: ProxyEndpoint,
        domain: Optional[str] = None,
        preferred_region: Optional[str] = None
    ) -> float:
        """
        Calculate comprehensive proxy score.
        
        Score components:
        - Success rate (40%): Historical success ratio
        - Latency (30%): Response time (inverse)
        - Stability (20%): Latency variance
        - Geography (10%): Region preference match
        """
        metrics = self._get_metrics(proxy)
        
        # Base scores
        success_score = metrics.get_success_rate()
        avg_latency = metrics.get_avg_latency()
        latency_score = max(0.0, 1.0 - (avg_latency / 2000))  # Normalize to 0-1
        stability_score = metrics.get_stability_score()
        
        # Geographic score
        geo_score = 0.5
        if preferred_region and proxy.region == preferred_region:
            geo_score = 1.0
        elif preferred_region and proxy.country_code == preferred_region.upper():
            geo_score = 0.8
        
        # Domain-specific adjustments
        if domain:
            profile = self._get_domain_profile(domain)
            if proxy.id in profile.blocked_proxies:
                return 0.0  # Completely avoid blocked proxies
            
            if proxy.id in profile.optimal_proxy_scores:
                # Boost previously successful proxies for this domain
                domain_bonus = profile.optimal_proxy_scores[proxy.id] * 0.2
                success_score = min(1.0, success_score + domain_bonus)
        
        # Weighted combination
        total_score = (
            success_score * self.success_weight +
            latency_score * self.latency_weight +
            stability_score * self.stability_weight +
            geo_score * self.geographic_weight
        )
        
        # Status penalties
        if proxy.status == ProxyStatus.DEGRADED:
            total_score *= 0.7
        elif proxy.status == ProxyStatus.UNHEALTHY:
            total_score *= 0.3
        elif proxy.status == ProxyStatus.BANNED:
            total_score = 0.0
        
        # Rate limit penalty
        if proxy.is_rate_limited():
            total_score *= 0.5
        
        return total_score
    
    async def select_proxy(
        self,
        proxies: List[ProxyEndpoint],
        domain: Optional[str] = None,
        preferred_region: Optional[str] = None,
        strategy: Optional[SelectionStrategy] = None,
        require_healthy: bool = True
    ) -> Optional[ProxyEndpoint]:
        """
        Select optimal proxy using specified strategy.
        """
        if not proxies:
            return None
        
        strategy = strategy or self.default_strategy
        
        # Filter by health if required
        candidates = proxies
        if require_healthy:
            candidates = [p for p in proxies if p.status == ProxyStatus.HEALTHY]
        
        if not candidates:
            logger.warning("No healthy proxies available")
            return None
        
        # Filter by rate limit
        candidates = [p for p in candidates if not p.is_rate_limited()]
        
        if not candidates:
            logger.warning("All proxies rate limited")
            return None
        
        # Apply selection strategy
        if strategy == SelectionStrategy.WEIGHTED_SCORE:
            return await self._select_weighted(candidates, domain, preferred_region)
        elif strategy == SelectionStrategy.LOWEST_LATENCY:
            return await self._select_lowest_latency(candidates)
        elif strategy == SelectionStrategy.ROUND_ROBIN:
            return await self._select_round_robin(candidates)
        elif strategy == SelectionStrategy.RANDOM:
            return await self._select_random(candidates)
        elif strategy == SelectionStrategy.PREDICTIVE:
            return await self._select_predictive(candidates, domain, preferred_region)
        elif strategy == SelectionStrategy.GEOGRAPHIC:
            return await self._select_geographic(candidates, preferred_region)
        else:
            return await self._select_weighted(candidates, domain, preferred_region)
    
    async def _select_weighted(
        self,
        proxies: List[ProxyEndpoint],
        domain: Optional[str],
        preferred_region: Optional[str]
    ) -> Optional[ProxyEndpoint]:
        """Select proxy using weighted random based on scores."""
        scores = [
            (p, self.calculate_proxy_score(p, domain, preferred_region))
            for p in proxies
        ]
        
        # Filter out zero-score proxies
        scores = [(p, s) for p, s in scores if s > 0]
        
        if not scores:
            return None
        
        # Weighted random selection
        total_score = sum(s for _, s in scores)
        if total_score == 0:
            return random.choice([p for p, _ in scores])
        
        pick = random.uniform(0, total_score)
        current = 0
        for proxy, score in scores:
            current += score
            if current >= pick:
                return proxy
        
        return scores[-1][0]
    
    async def _select_lowest_latency(self, proxies: List[ProxyEndpoint]) -> Optional[ProxyEndpoint]:
        """Select proxy with lowest average latency."""
        scored = [
            (p, self._get_metrics(p).get_avg_latency())
            for p in proxies
        ]
        scored.sort(key=lambda x: x[1])
        return scored[0][0] if scored else None
    
    async def _select_round_robin(self, proxies: List[ProxyEndpoint]) -> Optional[ProxyEndpoint]:
        """Select proxy using round-robin."""
        async with self._rr_lock:
            proxy = proxies[self._rr_index % len(proxies)]
            self._rr_index = (self._rr_index + 1) % len(proxies)
            return proxy
    
    async def _select_random(self, proxies: List[ProxyEndpoint]) -> Optional[ProxyEndpoint]:
        """Select random proxy."""
        return random.choice(proxies)
    
    async def _select_predictive(
        self,
        proxies: List[ProxyEndpoint],
        domain: Optional[str],
        preferred_region: Optional[str]
    ) -> Optional[ProxyEndpoint]:
        """
        Predictive selection using trend analysis.
        Prefers proxies with improving latency trends.
        """
        scored = []
        for proxy in proxies:
            metrics = self._get_metrics(proxy)
            base_score = self.calculate_proxy_score(proxy, domain, preferred_region)
            
            # Trend bonus: prefer improving proxies
            trend = metrics.get_latency_trend()
            trend_bonus = max(-0.2, min(0.2, -trend / 100))  # Normalize trend impact
            
            final_score = base_score + trend_bonus
            scored.append((proxy, final_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None
    
    async def _select_geographic(
        self,
        proxies: List[ProxyEndpoint],
        preferred_region: Optional[str]
    ) -> Optional[ProxyEndpoint]:
        """Select proxy based on geographic preference."""
        if not preferred_region:
            return await self._select_weighted(proxies, None, None)
        
        # Exact region match
        exact_matches = [p for p in proxies if p.region == preferred_region]
        if exact_matches:
            return await self._select_weighted(exact_matches, None, preferred_region)
        
        # Country code match
        country_matches = [
            p for p in proxies
            if p.country_code == preferred_region.upper()
        ]
        if country_matches:
            return await self._select_weighted(country_matches, None, preferred_region)
        
        # Fallback to weighted
        return await self._select_weighted(proxies, None, preferred_region)
    
    def record_result(
        self,
        proxy: ProxyEndpoint,
        domain: Optional[str],
        latency_ms: float,
        success: bool
    ):
        """Record request result for learning."""
        # Update metrics
        metrics = self._get_metrics(proxy)
        metrics.add_sample(latency_ms, success)
        
        # Update domain profile
        if domain:
            profile = self._get_domain_profile(domain)
            if success:
                # Calculate incremental score update
                current_score = profile.optimal_proxy_scores.get(proxy.id, 0.5)
                new_score = current_score * 0.9 + 0.1  # Incremental boost
                profile.update_score(proxy.id, new_score)
            else:
                # Mark as potentially blocked
                profile.mark_blocked(proxy.id)
        
        # Record selection for pattern analysis
        self._selection_history.append({
            "proxy_id": proxy.id,
            "domain": domain,
            "success": success,
            "latency_ms": latency_ms,
            "timestamp": time.time()
        })
    
    def detect_patterns(self) -> Dict[str, Any]:
        """Detect usage patterns and optimize accordingly."""
        if len(self._selection_history) < 100:
            return {"status": "insufficient_data"}
        
        patterns = {
            "domain_preferences": {},
            "time_based_patterns": {},
            "proxy_affinity": {}
        }
        
        # Analyze domain preferences
        domain_success = {}
        for record in self._selection_history:
            domain = record.get("domain")
            if not domain:
                continue
            
            if domain not in domain_success:
                domain_success[domain] = {}
            
            proxy_id = record["proxy_id"]
            if proxy_id not in domain_success[domain]:
                domain_success[domain][proxy_id] = {"success": 0, "total": 0}
            
            domain_success[domain][proxy_id]["total"] += 1
            if record["success"]:
                domain_success[domain][proxy_id]["success"] += 1
        
        # Calculate success rates per domain-proxy pair
        for domain, proxies in domain_success.items():
            patterns["domain_preferences"][domain] = {
                proxy_id: stats["success"] / stats["total"]
                for proxy_id, stats in proxies.items()
                if stats["total"] >= 5  # Minimum sample size
            }
        
        return patterns
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Check for underperforming proxies
        for proxy_id, metrics in self.proxy_metrics.items():
            success_rate = metrics.get_success_rate()
            if success_rate < 0.5:
                recommendations.append({
                    "type": "proxy_health",
                    "severity": "high",
                    "proxy_id": proxy_id,
                    "message": f"Proxy {proxy_id} has low success rate: {success_rate:.2%}",
                    "action": "investigate_or_remove"
                })
        
        # Check for domain-specific issues
        for domain, profile in self.domain_profiles.items():
            if len(profile.blocked_proxies) > 3:
                recommendations.append({
                    "type": "domain_blocking",
                    "severity": "medium",
                    "domain": domain,
                    "message": f"Domain {domain} has blocked {len(profile.blocked_proxies)} proxies",
                    "action": "expand_proxy_pool"
                })
        
        # Check for geographic gaps
        regions = set()
        for proxy_id, metrics in self.proxy_metrics.items():
            # This would need proxy object access in real implementation
            pass
        
        return recommendations


class AdaptiveLoadBalancer:
    """
    Adaptive load balancer that adjusts weights based on real-time performance.
    """
    
    def __init__(self, algorithm: ProxySelectionAlgorithm):
        self.algorithm = algorithm
        self._active_connections: Dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def acquire_proxy(
        self,
        proxies: List[ProxyEndpoint],
        domain: Optional[str] = None
    ) -> Tuple[ProxyEndpoint, str]:
        """
        Acquire a proxy with connection tracking.
        
        Returns:
            Tuple of (proxy, acquisition_token)
        """
        # Adjust scores based on active connections
        adjusted_proxies = []
        for proxy in proxies:
            base_score = self.algorithm.calculate_proxy_score(proxy, domain)
            active = self._active_connections.get(proxy.id, 0)
            
            # Penalize heavily loaded proxies
            load_penalty = min(0.3, active * 0.05)
            adjusted_score = max(0, base_score - load_penalty)
            
            adjusted_proxies.append((proxy, adjusted_score))
        
        # Select best available
        adjusted_proxies.sort(key=lambda x: x[1], reverse=True)
        selected = adjusted_proxies[0][0] if adjusted_proxies else None
        
        if not selected:
            raise RuntimeError("No available proxies")
        
        # Track connection
        async with self._lock:
            self._active_connections[selected.id] = self._active_connections.get(selected.id, 0) + 1
        
        token = f"{selected.id}_{secrets.token_hex(8)}"
        return selected, token
    
    async def release_proxy(self, token: str):
        """Release a previously acquired proxy."""
        proxy_id = token.split("_")[0]
        async with self._lock:
            if proxy_id in self._active_connections:
                self._active_connections[proxy_id] = max(0, self._active_connections[proxy_id] - 1)
    
    def get_load_distribution(self) -> Dict[str, int]:
        """Get current load distribution across proxies."""
        return dict(self._active_connections)
