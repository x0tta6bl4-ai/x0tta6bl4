"""
Yggdrasil Routing Optimizer - Advanced routing optimization for mesh networks.

Provides ML-based route optimization, latency prediction, and adaptive path selection
for Yggdrasil-based mesh networks.
"""

import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class RouteQuality(Enum):
    """Quality classification for routes."""
    EXCELLENT = "excellent"  # < 20ms latency, < 0.1% loss
    GOOD = "good"           # < 50ms latency, < 1% loss
    ACCEPTABLE = "acceptable"  # < 100ms latency, < 3% loss
    POOR = "poor"           # < 200ms latency, < 10% loss
    CRITICAL = "critical"   # >= 200ms latency or >= 10% loss


@dataclass
class RouteMetrics:
    """Metrics for a single route."""
    route_id: str
    destination: str
    next_hop: str
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    bandwidth_mbps: float = 0.0
    hop_count: int = 1
    last_updated: datetime = field(default_factory=datetime.utcnow)
    sample_count: int = 0
    
    # Computed scores
    quality_score: float = 0.0
    reliability_score: float = 0.0
    efficiency_score: float = 0.0
    
    def compute_scores(self) -> None:
        """Compute quality, reliability, and efficiency scores."""
        # Quality score (0-1, higher is better)
        latency_score = max(0, 1 - (self.latency_ms / 200))
        loss_score = max(0, 1 - (self.packet_loss / 10))
        self.quality_score = (latency_score * 0.6 + loss_score * 0.4)
        
        # Reliability score (based on consistency)
        jitter_penalty = min(1, self.jitter_ms / 50)
        self.reliability_score = max(0, self.quality_score * (1 - jitter_penalty * 0.3))
        
        # Efficiency score (bandwidth per hop)
        if self.hop_count > 0:
            self.efficiency_score = min(1, self.bandwidth_mbps / (100 * self.hop_count))
        else:
            self.efficiency_score = 0
    
    def classify_quality(self) -> RouteQuality:
        """Classify route quality."""
        if self.latency_ms < 20 and self.packet_loss < 0.1:
            return RouteQuality.EXCELLENT
        elif self.latency_ms < 50 and self.packet_loss < 1:
            return RouteQuality.GOOD
        elif self.latency_ms < 100 and self.packet_loss < 3:
            return RouteQuality.ACCEPTABLE
        elif self.latency_ms < 200 and self.packet_loss < 10:
            return RouteQuality.POOR
        else:
            return RouteQuality.CRITICAL


@dataclass
class OptimizationConfig:
    """Configuration for route optimization."""
    # Latency thresholds
    excellent_latency_ms: float = 20.0
    good_latency_ms: float = 50.0
    acceptable_latency_ms: float = 100.0
    poor_latency_ms: float = 200.0
    
    # Loss thresholds (percentage)
    excellent_loss_pct: float = 0.1
    good_loss_pct: float = 1.0
    acceptable_loss_pct: float = 3.0
    poor_loss_pct: float = 10.0
    
    # Optimization weights
    latency_weight: float = 0.4
    loss_weight: float = 0.3
    bandwidth_weight: float = 0.2
    hop_count_weight: float = 0.1
    
    # Learning parameters
    learning_rate: float = 0.1
    decay_factor: float = 0.95
    min_samples: int = 5
    
    # Route selection
    max_alternative_routes: int = 3
    route_timeout_seconds: float = 300.0
    probe_interval_seconds: float = 30.0


class LatencyPredictor:
    """
    ML-based latency predictor using exponential weighted moving average
    with trend analysis.
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self._history: Dict[str, List[float]] = {}
        self._predictions: Dict[str, float] = {}
        self._trends: Dict[str, float] = {}
        
    def update(self, route_id: str, latency: float) -> float:
        """
        Update predictor with new latency measurement.
        Returns predicted latency for next interval.
        """
        if route_id not in self._history:
            self._history[route_id] = []
            self._predictions[route_id] = latency
            self._trends[route_id] = 0.0
        
        history = self._history[route_id]
        history.append(latency)
        
        # Keep last 100 samples
        if len(history) > 100:
            history.pop(0)
        
        # Compute EWMA
        alpha = self.config.learning_rate
        prev_prediction = self._predictions[route_id]
        new_prediction = alpha * latency + (1 - alpha) * prev_prediction
        
        # Update trend
        if len(history) >= 2:
            trend = latency - history[-2]
            self._trends[route_id] = alpha * trend + (1 - alpha) * self._trends[route_id]
        
        self._predictions[route_id] = new_prediction
        return new_prediction + self._trends[route_id]
    
    def predict(self, route_id: str) -> Optional[float]:
        """Get predicted latency for route."""
        prediction = self._predictions.get(route_id)
        trend = self._trends.get(route_id, 0.0)
        if prediction is not None:
            return prediction + trend
        return None
    
    def get_confidence(self, route_id: str) -> float:
        """Get prediction confidence based on sample count."""
        history = self._history.get(route_id, [])
        sample_count = len(history)
        if sample_count < self.config.min_samples:
            return 0.0
        return min(1.0, sample_count / 50.0)


class AdaptivePathSelector:
    """
    Adaptive path selection using multi-armed bandit algorithm
    with Thompson Sampling for exploration/exploitation balance.
    """
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self._route_stats: Dict[str, Dict[str, float]] = {}
        self._selection_counts: Dict[str, int] = {}
        
    def register_route(self, route_id: str) -> None:
        """Register a route for selection."""
        if route_id not in self._route_stats:
            self._route_stats[route_id] = {
                "alpha": 1.0,  # Success parameter for Beta distribution
                "beta": 1.0,   # Failure parameter for Beta distribution
            }
            self._selection_counts[route_id] = 0
    
    def select_route(self, routes: List[str]) -> Optional[str]:
        """
        Select best route using Thompson Sampling.
        Balances exploration of new routes with exploitation of good routes.
        """
        import random
        
        valid_routes = [r for r in routes if r in self._route_stats]
        if not valid_routes:
            return routes[0] if routes else None
        
        # Thompson Sampling: sample from Beta distribution for each route
        best_route = None
        best_sample = -1.0
        
        for route_id in valid_routes:
            stats = self._route_stats[route_id]
            # Sample from Beta(alpha, beta)
            sample = self._sample_beta(stats["alpha"], stats["beta"])
            if sample > best_sample:
                best_sample = sample
                best_route = route_id
        
        if best_route:
            self._selection_counts[best_route] = self._selection_counts.get(best_route, 0) + 1
        
        return best_route
    
    def _sample_beta(self, alpha: float, beta: float) -> float:
        """Sample from Beta distribution using numpy-like approach."""
        import random
        # Approximate Beta sampling using ratio of Gamma samples
        x = self._sample_gamma(alpha, 1.0)
        y = self._sample_gamma(beta, 1.0)
        return x / (x + y) if (x + y) > 0 else 0.5
    
    def _sample_gamma(self, shape: float, scale: float) -> float:
        """Sample from Gamma distribution using Marsaglia and Tsang's method."""
        import random
        import math
        
        if shape < 1:
            return self._sample_gamma(shape + 1, scale) * (random.random() ** (1.0 / shape))
        
        d = shape - 1.0 / 3.0
        c = 1.0 / math.sqrt(9.0 * d)
        
        while True:
            x = random.gauss(0, 1)
            v = 1.0 + c * x
            if v <= 0:
                continue
            v = v * v * v
            u = random.random()
            if u < 1.0 - 0.0331 * (x * x) * (x * x):
                return d * v * scale
            if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
                return d * v * scale
    
    def update_reward(self, route_id: str, reward: float) -> None:
        """
        Update route statistics based on reward (0-1).
        High reward = good performance, low reward = poor performance.
        """
        if route_id not in self._route_stats:
            self.register_route(route_id)
        
        stats = self._route_stats[route_id]
        # Update Beta distribution parameters
        stats["alpha"] += reward
        stats["beta"] += (1.0 - reward)
        
        # Apply decay to prevent overfitting to old data
        decay = self.config.decay_factor
        stats["alpha"] = 1.0 + (stats["alpha"] - 1.0) * decay
        stats["beta"] = 1.0 + (stats["beta"] - 1.0) * decay


class YggdrasilOptimizer:
    """
    Main optimizer for Yggdrasil mesh routing.
    
    Features:
    - ML-based latency prediction
    - Adaptive path selection with Thompson Sampling
    - Multi-objective route optimization
    - Proactive route quality monitoring
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
        self._routes: Dict[str, RouteMetrics] = {}
        self._destination_routes: Dict[str, List[str]] = {}
        self._latency_predictor = LatencyPredictor(self.config)
        self._path_selector = AdaptivePathSelector(self.config)
        self._optimization_callbacks: List[Callable] = []
        self._running = False
        self._last_optimization: Optional[datetime] = None
        
    def register_route(self, route: RouteMetrics) -> None:
        """Register or update a route."""
        self._routes[route.route_id] = route
        route.compute_scores()
        
        # Index by destination
        if route.destination not in self._destination_routes:
            self._destination_routes[route.destination] = []
        if route.route_id not in self._destination_routes[route.destination]:
            self._destination_routes[route.destination].append(route.route_id)
        
        # Register with path selector
        self._path_selector.register_route(route.route_id)
        
        logger.debug(f"Registered route {route.route_id} to {route.destination}")
    
    def unregister_route(self, route_id: str) -> None:
        """Remove a route from optimization."""
        if route_id in self._routes:
            destination = self._routes[route_id].destination
            if destination in self._destination_routes:
                self._destination_routes[destination] = [
                    r for r in self._destination_routes[destination] if r != route_id
                ]
            del self._routes[route_id]
            logger.debug(f"Unregistered route {route_id}")
    
    def update_route_metrics(
        self,
        route_id: str,
        latency_ms: Optional[float] = None,
        packet_loss: Optional[float] = None,
        bandwidth_mbps: Optional[float] = None,
        jitter_ms: Optional[float] = None,
    ) -> Optional[RouteMetrics]:
        """Update metrics for a specific route."""
        route = self._routes.get(route_id)
        if not route:
            return None
        
        if latency_ms is not None:
            route.latency_ms = latency_ms
            # Update predictor
            predicted = self._latency_predictor.update(route_id, latency_ms)
            logger.debug(f"Route {route_id}: latency={latency_ms}ms, predicted={predicted:.1f}ms")
        
        if packet_loss is not None:
            route.packet_loss = packet_loss
        
        if bandwidth_mbps is not None:
            route.bandwidth_mbps = bandwidth_mbps
        
        if jitter_ms is not None:
            route.jitter_ms = jitter_ms
        
        route.last_updated = datetime.utcnow()
        route.sample_count += 1
        route.compute_scores()
        
        # Update path selector reward
        reward = self._compute_reward(route)
        self._path_selector.update_reward(route_id, reward)
        
        return route
    
    def _compute_reward(self, route: RouteMetrics) -> float:
        """Compute reward value (0-1) for a route."""
        # Combine quality, reliability, and efficiency scores
        reward = (
            route.quality_score * 0.5 +
            route.reliability_score * 0.3 +
            route.efficiency_score * 0.2
        )
        return max(0.0, min(1.0, reward))
    
    def select_best_route(
        self,
        destination: str,
        exclude: Optional[Set[str]] = None,
        prefer_low_latency: bool = True,
    ) -> Optional[RouteMetrics]:
        """
        Select the best route to a destination.
        
        Uses adaptive path selection with Thompson Sampling for
        exploration/exploitation balance.
        """
        route_ids = self._destination_routes.get(destination, [])
        if exclude:
            route_ids = [r for r in route_ids if r not in exclude]
        
        if not route_ids:
            return None
        
        # Get valid routes with sufficient samples
        valid_routes = [
            rid for rid in route_ids
            if rid in self._routes and
            self._routes[rid].sample_count >= self.config.min_samples
        ]
        
        if not valid_routes:
            # Fall back to first available route
            route_id = route_ids[0]
            return self._routes.get(route_id)
        
        # Use adaptive path selector
        selected_id = self._path_selector.select_route(valid_routes)
        if selected_id:
            return self._routes.get(selected_id)
        
        return None
    
    def get_alternative_routes(
        self,
        destination: str,
        exclude: Optional[Set[str]] = None,
        max_routes: Optional[int] = None,
    ) -> List[RouteMetrics]:
        """Get alternative routes to a destination, sorted by quality."""
        route_ids = self._destination_routes.get(destination, [])
        if exclude:
            route_ids = [r for r in route_ids if r not in exclude]
        
        routes = [self._routes[rid] for rid in route_ids if rid in self._routes]
        
        # Sort by quality score (descending)
        routes.sort(key=lambda r: r.quality_score, reverse=True)
        
        max_routes = max_routes or self.config.max_alternative_routes
        return routes[:max_routes]
    
    def predict_latency(self, route_id: str) -> Optional[float]:
        """Get predicted latency for a route."""
        return self._latency_predictor.predict(route_id)
    
    def get_prediction_confidence(self, route_id: str) -> float:
        """Get confidence in latency prediction."""
        return self._latency_predictor.get_confidence(route_id)
    
    def optimize_routes(self) -> Dict[str, Any]:
        """
        Perform route optimization analysis.
        
        Returns optimization recommendations and statistics.
        """
        optimization_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_routes": len(self._routes),
            "destinations": len(self._destination_routes),
            "recommendations": [],
            "statistics": {},
        }
        
        # Analyze route quality distribution
        quality_distribution = {q.value: 0 for q in RouteQuality}
        for route in self._routes.values():
            quality = route.classify_quality()
            quality_distribution[quality.value] += 1
        
        optimization_result["statistics"]["quality_distribution"] = quality_distribution
        
        # Find routes needing attention
        for route in self._routes.values():
            if route.classify_quality() in (RouteQuality.POOR, RouteQuality.CRITICAL):
                optimization_result["recommendations"].append({
                    "route_id": route.route_id,
                    "destination": route.destination,
                    "action": "investigate",
                    "reason": f"Route quality is {route.classify_quality().value}",
                    "metrics": {
                        "latency_ms": route.latency_ms,
                        "packet_loss": route.packet_loss,
                        "quality_score": route.quality_score,
                    }
                })
        
        # Check for stale routes
        now = datetime.utcnow()
        stale_threshold = timedelta(seconds=self.config.route_timeout_seconds)
        
        for route in self._routes.values():
            age = now - route.last_updated
            if age > stale_threshold:
                optimization_result["recommendations"].append({
                    "route_id": route.route_id,
                    "destination": route.destination,
                    "action": "refresh",
                    "reason": f"Route data is stale ({age.total_seconds():.0f}s old)",
                })
        
        # Compute aggregate statistics
        if self._routes:
            latencies = [r.latency_ms for r in self._routes.values()]
            losses = [r.packet_loss for r in self._routes.values()]
            
            optimization_result["statistics"]["avg_latency_ms"] = sum(latencies) / len(latencies)
            optimization_result["statistics"]["avg_packet_loss"] = sum(losses) / len(losses)
            optimization_result["statistics"]["min_latency_ms"] = min(latencies)
            optimization_result["statistics"]["max_latency_ms"] = max(latencies)
        
        self._last_optimization = datetime.utcnow()
        
        # Notify callbacks
        for callback in self._optimization_callbacks:
            try:
                callback(optimization_result)
            except Exception as e:
                logger.warning(f"Optimization callback failed: {e}")
        
        return optimization_result
    
    def add_optimization_callback(self, callback: Callable) -> None:
        """Add a callback to be called after optimization."""
        self._optimization_callbacks.append(callback)
    
    async def start_monitoring(self) -> None:
        """Start background route monitoring."""
        self._running = True
        logger.info("Started Yggdrasil route monitoring")
        
        while self._running:
            try:
                await asyncio.sleep(self.config.probe_interval_seconds)
                result = self.optimize_routes()
                
                if result["recommendations"]:
                    logger.info(f"Optimization found {len(result['recommendations'])} recommendations")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        logger.info("Stopped Yggdrasil route monitoring")
    
    def get_route_report(self, destination: Optional[str] = None) -> Dict[str, Any]:
        """Generate a detailed route report."""
        routes = []
        
        if destination:
            route_ids = self._destination_routes.get(destination, [])
            route_list = [self._routes[rid] for rid in route_ids if rid in self._routes]
        else:
            route_list = list(self._routes.values())
        
        for route in route_list:
            predicted_latency = self.predict_latency(route.route_id)
            confidence = self.get_prediction_confidence(route.route_id)
            
            routes.append({
                "route_id": route.route_id,
                "destination": route.destination,
                "next_hop": route.next_hop,
                "quality": route.classify_quality().value,
                "metrics": {
                    "latency_ms": route.latency_ms,
                    "predicted_latency_ms": predicted_latency,
                    "prediction_confidence": confidence,
                    "jitter_ms": route.jitter_ms,
                    "packet_loss": route.packet_loss,
                    "bandwidth_mbps": route.bandwidth_mbps,
                    "hop_count": route.hop_count,
                },
                "scores": {
                    "quality": route.quality_score,
                    "reliability": route.reliability_score,
                    "efficiency": route.efficiency_score,
                },
                "last_updated": route.last_updated.isoformat(),
                "sample_count": route.sample_count,
            })
        
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_routes": len(routes),
            "routes": routes,
        }


# Singleton instance
_optimizer_instance: Optional[YggdrasilOptimizer] = None


def get_optimizer(config: Optional[OptimizationConfig] = None) -> YggdrasilOptimizer:
    """Get or create the global optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = YggdrasilOptimizer(config)
    return _optimizer_instance
