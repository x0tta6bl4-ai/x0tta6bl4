"""
Dynamic MAPE-K Parameter Optimization

Dynamically adjusts MAPE-K cycle parameters based on system state and performance.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """System operational state"""
    HEALTHY = "healthy"  # All metrics normal
    DEGRADED = "degraded"  # Some metrics elevated
    CRITICAL = "critical"  # Multiple issues
    RECOVERING = "recovering"  # Improving from bad state
    OPTIMIZING = "optimizing"  # Learning and improving


@dataclass
class DynamicParameters:
    """MAPE-K cycle parameters"""
    monitoring_interval: float  # Seconds between monitor cycles
    analysis_depth: int  # Number of historical points to analyze
    planning_lookahead: float  # Seconds to plan ahead
    execution_parallelism: int  # Number of parallel execution threads
    knowledge_retention: int  # Days to keep knowledge
    learning_rate: float  # How quickly to adapt (0-1)


@dataclass
class PerformanceMetrics:
    """Metrics for MAPE-K cycle performance"""
    cpu_usage: float
    memory_usage: float
    cycle_latency: float
    decisions_per_minute: float
    decision_quality: float  # 0-1
    anomaly_detection_accuracy: float  # 0-1
    false_positive_rate: float


class DynamicOptimizer:
    """
    Dynamically optimizes MAPE-K parameters based on system state.
    """

    def __init__(self):
        self.base_parameters = DynamicParameters(
            monitoring_interval=60.0,
            analysis_depth=100,
            planning_lookahead=300.0,
            execution_parallelism=4,
            knowledge_retention=7,
            learning_rate=0.1
        )

        self.current_parameters = self._copy_params(self.base_parameters)
        self.current_state = SystemState.HEALTHY

        self.performance_history: List[PerformanceMetrics] = []
        self.optimization_events: List[Dict[str, Any]] = []
        self.max_history = 1000

        self.state_transitions = 0
        self.optimization_count = 0

    @staticmethod
    def _copy_params(params: DynamicParameters) -> DynamicParameters:
        return DynamicParameters(
            monitoring_interval=params.monitoring_interval,
            analysis_depth=params.analysis_depth,
            planning_lookahead=params.planning_lookahead,
            execution_parallelism=params.execution_parallelism,
            knowledge_retention=params.knowledge_retention,
            learning_rate=params.learning_rate
        )

    def record_performance(self, metrics: PerformanceMetrics):
        """Record performance metrics"""
        self.performance_history.append(metrics)
        if len(self.performance_history) > self.max_history:
            self.performance_history.pop(0)

    def analyze_state(self) -> SystemState:
        """Determine current system state from performance metrics"""
        if not self.performance_history:
            return SystemState.HEALTHY

        recent = self.performance_history[-10:]

        avg_cpu = sum(m.cpu_usage for m in recent) / len(recent)
        avg_mem = sum(m.memory_usage for m in recent) / len(recent)
        avg_latency = sum(m.cycle_latency for m in recent) / len(recent)
        avg_quality = sum(m.decision_quality for m in recent) / len(recent)

        # State machine logic
        if avg_cpu > 80 or avg_mem > 85 or avg_latency > 5.0:
            return SystemState.CRITICAL
        elif avg_cpu > 60 or avg_mem > 70 or avg_latency > 2.0:
            if self.current_state in (SystemState.DEGRADED, SystemState.CRITICAL):
                return SystemState.DEGRADED
            elif avg_quality > 0.8:
                return SystemState.OPTIMIZING
            else:
                return SystemState.DEGRADED
        elif self.current_state == SystemState.CRITICAL:
            return SystemState.RECOVERING
        elif self.current_state == SystemState.RECOVERING and avg_quality > 0.85:
            return SystemState.HEALTHY
        else:
            return SystemState.HEALTHY

    def optimize(self, state: Optional[SystemState] = None) -> DynamicParameters:
        """Optimize parameters based on system state"""
        if state is None:
            state = self.analyze_state()

        if state != self.current_state:
            self.state_transitions += 1
            logger.info(f"State transition: {self.current_state.value} → {state.value}")
            self._record_transition(state)

        self.current_state = state
        self.optimization_count += 1

        # Apply state-specific optimizations
        if state == SystemState.HEALTHY:
            self._optimize_for_healthy()
        elif state == SystemState.OPTIMIZING:
            self._optimize_for_learning()
        elif state == SystemState.DEGRADED:
            self._optimize_for_degraded()
        elif state == SystemState.CRITICAL:
            self._optimize_for_critical()
        elif state == SystemState.RECOVERING:
            self._optimize_for_recovery()

        return self._copy_params(self.current_parameters)

    def _optimize_for_healthy(self):
        """Optimize for normal operation"""
        self.current_parameters.monitoring_interval = 60.0
        self.current_parameters.analysis_depth = 100
        self.current_parameters.planning_lookahead = 300.0
        self.current_parameters.execution_parallelism = 4
        self.current_parameters.learning_rate = 0.1

    def _optimize_for_learning(self):
        """Optimize for faster learning"""
        self.current_parameters.monitoring_interval = 30.0
        self.current_parameters.analysis_depth = 150
        self.current_parameters.planning_lookahead = 600.0
        self.current_parameters.execution_parallelism = 6
        self.current_parameters.learning_rate = 0.3

    def _optimize_for_degraded(self):
        """Optimize for handling degradation"""
        self.current_parameters.monitoring_interval = 30.0
        self.current_parameters.analysis_depth = 50
        self.current_parameters.planning_lookahead = 180.0
        self.current_parameters.execution_parallelism = 2
        self.current_parameters.learning_rate = 0.2

    def _optimize_for_critical(self):
        """Optimize for critical situation handling"""
        self.current_parameters.monitoring_interval = 10.0
        self.current_parameters.analysis_depth = 20
        self.current_parameters.planning_lookahead = 60.0
        self.current_parameters.execution_parallelism = 1
        self.current_parameters.learning_rate = 0.05

    def _optimize_for_recovery(self):
        """Optimize for recovery phase"""
        self.current_parameters.monitoring_interval = 20.0
        self.current_parameters.analysis_depth = 80
        self.current_parameters.planning_lookahead = 240.0
        self.current_parameters.execution_parallelism = 3
        self.current_parameters.learning_rate = 0.15

    def _record_transition(self, new_state: SystemState):
        """Record state transition event"""
        event = {
            'timestamp': time.time(),
            'from_state': self.current_state.value,
            'to_state': new_state.value,
            'parameters': {
                'monitoring_interval': self.current_parameters.monitoring_interval,
                'analysis_depth': self.current_parameters.analysis_depth,
                'execution_parallelism': self.current_parameters.execution_parallelism
            }
        }
        self.optimization_events.append(event)
        if len(self.optimization_events) > 500:
            self.optimization_events.pop(0)

    def get_current_parameters(self) -> DynamicParameters:
        """Get current parameters"""
        return self._copy_params(self.current_parameters)

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        return {
            'current_state': self.current_state.value,
            'total_state_transitions': self.state_transitions,
            'total_optimizations': self.optimization_count,
            'performance_history_size': len(self.performance_history),
            'optimization_events': len(self.optimization_events),
            'current_parameters': {
                'monitoring_interval': self.current_parameters.monitoring_interval,
                'analysis_depth': self.current_parameters.analysis_depth,
                'planning_lookahead': self.current_parameters.planning_lookahead,
                'execution_parallelism': self.current_parameters.execution_parallelism,
                'learning_rate': self.current_parameters.learning_rate
            }
        }

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get optimization event history"""
        return self.optimization_events.copy()
