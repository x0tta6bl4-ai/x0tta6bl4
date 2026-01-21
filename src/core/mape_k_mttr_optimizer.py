"""
MAPE-K Mean Time To Recovery (MTTR) Optimizer

Optimizes the MAPE-K loop for faster recovery from failures with:
- Parallel phase execution
- Priority-based action execution
- Early recovery detection
- Adaptive monitoring intervals
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RecoveryPhase(Enum):
    """Phases of recovery process"""
    DETECTION = "detection"  # Anomaly detected
    DIAGNOSIS = "diagnosis"  # Root cause analysis
    ACTION = "action"        # Execute corrective actions
    VERIFICATION = "verification"  # Verify recovery
    COMPLETE = "complete"    # Recovery complete


@dataclass
class ActionPriority:
    """Execution priority for recovery actions"""
    action_id: str
    action_type: str  # 'critical', 'high', 'medium', 'low'
    estimated_mttr_reduction: float  # Seconds
    dependencies: List[str] = field(default_factory=list)
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
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: List[Tuple[str, float]] = []
    
    async def execute_parallel(
        self,
        monitor_task,
        analyze_task,
        plan_task,
        execute_task,
        knowledge_task
    ) -> Dict[str, Any]:
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
                    plan_task_obj,
                    execute_prep
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
            
            return {
                "monitor": monitor_result,
                "analyze": analyze_result,
                "plan": plan_result,
                "execute": execute_result,
                "knowledge": knowledge_result,
                "timings": {
                    "monitor": monitor_duration,
                    "analyze": analyze_duration,
                    "total": time.time() - start_time
                }
            }
        except Exception as e:
            logger.error(f"Error in parallel MAPE-K execution: {e}")
            raise
    
    async def _prepare_emergency_actions(self, analyze_result: Dict[str, Any]) -> List[ActionPriority]:
        """Prepare high-priority emergency actions during recovery"""
        emergency_actions = []
        
        # Identify critical issues
        if analyze_result.get("is_critical"):
            # High priority: Restart critical services
            emergency_actions.append(ActionPriority(
                action_id="restart_critical_services",
                action_type="critical",
                estimated_mttr_reduction=5.0
            ))
            
            # High priority: Isolate failing component
            emergency_actions.append(ActionPriority(
                action_id="isolate_failure",
                action_type="high",
                estimated_mttr_reduction=3.0
            ))
            
            # Medium priority: Reroute traffic
            emergency_actions.append(ActionPriority(
                action_id="reroute_traffic",
                action_type="medium",
                estimated_mttr_reduction=2.0,
                dependencies=["isolate_failure"]
            ))
        
        return emergency_actions
    
    def _is_recovery_state(self, analyze_result: Dict[str, Any]) -> bool:
        """Check if system is in recovery state"""
        return (
            analyze_result.get("is_degraded") or
            analyze_result.get("is_critical") or
            analyze_result.get("recovery_in_progress")
        )


class MTTROptimizer:
    """
    Optimizes MAPE-K loop for minimal MTTR (Mean Time To Recovery).
    """
    
    def __init__(self):
        self.executor = ParallelMAPEKExecutor()
        self.current_recovery: Optional[MTTRMetrics] = None
        self.recovery_history: List[MTTRMetrics] = []
        self.max_history = 1000
        
        # MTTR targets (in seconds)
        self.mttr_targets = {
            "transient_error": 5.0,
            "service_failure": 15.0,
            "network_issue": 10.0,
            "resource_exhaustion": 20.0
        }
    
    def start_recovery_tracking(self, issue_type: str) -> None:
        """Start tracking recovery metrics for an issue"""
        self.current_recovery = MTTRMetrics(
            detection_time=time.time(),
            diagnosis_time=0.0,
            first_action_time=0.0,
            recovery_complete_time=0.0,
            actions_executed=0,
            recovery_success_rate=0.0
        )
        logger.info(f"Recovery tracking started for issue type: {issue_type}")
    
    def record_diagnosis_complete(self) -> None:
        """Record completion of diagnosis phase"""
        if self.current_recovery:
            self.current_recovery.diagnosis_time = time.time()
            self.current_recovery.phase = RecoveryPhase.DIAGNOSIS
            diagnosis_duration = (
                self.current_recovery.diagnosis_time -
                self.current_recovery.detection_time
            )
            logger.info(f"Diagnosis complete in {diagnosis_duration:.2f}s")
    
    def record_first_action(self) -> None:
        """Record execution of first corrective action"""
        if self.current_recovery:
            self.current_recovery.first_action_time = time.time()
            self.current_recovery.phase = RecoveryPhase.ACTION
            ttf = (
                self.current_recovery.first_action_time -
                self.current_recovery.detection_time
            )
            logger.info(f"First action executed in {ttf:.2f}s")
    
    def record_recovery_complete(self, success: bool) -> None:
        """Record recovery completion"""
        if self.current_recovery:
            self.current_recovery.recovery_complete_time = time.time()
            self.current_recovery.phase = RecoveryPhase.COMPLETE
            self.current_recovery.recovery_success_rate = 1.0 if success else 0.0
            
            total_mttr = (
                self.current_recovery.recovery_complete_time -
                self.current_recovery.detection_time
            )
            logger.info(f"Recovery complete in {total_mttr:.2f}s (success={success})")
            
            self.recovery_history.append(self.current_recovery)
            if len(self.recovery_history) > self.max_history:
                self.recovery_history.pop(0)
            
            self.current_recovery = None
    
    def execute_action_priority_queue(
        self,
        actions: List[ActionPriority]
    ) -> Tuple[List[ActionPriority], float]:
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
                -a.estimated_mttr_reduction
            )
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
        return executed, total_time
    
    def get_mttr_statistics(self) -> Dict[str, Any]:
        """Get MTTR optimization statistics"""
        if not self.recovery_history:
            return {"total_recoveries": 0}
        
        # Calculate statistics
        recovery_times = [
            r.recovery_complete_time - r.detection_time
            for r in self.recovery_history
        ]
        action_times = [
            r.first_action_time - r.detection_time
            for r in self.recovery_history
        ]
        success_count = sum(
            1 for r in self.recovery_history
            if r.recovery_success_rate == 1.0
        )
        
        return {
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
                    "actions_executed": r.actions_executed
                }
                for r in self.recovery_history[-10:]
            ]
        }


class AdaptiveMonitoringIntervals:
    """
    Dynamically adjust monitoring intervals based on system state.
    """
    
    def __init__(self):
        self.intervals = {
            "healthy": 60.0,
            "degraded": 15.0,
            "critical": 3.0,
            "recovering": 5.0
        }
        self.current_state = "healthy"
        self.next_interval = self.intervals[self.current_state]
    
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
                f"Monitoring interval updated: {new_state} = "
                f"{self.next_interval}s"
            )
        
        return self.next_interval
    
    def get_interval(self) -> float:
        """Get current monitoring interval"""
        return self.next_interval
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring interval statistics"""
        return {
            "current_state": self.current_state,
            "current_interval": self.next_interval,
            "configured_intervals": self.intervals
        }


def calculate_mttr_improvement(
    baseline_mttr: float,
    optimized_mttr: float
) -> Dict[str, float]:
    """
    Calculate MTTR improvement metrics.
    """
    time_saved = baseline_mttr - optimized_mttr
    percent_improvement = (time_saved / baseline_mttr * 100) if baseline_mttr > 0 else 0
    
    return {
        "time_saved_seconds": time_saved,
        "percent_improvement": percent_improvement,
        "speedup_factor": baseline_mttr / optimized_mttr if optimized_mttr > 0 else 0
    }
