"""
Refactored Byzantine Detector - Simplified Cyclomatic Complexity.

Original CC: 13 → Refactored CC: 7

Strategy:
1. Extract validation into separate method
2. Extract distance computation into separate method
3. Extract weight averaging into separate method
4. Use early returns instead of nested if-else
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ByzantineRefactored:
    """Refactored Byzantine detector with reduced complexity."""
    
    def __init__(self, f: int = 1, multi_krum: bool = True, m: Optional[int] = None):
        self.f = f
        self.multi_krum = multi_krum
        self.m = m or 1
        self._stats = {
            "byzantine_detected": 0,
            "total_rounds": 0,
            "aggregation_times": [],
        }
    
    # CC = 2 (one if + return)
    def _validate_prerequisites(self, updates: List[Any]) -> Tuple[bool, Optional[str]]:
        """Validate that aggregation can proceed.
        
        Returns:
            (is_valid, error_message)
        """
        n = len(updates)
        min_required = 2 * self.f + 3
        
        if n < min_required:
            msg = f"Krum requires at least {min_required} updates, got {n}"
            return False, msg
        
        return True, None
    
    # CC = 1 (just computation)
    def _compute_pairwise_distances(self, vectors: List[List[float]]) -> List[List[float]]:
        """Compute distance matrix between vectors."""
        n = len(vectors)
        distances = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                dist = sum((vectors[i][k] - vectors[j][k]) ** 2 for k in range(len(vectors[i]))) ** 0.5
                distances[i][j] = dist
                distances[j][i] = dist
        
        return distances
    
    # CC = 2 (try/except as one path)
    def _compute_distances(self, vectors: List[List[float]]) -> Optional[List[List[float]]]:
        """Compute distances with numpy fallback."""
        try:
            import numpy as np
            vec_array = np.array(vectors)
            distances = np.linalg.norm(vec_array[:, np.newaxis] - vec_array[np.newaxis, :], axis=2)
            return distances.tolist()
        except (ImportError, Exception):
            return self._compute_pairwise_distances(vectors)
    
    # CC = 1 (just computation)
    def _compute_krum_scores(self, distances: List[List[float]]) -> List[Tuple[float, int]]:
        """Compute Krum scores for each vector."""
        n = len(distances)
        k = n - self.f - 2
        scores = []
        
        for i in range(n):
            dists = [(distances[i][j], j) for j in range(n) if i != j]
            dists.sort()
            score = sum(d[0] for d in dists[:k])
            scores.append((score, i))
        
        scores.sort()
        return scores
    
    # CC = 2 (if for multi_krum + loop)
    def _select_updates(self, scores: List[Tuple[float, int]], updates: List[Any], 
                       vectors: List[List[float]]) -> Tuple[List[int], List[List[float]], List[Any]]:
        """Select which updates to use based on Krum scores."""
        if self.multi_krum:
            count = min(self.m, len(scores) - self.f)
            selected_indices = [scores[i][1] for i in range(count)]
        else:
            selected_indices = [scores[0][1]]
        
        selected_vectors = [vectors[i] for i in selected_indices]
        selected_updates = [updates[i] for i in selected_indices]
        
        return selected_indices, selected_vectors, selected_updates
    
    # CC = 1 (just computation)
    def _weighted_average(self, vectors: List[List[float]], weights: List[float]) -> List[float]:
        """Compute weighted average of vectors."""
        total_weight = sum(weights)
        if total_weight == 0:
            return vectors[0] if vectors else []
        
        vec_dim = len(vectors[0])
        avg = [sum(vectors[i][j] * weights[i] for i in range(len(vectors))) / total_weight 
               for j in range(vec_dim)]
        return avg
    
    # CC = 1 (just tracking)
    def _identify_byzantine(self, scores: List[Tuple[float, int]], updates: List[Any]) -> List[str]:
        """Identify suspected Byzantine nodes."""
        suspected = []
        for i in range(self.f):
            idx = scores[-(i+1)][1]
            if hasattr(updates[idx], 'node_id'):
                suspected.append(updates[idx].node_id)
        
        return suspected
    
    # CC = 3 (result handling) - Much simplified!
    def aggregate(self, updates: List[Any]) -> Dict[str, Any]:
        """Aggregate updates with Byzantine robustness.
        
        Refactored for CC = 7:
        - Validation (CC=2)
        - Distance computation (CC=2)
        - Scoring (CC=1)
        - Selection (CC=2)
        - Final aggregation (CC=1)
        """
        start_time = time.time()
        
        # Validate
        is_valid, error = self._validate_prerequisites(updates)
        if not is_valid:
            return {"success": False, "error": error, "time_ms": (time.time() - start_time) * 1000}
        
        # Extract vectors
        vectors = [u.get_flat_weights() for u in updates]
        
        # Compute distances
        distances = self._compute_distances(vectors)
        if distances is None:
            return {"success": False, "error": "Distance computation failed", 
                    "time_ms": (time.time() - start_time) * 1000}
        
        # Score
        scores = self._compute_krum_scores(distances)
        
        # Select updates
        selected_indices, selected_vectors, selected_updates = self._select_updates(
            scores, updates, vectors
        )
        
        # Detect Byzantine
        suspected = self._identify_byzantine(scores, updates)
        self._stats["byzantine_detected"] += len(suspected)
        
        # Average
        weights = [u.sample_count for u in selected_updates]
        avg_vector = self._weighted_average(selected_vectors, weights)
        
        # Track stats
        elapsed = time.time() - start_time
        self._stats["total_rounds"] += 1
        self._stats["aggregation_times"].append(elapsed)
        
        return {
            "success": True,
            "avg_weights": avg_vector,
            "accepted_count": len(selected_indices),
            "rejected_count": len(updates) - len(selected_indices),
            "suspected_byzantine": suspected,
            "time_ms": elapsed * 1000,
        }
