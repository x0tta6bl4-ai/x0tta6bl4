"""
Knowledge base for MAPE-K Self-Healing.
"""
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from src.core.mape_k.interfaces import KnowledgeInterface

class MAPEKKnowledge(KnowledgeInterface):
    """
    Knowledge base for MAPE-K cycle with feedback loop support.
    """

    _THRESHOLD_BASELINES: Dict[str, float] = {
        "cpu_percent": 90.0,
        "memory_percent": 85.0,
        "packet_loss_percent": 5.0,
    }
    _THRESHOLD_CAPS: Dict[str, float] = {
        "cpu_percent": 100.0,
        "memory_percent": 100.0,
        "packet_loss_percent": 100.0,
    }

    def __init__(self, knowledge_storage=None):
        self.incidents: List[Dict[str, Any]] = []
        self.successful_patterns: Dict[str, List[Dict]] = {}
        self.failed_patterns: Dict[str, List[Dict]] = {}
        self.threshold_adjustments: Dict[str, float] = {}
        self.knowledge_storage = knowledge_storage

    def record(self, metrics: Dict, issue: str, action: str, success: bool = True, mttr: Optional[float] = None, node_id: str = "default"):
        """Record incident with success status for feedback learning."""
        incident = {
            "metrics": metrics, "issue": issue, "action": action,
            "timestamp": time.time(), "success": success, "mttr": mttr
        }
        self.incidents.append(incident)

        if self.knowledge_storage:
            try:
                if hasattr(self.knowledge_storage, "record_incident_sync"):
                    self.knowledge_storage.record_incident_sync(metrics=metrics, issue=issue, action=action, success=success, mttr=mttr)
                else:
                    import asyncio
                    try: asyncio.run(self.knowledge_storage.store_incident(incident, node_id))
                    except Exception: pass
            except Exception: pass

        if success:
            if issue not in self.successful_patterns: self.successful_patterns[issue] = []
            self.successful_patterns[issue].append(incident)
        else:
            if issue not in self.failed_patterns: self.failed_patterns[issue] = []
            self.failed_patterns[issue].append(incident)

        self._update_thresholds(metrics, issue, success)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get all incident history."""
        return self.incidents

    def get_successful_patterns(self, issue: str) -> List[Dict[str, Any]]:
        """Get successful recovery patterns for specific issue."""
        if self.knowledge_storage:
            try:
                if hasattr(self.knowledge_storage, "search_patterns_sync"):
                    res = self.knowledge_storage.search_patterns_sync(query=issue, k=10)
                    if res: return res
            except Exception: pass
        return self.successful_patterns.get(issue, [])

    def get_average_mttr(self, issue: str) -> Optional[float]:
        """Get average MTTR for a specific issue type."""
        patterns = self.get_successful_patterns(issue)
        if not patterns: return None
        mttr_values = [p.get("mttr", 0) or (p.get("execution_result") or {}).get("duration", 0) for p in patterns]
        mttr_values = [v for v in mttr_values if v and v > 0]
        if not mttr_values: return None
        return sum(mttr_values) / len(mttr_values)

    def get_recommended_action(self, issue: str) -> Optional[str]:
        """Get recommended action based on historical success patterns."""
        patterns = self.get_successful_patterns(issue)
        if not patterns: return None

        stats: Dict[str, Dict[str, Any]] = {}
        for p in patterns:
            action = p.get("recovery_plan") or p.get("action")
            if not action: continue
            res = p.get("execution_result") or {}
            mttr = res.get("duration") or p.get("mttr") or 5.0
            if action not in stats: stats[action] = {"successes": 0, "failures": 0, "total_mttr": 0.0}
            stats[action]["successes"] += 1
            stats[action]["total_mttr"] += mttr

        if issue in self.failed_patterns:
            for f in self.failed_patterns[issue]:
                action = f.get("action")
                if action and action in stats: stats[action]["failures"] += 1

        best_action, best_score = None, -1.0
        for action, data in stats.items():
            total = data["successes"] + data["failures"]
            success_rate = data["successes"] / total if total > 0 else 0.0
            avg_mttr = data["total_mttr"] / data["successes"] if data["successes"] > 0 else 10.0
            score = success_rate / max(avg_mttr, 0.1)
            if score > best_score: best_score, best_action = score, action
        return best_action

    def get_adjusted_threshold(self, metric: str, default: float) -> float:
        """Get adjusted threshold from knowledge base."""
        return self.threshold_adjustments.get(metric, default)

    def _update_thresholds(self, metrics: Dict, issue: str, success: bool):
        """Update detection thresholds based on feedback."""
        for metric_name, value in metrics.items():
            if not isinstance(value, (int, float)): continue
            if metric_name not in self.threshold_adjustments:
                self.threshold_adjustments[metric_name] = self._THRESHOLD_BASELINES.get(metric_name, value)
            if success: self.threshold_adjustments[metric_name] *= 1.02
            else: self.threshold_adjustments[metric_name] *= 0.95
            baseline = self._THRESHOLD_BASELINES.get(metric_name)
            if baseline is not None:
                lo, hi = baseline * 0.90, min(baseline * 1.10, self._THRESHOLD_CAPS.get(metric_name, float("inf")))
                self.threshold_adjustments[metric_name] = max(lo, min(self.threshold_adjustments[metric_name], hi))
            else:
                cap = self._THRESHOLD_CAPS.get(metric_name)
                if cap is not None: self.threshold_adjustments[metric_name] = max(1.0, min(self.threshold_adjustments[metric_name], cap))
