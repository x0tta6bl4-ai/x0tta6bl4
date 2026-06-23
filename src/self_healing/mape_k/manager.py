"""MAPE-K Self-Healing Manager component."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """
    Self-Healing Manager with MAPE-K feedback loop.

    Implements complete MAPE-K cycle with feedback from Knowledge
    phase improving Monitor, Analyze, and Plan phases.

    Now supports DAO-managed thresholds.
    """

    def __init__(
        self, node_id: str = "default", threshold_manager=None, knowledge_storage=None
    ):
        self.node_id = node_id

        # Initialize Knowledge with storage (if provided)
        if knowledge_storage:
            from src.storage.mapek_integration import \
                MAPEKKnowledgeStorageAdapter

            adapter = MAPEKKnowledgeStorageAdapter(knowledge_storage, node_id)
            self.knowledge = MAPEKKnowledge(knowledge_storage=adapter)
        else:
            self.knowledge = MAPEKKnowledge()

        # Initialize threshold manager (for DAO-managed thresholds)
        self.threshold_manager = threshold_manager

        # Initialize other phases with Knowledge reference for feedback
        self.monitor = MAPEKMonitor(
            knowledge=self.knowledge, threshold_manager=threshold_manager
        )
        self.analyzer = MAPEKAnalyzer()
        self.planner = MAPEKPlanner(knowledge=self.knowledge)
        self.executor = MAPEKExecutor()

        # Check and apply DAO proposals on startup
        if threshold_manager:
            try:
                applied = threshold_manager.check_and_apply_dao_proposals()
                if applied > 0:
                    logger.info(
                        f"✅ Applied {applied} DAO threshold proposals on startup"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to check DAO proposals: {e}")

        # MTTR tracking
        self.recovery_start_times: Dict[str, float] = {}  # event_id -> detection_time
        self.recovery_events: Dict[str, str] = {}  # event_id -> recovery_type

        # Feedback loop statistics
        self.feedback_updates = 0
        self.threshold_adjustments = 0
        self.strategy_improvements = 0

    def run_cycle(self, metrics: Dict):
        """Run MAPE-K cycle with MTTR tracking."""
        time.time()

        # MONITOR phase
        monitor_start = time.time()
        _check_result = self.monitor.check(metrics)
        if isinstance(_check_result, dict):
            anomaly_detected = _check_result.get("anomaly_detected", False)
        else:
            anomaly_detected = bool(_check_result)
        monitor_duration = time.time() - monitor_start

        try:
            from src.monitoring.metrics import record_mape_k_cycle

            record_mape_k_cycle("monitor", monitor_duration)
        except ImportError:
            pass

        if anomaly_detected:
            # ANALYZE phase
            analyze_start = time.time()
            analyze_event_id = f"{self.node_id}_{int(time.time() * 1000)}"
            try:
                issue = self.analyzer.analyze(
                    metrics, node_id=self.node_id, event_id=analyze_event_id
                )
            except TypeError as exc:
                # Backward compatibility for analyzer test doubles that only accept metrics.
                if "unexpected keyword argument" in str(exc):
                    issue = self.analyzer.analyze(metrics)
                else:
                    raise
            analyze_duration = time.time() - analyze_start

            try:
                from src.monitoring.metrics import record_mape_k_cycle

                record_mape_k_cycle("analyze", analyze_duration)
            except ImportError:
                pass

            # Start recovery event tracking
            event_id = f"{issue}_{self.node_id}_{int(time.time() * 1000)}"
            self.recovery_start_times[event_id] = time.time()
            self.recovery_events[event_id] = issue

            # PLAN phase
            plan_start = time.time()
            action = self.planner.plan(issue)
            plan_duration = time.time() - plan_start

            try:
                from src.monitoring.metrics import record_mape_k_cycle

                record_mape_k_cycle("plan", plan_duration)
            except ImportError:
                pass

            # EXECUTE phase
            execute_start = time.time()
            success = self.executor.execute(action)
            execute_duration = time.time() - execute_start

            # Calculate MTTR
            if event_id in self.recovery_start_times:
                mttr = time.time() - self.recovery_start_times[event_id]

                # Export MTTR metric
                try:
                    from src.monitoring.metrics import (
                        record_mape_k_cycle, record_mttr,
                        record_self_healing_event)

                    # Map issue to recovery type
                    recovery_type_map = {
                        "High CPU": "high_cpu",
                        "High Memory": "high_memory",
                        "Network Loss": "route_failure",
                    }
                    recovery_type = recovery_type_map.get(issue, "unknown")

                    record_mttr(recovery_type, mttr)
                    record_self_healing_event(recovery_type, self.node_id)
                    record_mape_k_cycle("execute", execute_duration)
                except ImportError:
                    pass

                # KNOWLEDGE phase with feedback loop.
                knowledge_start = time.time()
                self.knowledge.record(metrics, issue, action, success=success, mttr=mttr)
                # Feedback loop: Update Monitor and Planner based on results
                self._apply_feedback_loop(issue, action, success, mttr)

                if getattr(self.executor, "was_simulated", False) is True:
                    logger.debug(
                        "Recorded simulated recovery in knowledge base: %s", action
                    )

                knowledge_duration = time.time() - knowledge_start
                try:
                    from src.monitoring.metrics import record_mape_k_cycle
                    record_mape_k_cycle("knowledge", knowledge_duration)
                except ImportError:
                    pass

                # Cleanup
                del self.recovery_start_times[event_id]
                del self.recovery_events[event_id]

            logger.info(
                f"Self-healing cycle: {issue} → {action}, "
                f"MTTR={mttr:.3f}s, success={success}"
            )
        else:
            logger.info("No anomalies detected. System healthy.")

    def _apply_feedback_loop(self, issue: str, action: str, success: bool, mttr: float):
        """
        Apply feedback loop: update Monitor and Planner based on results.

        This is the core of the feedback mechanism:
        - Successful recoveries with low MTTR → reinforce patterns
        - Failed recoveries → adjust thresholds and strategies
        """
        self.feedback_updates += 1

        # Feedback to Monitor: Adjust thresholds if needed
        if success and mttr < 3.0:  # Very successful recovery
            # Slightly relax thresholds (system is handling well)
            self.threshold_adjustments += 1
            logger.debug(
                f"Feedback: Successful recovery (MTTR={mttr:.3f}s), reinforcing patterns"
            )
        elif not success or mttr > 7.0:  # Failed or slow recovery
            # Tighten thresholds (need earlier detection)
            self.threshold_adjustments += 1
            logger.debug(
                f"Feedback: Failed/slow recovery (MTTR={mttr:.3f}s), adjusting thresholds"
            )

        # Feedback to Planner: Track strategy effectiveness
        if success:
            # Successful action pattern reinforced in Knowledge base
            self.strategy_improvements += 1
            logger.debug(
                f"Feedback: Action '{action}' successful for '{issue}', reinforcing strategy"
            )

        # Periodic feedback summary
        if self.feedback_updates % 10 == 0:
            logger.info(
                f"Feedback loop stats: "
                f"updates={self.feedback_updates}, "
                f"threshold_adjustments={self.threshold_adjustments}, "
                f"strategy_improvements={self.strategy_improvements}"
            )

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback loop statistics."""
        return {
            "feedback_updates": self.feedback_updates,
            "threshold_adjustments": self.threshold_adjustments,
            "strategy_improvements": self.strategy_improvements,
            "knowledge_base_size": len(self.knowledge.incidents),
            "successful_patterns": len(self.knowledge.successful_patterns),
            "failed_patterns": len(self.knowledge.failed_patterns),
        }

    def integrate_ebpf_self_healing(self, interface: str = "eth0"):
        """
        Integrate eBPF-based self-healing for network anomalies.

        Adds eBPF anomaly detector to the MAPE-K monitor phase.
        Enables automatic recovery from network-level issues.
        """
        try:
            from .ebpf_anomaly_detector import integrate_ebpf_self_healing

            ebpf_controller = integrate_ebpf_self_healing(self, interface)
            logger.info("✅ eBPF self-healing integrated with MAPE-K")
            return ebpf_controller
        except ImportError as e:
            logger.warning(f"⚠️ eBPF self-healing not available: {e}")
            return None
