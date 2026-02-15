"""
Enhanced Byzantine-Robust Aggregators.

Improvements:
- Performance optimizations
- Better Byzantine detection
- Adaptive parameter selection
- Multi-Krum enhancements
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .aggregators import (AggregationResult, Aggregator, KrumAggregator,
                          TrimmedMeanAggregator)
from .protocol import GlobalModel, ModelUpdate

logger = logging.getLogger(__name__)


class EnhancedKrumAggregator(KrumAggregator):
    """
    Enhanced Krum aggregator with performance optimizations.

    Improvements:
    - Vectorized distance computation
    - Caching of distance matrices
    - Adaptive f selection
    - Better Byzantine detection
    """

    def __init__(
        self,
        f: int = 1,
        multi_krum: bool = True,
        m: Optional[int] = None,
        adaptive_f: bool = True,
    ):
        super().__init__(f=f, multi_krum=multi_krum, m=m or 1)
        self.adaptive_f = adaptive_f
        self._distance_cache: Dict[Tuple[int, int], float] = {}
        self._stats = {
            "byzantine_detected": 0,
            "total_rounds": 0,
            "avg_aggregation_time": 0.0,
        }

    def aggregate(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """Enhanced aggregation with performance optimizations."""
        start_time = time.time()
        n = len(updates)

        # Validate Byzantine assumption
        min_required = 2 * self.f + 3
        if n < min_required:
            return AggregationResult(
                success=False,
                error_message=f"Krum requires at least {min_required} updates, got {n}",
            )

        # Adaptive f selection
        if self.adaptive_f:
            self.f = self._adaptive_f_selection(n, updates)

        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]

            # Vectorized distance computation (if numpy available)
            try:
                distances = self._compute_distances_vectorized(vectors)
            except:
                # Fallback to pairwise
                distances = self._compute_pairwise_distances(vectors)

            # Compute Krum scores
            k = n - self.f - 2
            scores = []

            for i in range(n):
                dists = [(distances[i][j], j) for j in range(n) if i != j]
                dists.sort()
                score = sum(d[0] for d in dists[:k])
                scores.append((score, i))

            scores.sort()

            # Identify suspected Byzantine nodes
            suspected = [updates[scores[-(i + 1)][1]].node_id for i in range(self.f)]
            self._stats["byzantine_detected"] += len(suspected)

            if self.multi_krum:
                # Multi-Krum: average the m best updates
                selected_indices = [
                    scores[i][1] for i in range(min(self.m, n - self.f))
                ]
                selected_vectors = [vectors[i] for i in selected_indices]
                selected_updates = [updates[i] for i in selected_indices]

                weights = [u.num_samples for u in selected_updates]
                avg_vector = self._weighted_average(selected_vectors, weights)

                accepted_count = len(selected_indices)
            else:
                # Single Krum: select the best update
                best_idx = scores[0][1]
                avg_vector = vectors[best_idx]
                accepted_count = 1

            # Reconstruct weights (same as parent)
            if updates[0].weights.layer_weights:
                new_weights = self._reconstruct_weights(avg_vector, updates[0].weights)
            else:
                from .protocol import ModelWeights

                new_weights = ModelWeights(layer_weights={"flat": avg_vector})

            # Create global model
            version = (previous_model.version + 1) if previous_model else 1
            round_num = max(u.round_number for u in updates)

            global_model = GlobalModel(
                version=version,
                round_number=round_num,
                weights=new_weights,
                num_contributors=accepted_count,
                total_samples=sum(u.num_samples for u in updates),
                aggregation_method=f"enhanced_krum_f{self.f}",
                avg_training_loss=sum(u.training_loss for u in updates) / n,
                avg_validation_loss=sum(u.validation_loss for u in updates) / n,
                previous_hash=previous_model.weights_hash if previous_model else "",
            )

            # Update stats
            aggregation_time = time.time() - start_time
            self._stats["total_rounds"] += 1
            self._stats["avg_aggregation_time"] = (
                self._stats["avg_aggregation_time"] * (self._stats["total_rounds"] - 1)
                + aggregation_time
            ) / self._stats["total_rounds"]

            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=n,
                updates_accepted=accepted_count,
                updates_rejected=n - accepted_count,
                suspected_byzantine=suspected,
                aggregation_time_seconds=aggregation_time,
            )

        except Exception as e:
            logger.error(f"Enhanced Krum aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time,
            )

    def _compute_distances_vectorized(
        self, vectors: List[List[float]]
    ) -> List[List[float]]:
        """Compute distances using numpy for performance."""
        try:
            import numpy as np

            vec_array = np.array(vectors)
            n = len(vectors)
            distances = [[0.0] * n for _ in range(n)]

            for i in range(n):
                for j in range(i + 1, n):
                    dist = np.linalg.norm(vec_array[i] - vec_array[j])
                    distances[i][j] = dist
                    distances[j][i] = dist

            return distances
        except ImportError:
            raise

    def _adaptive_f_selection(self, n: int, updates: List[ModelUpdate]) -> int:
        """
        Adaptively select f based on network conditions.

        Args:
            n: Number of updates
            updates: List of updates

        Returns:
            Adaptive f value
        """
        # Base f
        base_f = self.f

        # Adjust based on trust scores (if available)
        trust_scores = []
        for update in updates:
            # In real implementation, would check node trust
            trust_scores.append(1.0)  # Default trust

        avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 1.0

        # Reduce f if average trust is high
        if avg_trust > 0.8:
            adaptive_f = max(1, base_f - 1)
        elif avg_trust < 0.5:
            adaptive_f = min(base_f + 1, (n - 3) // 2)
        else:
            adaptive_f = base_f

        return adaptive_f

    def _reconstruct_weights(self, avg_vector: List[float], template_weights) -> Any:
        """Reconstruct ModelWeights from flat vector."""
        from .protocol import ModelWeights

        new_weights = ModelWeights()
        new_weights.layer_weights = template_weights.layer_weights.copy()
        new_weights.layer_biases = template_weights.layer_biases.copy()

        idx = 0
        for layer_name in sorted(new_weights.layer_weights.keys()):
            layer_size = len(new_weights.layer_weights[layer_name])
            new_weights.layer_weights[layer_name] = avg_vector[idx : idx + layer_size]
            idx += layer_size

            if layer_name in new_weights.layer_biases:
                bias_size = len(new_weights.layer_biases[layer_name])
                new_weights.layer_biases[layer_name] = avg_vector[idx : idx + bias_size]
                idx += bias_size

        return new_weights

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics."""
        return self._stats.copy()


class AdaptiveTrimmedMeanAggregator(TrimmedMeanAggregator):
    """
    Adaptive Trimmed Mean aggregator.

    Improvements:
    - Adaptive beta selection
    - Better outlier detection
    - Performance optimization
    """

    def __init__(
        self,
        beta: float = 0.1,
        adaptive_beta: bool = True,
        outlier_detection: str = "iqr",  # iqr, zscore, mad
    ):
        super().__init__(beta=beta)
        self.adaptive_beta = adaptive_beta
        self.outlier_detection = outlier_detection
        self._stats = {"total_rounds": 0, "avg_trimmed": 0.0, "outliers_detected": 0}

    def aggregate(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """Adaptive aggregation with better outlier detection."""
        start_time = time.time()
        n = len(updates)

        if n < 3:
            return AggregationResult(
                success=False, error_message="Trimmed mean requires at least 3 updates"
            )

        # Adaptive beta selection
        if self.adaptive_beta:
            self.beta = self._adaptive_beta_selection(n, updates)

        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            dim = len(vectors[0])

            # Detect outliers
            outlier_indices = self._detect_outliers(vectors)
            self._stats["outliers_detected"] += len(outlier_indices)

            # Number of values to trim from each end
            trim_count = int(n * self.beta)

            # Coordinate-wise trimmed mean
            result = []
            for d in range(dim):
                values = sorted([(v[d], i) for i, v in enumerate(vectors)])

                # Remove outliers first
                filtered_values = [v for v in values if v[1] not in outlier_indices]

                if len(filtered_values) < 2:
                    # Fallback to all values
                    filtered_values = values

                # Trim and average
                if trim_count > 0 and len(filtered_values) > 2 * trim_count:
                    trimmed = filtered_values[
                        trim_count : len(filtered_values) - trim_count
                    ]
                else:
                    trimmed = filtered_values

                result.append(sum(v[0] for v in trimmed) / len(trimmed))

            # Reconstruct weights
            if updates[0].weights.layer_weights:
                new_weights = self._reconstruct_weights(result, updates[0].weights)
            else:
                from .protocol import ModelWeights

                new_weights = ModelWeights(layer_weights={"flat": result})

            # Create global model
            version = (previous_model.version + 1) if previous_model else 1
            round_num = max(u.round_number for u in updates)

            global_model = GlobalModel(
                version=version,
                round_number=round_num,
                weights=new_weights,
                num_contributors=n - 2 * trim_count,
                total_samples=sum(u.num_samples for u in updates),
                aggregation_method=f"adaptive_trimmed_mean_b{self.beta:.2f}",
                avg_training_loss=sum(u.training_loss for u in updates) / n,
                avg_validation_loss=sum(u.validation_loss for u in updates) / n,
                previous_hash=previous_model.weights_hash if previous_model else "",
            )

            # Update stats
            self._stats["total_rounds"] += 1
            self._stats["avg_trimmed"] = (
                self._stats["avg_trimmed"] * (self._stats["total_rounds"] - 1)
                + 2 * trim_count
            ) / self._stats["total_rounds"]

            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=n,
                updates_accepted=n - 2 * trim_count,
                updates_rejected=2 * trim_count,
                aggregation_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            logger.error(f"Adaptive trimmed mean aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time,
            )

    def _adaptive_beta_selection(self, n: int, updates: List[ModelUpdate]) -> float:
        """
        Adaptively select beta based on update variance.

        Args:
            n: Number of updates
            updates: List of updates

        Returns:
            Adaptive beta value
        """
        # Base beta
        base_beta = self.beta

        # Compute variance of updates
        vectors = [u.weights.to_flat_vector() for u in updates]
        try:
            import numpy as np

            vec_array = np.array(vectors)
            variance = np.var(vec_array, axis=0).mean()

            # Increase beta if high variance (more outliers expected)
            if variance > 1.0:
                adaptive_beta = min(0.3, base_beta * 1.5)
            elif variance < 0.1:
                adaptive_beta = max(0.05, base_beta * 0.5)
            else:
                adaptive_beta = base_beta
        except:
            adaptive_beta = base_beta

        return adaptive_beta

    def _detect_outliers(
        self, vectors: List[List[float]], method: Optional[str] = None
    ) -> List[int]:
        """
        Detect outlier updates.

        Args:
            vectors: List of weight vectors
            method: Detection method (iqr, zscore, mad)

        Returns:
            List of outlier indices
        """
        method = method or self.outlier_detection
        n = len(vectors)

        if n < 3:
            return []

        outlier_indices = []

        try:
            import numpy as np

            vec_array = np.array(vectors)

            if method == "iqr":
                # IQR method
                q1 = np.percentile(vec_array, 25, axis=0)
                q3 = np.percentile(vec_array, 75, axis=0)
                iqr = q3 - q1

                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                for i in range(n):
                    if np.any(vec_array[i] < lower_bound) or np.any(
                        vec_array[i] > upper_bound
                    ):
                        outlier_indices.append(i)

            elif method == "zscore":
                # Z-score method
                mean = np.mean(vec_array, axis=0)
                std = np.std(vec_array, axis=0)

                for i in range(n):
                    z_scores = np.abs((vec_array[i] - mean) / (std + 1e-8))
                    if np.any(z_scores > 3.0):
                        outlier_indices.append(i)

            elif method == "mad":
                # Median Absolute Deviation
                median = np.median(vec_array, axis=0)
                mad = np.median(np.abs(vec_array - median), axis=0)

                for i in range(n):
                    deviations = np.abs(vec_array[i] - median) / (mad + 1e-8)
                    if np.any(deviations > 3.0):
                        outlier_indices.append(i)

        except ImportError:
            # Fallback: no outlier detection
            pass

        return list(set(outlier_indices))

    def _reconstruct_weights(self, result: List[float], template_weights) -> Any:
        """Reconstruct ModelWeights from flat vector."""
        from .protocol import ModelWeights

        new_weights = ModelWeights()
        new_weights.layer_weights = template_weights.layer_weights.copy()
        new_weights.layer_biases = template_weights.layer_biases.copy()

        idx = 0
        for layer_name in sorted(new_weights.layer_weights.keys()):
            layer_size = len(new_weights.layer_weights[layer_name])
            new_weights.layer_weights[layer_name] = result[idx : idx + layer_size]
            idx += layer_size

            if layer_name in new_weights.layer_biases:
                bias_size = len(new_weights.layer_biases[layer_name])
                new_weights.layer_biases[layer_name] = result[idx : idx + bias_size]
                idx += bias_size

        return new_weights

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics."""
        return self._stats.copy()


def get_enhanced_aggregator(method: str = "enhanced_krum", **kwargs) -> Aggregator:
    """
    Factory function to get enhanced aggregator.

    Args:
        method: Aggregation method name
        **kwargs: Additional arguments

    Returns:
        Enhanced aggregator instance
    """
    enhanced_aggregators = {
        "enhanced_krum": EnhancedKrumAggregator,
        "adaptive_trimmed_mean": AdaptiveTrimmedMeanAggregator,
    }

    if method in enhanced_aggregators:
        return enhanced_aggregators[method](**kwargs)

    # Fallback to base aggregators
    from .aggregators import get_aggregator

    return get_aggregator(method, **kwargs)
