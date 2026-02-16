"""
MAPE-K Feedback Loops

Implements closed-loop feedback between self-learning optimizer,
dynamic optimizer, and the main MAPE-K cycle.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackLoopType(Enum):
    """Types of feedback loops"""

    METRICS_LEARNING = "metrics_learning"  # Metrics → Learning → Thresholds
    PERFORMANCE_ADAPTATION = (
        "performance_adaptation"  # Performance → Optimization → Params
    )
    DECISION_QUALITY = "decision_quality"  # Decision outcome → Quality → Strategy
    ANOMALY_FEEDBACK = (
        "anomaly_feedback"  # Anomalies → Detection accuracy → Sensitivity
    )
    RESOURCE_OPTIMIZATION = (
        "resource_optimization"  # Resources → Utilization → Allocation
    )


@dataclass
class FeedbackSignal:
    """Signal for feedback loops"""

    loop_type: FeedbackLoopType
    timestamp: float
    source: str  # Where signal came from
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopAction:
    """Action to take based on feedback"""

    parameter: str
    old_value: float
    new_value: float
    reason: str
    loop_type: FeedbackLoopType


class FeedbackLoopManager:
    """
    Manages all feedback loops in the system.
    """

    def __init__(self, self_learning_optimizer=None, dynamic_optimizer=None):
        self.self_learning = self_learning_optimizer
        self.dynamic_optimizer = dynamic_optimizer

        self.signal_history: deque = deque(maxlen=10000)
        self.action_history: deque = deque(maxlen=5000)

        self.loop_metrics: Dict[FeedbackLoopType, Dict[str, float]] = {
            loop_type: {
                "signals_processed": 0,
                "actions_taken": 0,
                "last_signal_time": 0,
                "effectiveness": 0.5,
            }
            for loop_type in FeedbackLoopType
        }

        self.callbacks: Dict[FeedbackLoopType, List[Callable]] = {
            loop_type: [] for loop_type in FeedbackLoopType
        }

    def register_callback(
        self, loop_type: FeedbackLoopType, callback: Callable[[FeedbackSignal], None]
    ):
        """Register callback for feedback loop"""
        self.callbacks[loop_type].append(callback)

    def signal_metrics_learning(
        self, parameter: str, threshold_value: float, confidence: float
    ) -> Optional[LoopAction]:
        """
        Process metrics learning signal.
        Learns optimal thresholds from metric observations.
        """
        signal = FeedbackSignal(
            loop_type=FeedbackLoopType.METRICS_LEARNING,
            timestamp=time.time(),
            source="metrics_observer",
            value=threshold_value,
            metadata={"confidence": confidence, "parameter": parameter},
        )

        self.signal_history.append(signal)
        self.loop_metrics[FeedbackLoopType.METRICS_LEARNING]["signals_processed"] += 1

        if self.self_learning:
            old_value = self.self_learning.get_recommendation(parameter)
            if old_value:
                old_value = old_value.recommended_value
            else:
                old_value = threshold_value

            action = LoopAction(
                parameter=parameter,
                old_value=old_value,
                new_value=threshold_value,
                reason=f"Learned from metrics (confidence: {confidence:.2f})",
                loop_type=FeedbackLoopType.METRICS_LEARNING,
            )

            self.action_history.append(action)
            self.loop_metrics[FeedbackLoopType.METRICS_LEARNING]["actions_taken"] += 1

            self._execute_callbacks(FeedbackLoopType.METRICS_LEARNING, signal)
            return action

        return None

    def signal_performance_degradation(
        self, cpu_usage: float, memory_usage: float, latency_ms: float
    ) -> Optional[LoopAction]:
        """
        Process performance degradation signal.
        Triggers dynamic optimization to handle degradation.
        """
        signal = FeedbackSignal(
            loop_type=FeedbackLoopType.PERFORMANCE_ADAPTATION,
            timestamp=time.time(),
            source="performance_monitor",
            value=max(cpu_usage, memory_usage),
            metadata={"cpu": cpu_usage, "memory": memory_usage, "latency": latency_ms},
        )

        self.signal_history.append(signal)
        self.loop_metrics[FeedbackLoopType.PERFORMANCE_ADAPTATION][
            "signals_processed"
        ] += 1

        if self.dynamic_optimizer:
            old_interval = self.dynamic_optimizer.current_parameters.monitoring_interval

            new_params = self.dynamic_optimizer.optimize()

            action = LoopAction(
                parameter="monitoring_interval",
                old_value=old_interval,
                new_value=new_params.monitoring_interval,
                reason=f"Performance degradation (CPU: {cpu_usage:.1f}%, "
                f"Memory: {memory_usage:.1f}%, Latency: {latency_ms:.1f}ms)",
                loop_type=FeedbackLoopType.PERFORMANCE_ADAPTATION,
            )

            self.action_history.append(action)
            self.loop_metrics[FeedbackLoopType.PERFORMANCE_ADAPTATION][
                "actions_taken"
            ] += 1

            self._execute_callbacks(FeedbackLoopType.PERFORMANCE_ADAPTATION, signal)
            return action

        return None

    def signal_decision_quality(
        self, decision_id: str, predicted_outcome: float, actual_outcome: float
    ) -> Optional[LoopAction]:
        """
        Process decision quality feedback.
        Measures how well our decisions match actual outcomes.
        """
        error = abs(predicted_outcome - actual_outcome)
        accuracy = 1.0 - (error / max(abs(actual_outcome), 1.0))

        signal = FeedbackSignal(
            loop_type=FeedbackLoopType.DECISION_QUALITY,
            timestamp=time.time(),
            source="decision_evaluator",
            value=accuracy,
            metadata={
                "decision_id": decision_id,
                "predicted": predicted_outcome,
                "actual": actual_outcome,
                "error": error,
            },
        )

        self.signal_history.append(signal)
        self.loop_metrics[FeedbackLoopType.DECISION_QUALITY]["signals_processed"] += 1

        # Update decision quality metrics
        if self.dynamic_optimizer:
            old_rate = self.dynamic_optimizer.current_parameters.learning_rate

            if accuracy < 0.5:
                new_rate = old_rate * 1.2  # Increase learning
            elif accuracy > 0.9:
                new_rate = old_rate * 0.9  # Decrease learning (stable)
            else:
                new_rate = old_rate

            new_rate = min(1.0, max(0.05, new_rate))

            action = LoopAction(
                parameter="learning_rate",
                old_value=old_rate,
                new_value=new_rate,
                reason=f"Decision quality feedback (accuracy: {accuracy:.2f})",
                loop_type=FeedbackLoopType.DECISION_QUALITY,
            )

            if new_rate != old_rate:
                self.action_history.append(action)
                self.loop_metrics[FeedbackLoopType.DECISION_QUALITY][
                    "actions_taken"
                ] += 1

            self._execute_callbacks(FeedbackLoopType.DECISION_QUALITY, signal)
            return action

        return None

    def signal_anomaly_detection(
        self, true_positive: bool, false_positive: bool, false_negative: bool
    ) -> Optional[LoopAction]:
        """
        Process anomaly detection feedback.
        Adjusts sensitivity based on detection accuracy.
        """
        signal = FeedbackSignal(
            loop_type=FeedbackLoopType.ANOMALY_FEEDBACK,
            timestamp=time.time(),
            source="anomaly_evaluator",
            value=1.0 if true_positive else 0.0,
            metadata={"tp": true_positive, "fp": false_positive, "fn": false_negative},
        )

        self.signal_history.append(signal)
        self.loop_metrics[FeedbackLoopType.ANOMALY_FEEDBACK]["signals_processed"] += 1

        if false_positive:
            # Too sensitive, reduce sensitivity
            adjustment = "reduce_sensitivity"
        elif false_negative:
            # Not sensitive enough, increase sensitivity
            adjustment = "increase_sensitivity"
        else:
            adjustment = "maintain"

        if adjustment != "maintain":
            action = LoopAction(
                parameter="anomaly_sensitivity",
                old_value=1.0,
                new_value=1.0,
                reason=f"Anomaly feedback: TP={true_positive}, FP={false_positive}, FN={false_negative}",
                loop_type=FeedbackLoopType.ANOMALY_FEEDBACK,
            )

            self.action_history.append(action)
            self.loop_metrics[FeedbackLoopType.ANOMALY_FEEDBACK]["actions_taken"] += 1

            self._execute_callbacks(FeedbackLoopType.ANOMALY_FEEDBACK, signal)
            return action

        return None

    def signal_resource_pressure(
        self, resource_type: str, utilization: float
    ) -> Optional[LoopAction]:
        """
        Process resource pressure signal.
        Adjusts resource allocation based on usage patterns.
        """
        signal = FeedbackSignal(
            loop_type=FeedbackLoopType.RESOURCE_OPTIMIZATION,
            timestamp=time.time(),
            source="resource_monitor",
            value=utilization,
            metadata={"resource": resource_type},
        )

        self.signal_history.append(signal)
        self.loop_metrics[FeedbackLoopType.RESOURCE_OPTIMIZATION][
            "signals_processed"
        ] += 1

        if self.dynamic_optimizer and utilization > 0.8:
            old_parallelism = (
                self.dynamic_optimizer.current_parameters.execution_parallelism
            )
            new_parallelism = max(1, old_parallelism - 1)

            action = LoopAction(
                parameter="execution_parallelism",
                old_value=old_parallelism,
                new_value=new_parallelism,
                reason=f"Resource pressure: {resource_type} utilization {utilization:.0%}",
                loop_type=FeedbackLoopType.RESOURCE_OPTIMIZATION,
            )

            self.action_history.append(action)
            self.loop_metrics[FeedbackLoopType.RESOURCE_OPTIMIZATION][
                "actions_taken"
            ] += 1

            self._execute_callbacks(FeedbackLoopType.RESOURCE_OPTIMIZATION, signal)
            return action

        return None

    def _execute_callbacks(self, loop_type: FeedbackLoopType, signal: FeedbackSignal):
        """Execute registered callbacks for feedback loop"""
        for callback in self.callbacks[loop_type]:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Callback error in {loop_type.value}: {e}")

    def get_loop_metrics(self) -> Dict[str, Any]:
        """Get metrics for all feedback loops"""
        return {
            loop_type.value: metrics.copy()
            for loop_type, metrics in self.loop_metrics.items()
        }

    def get_signal_history(
        self, loop_type: Optional[FeedbackLoopType] = None, limit: int = 100
    ) -> List[FeedbackSignal]:
        """Get signal history"""
        history = list(self.signal_history)[-limit:]

        if loop_type:
            history = [s for s in history if s.loop_type == loop_type]

        return history

    def get_action_history(
        self, loop_type: Optional[FeedbackLoopType] = None, limit: int = 100
    ) -> List[LoopAction]:
        """Get action history"""
        history = list(self.action_history)[-limit:]

        if loop_type:
            history = [a for a in history if a.loop_type == loop_type]

        return history

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get overall feedback loop statistics"""
        total_signals = sum(m["signals_processed"] for m in self.loop_metrics.values())
        total_actions = sum(m["actions_taken"] for m in self.loop_metrics.values())

        return {
            "total_signals": total_signals,
            "total_actions": total_actions,
            "action_ratio": total_actions / max(1, total_signals),
            "loops": self.get_loop_metrics(),
            "active_callbacks": {
                lt.value: len(cbs) for lt, cbs in self.callbacks.items()
            },
        }
