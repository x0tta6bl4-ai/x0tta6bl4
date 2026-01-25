"""
Enhanced Federated Learning Aggregators

Improved aggregators with:
- Advanced metrics tracking
- Performance optimizations
- Adaptive aggregation strategies
- Better error handling
- Progress monitoring
"""

import time
import logging
import math
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from .aggregators import Aggregator, FedAvgAggregator, KrumAggregator, TrimmedMeanAggregator, MedianAggregator
from .protocol import ModelUpdate, GlobalModel, ModelWeights, AggregationResult

logger = logging.getLogger(__name__)

# Try to import numpy for optimizations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("⚠️ NumPy not available. Some optimizations disabled.")


@dataclass
class AggregationMetrics:
    """Enhanced metrics for aggregation"""
    aggregation_time_seconds: float = 0.0
    updates_received: int = 0
    updates_accepted: int = 0
    updates_rejected: int = 0
    total_parameters: int = 0
    memory_used_mb: float = 0.0
    convergence_score: float = 0.0
    weight_drift: float = 0.0
    byzantine_detected: int = 0
    quality_score: float = 0.0
    progress_percentage: float = 0.0


class EnhancedAggregator(Aggregator):
    """
    Enhanced base aggregator with metrics and optimizations.
    
    Extends base Aggregator with:
    - Performance metrics
    - Progress tracking
    - Memory optimization
    - Quality assessment
    """
    
    def __init__(self, name: str = "enhanced_base", enable_metrics: bool = True):
        super().__init__(name=name)
        self.enable_metrics = enable_metrics
        self.metrics_history: List[AggregationMetrics] = []
        self._last_aggregation_time = 0.0
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """
        Aggregate with enhanced metrics.
        
        Override in subclasses but call super() for metrics.
        """
        start_time = time.time()
        metrics = AggregationMetrics()
        metrics.updates_received = len(updates)
        
        # Track memory usage
        if self.enable_metrics:
            import sys
            initial_memory = sys.getsizeof(updates) / (1024 * 1024)  # MB
            metrics.memory_used_mb = initial_memory
        
        # Call base aggregation (to be implemented by subclasses)
        result = self._aggregate_impl(updates, previous_model, metrics)
        
        # Finalize metrics
        metrics.aggregation_time_seconds = time.time() - start_time
        metrics.updates_accepted = result.updates_accepted if result.success else 0
        metrics.updates_rejected = result.updates_rejected if hasattr(result, 'updates_rejected') else 0
        
        # Calculate quality score
        if result.success and result.global_model:
            metrics.quality_score = self._calculate_quality_score(
                updates, result.global_model, previous_model
            )
            metrics.convergence_score = self._calculate_convergence_score(
                updates, result.global_model, previous_model
            )
            if previous_model:
                metrics.weight_drift = self._calculate_weight_drift(
                    previous_model, result.global_model
                )
        
        # Store metrics
        if self.enable_metrics:
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > 100:  # Keep last 100
                self.metrics_history = self.metrics_history[-100:]
        
        # Add metrics to result
        if hasattr(result, 'metadata'):
            result.metadata = result.metadata or {}
            result.metadata['metrics'] = metrics.__dict__
        else:
            result.metadata = {'metrics': metrics.__dict__}
        
        return result
    
    def _aggregate_impl(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel],
        metrics: AggregationMetrics
    ) -> AggregationResult:
        """Implementation to be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement _aggregate_impl")
    
    def _calculate_quality_score(
        self,
        updates: List[ModelUpdate],
        global_model: GlobalModel,
        previous_model: Optional[GlobalModel]
    ) -> float:
        """
        Calculate quality score based on update consistency.
        
        Returns:
            Quality score (0.0-1.0)
        """
        if len(updates) < 2:
            return 1.0
        
        try:
            # Extract weight vectors
            vectors = [u.weights.to_flat_vector() for u in updates]
            
            # Calculate pairwise similarities
            similarities = []
            for i in range(len(vectors)):
                for j in range(i + 1, len(vectors)):
                    # Cosine similarity
                    v1, v2 = vectors[i], vectors[j]
                    dot = sum(a * b for a, b in zip(v1, v2))
                    norm1 = math.sqrt(sum(a * a for a in v1))
                    norm2 = math.sqrt(sum(b * b for b in v2))
                    if norm1 > 0 and norm2 > 0:
                        similarity = dot / (norm1 * norm2)
                        similarities.append(similarity)
            
            if similarities:
                avg_similarity = sum(similarities) / len(similarities)
                # Normalize to 0-1 (cosine similarity is -1 to 1)
                quality = (avg_similarity + 1) / 2
                return max(0.0, min(1.0, quality))
            
            return 0.5  # Default if can't calculate
        except Exception as e:
            logger.warning(f"Failed to calculate quality score: {e}")
            return 0.5
    
    def _calculate_convergence_score(
        self,
        updates: List[ModelUpdate],
        global_model: GlobalModel,
        previous_model: Optional[GlobalModel]
    ) -> float:
        """
        Calculate convergence score based on loss reduction.
        
        Returns:
            Convergence score (0.0-1.0)
        """
        if not previous_model:
            return 0.5  # No baseline
        
        try:
            current_loss = global_model.avg_training_loss
            previous_loss = previous_model.avg_training_loss
            
            if previous_loss == 0:
                return 0.5
            
            # Loss reduction percentage
            reduction = (previous_loss - current_loss) / previous_loss
            # Normalize to 0-1 (assuming max 100% reduction)
            convergence = max(0.0, min(1.0, (reduction + 1) / 2))
            return convergence
        except Exception as e:
            logger.warning(f"Failed to calculate convergence score: {e}")
            return 0.5
    
    def _calculate_weight_drift(
        self,
        previous_model: GlobalModel,
        current_model: GlobalModel
    ) -> float:
        """
        Calculate weight drift between models.
        
        Returns:
            Weight drift (normalized)
        """
        try:
            prev_weights = previous_model.weights.to_flat_vector()
            curr_weights = current_model.weights.to_flat_vector()
            
            if len(prev_weights) != len(curr_weights):
                return 1.0  # High drift if dimensions differ
            
            # Calculate L2 distance
            diff = [a - b for a, b in zip(curr_weights, prev_weights)]
            drift = math.sqrt(sum(d * d for d in diff))
            
            # Normalize by average weight magnitude
            avg_magnitude = math.sqrt(sum(w * w for w in prev_weights) / len(prev_weights))
            if avg_magnitude > 0:
                normalized_drift = drift / avg_magnitude
                return min(1.0, normalized_drift)
            
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to calculate weight drift: {e}")
            return 0.0
    
    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics."""
        if not self.metrics_history:
            return {}
        
        recent = self.metrics_history[-10:]  # Last 10 aggregations
        
        return {
            'total_aggregations': len(self.metrics_history),
            'avg_aggregation_time': sum(m.aggregation_time_seconds for m in recent) / len(recent),
            'avg_quality_score': sum(m.quality_score for m in recent) / len(recent),
            'avg_convergence_score': sum(m.convergence_score for m in recent) / len(recent),
            'avg_updates_accepted': sum(m.updates_accepted for m in recent) / len(recent),
            'avg_memory_mb': sum(m.memory_used_mb for m in recent) / len(recent),
            'total_byzantine_detected': sum(m.byzantine_detected for m in self.metrics_history)
        }


class EnhancedFedAvgAggregator(EnhancedAggregator, FedAvgAggregator):
    """
    Enhanced FedAvg with metrics and optimizations.
    """
    
    def __init__(self, enable_metrics: bool = True):
        FedAvgAggregator.__init__(self)
        EnhancedAggregator.__init__(self, name="enhanced_fedavg", enable_metrics=enable_metrics)
    
    def _aggregate_impl(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel],
        metrics: AggregationMetrics
    ) -> AggregationResult:
        """Use base FedAvg implementation."""
        return FedAvgAggregator.aggregate(self, updates, previous_model)


class AdaptiveAggregator(EnhancedAggregator):
    """
    Adaptive aggregator that selects strategy based on conditions.
    
    Automatically switches between:
    - FedAvg: When all nodes are trusted
    - Krum: When Byzantine risk is high
    - Trimmed Mean: When outliers detected
    """
    
    def __init__(
        self,
        trust_threshold: float = 0.8,
        outlier_threshold: float = 2.0,
        enable_metrics: bool = True
    ):
        super().__init__(name="adaptive", enable_metrics=enable_metrics)
        self.trust_threshold = trust_threshold
        self.outlier_threshold = outlier_threshold
        
        # Initialize sub-aggregators
        self.fedavg = FedAvgAggregator()
        self.krum = KrumAggregator(f=1)
        self.trimmed_mean = TrimmedMeanAggregator(beta=0.1)
        
        self.strategy_history: List[str] = []
    
    def _aggregate_impl(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel],
        metrics: AggregationMetrics
    ) -> AggregationResult:
        """Select and apply appropriate aggregation strategy."""
        n = len(updates)
        
        if n == 0:
            return AggregationResult(
                success=False,
                error_message="No updates to aggregate"
            )
        
        # Strategy selection logic
        strategy = self._select_strategy(updates, previous_model)
        self.strategy_history.append(strategy)
        
        logger.info(f"🔄 Adaptive aggregator selected: {strategy}")
        
        # Apply selected strategy
        if strategy == "fedavg":
            result = self.fedavg.aggregate(updates, previous_model)
        elif strategy == "krum":
            result = self.krum.aggregate(updates, previous_model)
        elif strategy == "trimmed_mean":
            result = self.trimmed_mean.aggregate(updates, previous_model)
        else:
            # Fallback to FedAvg
            result = self.fedavg.aggregate(updates, previous_model)
        
        # Add strategy info to metadata
        if hasattr(result, 'metadata'):
            result.metadata = result.metadata or {}
            result.metadata['strategy'] = strategy
        else:
            result.metadata = {'strategy': strategy}
        
        return result
    
    def _select_strategy(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel]
    ) -> str:
        """
        Select aggregation strategy based on conditions.
        
        Returns:
            Strategy name: "fedavg", "krum", or "trimmed_mean"
        """
        n = len(updates)
        
        # Check for outliers (high variance in updates)
        if n >= 3:
            try:
                vectors = [u.weights.to_flat_vector() for u in updates]
                # Calculate variance for each dimension
                variances = []
                for d in range(min(100, len(vectors[0]))):  # Sample first 100 dims
                    values = [v[d] for v in vectors]
                    mean = sum(values) / len(values)
                    variance = sum((v - mean) ** 2 for v in values) / len(values)
                    variances.append(variance)
                
                avg_variance = sum(variances) / len(variances) if variances else 0
                
                # High variance suggests outliers
                if avg_variance > self.outlier_threshold:
                    logger.info(f"⚠️ High variance detected ({avg_variance:.2f}), using trimmed_mean")
                    return "trimmed_mean"
            except Exception as e:
                logger.warning(f"Failed to check variance: {e}")
        
        # Check Byzantine risk (low trust scores, many participants)
        # For now, use Krum if many participants (heuristic)
        if n >= 5:
            # Check if we have trust scores (would need node info)
            # For now, use Krum for large groups
            return "krum"
        
        # Default to FedAvg for trusted scenarios
        return "fedavg"
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy selection statistics."""
        if not self.strategy_history:
            return {}
        
        counts = defaultdict(int)
        for strategy in self.strategy_history:
            counts[strategy] += 1
        
        total = len(self.strategy_history)
        return {
            'total_aggregations': total,
            'strategy_usage': {k: v / total for k, v in counts.items()},
            'strategy_counts': dict(counts)
        }


def get_enhanced_aggregator(
    method: str = "enhanced_fedavg",
    **kwargs
) -> EnhancedAggregator:
    """
    Factory function to get enhanced aggregator.
    
    Args:
        method: Aggregation method name
        **kwargs: Additional arguments
    
    Returns:
        EnhancedAggregator instance
    """
    aggregators = {
        "enhanced_fedavg": EnhancedFedAvgAggregator,
        "adaptive": AdaptiveAggregator
    }
    
    if method not in aggregators:
        raise ValueError(f"Unknown enhanced aggregator: {method}. Available: {list(aggregators.keys())}")
    
    return aggregators[method](**kwargs)

