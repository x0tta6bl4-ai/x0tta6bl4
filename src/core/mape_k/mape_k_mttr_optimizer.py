"""
MAPE-K Mean Time To Recovery (MTTR) Optimizer

Optimizes the MAPE-K loop for faster recovery from failures with:
- Parallel phase execution
- Priority-based action execution
- Early recovery detection
- Adaptive monitoring intervals
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _duration_band(seconds: float) -> str:
    if seconds <= 0:
        return "none"
    if seconds < 1:
        return "subsecond"
    if seconds < 5:
        return "fast"
    if seconds < 30:
        return "moderate"
    return "slow"


def _action_summary(actions: list["ActionPriority"]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for action in actions:
        by_type[action.action_type] = by_type.get(action.action_type, 0) + 1
    return {
        "count": len(actions),
        "count_bucket": _safe_count_bucket(len(actions)),
        "by_type": by_type,
        "action_hashes": [_safe_hash(action.action_id) for action in actions[:10]],
        "dependency_count": sum(len(action.dependencies) for action in actions),
    }


class RecoveryPhase(Enum):
    """Phases of recovery process"""

    DETECTION = "detection"  # Anomaly detected
    DIAGNOSIS = "diagnosis"  # Root cause analysis
    ACTION = "action"  # Execute corrective actions
    VERIFICATION = "verification"  # Verify recovery
    COMPLETE = "complete"  # Recovery complete


@dataclass
class ActionPriority:
    """Execution priority for recovery actions"""

    action_id: str
    action_type: str  # 'critical', 'high', 'medium', 'low'
    estimated_mttr_reduction: float  # Seconds
    dependencies: list[str] = field(default_factory=list)
    executed: bool = False
    completion_time: float = 0.0


@dataclass
class MTTRMetrics:
    """Metrics for MTTR optimization"""

    detection_time: float  # Time to detect issue
    diagnosis_time: float  # Time to identify root cause
    first_action_time: float  # Time to first corrective action
    recovery_complete_time: float  # Total MTTR
    actions_executed: int
    recovery_success_rate: float  # 0-1
    phase: RecoveryPhase = RecoveryPhase.DETECTION


class ParallelMAPEKExecutor:
    """
    Executes MAPE-K phases in parallel where possible for faster recovery.
    """

    def __init__(self, max_parallel_tasks: int = 8):
        self.max_parallel_tasks = max_parallel_tasks
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.completed_tasks: list[tuple[str, float]] = []
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"parallel-mapek-executor:{_safe_hash(id(self))}",
            role="healing",
            capabilities=("mape_k", "ops", "coordinator"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "parallel_mapek_executor_init",
                "goal": "Initialize parallel MAPE-K execution decisions",
                "signals": {"max_parallel_tasks": max_parallel_tasks},
                "safety_boundary": (
                    "Do not expose raw phase payloads or action ids in execution "
                    "thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_phase_payloads": True,
                    "redact_action_ids": True,
                    "preserve_parallel_execution_contract": True,
                },
                "safety_boundary": (
                    "Use recovery flags, action summaries, counts, and duration bands."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def execute_parallel(
        self, monitor_task, analyze_task, plan_task, execute_task, knowledge_task
    ) -> dict[str, Any]:
        """
        Execute MAPE-K phases with intelligent parallelization.

        Phases that can run in parallel:
        - Monitor and previous knowledge simultaneous
        - Analyze runs after Monitor completes
        - Plan and Execute can run in parallel during recovery
        """
        try:
            # Phase 1: Monitor (always first)
            start_time = time.time()
            monitor_result = await monitor_task()
            monitor_duration = time.time() - start_time

            # Phase 2: Analyze (depends on Monitor)
            start_time = time.time()
            analyze_result = await analyze_task(monitor_result)
            analyze_duration = time.time() - start_time

            # Phase 3 & 4: Plan and Execute can run in parallel if in recovery
            if self._is_recovery_state(analyze_result):
                # Parallel execution during recovery
                plan_task_obj = asyncio.create_task(plan_task(analyze_result))
                execute_prep = asyncio.create_task(
                    self._prepare_emergency_actions(analyze_result)
                )

                plan_result, emergency_actions = await asyncio.gather(
                    plan_task_obj, execute_prep
                )

                # Execute with priority ordering
                execute_result = await execute_task(plan_result, emergency_actions)
            else:
                # Sequential execution for normal operation
                plan_result = await plan_task(analyze_result)
                execute_result = await execute_task(plan_result, [])

            # Phase 5: Knowledge (can run in parallel with monitoring)
            knowledge_result = await knowledge_task(
                analyze_result, plan_result, execute_result
            )

            result = {
                "monitor": monitor_result,
                "analyze": analyze_result,
                "plan": plan_result,
                "execute": execute_result,
                "knowledge": knowledge_result,
                "timings": {
                    "monitor": monitor_duration,
                    "analyze": analyze_duration,
                    "total": time.time() - start_time,
                },
            }
            self._record_thinking(
                "parallel_mapek_executed",
                "Execute MAPE-K phases with recovery-aware parallelism",
                {
                    "recovery_state": self._is_recovery_state(analyze_result),
                    "analyze_flags": {
                        "is_degraded": bool(analyze_result.get("is_degraded")),
                        "is_critical": bool(analyze_result.get("is_critical")),
                        "recovery_in_progress": bool(
                            analyze_result.get("recovery_in_progress")
                        ),
                    },
                    "emergency_actions": _action_summary(
                        await self._prepare_emergency_actions(analyze_result)
                    ),
                    "monitor_duration_band": _duration_band(monitor_duration),
                    "analyze_duration_band": _duration_band(analyze_duration),
                    "total_duration_band": _duration_band(result["timings"]["total"]),
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error in parallel MAPE-K execution: {e}")
            self._record_thinking(
                "parallel_mapek_failed",
                "Handle parallel MAPE-K execution failure",
                {"error_type": type(e).__name__},
            )
            raise

    async def _prepare_emergency_actions(
        self, analyze_result: dict[str, Any]
    ) -> list[ActionPriority]:
        """Prepare high-priority emergency actions during recovery"""
        emergency_actions = []

        # Identify critical issues
        if analyze_result.get("is_critical"):
            # High priority: Restart critical services
            emergency_actions.append(
                ActionPriority(
                    action_id="restart_critical_services",
                    action_type="critical",
                    estimated_mttr_reduction=5.0,
                )
            )

            # High priority: Isolate failing component
            emergency_actions.append(
                ActionPriority(
                    action_id="isolate_failure",
                    action_type="high",
                    estimated_mttr_reduction=3.0,
                )
            )

            # Medium priority: Reroute traffic
            emergency_actions.append(
                ActionPriority(
                    action_id="reroute_traffic",
                    action_type="medium",
                    estimated_mttr_reduction=2.0,
                    dependencies=["isolate_failure"],
                )
            )

        self._record_thinking(
            "parallel_mapek_emergency_actions_prepared",
            "Prepare emergency actions for recovery state",
            {
                "is_critical": bool(analyze_result.get("is_critical")),
                "actions": _action_summary(emergency_actions),
            },
        )
        return emergency_actions

    def _is_recovery_state(self, analyze_result: dict[str, Any]) -> bool:
        """Check if system is in recovery state"""
        return bool(
            analyze_result.get("is_degraded")
            or analyze_result.get("is_critical")
            or analyze_result.get("recovery_in_progress")
        )


class MTTROptimizer:
    """
    Optimizes MAPE-K loop for minimal MTTR (Mean Time To Recovery).
    """

    def __init__(self):
        self.executor = ParallelMAPEKExecutor()
        self.current_recovery: MTTRMetrics | None = None
        self.recovery_history: list[MTTRMetrics] = []
        self.max_history = 1000

        # MTTR targets (in seconds)
        self.mttr_targets = {
            "transient_error": 5.0,
            "service_failure": 15.0,
            "network_issue": 10.0,
            "resource_exhaustion": 20.0,
        }
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"mttr-optimizer:{_safe_hash(id(self))}",
            role="healing",
            capabilities=("mape_k", "ops", "chaos_driven_design"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mttr_optimizer_init",
                "goal": "Initialize MTTR optimization decisions",
                "signals": {
                    "target_count": len(self.mttr_targets),
                    "max_history": self.max_history,
                },
                "safety_boundary": (
                    "Do not expose raw issue types, action ids, or phase payloads in "
                    "MTTR thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_issue_types": True,
                    "redact_action_ids": True,
                    "preserve_mttr_contract": True,
                },
                "safety_boundary": (
                    "Use hashes, phases, counts, success flags, and duration bands."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "executor": self.executor.get_thinking_status(),
        }

    def start_recovery_tracking(self, issue_type: str) -> None:
        """Start tracking recovery metrics for an issue"""
        self.current_recovery = MTTRMetrics(
            detection_time=time.time(),
            diagnosis_time=0.0,
            first_action_time=0.0,
            recovery_complete_time=0.0,
            actions_executed=0,
            recovery_success_rate=0.0,
        )
        logger.info(f"Recovery tracking started for issue type: {issue_type}")
        self._record_thinking(
            "mttr_recovery_started",
            "Start MTTR recovery tracking",
            {
                "issue_hash": _safe_hash(issue_type),
                "phase": RecoveryPhase.DETECTION.value,
                "history_count_bucket": _safe_count_bucket(len(self.recovery_history)),
            },
        )

    def record_diagnosis_complete(self) -> None:
        """Record completion of diagnosis phase"""
        if self.current_recovery:
            self.current_recovery.diagnosis_time = time.time()
            self.current_recovery.phase = RecoveryPhase.DIAGNOSIS
            diagnosis_duration = (
                self.current_recovery.diagnosis_time
                - self.current_recovery.detection_time
            )
            logger.info(f"Diagnosis complete in {diagnosis_duration:.2f}s")
            self._record_thinking(
                "mttr_diagnosis_completed",
                "Record diagnosis phase completion",
                {
                    "phase": self.current_recovery.phase.value,
                    "diagnosis_duration_band": _duration_band(diagnosis_duration),
                },
            )

    def record_first_action(self) -> None:
        """Record execution of first corrective action"""
        if self.current_recovery:
            self.current_recovery.first_action_time = time.time()
            self.current_recovery.phase = RecoveryPhase.ACTION
            ttf = (
                self.current_recovery.first_action_time
                - self.current_recovery.detection_time
            )
            logger.info(f"First action executed in {ttf:.2f}s")
            self._record_thinking(
                "mttr_first_action_recorded",
                "Record first corrective action timing",
                {
                    "phase": self.current_recovery.phase.value,
                    "time_to_first_action_band": _duration_band(ttf),
                },
            )

    def record_recovery_complete(self, success: bool) -> None:
        """Record recovery completion"""
        if self.current_recovery:
            self.current_recovery.recovery_complete_time = time.time()
            self.current_recovery.phase = RecoveryPhase.COMPLETE
            self.current_recovery.recovery_success_rate = 1.0 if success else 0.0

            total_mttr = (
                self.current_recovery.recovery_complete_time
                - self.current_recovery.detection_time
            )
            logger.info(f"Recovery complete in {total_mttr:.2f}s (success={success})")

            self.recovery_history.append(self.current_recovery)
            if len(self.recovery_history) > self.max_history:
                self.recovery_history.pop(0)

            self.current_recovery = None
            self._record_thinking(
                "mttr_recovery_completed",
                "Record recovery completion and update history",
                {
                    "success": success,
                    "total_mttr_band": _duration_band(total_mttr),
                    "history_count_bucket": _safe_count_bucket(
                        len(self.recovery_history)
                    ),
                },
            )

    def execute_action_priority_queue(
        self, actions: list[ActionPriority]
    ) -> tuple[list[ActionPriority], float]:
        """
        Execute actions in priority order, respecting dependencies.

        Returns:
            Tuple of (executed_actions, total_execution_time)
        """
        executed = []
        execution_time = time.time()

        # Sort by priority (critical > high > medium > low)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_actions = sorted(
            actions,
            key=lambda a: (
                priority_order.get(a.action_type, 999),
                -a.estimated_mttr_reduction,
            ),
        )

        # Execute respecting dependencies
        completed_ids = set()
        for action in sorted_actions:
            # Check dependencies
            if all(dep in completed_ids for dep in action.dependencies):
                action.executed = True
                action.completion_time = time.time()
                executed.append(action)
                completed_ids.add(action.action_id)

                if self.current_recovery:
                    self.current_recovery.actions_executed += 1

        total_time = time.time() - execution_time
        self._record_thinking(
            "mttr_priority_queue_executed",
            "Execute recovery actions by priority and dependency readiness",
            {
                "input_actions": _action_summary(actions),
                "executed_actions": _action_summary(executed),
                "total_execution_band": _duration_band(total_time),
                "current_recovery_present": self.current_recovery is not None,
            },
        )
        return executed, total_time

    def get_mttr_statistics(self) -> dict[str, Any]:
        """Get MTTR optimization statistics"""
        if not self.recovery_history:
            self._record_thinking(
                "mttr_statistics_empty",
                "Return empty MTTR statistics",
                {"history_count": 0},
            )
            return {"total_recoveries": 0}

        # Calculate statistics
        recovery_times = [
            r.recovery_complete_time - r.detection_time for r in self.recovery_history
        ]
        action_times = [
            r.first_action_time - r.detection_time for r in self.recovery_history
        ]
        success_count = sum(
            1 for r in self.recovery_history if r.recovery_success_rate == 1.0
        )

        stats = {
            "total_recoveries": len(self.recovery_history),
            "average_mttr": sum(recovery_times) / len(recovery_times),
            "min_mttr": min(recovery_times),
            "max_mttr": max(recovery_times),
            "average_time_to_first_action": sum(action_times) / len(action_times),
            "success_rate": success_count / len(self.recovery_history),
            "recent_recoveries": [
                {
                    "detection_to_diagnosis": r.diagnosis_time - r.detection_time,
                    "detection_to_action": r.first_action_time - r.detection_time,
                    "total_mttr": r.recovery_complete_time - r.detection_time,
                    "actions_executed": r.actions_executed,
                }
                for r in self.recovery_history[-10:]
            ],
        }
        self._record_thinking(
            "mttr_statistics_collected",
            "Collect MTTR recovery statistics",
            {
                "total_recoveries_bucket": _safe_count_bucket(
                    stats["total_recoveries"]
                ),
                "average_mttr_band": _duration_band(stats["average_mttr"]),
                "min_mttr_band": _duration_band(stats["min_mttr"]),
                "max_mttr_band": _duration_band(stats["max_mttr"]),
                "success_rate": stats["success_rate"],
            },
        )
        return stats


class AdaptiveMonitoringIntervals:
    """
    Dynamically adjust monitoring intervals based on system state.
    """

    def __init__(self):
        self.intervals = {
            "healthy": 60.0,
            "degraded": 15.0,
            "critical": 3.0,
            "recovering": 5.0,
        }
        self.current_state = "healthy"
        self.next_interval = self.intervals[self.current_state]
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"adaptive-monitoring-intervals:{_safe_hash(id(self))}",
            role="monitoring",
            capabilities=("mape_k", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "adaptive_monitoring_intervals_init",
                "goal": "Initialize adaptive monitoring interval policy",
                "signals": {
                    "state": self.current_state,
                    "interval_count": len(self.intervals),
                    "current_interval_band": _duration_band(self.next_interval),
                },
                "safety_boundary": (
                    "Do not expose caller payloads in interval thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "preserve_interval_contract": True,
                    "redact_unknown_state_names": True,
                },
                "safety_boundary": (
                    "Use known states, state hashes, interval bands, and booleans."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def update_state(self, new_state: str) -> float:
        """
        Update system state and return new monitoring interval.

        Returns:
            Monitoring interval in seconds
        """
        if new_state in self.intervals:
            self.current_state = new_state
            self.next_interval = self.intervals[new_state]
            logger.info(
                f"Monitoring interval updated: {new_state} = " f"{self.next_interval}s"
            )
            self._record_thinking(
                "adaptive_monitoring_interval_updated",
                "Update monitoring interval for known state",
                {
                    "state": new_state,
                    "known_state": True,
                    "interval_band": _duration_band(self.next_interval),
                },
            )
        else:
            self._record_thinking(
                "adaptive_monitoring_interval_unchanged",
                "Keep monitoring interval for unknown state",
                {
                    "state_hash": _safe_hash(new_state),
                    "known_state": False,
                    "current_state": self.current_state,
                    "interval_band": _duration_band(self.next_interval),
                },
            )

        return self.next_interval

    def get_interval(self) -> float:
        """Get current monitoring interval"""
        return self.next_interval

    def get_statistics(self) -> dict[str, Any]:
        """Get monitoring interval statistics"""
        stats = {
            "current_state": self.current_state,
            "current_interval": self.next_interval,
            "configured_intervals": self.intervals,
        }
        self._record_thinking(
            "adaptive_monitoring_interval_stats",
            "Collect adaptive monitoring interval statistics",
            {
                "current_state": self.current_state,
                "current_interval_band": _duration_band(self.next_interval),
                "interval_count": len(self.intervals),
            },
        )
        return stats


def calculate_mttr_improvement(
    baseline_mttr: float, optimized_mttr: float
) -> dict[str, float]:
    """
    Calculate MTTR improvement metrics.
    """
    time_saved = baseline_mttr - optimized_mttr
    percent_improvement = (time_saved / baseline_mttr * 100) if baseline_mttr > 0 else 0

    return {
        "time_saved_seconds": time_saved,
        "percent_improvement": percent_improvement,
        "speedup_factor": baseline_mttr / optimized_mttr if optimized_mttr > 0 else 0,
    }

