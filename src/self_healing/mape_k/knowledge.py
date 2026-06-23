"""MAPE-K Knowledge component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MAPEKKnowledge:
    """
    Knowledge base for MAPE-K cycle with feedback loop support.

    Stores incident history and provides feedback to improve:
    - Monitor: Adaptive thresholds based on historical patterns
    - Analyze: Improved root cause analysis from successful patterns
    - Plan: Optimized recovery strategies from experience

    Now integrated with Knowledge Storage v2.0 (IPFS + CRDT + Vector Memory)
    """

    def __init__(self, knowledge_storage=None):
        self.incidents: List[Dict[str, Any]] = []
        self.successful_patterns: Dict[str, List[Dict]] = (
            {}
        )  # issue -> [successful incidents]
        self.failed_patterns: Dict[str, List[Dict]] = {}  # issue -> [failed incidents]
        self.threshold_adjustments: Dict[str, float] = (
            {}
        )  # metric -> adjusted threshold

        # Integration with Knowledge Storage v2.0
        # knowledge_storage can be KnowledgeStorageV2 or MAPEKKnowledgeStorageAdapter
        self.knowledge_storage = knowledge_storage
        if knowledge_storage:
            logger.info("✅ MAPE-K Knowledge integrated with Knowledge Storage v2.0")

    def record(
        self,
        metrics: Dict,
        issue: str,
        action: str,
        success: bool = True,
        mttr: Optional[float] = None,
        node_id: str = "default",
    ):
        """Record incident with success status for feedback learning."""
        incident = {
            "metrics": metrics,
            "issue": issue,
            "action": action,
            "timestamp": time.time(),
            "success": success,
            "mttr": mttr,
        }
        self.incidents.append(incident)

        # Store in Knowledge Storage v2.0 (IPFS + Vector Memory)
        if self.knowledge_storage:
            try:
                # Check if it's an adapter (has record_incident_sync method)
                if hasattr(self.knowledge_storage, "record_incident_sync"):
                    # Use adapter's sync method
                    self.knowledge_storage.record_incident_sync(
                        metrics=metrics,
                        issue=issue,
                        action=action,
                        success=success,
                        mttr=mttr,
                    )
                else:
                    # Direct KnowledgeStorageV2 - use async
                    import asyncio

                    incident_entry = {
                        "id": f"incident-{int(time.time() * 1000)}",
                        "timestamp": time.time(),
                        "anomaly_type": issue,
                        "metrics": metrics,
                        "root_cause": issue,  # Will be improved by Causal Analysis
                        "recovery_plan": action,
                        "execution_result": {
                            "success": success,
                            "duration": mttr or 0.0,
                        },
                    }
                    # Run async in sync context
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, schedule as task
                            asyncio.create_task(
                                self.knowledge_storage.store_incident(
                                    incident_entry, node_id
                                )
                            )
                        else:
                            # If no loop, run it
                            loop.run_until_complete(
                                self.knowledge_storage.store_incident(
                                    incident_entry, node_id
                                )
                            )
                    except RuntimeError:
                        # No event loop, create new one
                        asyncio.run(
                            self.knowledge_storage.store_incident(
                                incident_entry, node_id
                            )
                        )
                    logger.debug(
                        f"📚 Stored incident in Knowledge Storage v2.0: {issue}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to store in Knowledge Storage: {e}")

        # Categorize by success/failure for pattern learning
        if success:
            if issue not in self.successful_patterns:
                self.successful_patterns[issue] = []
            self.successful_patterns[issue].append(incident)
        else:
            if issue not in self.failed_patterns:
                self.failed_patterns[issue] = []
            self.failed_patterns[issue].append(incident)

        # Update thresholds based on feedback
        self._update_thresholds(metrics, issue, success)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get all incident history."""
        return self.incidents

    def get_successful_patterns(self, issue: str) -> List[Dict[str, Any]]:
        """Get successful recovery patterns for specific issue."""
        # Try to get from Knowledge Storage v2.0 first (with RAG search)
        if self.knowledge_storage:
            try:
                # Check if it's an adapter (has search_patterns_sync method)
                if hasattr(self.knowledge_storage, "search_patterns_sync"):
                    # Use adapter's sync method
                    results = self.knowledge_storage.search_patterns_sync(
                        query=f"{issue} successful recovery", k=10, threshold=0.7
                    )
                    if results:
                        logger.debug(
                            f"🔍 Found {len(results)} patterns from Knowledge Storage"
                        )
                        return results
                elif hasattr(self.knowledge_storage, "get_successful_patterns"):
                    # Direct KnowledgeStorageV2 - use async
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Can't run async in sync context, return local patterns
                            logger.debug(
                                "⚠️ Cannot run async search in running loop, using local patterns"
                            )
                            return self.successful_patterns.get(issue, [])
                        else:
                            # Run synchronously
                            results = loop.run_until_complete(
                                self.knowledge_storage.get_successful_patterns(issue)
                            )
                            if results:
                                logger.debug(
                                    f"🔍 Found {len(results)} patterns from Knowledge Storage"
                                )
                                return results
                    except RuntimeError:
                        # No event loop, create new one
                        results = asyncio.run(
                            self.knowledge_storage.get_successful_patterns(issue)
                        )
                        if results:
                            return results
                else:
                    # Try async search_incidents
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            return self.successful_patterns.get(issue, [])
                        else:
                            results = loop.run_until_complete(
                                self.knowledge_storage.search_incidents(
                                    f"{issue} successful recovery", k=10, threshold=0.7
                                )
                            )
                            if results:
                                logger.debug(
                                    f"🔍 Found {len(results)} patterns from Knowledge Storage"
                                )
                                return results
                    except RuntimeError:
                        results = asyncio.run(
                            self.knowledge_storage.search_incidents(
                                f"{issue} successful recovery", k=10, threshold=0.7
                            )
                        )
                        if results:
                            return results
            except Exception as e:
                logger.warning(f"⚠️ Failed to search Knowledge Storage: {e}")

        # Fallback to local patterns
        return self.successful_patterns.get(issue, [])

    def get_average_mttr(self, issue: str) -> Optional[float]:
        """
        Get average MTTR for a specific issue type from historical data.

        Args:
            issue: Issue type/root cause

        Returns:
            Average MTTR in seconds, or None if no data available
        """
        # Get successful incidents for this issue
        successful_incidents = self.successful_patterns.get(issue, [])

        if not successful_incidents:
            # Try to get from Knowledge Storage v2.0
            if self.knowledge_storage:
                try:
                    # Query knowledge storage for historical MTTR
                    patterns = self.get_successful_patterns(issue)
                    if patterns:
                        mttr_values = [
                            p.get("mttr", 0)
                            for p in patterns
                            if p.get("mttr") and p.get("mttr", 0) > 0
                        ]
                        if mttr_values:
                            return sum(mttr_values) / len(mttr_values)
                except Exception:
                    pass
            return None

        # Calculate average MTTR from successful incidents
        mttr_values = [
            inc.get("mttr", 0)
            for inc in successful_incidents
            if inc.get("mttr") and inc.get("mttr", 0) > 0
        ]

        if not mttr_values:
            return None

        return sum(mttr_values) / len(mttr_values)

    def get_recommended_action(self, issue: str) -> Optional[str]:
        """
        Get recommended action based on historical success patterns.

        Returns most successful action for this issue type using RL logic.
        """
        # 1. Fetch patterns (Local + Knowledge Storage)
        patterns = self.get_successful_patterns(issue)
        if not patterns:
            return None

        # 2. Score actions: (Successes / Total) * (1 / Avg MTTR)
        # We need to consider failures too, but get_successful_patterns only returns successes.
        # Let's count attempts from self.incidents and Knowledge Storage if possible.
        
        stats: Dict[str, Dict[str, Any]] = {} # action -> {successes, failures, total_mttr}
        
        # Process successes from patterns
        for p in patterns:
            # Handle different formats (from KnowledgeStorageV2 vs local)
            action = p.get("recovery_plan") or p.get("action")
            if not action: continue
            
            res = p.get("execution_result") or {}
            mttr = res.get("duration") or p.get("mttr") or 5.0
            
            if action not in stats:
                stats[action] = {"successes": 0, "failures": 0, "total_mttr": 0.0}
            
            stats[action]["successes"] += 1
            stats[action]["total_mttr"] += mttr

        # Process failures from local cache
        if issue in self.failed_patterns:
            for f in self.failed_patterns[issue]:
                action = f.get("action")
                if action and action in stats:
                    stats[action]["failures"] += 1

        # 3. Find best action using a simple scoring formula
        if not stats:
            return None

        best_action = None
        best_score = -1.0

        for action, data in stats.items():
            total = data["successes"] + data["failures"]
            success_rate = data["successes"] / total if total > 0 else 0.0
            avg_mttr = data["total_mttr"] / data["successes"] if data["successes"] > 0 else 10.0
            
            # Score = success_rate / avg_mttr (higher is better)
            score = success_rate / max(avg_mttr, 0.1)
            
            if score > best_score:
                best_score = score
                best_action = action

        if best_action:
            logger.info(f"📈 RL-Planner: Selected '{best_action}' for '{issue}' (score: {best_score:.3f})")
            
        return best_action

    def get_adjusted_threshold(
        self, metric_name: str, default_threshold: float
    ) -> float:
        """
        Get adjusted threshold based on feedback learning.

        Thresholds are adjusted based on false positive/negative rates.
        """
        if metric_name in self.threshold_adjustments:
            return self.threshold_adjustments[metric_name]
        return default_threshold

    # Default baselines used for threshold initialisation — mirrors MAPEKMonitor defaults.
    _THRESHOLD_BASELINES: Dict[str, float] = {
        "cpu_percent": 90.0,
        "memory_percent": 85.0,
        "packet_loss_percent": 5.0,
    }
    # Hard caps: percentage metrics cannot exceed 100 %; others are unbounded.
    _THRESHOLD_CAPS: Dict[str, float] = {
        "cpu_percent": 100.0,
        "memory_percent": 100.0,
        "packet_loss_percent": 100.0,
    }

    def _update_thresholds(self, metrics: Dict, issue: str, success: bool):
        """
        Update detection thresholds based on feedback.

        Initialises from the *default* baseline for known metrics (not from the
        anomaly-triggering value, which would push the threshold above 100 % for
        percentage metrics and blind the Monitor phase).

        If successful recovery: slightly relax threshold (+2 %).
        If failed recovery: tighten threshold (-5 %).
        Hard cap at 100 % for percentage metrics to prevent impossible thresholds.
        """
        for metric_name, value in metrics.items():
            if not isinstance(value, (int, float)):
                continue

            if metric_name not in self.threshold_adjustments:
                # Use the known baseline, fall back to current value only for
                # unknown metrics (where 10 % headroom is a reasonable heuristic).
                baseline = self._THRESHOLD_BASELINES.get(metric_name, value)
                self.threshold_adjustments[metric_name] = baseline

            # Adjust based on success rate
            if success:
                # Successful recovery: slightly relax threshold (raise by 2 %)
                self.threshold_adjustments[metric_name] *= 1.02
            else:
                # Failed recovery: tighten threshold (lower by 5 %)
                self.threshold_adjustments[metric_name] *= 0.95

            # Clamp within ±10 % of the baseline to prevent unbounded drift.
            baseline = self._THRESHOLD_BASELINES.get(metric_name)
            if baseline is not None:
                lo = baseline * 0.90
                hi = min(baseline * 1.10, self._THRESHOLD_CAPS.get(metric_name, float("inf")))
                self.threshold_adjustments[metric_name] = max(
                    lo, min(self.threshold_adjustments[metric_name], hi)
                )
            else:
                # For unknown metrics: cap at hard ceiling if applicable
                cap = self._THRESHOLD_CAPS.get(metric_name)
                if cap is not None:
                    self.threshold_adjustments[metric_name] = max(
                        1.0, min(self.threshold_adjustments[metric_name], cap)
                    )


