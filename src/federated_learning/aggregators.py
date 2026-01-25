"""
Byzantine-Robust Aggregators for Federated Learning.

Implements multiple aggregation strategies:
- FedAvg: Standard weighted averaging
- Krum: Byzantine-robust selection
- Trimmed Mean: Removes outliers before averaging
- Median: Coordinate-wise median

Reference: "Byzantine-Robust Distributed Learning" (Blanchard et al., 2017)
"""
import time
import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .protocol import ModelUpdate, GlobalModel, ModelWeights, AggregationResult

logger = logging.getLogger(__name__)


class Aggregator(ABC):
    """Base class for FL aggregation strategies."""
    
    def __init__(self, name: str = "base"):
        self.name = name
        self._stats: Dict[str, Any] = {}
    
    @abstractmethod
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """
        Aggregate model updates into a new global model.
        
        Args:
            updates: List of local model updates
            previous_model: Previous global model (for versioning)
            
        Returns:
            AggregationResult with new global model
        """
        pass
    
    def _compute_pairwise_distances(
        self,
        vectors: List[List[float]]
    ) -> List[List[float]]:
        """Compute pairwise Euclidean distances between vectors."""
        n = len(vectors)
        distances = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                dist = self._euclidean_distance(vectors[i], vectors[j])
                distances[i][j] = dist
                distances[j][i] = dist
        
        return distances
    
    def _euclidean_distance(self, v1: List[float], v2: List[float]) -> float:
        """Compute Euclidean distance between two vectors."""
        if len(v1) != len(v2):
            raise ValueError("Vectors must have same length")
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))
    
    def _weighted_average(
        self,
        vectors: List[List[float]],
        weights: List[float]
    ) -> List[float]:
        """Compute weighted average of vectors."""
        if not vectors:
            return []
        
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1.0
        
        dim = len(vectors[0])
        result = [0.0] * dim
        
        for vec, w in zip(vectors, weights):
            norm_w = w / total_weight
            for i, v in enumerate(vec):
                result[i] += v * norm_w
        
        return result


class FedAvgAggregator(Aggregator):
    """
    Federated Averaging (FedAvg).
    
    Standard weighted averaging based on number of samples.
    Not Byzantine-robust but efficient.
    
    Reference: "Communication-Efficient Learning" (McMahan et al., 2017)
    """
    
    def __init__(self):
        super().__init__(name="fedavg")
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        start_time = time.time()
        
        if not updates:
            return AggregationResult(
                success=False,
                error_message="No updates to aggregate"
            )
        
        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            sample_counts = [max(1, u.num_samples) for u in updates]
            
            # Weighted average
            avg_vector = self._weighted_average(vectors, sample_counts)
            
            # Create new weights
            if updates[0].weights.layer_weights:
                # Reconstruct from layer info
                new_weights = ModelWeights()
                new_weights.layer_weights = updates[0].weights.layer_weights.copy()
                new_weights.layer_biases = updates[0].weights.layer_biases.copy()
                
                # Update with averaged values
                idx = 0
                for layer_name in sorted(new_weights.layer_weights.keys()):
                    layer_size = len(new_weights.layer_weights[layer_name])
                    new_weights.layer_weights[layer_name] = avg_vector[idx:idx + layer_size]
                    idx += layer_size
                    
                    if layer_name in new_weights.layer_biases:
                        bias_size = len(new_weights.layer_biases[layer_name])
                        new_weights.layer_biases[layer_name] = avg_vector[idx:idx + bias_size]
                        idx += bias_size
            else:
                new_weights = ModelWeights(
                    layer_weights={"flat": avg_vector}
                )
            
            # Create global model
            version = (previous_model.version + 1) if previous_model else 1
            round_num = max(u.round_number for u in updates)
            
            global_model = GlobalModel(
                version=version,
                round_number=round_num,
                weights=new_weights,
                num_contributors=len(updates),
                total_samples=sum(sample_counts),
                aggregation_method=self.name,
                avg_training_loss=sum(u.training_loss for u in updates) / len(updates),
                avg_validation_loss=sum(u.validation_loss for u in updates) / len(updates),
                previous_hash=previous_model.weights_hash if previous_model else ""
            )
            
            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=len(updates),
                updates_accepted=len(updates),
                aggregation_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"FedAvg aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time
            )


class KrumAggregator(Aggregator):
    """
    Krum Byzantine-Robust Aggregator.
    
    Selects the update that is closest to its k nearest neighbors.
    Tolerates up to f < (n-2)/2 Byzantine nodes.
    
    Reference: "Machine Learning with Adversaries" (Blanchard et al., 2017)
    
    Args:
        f: Number of Byzantine nodes to tolerate
        multi_krum: If True, returns average of m best updates (Multi-Krum)
    """
    
    def __init__(self, f: int = 1, multi_krum: bool = False, m: int = 1):
        super().__init__(name="krum")
        self.f = f
        self.multi_krum = multi_krum
        self.m = m  # Number of updates to select in Multi-Krum
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        start_time = time.time()
        n = len(updates)
        
        # Validate Byzantine assumption
        # Krum requires n >= 2f + 3
        min_required = 2 * self.f + 3
        if n < min_required:
            return AggregationResult(
                success=False,
                error_message=f"Krum requires at least {min_required} updates, got {n}"
            )
        
        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            
            # Compute pairwise distances
            distances = self._compute_pairwise_distances(vectors)
            
            # Compute Krum scores
            # For each vector, sum of distances to n - f - 2 closest vectors
            k = n - self.f - 2
            scores = []
            
            for i in range(n):
                # Get distances to all other vectors
                dists = [(distances[i][j], j) for j in range(n) if i != j]
                dists.sort()
                
                # Sum of k smallest distances
                score = sum(d[0] for d in dists[:k])
                scores.append((score, i))
            
            # Sort by score (lower is better)
            scores.sort()
            
            # Identify suspected Byzantine nodes (worst scores)
            suspected = [updates[scores[-(i+1)][1]].node_id for i in range(self.f)]
            
            if self.multi_krum:
                # Multi-Krum: average the m best updates
                selected_indices = [scores[i][1] for i in range(min(self.m, n - self.f))]
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
            
            # Reconstruct weights
            if updates[0].weights.layer_weights:
                new_weights = ModelWeights()
                new_weights.layer_weights = updates[0].weights.layer_weights.copy()
                new_weights.layer_biases = updates[0].weights.layer_biases.copy()
                
                idx = 0
                for layer_name in sorted(new_weights.layer_weights.keys()):
                    layer_size = len(new_weights.layer_weights[layer_name])
                    new_weights.layer_weights[layer_name] = avg_vector[idx:idx + layer_size]
                    idx += layer_size
                    
                    if layer_name in new_weights.layer_biases:
                        bias_size = len(new_weights.layer_biases[layer_name])
                        new_weights.layer_biases[layer_name] = avg_vector[idx:idx + bias_size]
                        idx += bias_size
            else:
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
                aggregation_method=f"krum_f{self.f}",
                avg_training_loss=sum(u.training_loss for u in updates) / n,
                avg_validation_loss=sum(u.validation_loss for u in updates) / n,
                previous_hash=previous_model.weights_hash if previous_model else ""
            )
            
            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=n,
                updates_accepted=accepted_count,
                updates_rejected=n - accepted_count,
                suspected_byzantine=suspected,
                aggregation_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Krum aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time
            )


class TrimmedMeanAggregator(Aggregator):
    """
    Trimmed Mean Aggregator.
    
    Removes the top and bottom β fraction of values for each coordinate,
    then computes the mean of the remaining values.
    
    Args:
        beta: Fraction of values to trim (0 < beta < 0.5)
    """
    
    def __init__(self, beta: float = 0.1):
        super().__init__(name="trimmed_mean")
        self.beta = min(max(beta, 0.0), 0.49)  # Clamp to valid range
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        start_time = time.time()
        n = len(updates)
        
        if n < 3:
            return AggregationResult(
                success=False,
                error_message="Trimmed mean requires at least 3 updates"
            )
        
        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            dim = len(vectors[0])
            
            # Number of values to trim from each end
            trim_count = int(n * self.beta)
            
            # Coordinate-wise trimmed mean
            result = []
            for d in range(dim):
                values = sorted([v[d] for v in vectors])
                # Trim and average
                trimmed = values[trim_count:n - trim_count] if trim_count > 0 else values
                result.append(sum(trimmed) / len(trimmed))
            
            # Reconstruct weights
            if updates[0].weights.layer_weights:
                new_weights = ModelWeights()
                new_weights.layer_weights = updates[0].weights.layer_weights.copy()
                new_weights.layer_biases = updates[0].weights.layer_biases.copy()
                
                idx = 0
                for layer_name in sorted(new_weights.layer_weights.keys()):
                    layer_size = len(new_weights.layer_weights[layer_name])
                    new_weights.layer_weights[layer_name] = result[idx:idx + layer_size]
                    idx += layer_size
                    
                    if layer_name in new_weights.layer_biases:
                        bias_size = len(new_weights.layer_biases[layer_name])
                        new_weights.layer_biases[layer_name] = result[idx:idx + bias_size]
                        idx += bias_size
            else:
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
                aggregation_method=f"trimmed_mean_b{self.beta}",
                avg_training_loss=sum(u.training_loss for u in updates) / n,
                avg_validation_loss=sum(u.validation_loss for u in updates) / n,
                previous_hash=previous_model.weights_hash if previous_model else ""
            )
            
            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=n,
                updates_accepted=n - 2 * trim_count,
                updates_rejected=2 * trim_count,
                aggregation_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Trimmed mean aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time
            )


class MedianAggregator(Aggregator):
    """
    Coordinate-wise Median Aggregator.
    
    Computes the median for each coordinate independently.
    Simple and robust but may not converge as fast as Krum.
    """
    
    def __init__(self):
        super().__init__(name="median")
    
    def _median(self, values: List[float]) -> float:
        """Compute median of a list of values."""
        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2
        
        if n % 2 == 0:
            return (sorted_values[mid - 1] + sorted_values[mid]) / 2
        else:
            return sorted_values[mid]
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        start_time = time.time()
        n = len(updates)
        
        if n == 0:
            return AggregationResult(
                success=False,
                error_message="No updates to aggregate"
            )
        
        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            dim = len(vectors[0])
            
            # Coordinate-wise median
            result = []
            for d in range(dim):
                values = [v[d] for v in vectors]
                result.append(self._median(values))
            
            # Reconstruct weights
            if updates[0].weights.layer_weights:
                new_weights = ModelWeights()
                new_weights.layer_weights = updates[0].weights.layer_weights.copy()
                new_weights.layer_biases = updates[0].weights.layer_biases.copy()
                
                idx = 0
                for layer_name in sorted(new_weights.layer_weights.keys()):
                    layer_size = len(new_weights.layer_weights[layer_name])
                    new_weights.layer_weights[layer_name] = result[idx:idx + layer_size]
                    idx += layer_size
                    
                    if layer_name in new_weights.layer_biases:
                        bias_size = len(new_weights.layer_biases[layer_name])
                        new_weights.layer_biases[layer_name] = result[idx:idx + bias_size]
                        idx += bias_size
            else:
                new_weights = ModelWeights(layer_weights={"flat": result})
            
            # Create global model
            version = (previous_model.version + 1) if previous_model else 1
            round_num = max(u.round_number for u in updates)
            
            global_model = GlobalModel(
                version=version,
                round_number=round_num,
                weights=new_weights,
                num_contributors=n,
                total_samples=sum(u.num_samples for u in updates),
                aggregation_method=self.name,
                avg_training_loss=sum(u.training_loss for u in updates) / n,
                avg_validation_loss=sum(u.validation_loss for u in updates) / n,
                previous_hash=previous_model.weights_hash if previous_model else ""
            )
            
            return AggregationResult(
                success=True,
                global_model=global_model,
                updates_received=n,
                updates_accepted=n,
                aggregation_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Median aggregation failed: {e}")
            return AggregationResult(
                success=False,
                error_message=str(e),
                aggregation_time_seconds=time.time() - start_time
            )


def get_aggregator(
    method: str = "fedavg",
    **kwargs
) -> Aggregator:
    """
    Factory function to get aggregator by name.
    
    Args:
        method: Aggregation method name
        **kwargs: Additional arguments for specific aggregators
        
    Returns:
        Aggregator instance
    """
    aggregators = {
        "fedavg": FedAvgAggregator,
        "krum": KrumAggregator,
        "trimmed_mean": TrimmedMeanAggregator,
        "median": MedianAggregator
    }
    
    if method not in aggregators:
        raise ValueError(f"Unknown aggregator: {method}. Available: {list(aggregators.keys())}")
    
    return aggregators[method](**kwargs)
