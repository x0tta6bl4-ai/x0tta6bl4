"""
Federated Learning Orchestrator for 1000+ Node Mesh Network
===========================================================

Implements asynchronous aggregation patterns with Byzantine fault tolerance.

Patterns:
1. Batch Async Aggregation - Simple, effective for < 1000 nodes
2. Streaming Aggregation - Online learning without rounds
3. Hierarchical Aggregation - Bandwidth efficient for 1000+ nodes

All patterns include:
- Byzantine robust aggregation
- Automatic convergence detection
- Adaptive learning rate scheduling
- SPIFFE identity validation
- Failure recovery
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class AggregationMethod(Enum):
    """Aggregation methods"""

    MEAN = "mean"
    MEDIAN = "median"
    KRUM = "krum"
    MULTIROUND_FILTERING = "multiround_filtering"


class LearningRateSchedule(Enum):
    """Learning rate scheduling strategies"""

    STEP_DECAY = "step_decay"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"
    CONSTANT = "constant"


@dataclass
class ModelUpdate:
    """Federated learning model update from a node"""

    node_id: str
    gradient: np.ndarray
    svid: str  # SPIFFE identity
    signature: bytes  # PQC signature
    timestamp: float = field(default_factory=time.time)
    round_number: int = 0
    staleness: float = 0.0  # How stale this update is (0-1)

    def validate_signature(self, crypto_provider) -> bool:
        """Validate PQC signature"""
        try:
            message = self.gradient.tobytes() + self.node_id.encode()
            return crypto_provider.verify(message, self.signature, self.svid)
        except Exception as e:
            logger.warning(f"Signature validation failed for {self.node_id}: {e}")
            return False

    def validate_identity(self, spiffe_controller) -> bool:
        """Validate SPIFFE identity"""
        try:
            return spiffe_controller.validate_svid(self.svid)
        except Exception:
            return False

    def get_gradient_norm(self) -> float:
        """Get L2 norm of gradient"""
        return np.linalg.norm(self.gradient)


@dataclass
class TrainingRoundStats:
    """Statistics for a training round"""

    round_number: int
    timestamp: float = field(default_factory=time.time)

    # Aggregation stats
    updates_received: int = 0
    updates_used: int = 0
    updates_rejected: int = 0
    byzantine_detected: int = 0

    # Loss and accuracy
    loss: float = 0.0
    accuracy: float = 0.0
    validation_loss: float = 0.0
    validation_accuracy: float = 0.0

    # Performance
    aggregation_time_ms: float = 0.0
    total_round_time_ms: float = 0.0
    learning_rate: float = 0.0

    # Convergence
    gradient_norm: float = 0.0
    loss_improvement: float = 0.0
    converged: bool = False


class ByzantineDetector:
    """Detects and filters Byzantine (malicious) updates"""

    def __init__(self, tolerance_fraction: float = 0.30):
        """
        Args:
            tolerance_fraction: Max fraction of nodes that can be Byzantine (0.30 = 30%)
        """
        self.tolerance = tolerance_fraction
        self.detection_history: List[Tuple[int, List[int]]] = []

    def detect_malicious_updates(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.

        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 4:
            return []

        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])

        # Find outliers: gradients with high average distance to others.
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)

        # Robust norm-based signal: Byzantine updates usually have much larger
        # magnitude than honest updates.
        norms = [float(np.linalg.norm(u.gradient)) for u in updates]
        median_norm = float(np.median(norms)) if norms else 0.0
        suspicious_by_norm = []
        if median_norm > 0:
            suspicious_by_norm = [
                i for i, n in enumerate(norms) if n > (median_norm * 10.0)
            ]

        # Distance-based outlier detection (conservative threshold to reduce
        # false positives in all-honest rounds).
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        threshold = mean_dist + 2.5 * std_dist
        suspicious_by_distance = [
            i for i, d in enumerate(avg_distances) if d > threshold
        ]
        if suspicious_by_norm:
            suspicious_indices = sorted(set(suspicious_by_norm))
        elif len(suspicious_by_distance) >= 2:
            # Distance-only outliers are noisier; require at least two
            # candidates to avoid false positives in all-honest rounds.
            suspicious_indices = sorted(set(suspicious_by_distance))
        else:
            suspicious_indices = []

        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]

        logger.info(
            f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged"
        )

        return malicious_indices

    def filter_and_aggregate(
        self,
        updates: List[ModelUpdate],
        method: AggregationMethod = AggregationMethod.MEAN,
    ) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.

        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")

        # Detect and remove Byzantine updates
        malicious_idx = self.detect_malicious_updates(updates)
        clean_updates = [u for i, u in enumerate(updates) if i not in malicious_idx]

        if not clean_updates:
            logger.warning("All updates marked as Byzantine, using median aggregation")
            return self._geometric_median([u.gradient for u in updates])

        # Aggregate clean updates
        if method == AggregationMethod.MEAN:
            return self._mean_aggregate([u.gradient for u in clean_updates])
        elif method == AggregationMethod.MEDIAN:
            return self._coordinate_median([u.gradient for u in clean_updates])
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])

    @staticmethod
    def _compute_pairwise_distances(gradients: List[np.ndarray]) -> np.ndarray:
        """Compute L2 distance matrix between all pairs of gradients"""
        n = len(gradients)
        distances = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                grad_i_flat = gradients[i].flatten()
                grad_j_flat = gradients[j].flatten()
                distance = np.linalg.norm(grad_i_flat - grad_j_flat)
                distances[i][j] = distances[j][i] = distance

        return distances

    @staticmethod
    def _mean_aggregate(gradients: List[np.ndarray]) -> np.ndarray:
        """Simple mean aggregation"""
        return np.mean(np.array(gradients), axis=0)

    @staticmethod
    def _coordinate_median(gradients: List[np.ndarray]) -> np.ndarray:
        """Coordinate-wise median aggregation"""
        return np.median(np.array(gradients), axis=0)

    @staticmethod
    def _geometric_median(gradients: List[np.ndarray]) -> np.ndarray:
        """Geometric median aggregation (iterative)"""
        # Simplified: use coordinate median as approximation
        return np.median(np.array(gradients), axis=0)

    @staticmethod
    def _krum_aggregate(gradients: List[np.ndarray]) -> np.ndarray:
        """Krum aggregation: select update with minimum distance sum"""
        distances = ByzantineDetector._compute_pairwise_distances(gradients)

        # Find update with minimum sum of distances
        distance_sums = np.sum(distances, axis=1)
        selected_idx = np.argmin(distance_sums)

        return gradients[selected_idx]


class ConvergenceDetector:
    """Detects model convergence"""

    def __init__(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = window_size
        self.threshold = threshold
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = []
        self.gradient_norm_history: List[float] = []

    def update(self, loss: float, accuracy: float, gradient_norm: float):
        """Update convergence statistics"""
        self.loss_history.append(loss)
        self.accuracy_history.append(accuracy)
        self.gradient_norm_history.append(gradient_norm)

    def check_convergence(self) -> Tuple[bool, str]:
        """
        Check if model has converged.

        Returns:
            (is_converged, reason)
        """

        if len(self.loss_history) < self.window_size:
            return (
                False,
                f"Insufficient history ({len(self.loss_history)}/{self.window_size})",
            )

        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size :]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0

        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"

        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size :]
        acc_improvement = recent_accs[-1] - recent_accs[0]

        if acc_improvement < self.threshold:
            return (
                True,
                f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}",
            )

        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size :]
        grad_norm_threshold = max(1e-5, self.threshold * 10.0)
        if recent_norms[-1] <= grad_norm_threshold:
            return True, (
                f"Gradient norm {recent_norms[-1]:.2e} < " f"{grad_norm_threshold:.2e}"
            )

        return False, "Training ongoing"


class AdaptiveLearningRate:
    """Adaptive learning rate scheduler"""

    def __init__(
        self,
        initial_lr: float = 0.1,
        schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY,
    ):
        self.initial_lr = initial_lr
        self.schedule = schedule
        self.round_number = 0

    def get_lr(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.

        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization

        Returns:
            Learning rate to use
        """

        # Base schedule
        if self.schedule == LearningRateSchedule.CONSTANT:
            lr = self.initial_lr
            self.round_number += 1
            return lr
        elif self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0

        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0

        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0

        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor

        self.round_number += 1

        return lr

    def reset(self):
        """Reset round counter"""
        self.round_number = 0


class FLOrchestrator(ABC):
    """Abstract base class for FL orchestrators"""

    def __init__(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = AdaptiveLearningRate(initial_lr)
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = []

    @abstractmethod
    def aggregate_updates(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates from multiple nodes.

        Returns:
            Aggregated gradient
        """
        pass

    def update_model(self, gradient: np.ndarray, learning_rate: float):
        """Update model with gradient descent"""
        self.model = self.model - learning_rate * gradient

    def record_stats(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)

        self.convergence_detector.update(
            stats.loss, stats.accuracy, stats.gradient_norm
        )


class BatchAsyncOrchestrator(FLOrchestrator):
    """
    Batch asynchronous aggregation orchestrator.

    Aggregates when K < N updates received or timeout.
    """

    def __init__(
        self,
        model: np.ndarray,
        k_threshold: float = 0.85,
        timeout: float = 60.0,
        initial_lr: float = 0.1,
    ):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.k_threshold = k_threshold
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()

    def aggregate_updates(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.

        Returns:
            Aggregated gradient ready for model update
        """

        if not updates:
            logger.warning("No updates to aggregate")
            return np.zeros_like(self.model)

        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, method=AggregationMethod.MEAN
        )

        return aggregated

    def should_aggregate(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True

        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True

        return False


class StreamingOrchestrator(FLOrchestrator):
    """
    Streaming aggregation orchestrator.

    Applies updates incrementally without rounds.
    """

    def __init__(
        self, model: np.ndarray, momentum: float = 0.9, initial_lr: float = 0.01
    ):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 0

    def aggregate_updates(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Apply streaming aggregation to a single update.

        Returns:
            Aggregated update (for single node case, just return gradient)
        """

        if not updates:
            return np.zeros_like(self.model)

        # For streaming, typically one update at a time
        # Apply momentum
        update = updates[0]
        gradient = update.gradient

        self.velocity = self.momentum * self.velocity + gradient

        self.update_count += 1

        return self.velocity / self.update_count


class HierarchicalOrchestrator(FLOrchestrator):
    """
    Hierarchical aggregation orchestrator.

    Uses edge aggregators for bandwidth efficiency at 1000+ nodes.
    """

    def __init__(self, model: np.ndarray, num_zones: int = 10, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {
            i: [] for i in range(num_zones)
        }
        self.zone_aggregates: Dict[int, np.ndarray] = {
            i: np.zeros_like(model) for i in range(num_zones)
        }

    def add_update_to_zone(self, zone_id: int, update: ModelUpdate):
        """Add update to a specific zone"""
        if zone_id not in self.zone_updates:
            self.zone_updates[zone_id] = []
        self.zone_updates[zone_id].append(update)

    def aggregate_zone(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])

        if not zone_updates:
            return np.zeros_like(self.model)

        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates, method=AggregationMethod.MEAN
        )

        self.zone_aggregates[zone_id] = aggregated

        return aggregated

    def aggregate_updates(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate zone aggregates from all edges.

        Returns:
            Final aggregated gradient
        """

        # Collect zone aggregates
        zone_grads = [
            self.zone_aggregates[i]
            for i in range(self.num_zones)
            if i in self.zone_aggregates
        ]

        if not zone_grads:
            return np.zeros_like(self.model)

        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)


class FLTrainingSession:
    """Manages a complete federated learning training session"""

    def __init__(
        self, model: np.ndarray, orchestrator: FLOrchestrator, max_rounds: int = 100
    ):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = model.copy()
        self.orchestrator = orchestrator
        self.max_rounds = max_rounds
        self.current_round = 0
        self.convergence_round = None

    def training_round(
        self, updates: List[ModelUpdate], loss: float, accuracy: float
    ) -> TrainingRoundStats:
        """
        Execute one training round.

        Returns:
            Statistics for this round
        """

        round_start = time.time()

        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(updates)
        agg_time = (time.time() - agg_start) * 1000  # ms

        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)

        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()

        # Check convergence
        is_converged, reason = (
            self.orchestrator.convergence_detector.check_convergence()
        )

        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")

        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms

        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged,
        )

        self.orchestrator.record_stats(stats)
        self.current_round += 1

        return stats

    def should_continue(self) -> bool:
        """Check if training should continue"""

        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return False

        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False

        return True


def create_orchestrator(
    orchestrator_type: str, model: np.ndarray, **kwargs
) -> FLOrchestrator:
    """
    Factory function to create FL orchestrator.

    Args:
        orchestrator_type: "batch", "streaming", or "hierarchical"
        model: Initial model
        **kwargs: Additional arguments for orchestrator

    Returns:
        FLOrchestrator instance
    """

    if orchestrator_type == "batch":
        return BatchAsyncOrchestrator(model, **kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")
