"""
Trust-MAPE-K Integration Module.

Integrates Cisco-like dynamic trust scores with the MAPE-K feedback loop
for self-healing network operations.

Key Features:
- Dynamic trust evaluation based on path behavior
- Trust-aware routing decisions in MAPE-K Plan phase
- Automatic trust decay for failing paths
- Trust recovery for healthy paths
- Integration with Zero-Trust security framework
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import time

from .make_never_break import (
    MakeNeverBreakEngine,
    NetworkPath,
    PathMetrics,
    PathState,
    PathType,
    ResilienceConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class TrustPolicy:
    """Policy for trust score management."""
    # Trust thresholds
    min_trust_for_primary: float = 0.8      # Minimum trust to be primary path
    min_trust_for_backup: float = 0.5       # Minimum trust to be backup path
    min_trust_for_emergency: float = 0.2    # Minimum trust for emergency use
    
    # Trust adjustments
    trust_penalty_failure: float = 0.2      # Penalty for path failure
    trust_penalty_degraded: float = 0.05    # Penalty for degraded state
    trust_reward_success: float = 0.02      # Reward for successful transmission
    trust_reward_low_latency: float = 0.01  # Reward for low latency
    
    # Time-based decay
    trust_decay_interval_sec: float = 60.0  # How often to decay trust
    trust_decay_rate: float = 0.01          # Decay rate per interval
    
    # Recovery
    trust_recovery_rate: float = 0.03       # Recovery rate for healthy paths


@dataclass
class TrustEvent:
    """A trust-affecting event."""
    path_id: str
    event_type: str  # "success", "failure", "degraded", "timeout", "security_alert"
    timestamp: datetime
    trust_delta: float
    details: Dict[str, Any] = field(default_factory=dict)


class TrustAwareMAPEK:
    """
    Trust-aware MAPE-K integration for network resilience.
    
    Extends the standard MAPE-K loop with Cisco-like trust evaluation:
    - Monitor: Collect trust metrics from paths
    - Analyze: Evaluate trust trends and anomalies
    - Plan: Make trust-aware routing decisions
    - Execute: Apply trust-based path changes
    - Knowledge: Learn trust patterns
    """
    
    def __init__(
        self,
        resilience_engine: MakeNeverBreakEngine,
        policy: Optional[TrustPolicy] = None,
    ):
        self.engine = resilience_engine
        self.policy = policy or TrustPolicy()
        
        # Trust history for analysis
        self._trust_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._events: List[TrustEvent] = []
        
        # Trust anomalies detected
        self._anomalies: List[Dict[str, Any]] = []
        
        # Callbacks
        self._on_trust_change: Optional[Callable[[str, float, float], None]] = None
        self._on_anomaly: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Background task
        self._decay_task: Optional[asyncio.Task] = None
        self._running = False
    
    def set_callbacks(
        self,
        on_trust_change: Optional[Callable[[str, float, float], None]] = None,
        on_anomaly: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """Set callbacks for trust events."""
        self._on_trust_change = on_trust_change
        self._on_anomaly = on_anomaly
    
    async def start(self) -> None:
        """Start trust management."""
        self._running = True
        self._decay_task = asyncio.create_task(self._trust_decay_loop())
        logger.info("Trust-MAPE-K integration started")
    
    async def stop(self) -> None:
        """Stop trust management."""
        self._running = False
        if self._decay_task:
            self._decay_task.cancel()
            try:
                await self._decay_task
            except asyncio.CancelledError:
                pass
        logger.info("Trust-MAPE-K integration stopped")
    
    # -------------------------------------------------------------------------
    # MONITOR: Collect Trust Metrics
    # -------------------------------------------------------------------------
    
    def collect_trust_metrics(self) -> Dict[str, Any]:
        """
        Collect trust metrics from all paths.
        
        Returns metrics suitable for MAPE-K Monitor phase.
        """
        stats = self.engine.get_stats()
        
        trust_metrics = {
            "total_paths": stats["total_paths"],
            "active_paths": stats["active_paths"],
            "failed_paths": stats["failed_paths"],
            "avg_trust_score": 0.0,
            "min_trust_score": 1.0,
            "max_trust_score": 0.0,
            "low_trust_paths": 0,
            "high_trust_paths": 0,
            "trust_distribution": {
                "primary_eligible": 0,   # trust >= 0.8
                "backup_eligible": 0,    # trust >= 0.5
                "emergency_only": 0,     # trust >= 0.2
                "unusable": 0,           # trust < 0.2
            },
            "trust_trends": {},
            "recent_anomalies": len(self._anomalies),
        }
        
        # Calculate aggregate trust statistics
        trust_scores = []
        for path in self.engine._paths.values():
            score = path.metrics.trust_score
            trust_scores.append(score)
            
            # Update min/max
            trust_metrics["min_trust_score"] = min(trust_metrics["min_trust_score"], score)
            trust_metrics["max_trust_score"] = max(trust_metrics["max_trust_score"], score)
            
            # Count by threshold
            if score >= self.policy.min_trust_for_primary:
                trust_metrics["trust_distribution"]["primary_eligible"] += 1
                trust_metrics["high_trust_paths"] += 1
            elif score >= self.policy.min_trust_for_backup:
                trust_metrics["trust_distribution"]["backup_eligible"] += 1
            elif score >= self.policy.min_trust_for_emergency:
                trust_metrics["trust_distribution"]["emergency_only"] += 1
                trust_metrics["low_trust_paths"] += 1
            else:
                trust_metrics["trust_distribution"]["unusable"] += 1
                trust_metrics["low_trust_paths"] += 1
            
            # Calculate trust trend for this path
            trend = self._calculate_trust_trend(path.path_id)
            if trend is not None:
                trust_metrics["trust_trends"][path.path_id] = trend
        
        # Calculate average
        if trust_scores:
            trust_metrics["avg_trust_score"] = sum(trust_scores) / len(trust_scores)
        
        return trust_metrics
    
    # -------------------------------------------------------------------------
    # ANALYZE: Evaluate Trust State
    # -------------------------------------------------------------------------
    
    def analyze_trust_state(self, trust_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze trust state for MAPE-K Analyze phase.
        
        Returns analysis with recommendations.
        """
        analysis = {
            "trust_health": "healthy",  # healthy, degraded, critical
            "issues": [],
            "recommendations": [],
            "risk_score": 0.0,
        }
        
        # Check average trust
        avg_trust = trust_metrics["avg_trust_score"]
        if avg_trust < 0.5:
            analysis["trust_health"] = "critical"
            analysis["issues"].append(f"Average trust score critically low: {avg_trust:.2f}")
            analysis["risk_score"] = 0.8
        elif avg_trust < 0.7:
            analysis["trust_health"] = "degraded"
            analysis["issues"].append(f"Average trust score degraded: {avg_trust:.2f}")
            analysis["risk_score"] = 0.4
        
        # Check trust distribution
        dist = trust_metrics["trust_distribution"]
        if dist["primary_eligible"] < 2:
            analysis["issues"].append(
                f"Insufficient primary-eligible paths: {dist['primary_eligible']}"
            )
            analysis["recommendations"].append("establish_more_paths")
            analysis["risk_score"] = max(analysis["risk_score"], 0.5)
        
        if dist["unusable"] > dist["primary_eligible"]:
            analysis["issues"].append(
                f"More unusable paths than primary-eligible: {dist['unusable']} vs {dist['primary_eligible']}"
            )
            analysis["recommendations"].append("cleanup_failed_paths")
        
        # Check trust trends
        declining_paths = []
        for path_id, trend in trust_metrics.get("trust_trends", {}).items():
            if trend < -0.1:  # Declining trend
                declining_paths.append(path_id)
        
        if declining_paths:
            analysis["issues"].append(f"Declining trust for {len(declining_paths)} paths")
            analysis["recommendations"].append("investigate_declining_paths")
        
        # Check anomalies
        if trust_metrics["recent_anomalies"] > 0:
            analysis["issues"].append(f"{trust_metrics['recent_anomalies']} trust anomalies detected")
            analysis["recommendations"].append("review_anomalies")
        
        return analysis
    
    # -------------------------------------------------------------------------
    # PLAN: Trust-Aware Decisions
    # -------------------------------------------------------------------------
    
    def plan_trust_actions(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan trust-based actions for MAPE-K Plan phase.
        
        Returns action directives.
        """
        directives = {
            "actions": [],
            "path_changes": [],
            "trust_adjustments": [],
        }
        
        # Handle critical trust state
        if analysis["trust_health"] == "critical":
            directives["actions"].append({
                "type": "emergency_path_establishment",
                "priority": 10,
                "reason": "Critical trust state - need new reliable paths",
            })
        
        # Handle recommendations
        for rec in analysis.get("recommendations", []):
            if rec == "establish_more_paths":
                directives["actions"].append({
                    "type": "establish_redundant_paths",
                    "priority": 7,
                    "reason": "Insufficient primary-eligible paths",
                })
            elif rec == "cleanup_failed_paths":
                directives["actions"].append({
                    "type": "cleanup_failed_paths",
                    "priority": 3,
                    "reason": "Remove unusable paths",
                })
            elif rec == "investigate_declining_paths":
                directives["actions"].append({
                    "type": "investigate_paths",
                    "priority": 5,
                    "reason": "Declining trust trends detected",
                })
        
        # Evaluate each path for role changes
        for path in self.engine._paths.values():
            role_change = self._evaluate_path_role(path)
            if role_change:
                directives["path_changes"].append(role_change)
        
        return directives
    
    def _evaluate_path_role(self, path: NetworkPath) -> Optional[Dict[str, Any]]:
        """Evaluate if path should change role based on trust."""
        trust = path.metrics.trust_score
        current_type = path.path_type
        
        # Determine appropriate role based on trust
        if trust >= self.policy.min_trust_for_primary:
            appropriate_type = PathType.PRIMARY
        elif trust >= self.policy.min_trust_for_backup:
            appropriate_type = PathType.BACKUP
        elif trust >= self.policy.min_trust_for_emergency:
            appropriate_type = PathType.EMERGENCY
        else:
            appropriate_type = None  # Should not be used
        
        # Check if change needed
        if appropriate_type and current_type != appropriate_type:
            return {
                "path_id": path.path_id,
                "current_type": current_type.value,
                "recommended_type": appropriate_type.value,
                "trust_score": trust,
                "reason": f"Trust score {trust:.2f} suggests {appropriate_type.value} role",
            }
        
        return None
    
    # -------------------------------------------------------------------------
    # EXECUTE: Apply Trust Changes
    # -------------------------------------------------------------------------
    
    async def execute_trust_actions(self, directives: Dict[str, Any]) -> List[str]:
        """
        Execute trust-based actions for MAPE-K Execute phase.
        
        Returns list of actions taken.
        """
        actions_taken = []
        
        # Execute actions
        for action in directives.get("actions", []):
            action_type = action["type"]
            
            if action_type == "emergency_path_establishment":
                # Trigger emergency path establishment
                # In real implementation, would call path discovery
                actions_taken.append("emergency_path_discovery_initiated")
                logger.warning("Emergency path establishment triggered by trust analysis")
            
            elif action_type == "cleanup_failed_paths":
                # Clean up unusable paths
                cleaned = self._cleanup_unusable_paths()
                actions_taken.append(f"cleaned_{cleaned}_unusable_paths")
            
            elif action_type == "investigate_paths":
                # Log investigation needed
                actions_taken.append("path_investigation_scheduled")
                logger.info("Path investigation scheduled due to declining trust")
        
        # Apply path role changes
        for change in directives.get("path_changes", []):
            path_id = change["path_id"]
            path = self.engine._paths.get(path_id)
            
            if path:
                new_type = PathType(change["recommended_type"])
                old_type = path.path_type
                path.path_type = new_type
                actions_taken.append(
                    f"path_{path_id}_role_changed_{old_type.value}_to_{new_type.value}"
                )
                logger.info(
                    f"Path {path_id} role changed: {old_type.value} -> {new_type.value} "
                    f"(trust: {change['trust_score']:.2f})"
                )
        
        return actions_taken
    
    def _cleanup_unusable_paths(self) -> int:
        """Remove paths with trust below minimum."""
        to_remove = []
        
        for path_id, path in self.engine._paths.items():
            if path.metrics.trust_score < self.policy.min_trust_for_emergency:
                to_remove.append(path_id)
        
        for path_id in to_remove:
            self.engine._remove_path(path_id)
        
        return len(to_remove)
    
    # -------------------------------------------------------------------------
    # KNOWLEDGE: Learn Trust Patterns
    # -------------------------------------------------------------------------
    
    def update_knowledge(self, actions_taken: List[str]) -> None:
        """
        Update knowledge base for MAPE-K Knowledge phase.
        
        Learns from trust patterns and actions.
        """
        # Record trust history for trend analysis
        for path in self.engine._paths.values():
            if path.path_id not in self._trust_history:
                self._trust_history[path.path_id] = []
            
            self._trust_history[path.path_id].append(
                (datetime.utcnow(), path.metrics.trust_score)
            )
            
            # Keep only last 100 entries per path
            if len(self._trust_history[path.path_id]) > 100:
                self._trust_history[path.path_id] = self._trust_history[path.path_id][-100:]
        
        # Detect anomalies
        self._detect_trust_anomalies()
        
        # Clean old events
        self._cleanup_old_events()
    
    def _calculate_trust_trend(self, path_id: str) -> Optional[float]:
        """Calculate trust trend for a path (-1 to 1, negative = declining)."""
        history = self._trust_history.get(path_id, [])
        
        if len(history) < 2:
            return None
        
        # Simple linear regression on recent history
        recent = history[-10:]  # Last 10 entries
        
        if len(recent) < 2:
            return None
        
        # Calculate slope
        times = [(t - recent[0][0]).total_seconds() for t, _ in recent]
        scores = [s for _, s in recent]
        
        n = len(recent)
        sum_x = sum(times)
        sum_y = sum(scores)
        sum_xy = sum(t * s for t, s in zip(times, scores))
        sum_xx = sum(t * t for t in times)
        
        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Normalize to -1 to 1 range
        return max(-1.0, min(1.0, slope * 100))  # Scale for interpretability
    
    def _detect_trust_anomalies(self) -> None:
        """Detect trust anomalies across paths."""
        self._anomalies = []
        
        for path_id, history in self._trust_history.items():
            if len(history) < 5:
                continue
            
            recent_scores = [s for _, s in history[-5:]]
            avg_recent = sum(recent_scores) / len(recent_scores)
            
            # Check for sudden drop
            if len(history) >= 10:
                older_scores = [s for _, s in history[-10:-5]]
                avg_older = sum(older_scores) / len(older_scores)
                
                drop = avg_older - avg_recent
                if drop > 0.3:  # 30% sudden drop
                    anomaly = {
                        "type": "sudden_trust_drop",
                        "path_id": path_id,
                        "drop": drop,
                        "from_trust": avg_older,
                        "to_trust": avg_recent,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    self._anomalies.append(anomaly)
                    
                    if self._on_anomaly:
                        self._on_anomaly(anomaly)
                    
                    logger.warning(
                        f"Trust anomaly detected: {path_id} dropped {drop:.2f} "
                        f"({avg_older:.2f} -> {avg_recent:.2f})"
                    )
    
    def _cleanup_old_events(self) -> None:
        """Remove old events from history."""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        # Clean events
        self._events = [e for e in self._events if e.timestamp > cutoff]
        
        # Clean anomalies
        self._anomalies = [
            a for a in self._anomalies 
            if datetime.fromisoformat(a["timestamp"]) > cutoff
        ]
    
    # -------------------------------------------------------------------------
    # Trust Event Recording
    # -------------------------------------------------------------------------
    
    def record_trust_event(
        self,
        path_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a trust-affecting event."""
        # Calculate trust delta
        trust_delta = self._calculate_trust_delta(event_type)
        
        # Create event
        event = TrustEvent(
            path_id=path_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            trust_delta=trust_delta,
            details=details or {},
        )
        self._events.append(event)
        
        # Apply trust update
        old_trust = 0.0
        path = self.engine._paths.get(path_id)
        if path:
            old_trust = path.metrics.trust_score
            self.engine.update_trust_score(path_id, trust_delta)
            new_trust = path.metrics.trust_score
            
            if self._on_trust_change:
                self._on_trust_change(path_id, old_trust, new_trust)
        
        logger.debug(
            f"Trust event: {event_type} on {path_id} "
            f"(delta: {trust_delta:+.2f}, old: {old_trust:.2f})"
        )
    
    def _calculate_trust_delta(self, event_type: str) -> float:
        """Calculate trust delta for an event type."""
        deltas = {
            "success": self.policy.trust_reward_success,
            "failure": -self.policy.trust_penalty_failure,
            "degraded": -self.policy.trust_penalty_degraded,
            "timeout": -self.policy.trust_penalty_failure * 0.5,
            "security_alert": -self.policy.trust_penalty_failure * 2,
            "low_latency": self.policy.trust_reward_low_latency,
            "recovery": self.policy.trust_recovery_rate,
        }
        return deltas.get(event_type, 0.0)
    
    # -------------------------------------------------------------------------
    # Background Tasks
    # -------------------------------------------------------------------------
    
    async def _trust_decay_loop(self) -> None:
        """Periodic trust decay for inactive paths."""
        while self._running:
            try:
                await asyncio.sleep(self.policy.trust_decay_interval_sec)
                
                # Apply decay to all paths
                for path in self.engine._paths.values():
                    # Decay based on time since last success
                    if path.metrics.last_success:
                        time_since_success = (
                            datetime.utcnow() - path.metrics.last_success
                        ).total_seconds()
                        
                        if time_since_success > 300:  # 5 minutes
                            decay = self.policy.trust_decay_rate * (
                                time_since_success / 300
                            )
                            self.engine.update_trust_score(
                                path.path_id, 
                                -min(decay, 0.1)  # Cap decay at 10%
                            )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trust decay loop error: {e}")
    
    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------
    
    def get_trust_summary(self) -> Dict[str, Any]:
        """Get summary of trust state."""
        metrics = self.collect_trust_metrics()
        analysis = self.analyze_trust_state(metrics)
        
        return {
            "metrics": metrics,
            "analysis": analysis,
            "recent_events": len(self._events),
            "anomalies": self._anomalies[:5],  # Last 5 anomalies
        }
    
    def get_path_trust_history(self, path_id: str) -> List[Tuple[str, float]]:
        """Get trust history for a specific path."""
        history = self._trust_history.get(path_id, [])
        return [(t.isoformat(), s) for t, s in history]


# Export
__all__ = [
    "TrustPolicy",
    "TrustEvent",
    "TrustAwareMAPEK",
]
