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

import numpy as np
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


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
    
    def xǁByzantineDetectorǁ__init____mutmut_orig(self, tolerance_fraction: float = 0.30):
        """
        Args:
            tolerance_fraction: Max fraction of nodes that can be Byzantine (0.30 = 30%)
        """
        self.tolerance = tolerance_fraction
        self.detection_history: List[Tuple[int, List[int]]] = []
    
    def xǁByzantineDetectorǁ__init____mutmut_1(self, tolerance_fraction: float = 1.3):
        """
        Args:
            tolerance_fraction: Max fraction of nodes that can be Byzantine (0.30 = 30%)
        """
        self.tolerance = tolerance_fraction
        self.detection_history: List[Tuple[int, List[int]]] = []
    
    def xǁByzantineDetectorǁ__init____mutmut_2(self, tolerance_fraction: float = 0.30):
        """
        Args:
            tolerance_fraction: Max fraction of nodes that can be Byzantine (0.30 = 30%)
        """
        self.tolerance = None
        self.detection_history: List[Tuple[int, List[int]]] = []
    
    def xǁByzantineDetectorǁ__init____mutmut_3(self, tolerance_fraction: float = 0.30):
        """
        Args:
            tolerance_fraction: Max fraction of nodes that can be Byzantine (0.30 = 30%)
        """
        self.tolerance = tolerance_fraction
        self.detection_history: List[Tuple[int, List[int]]] = None
    
    xǁByzantineDetectorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁByzantineDetectorǁ__init____mutmut_1': xǁByzantineDetectorǁ__init____mutmut_1, 
        'xǁByzantineDetectorǁ__init____mutmut_2': xǁByzantineDetectorǁ__init____mutmut_2, 
        'xǁByzantineDetectorǁ__init____mutmut_3': xǁByzantineDetectorǁ__init____mutmut_3
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁByzantineDetectorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁByzantineDetectorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁByzantineDetectorǁ__init____mutmut_orig)
    xǁByzantineDetectorǁ__init____mutmut_orig.__name__ = 'xǁByzantineDetectorǁ__init__'
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_orig(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_1(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) <= 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_2(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 11:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_3(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = None
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_4(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances(None)
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_5(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = None
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_6(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(None):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_7(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = None
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_8(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(None)
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_9(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(None)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_10(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = None
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_11(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(None)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_12(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = None
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_13(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(None) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_14(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) >= 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_15(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 2 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_16(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 2.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_17(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = None
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_18(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist - 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_19(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 / std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_20(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 2.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_21(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = None
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_22(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(None) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_23(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d >= threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_24(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = None
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_25(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(None, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_26(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, None)
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_27(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_28(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, )
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_29(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(2, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_30(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(None))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_31(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) / self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_32(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = None
        
        logger.info(f"Byzantine detection: {len(malicious_indices)}/{len(updates)} flagged")
        
        return malicious_indices
    
    def xǁByzantineDetectorǁdetect_malicious_updates__mutmut_33(self, updates: List[ModelUpdate]) -> List[int]:
        """
        Detect indices of suspected Byzantine updates.
        
        Returns:
            List of indices in updates that are likely Byzantine
        """
        if len(updates) < 10:
            return []
        
        # Compute pairwise L2 distances between gradients
        distances = self._compute_pairwise_distances([u.gradient for u in updates])
        
        # Find outliers: gradients with high average distance to others
        avg_distances = []
        for i in range(len(updates)):
            avg_dist = np.mean(distances[i])
            avg_distances.append(avg_dist)
        
        # Statistical outlier detection
        mean_dist = np.mean(avg_distances)
        std_dist = np.std(avg_distances) if len(avg_distances) > 1 else 1.0
        
        threshold = mean_dist + 1.5 * std_dist
        
        suspicious_indices = [
            i for i, d in enumerate(avg_distances) 
            if d > threshold
        ]
        
        # Limit detections to tolerance level
        max_detections = max(1, int(len(updates) * self.tolerance))
        malicious_indices = suspicious_indices[:max_detections]
        
        logger.info(None)
        
        return malicious_indices
    
    xǁByzantineDetectorǁdetect_malicious_updates__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_1': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_1, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_2': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_2, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_3': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_3, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_4': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_4, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_5': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_5, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_6': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_6, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_7': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_7, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_8': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_8, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_9': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_9, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_10': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_10, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_11': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_11, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_12': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_12, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_13': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_13, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_14': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_14, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_15': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_15, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_16': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_16, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_17': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_17, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_18': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_18, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_19': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_19, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_20': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_20, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_21': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_21, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_22': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_22, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_23': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_23, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_24': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_24, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_25': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_25, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_26': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_26, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_27': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_27, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_28': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_28, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_29': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_29, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_30': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_30, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_31': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_31, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_32': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_32, 
        'xǁByzantineDetectorǁdetect_malicious_updates__mutmut_33': xǁByzantineDetectorǁdetect_malicious_updates__mutmut_33
    }
    
    def detect_malicious_updates(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁByzantineDetectorǁdetect_malicious_updates__mutmut_orig"), object.__getattribute__(self, "xǁByzantineDetectorǁdetect_malicious_updates__mutmut_mutants"), args, kwargs, self)
        return result 
    
    detect_malicious_updates.__signature__ = _mutmut_signature(xǁByzantineDetectorǁdetect_malicious_updates__mutmut_orig)
    xǁByzantineDetectorǁdetect_malicious_updates__mutmut_orig.__name__ = 'xǁByzantineDetectorǁdetect_malicious_updates'
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_orig(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_1(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if updates:
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_2(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError(None)
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_3(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("XXNo updates to aggregateXX")
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_4(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("no updates to aggregate")
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_5(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("NO UPDATES TO AGGREGATE")
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_6(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Detect and remove Byzantine updates
        malicious_idx = None
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_7(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Detect and remove Byzantine updates
        malicious_idx = self.detect_malicious_updates(None)
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_8(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Detect and remove Byzantine updates
        malicious_idx = self.detect_malicious_updates(updates)
        clean_updates = None
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_9(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Detect and remove Byzantine updates
        malicious_idx = self.detect_malicious_updates(updates)
        clean_updates = [u for i, u in enumerate(None) if i not in malicious_idx]
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_10(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
        """
        Filter Byzantine updates and aggregate clean ones.
        
        Returns:
            Aggregated gradient (numpy array)
        """
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Detect and remove Byzantine updates
        malicious_idx = self.detect_malicious_updates(updates)
        clean_updates = [u for i, u in enumerate(updates) if i in malicious_idx]
        
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_11(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
        
        if clean_updates:
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_12(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            logger.warning(None)
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_13(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            logger.warning("XXAll updates marked as Byzantine, using median aggregationXX")
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_14(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            logger.warning("all updates marked as byzantine, using median aggregation")
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_15(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            logger.warning("ALL UPDATES MARKED AS BYZANTINE, USING MEDIAN AGGREGATION")
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
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_16(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            return self._geometric_median(None)
        
        # Aggregate clean updates
        if method == AggregationMethod.MEAN:
            return self._mean_aggregate([u.gradient for u in clean_updates])
        elif method == AggregationMethod.MEDIAN:
            return self._coordinate_median([u.gradient for u in clean_updates])
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_17(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
        if method != AggregationMethod.MEAN:
            return self._mean_aggregate([u.gradient for u in clean_updates])
        elif method == AggregationMethod.MEDIAN:
            return self._coordinate_median([u.gradient for u in clean_updates])
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_18(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            return self._mean_aggregate(None)
        elif method == AggregationMethod.MEDIAN:
            return self._coordinate_median([u.gradient for u in clean_updates])
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_19(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
        elif method != AggregationMethod.MEDIAN:
            return self._coordinate_median([u.gradient for u in clean_updates])
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_20(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            return self._coordinate_median(None)
        elif method == AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_21(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
        elif method != AggregationMethod.KRUM:
            return self._krum_aggregate([u.gradient for u in clean_updates])
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_22(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            return self._krum_aggregate(None)
        else:
            return self._mean_aggregate([u.gradient for u in clean_updates])
    
    def xǁByzantineDetectorǁfilter_and_aggregate__mutmut_23(self, updates: List[ModelUpdate], 
                           method: AggregationMethod = AggregationMethod.MEAN) -> np.ndarray:
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
            return self._mean_aggregate(None)
    
    xǁByzantineDetectorǁfilter_and_aggregate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_1': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_1, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_2': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_2, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_3': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_3, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_4': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_4, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_5': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_5, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_6': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_6, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_7': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_7, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_8': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_8, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_9': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_9, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_10': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_10, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_11': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_11, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_12': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_12, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_13': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_13, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_14': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_14, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_15': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_15, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_16': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_16, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_17': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_17, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_18': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_18, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_19': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_19, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_20': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_20, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_21': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_21, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_22': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_22, 
        'xǁByzantineDetectorǁfilter_and_aggregate__mutmut_23': xǁByzantineDetectorǁfilter_and_aggregate__mutmut_23
    }
    
    def filter_and_aggregate(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁByzantineDetectorǁfilter_and_aggregate__mutmut_orig"), object.__getattribute__(self, "xǁByzantineDetectorǁfilter_and_aggregate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    filter_and_aggregate.__signature__ = _mutmut_signature(xǁByzantineDetectorǁfilter_and_aggregate__mutmut_orig)
    xǁByzantineDetectorǁfilter_and_aggregate__mutmut_orig.__name__ = 'xǁByzantineDetectorǁfilter_and_aggregate'
    
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
    
    def xǁConvergenceDetectorǁ__init____mutmut_orig(self, window_size: int = 5, threshold: float = 0.001):
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
    
    def xǁConvergenceDetectorǁ__init____mutmut_1(self, window_size: int = 6, threshold: float = 0.001):
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
    
    def xǁConvergenceDetectorǁ__init____mutmut_2(self, window_size: int = 5, threshold: float = 1.001):
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
    
    def xǁConvergenceDetectorǁ__init____mutmut_3(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = None
        self.threshold = threshold
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = []
        self.gradient_norm_history: List[float] = []
    
    def xǁConvergenceDetectorǁ__init____mutmut_4(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = window_size
        self.threshold = None
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = []
        self.gradient_norm_history: List[float] = []
    
    def xǁConvergenceDetectorǁ__init____mutmut_5(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = window_size
        self.threshold = threshold
        self.loss_history: List[float] = None
        self.accuracy_history: List[float] = []
        self.gradient_norm_history: List[float] = []
    
    def xǁConvergenceDetectorǁ__init____mutmut_6(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = window_size
        self.threshold = threshold
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = None
        self.gradient_norm_history: List[float] = []
    
    def xǁConvergenceDetectorǁ__init____mutmut_7(self, window_size: int = 5, threshold: float = 0.001):
        """
        Args:
            window_size: Number of rounds to consider for convergence
            threshold: Relative improvement threshold
        """
        self.window_size = window_size
        self.threshold = threshold
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = []
        self.gradient_norm_history: List[float] = None
    
    xǁConvergenceDetectorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁConvergenceDetectorǁ__init____mutmut_1': xǁConvergenceDetectorǁ__init____mutmut_1, 
        'xǁConvergenceDetectorǁ__init____mutmut_2': xǁConvergenceDetectorǁ__init____mutmut_2, 
        'xǁConvergenceDetectorǁ__init____mutmut_3': xǁConvergenceDetectorǁ__init____mutmut_3, 
        'xǁConvergenceDetectorǁ__init____mutmut_4': xǁConvergenceDetectorǁ__init____mutmut_4, 
        'xǁConvergenceDetectorǁ__init____mutmut_5': xǁConvergenceDetectorǁ__init____mutmut_5, 
        'xǁConvergenceDetectorǁ__init____mutmut_6': xǁConvergenceDetectorǁ__init____mutmut_6, 
        'xǁConvergenceDetectorǁ__init____mutmut_7': xǁConvergenceDetectorǁ__init____mutmut_7
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁConvergenceDetectorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁConvergenceDetectorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁConvergenceDetectorǁ__init____mutmut_orig)
    xǁConvergenceDetectorǁ__init____mutmut_orig.__name__ = 'xǁConvergenceDetectorǁ__init__'
    
    def xǁConvergenceDetectorǁupdate__mutmut_orig(self, loss: float, accuracy: float, gradient_norm: float):
        """Update convergence statistics"""
        self.loss_history.append(loss)
        self.accuracy_history.append(accuracy)
        self.gradient_norm_history.append(gradient_norm)
    
    def xǁConvergenceDetectorǁupdate__mutmut_1(self, loss: float, accuracy: float, gradient_norm: float):
        """Update convergence statistics"""
        self.loss_history.append(None)
        self.accuracy_history.append(accuracy)
        self.gradient_norm_history.append(gradient_norm)
    
    def xǁConvergenceDetectorǁupdate__mutmut_2(self, loss: float, accuracy: float, gradient_norm: float):
        """Update convergence statistics"""
        self.loss_history.append(loss)
        self.accuracy_history.append(None)
        self.gradient_norm_history.append(gradient_norm)
    
    def xǁConvergenceDetectorǁupdate__mutmut_3(self, loss: float, accuracy: float, gradient_norm: float):
        """Update convergence statistics"""
        self.loss_history.append(loss)
        self.accuracy_history.append(accuracy)
        self.gradient_norm_history.append(None)
    
    xǁConvergenceDetectorǁupdate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁConvergenceDetectorǁupdate__mutmut_1': xǁConvergenceDetectorǁupdate__mutmut_1, 
        'xǁConvergenceDetectorǁupdate__mutmut_2': xǁConvergenceDetectorǁupdate__mutmut_2, 
        'xǁConvergenceDetectorǁupdate__mutmut_3': xǁConvergenceDetectorǁupdate__mutmut_3
    }
    
    def update(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁConvergenceDetectorǁupdate__mutmut_orig"), object.__getattribute__(self, "xǁConvergenceDetectorǁupdate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update.__signature__ = _mutmut_signature(xǁConvergenceDetectorǁupdate__mutmut_orig)
    xǁConvergenceDetectorǁupdate__mutmut_orig.__name__ = 'xǁConvergenceDetectorǁupdate'
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_orig(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_1(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) <= self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_2(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return True, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_3(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = None
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_4(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[+self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_5(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[1] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_6(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] >= 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_7(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 1:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_8(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = None
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_9(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) * recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_10(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] + recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_11(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[1] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_12(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[+1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_13(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-2]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_14(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[1]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_15(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = None
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_16(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 1
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_17(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement <= self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_18(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return False, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_19(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = None
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_20(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[+self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_21(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = None
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_22(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] + recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_23(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[+1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_24(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-2] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_25(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[1]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_26(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement <= self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_27(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return False, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_28(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = None
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_29(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[+self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_30(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[+1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_31(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-2] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_32(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] <= 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_33(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1.00001:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_34(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return False, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_35(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[+1]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_36(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-2]:.2e} < 1e-5"
        
        return False, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_37(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return True, "Training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_38(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "XXTraining ongoingXX"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_39(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "training ongoing"
    
    def xǁConvergenceDetectorǁcheck_convergence__mutmut_40(self) -> Tuple[bool, str]:
        """
        Check if model has converged.
        
        Returns:
            (is_converged, reason)
        """
        
        if len(self.loss_history) < self.window_size:
            return False, f"Insufficient history ({len(self.loss_history)}/{self.window_size})"
        
        # Check loss improvement
        recent_losses = self.loss_history[-self.window_size:]
        if recent_losses[0] > 0:
            loss_improvement = (recent_losses[0] - recent_losses[-1]) / recent_losses[0]
        else:
            loss_improvement = 0
        
        if loss_improvement < self.threshold:
            return True, f"Loss improvement {loss_improvement:.4f} < {self.threshold}"
        
        # Check accuracy plateau
        recent_accs = self.accuracy_history[-self.window_size:]
        acc_improvement = recent_accs[-1] - recent_accs[0]
        
        if acc_improvement < self.threshold:
            return True, f"Accuracy improvement {acc_improvement:.4f} < {self.threshold}"
        
        # Check gradient norm
        recent_norms = self.gradient_norm_history[-self.window_size:]
        if recent_norms[-1] < 1e-5:
            return True, f"Gradient norm {recent_norms[-1]:.2e} < 1e-5"
        
        return False, "TRAINING ONGOING"
    
    xǁConvergenceDetectorǁcheck_convergence__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁConvergenceDetectorǁcheck_convergence__mutmut_1': xǁConvergenceDetectorǁcheck_convergence__mutmut_1, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_2': xǁConvergenceDetectorǁcheck_convergence__mutmut_2, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_3': xǁConvergenceDetectorǁcheck_convergence__mutmut_3, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_4': xǁConvergenceDetectorǁcheck_convergence__mutmut_4, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_5': xǁConvergenceDetectorǁcheck_convergence__mutmut_5, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_6': xǁConvergenceDetectorǁcheck_convergence__mutmut_6, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_7': xǁConvergenceDetectorǁcheck_convergence__mutmut_7, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_8': xǁConvergenceDetectorǁcheck_convergence__mutmut_8, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_9': xǁConvergenceDetectorǁcheck_convergence__mutmut_9, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_10': xǁConvergenceDetectorǁcheck_convergence__mutmut_10, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_11': xǁConvergenceDetectorǁcheck_convergence__mutmut_11, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_12': xǁConvergenceDetectorǁcheck_convergence__mutmut_12, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_13': xǁConvergenceDetectorǁcheck_convergence__mutmut_13, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_14': xǁConvergenceDetectorǁcheck_convergence__mutmut_14, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_15': xǁConvergenceDetectorǁcheck_convergence__mutmut_15, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_16': xǁConvergenceDetectorǁcheck_convergence__mutmut_16, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_17': xǁConvergenceDetectorǁcheck_convergence__mutmut_17, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_18': xǁConvergenceDetectorǁcheck_convergence__mutmut_18, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_19': xǁConvergenceDetectorǁcheck_convergence__mutmut_19, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_20': xǁConvergenceDetectorǁcheck_convergence__mutmut_20, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_21': xǁConvergenceDetectorǁcheck_convergence__mutmut_21, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_22': xǁConvergenceDetectorǁcheck_convergence__mutmut_22, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_23': xǁConvergenceDetectorǁcheck_convergence__mutmut_23, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_24': xǁConvergenceDetectorǁcheck_convergence__mutmut_24, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_25': xǁConvergenceDetectorǁcheck_convergence__mutmut_25, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_26': xǁConvergenceDetectorǁcheck_convergence__mutmut_26, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_27': xǁConvergenceDetectorǁcheck_convergence__mutmut_27, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_28': xǁConvergenceDetectorǁcheck_convergence__mutmut_28, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_29': xǁConvergenceDetectorǁcheck_convergence__mutmut_29, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_30': xǁConvergenceDetectorǁcheck_convergence__mutmut_30, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_31': xǁConvergenceDetectorǁcheck_convergence__mutmut_31, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_32': xǁConvergenceDetectorǁcheck_convergence__mutmut_32, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_33': xǁConvergenceDetectorǁcheck_convergence__mutmut_33, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_34': xǁConvergenceDetectorǁcheck_convergence__mutmut_34, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_35': xǁConvergenceDetectorǁcheck_convergence__mutmut_35, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_36': xǁConvergenceDetectorǁcheck_convergence__mutmut_36, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_37': xǁConvergenceDetectorǁcheck_convergence__mutmut_37, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_38': xǁConvergenceDetectorǁcheck_convergence__mutmut_38, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_39': xǁConvergenceDetectorǁcheck_convergence__mutmut_39, 
        'xǁConvergenceDetectorǁcheck_convergence__mutmut_40': xǁConvergenceDetectorǁcheck_convergence__mutmut_40
    }
    
    def check_convergence(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁConvergenceDetectorǁcheck_convergence__mutmut_orig"), object.__getattribute__(self, "xǁConvergenceDetectorǁcheck_convergence__mutmut_mutants"), args, kwargs, self)
        return result 
    
    check_convergence.__signature__ = _mutmut_signature(xǁConvergenceDetectorǁcheck_convergence__mutmut_orig)
    xǁConvergenceDetectorǁcheck_convergence__mutmut_orig.__name__ = 'xǁConvergenceDetectorǁcheck_convergence'


class AdaptiveLearningRate:
    """Adaptive learning rate scheduler"""
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_orig(self, initial_lr: float = 0.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = initial_lr
        self.schedule = schedule
        self.round_number = 0
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_1(self, initial_lr: float = 1.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = initial_lr
        self.schedule = schedule
        self.round_number = 0
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_2(self, initial_lr: float = 0.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = None
        self.schedule = schedule
        self.round_number = 0
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_3(self, initial_lr: float = 0.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = initial_lr
        self.schedule = None
        self.round_number = 0
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_4(self, initial_lr: float = 0.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = initial_lr
        self.schedule = schedule
        self.round_number = None
    
    def xǁAdaptiveLearningRateǁ__init____mutmut_5(self, initial_lr: float = 0.1, 
                 schedule: LearningRateSchedule = LearningRateSchedule.STEP_DECAY):
        self.initial_lr = initial_lr
        self.schedule = schedule
        self.round_number = 1
    
    xǁAdaptiveLearningRateǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁAdaptiveLearningRateǁ__init____mutmut_1': xǁAdaptiveLearningRateǁ__init____mutmut_1, 
        'xǁAdaptiveLearningRateǁ__init____mutmut_2': xǁAdaptiveLearningRateǁ__init____mutmut_2, 
        'xǁAdaptiveLearningRateǁ__init____mutmut_3': xǁAdaptiveLearningRateǁ__init____mutmut_3, 
        'xǁAdaptiveLearningRateǁ__init____mutmut_4': xǁAdaptiveLearningRateǁ__init____mutmut_4, 
        'xǁAdaptiveLearningRateǁ__init____mutmut_5': xǁAdaptiveLearningRateǁ__init____mutmut_5
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁAdaptiveLearningRateǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁAdaptiveLearningRateǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁAdaptiveLearningRateǁ__init____mutmut_orig)
    xǁAdaptiveLearningRateǁ__init____mutmut_orig.__name__ = 'xǁAdaptiveLearningRateǁ__init__'
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_orig(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_1(self, staleness: float = 1.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_2(self, staleness: float = 0.0, gradient_norm: float = 2.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_3(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule != LearningRateSchedule.STEP_DECAY:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_4(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = None
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_5(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 * (self.round_number // 10)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_6(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 1.1 ** (self.round_number // 10)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_7(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number / 10)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_8(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 11)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_9(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule != LearningRateSchedule.EXPONENTIAL:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_10(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = None
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_11(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(None)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_12(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number * 100)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_13(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(+self.round_number / 100)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_14(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 101)
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_15(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule != LearningRateSchedule.ADAPTIVE:
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
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_16(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = None
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_17(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 * (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_18(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 2.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_19(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 - self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_20(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (2.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_21(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = None
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_22(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 2.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_23(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = None
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_24(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 + 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_25(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 2.0 - 0.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_26(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 / staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_27(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 1.5 * staleness if staleness > 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_28(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness >= 0 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_29(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 1 else 1.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_30(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
            decay_factor = 0.1 ** (self.round_number // 10)
        elif self.schedule == LearningRateSchedule.EXPONENTIAL:
            decay_factor = np.exp(-self.round_number / 100)
        elif self.schedule == LearningRateSchedule.ADAPTIVE:
            decay_factor = 1.0 / (1.0 + self.round_number)
        else:
            decay_factor = 1.0
        
        # Account for staleness: stale updates use lower learning rate
        staleness_factor = 1.0 - 0.5 * staleness if staleness > 0 else 2.0
        
        # Normalize by gradient norm
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_31(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = None
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_32(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 * (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_33(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 2.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_34(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 / (1.0 - gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_35(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 / (2.0 + gradient_norm) if gradient_norm > 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_36(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm >= 0 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_37(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 1 else 1.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_38(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        norm_factor = 1.0 / (1.0 + gradient_norm) if gradient_norm > 0 else 2.0
        
        lr = self.initial_lr * decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_39(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        lr = None
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_40(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        lr = self.initial_lr * decay_factor * staleness_factor / norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_41(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        lr = self.initial_lr * decay_factor / staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_42(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        lr = self.initial_lr / decay_factor * staleness_factor * norm_factor
        
        self.round_number += 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_43(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        self.round_number = 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_44(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        self.round_number -= 1
        
        return lr
    
    def xǁAdaptiveLearningRateǁget_lr__mutmut_45(self, staleness: float = 0.0, gradient_norm: float = 1.0) -> float:
        """
        Get learning rate for current round.
        
        Args:
            staleness: Fraction indicating update staleness (0-1)
            gradient_norm: Gradient norm for normalization
        
        Returns:
            Learning rate to use
        """
        
        # Base schedule
        if self.schedule == LearningRateSchedule.STEP_DECAY:
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
        
        self.round_number += 2
        
        return lr
    
    xǁAdaptiveLearningRateǁget_lr__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁAdaptiveLearningRateǁget_lr__mutmut_1': xǁAdaptiveLearningRateǁget_lr__mutmut_1, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_2': xǁAdaptiveLearningRateǁget_lr__mutmut_2, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_3': xǁAdaptiveLearningRateǁget_lr__mutmut_3, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_4': xǁAdaptiveLearningRateǁget_lr__mutmut_4, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_5': xǁAdaptiveLearningRateǁget_lr__mutmut_5, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_6': xǁAdaptiveLearningRateǁget_lr__mutmut_6, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_7': xǁAdaptiveLearningRateǁget_lr__mutmut_7, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_8': xǁAdaptiveLearningRateǁget_lr__mutmut_8, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_9': xǁAdaptiveLearningRateǁget_lr__mutmut_9, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_10': xǁAdaptiveLearningRateǁget_lr__mutmut_10, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_11': xǁAdaptiveLearningRateǁget_lr__mutmut_11, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_12': xǁAdaptiveLearningRateǁget_lr__mutmut_12, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_13': xǁAdaptiveLearningRateǁget_lr__mutmut_13, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_14': xǁAdaptiveLearningRateǁget_lr__mutmut_14, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_15': xǁAdaptiveLearningRateǁget_lr__mutmut_15, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_16': xǁAdaptiveLearningRateǁget_lr__mutmut_16, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_17': xǁAdaptiveLearningRateǁget_lr__mutmut_17, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_18': xǁAdaptiveLearningRateǁget_lr__mutmut_18, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_19': xǁAdaptiveLearningRateǁget_lr__mutmut_19, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_20': xǁAdaptiveLearningRateǁget_lr__mutmut_20, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_21': xǁAdaptiveLearningRateǁget_lr__mutmut_21, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_22': xǁAdaptiveLearningRateǁget_lr__mutmut_22, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_23': xǁAdaptiveLearningRateǁget_lr__mutmut_23, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_24': xǁAdaptiveLearningRateǁget_lr__mutmut_24, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_25': xǁAdaptiveLearningRateǁget_lr__mutmut_25, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_26': xǁAdaptiveLearningRateǁget_lr__mutmut_26, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_27': xǁAdaptiveLearningRateǁget_lr__mutmut_27, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_28': xǁAdaptiveLearningRateǁget_lr__mutmut_28, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_29': xǁAdaptiveLearningRateǁget_lr__mutmut_29, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_30': xǁAdaptiveLearningRateǁget_lr__mutmut_30, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_31': xǁAdaptiveLearningRateǁget_lr__mutmut_31, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_32': xǁAdaptiveLearningRateǁget_lr__mutmut_32, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_33': xǁAdaptiveLearningRateǁget_lr__mutmut_33, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_34': xǁAdaptiveLearningRateǁget_lr__mutmut_34, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_35': xǁAdaptiveLearningRateǁget_lr__mutmut_35, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_36': xǁAdaptiveLearningRateǁget_lr__mutmut_36, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_37': xǁAdaptiveLearningRateǁget_lr__mutmut_37, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_38': xǁAdaptiveLearningRateǁget_lr__mutmut_38, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_39': xǁAdaptiveLearningRateǁget_lr__mutmut_39, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_40': xǁAdaptiveLearningRateǁget_lr__mutmut_40, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_41': xǁAdaptiveLearningRateǁget_lr__mutmut_41, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_42': xǁAdaptiveLearningRateǁget_lr__mutmut_42, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_43': xǁAdaptiveLearningRateǁget_lr__mutmut_43, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_44': xǁAdaptiveLearningRateǁget_lr__mutmut_44, 
        'xǁAdaptiveLearningRateǁget_lr__mutmut_45': xǁAdaptiveLearningRateǁget_lr__mutmut_45
    }
    
    def get_lr(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁAdaptiveLearningRateǁget_lr__mutmut_orig"), object.__getattribute__(self, "xǁAdaptiveLearningRateǁget_lr__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_lr.__signature__ = _mutmut_signature(xǁAdaptiveLearningRateǁget_lr__mutmut_orig)
    xǁAdaptiveLearningRateǁget_lr__mutmut_orig.__name__ = 'xǁAdaptiveLearningRateǁget_lr'
    
    def xǁAdaptiveLearningRateǁreset__mutmut_orig(self):
        """Reset round counter"""
        self.round_number = 0
    
    def xǁAdaptiveLearningRateǁreset__mutmut_1(self):
        """Reset round counter"""
        self.round_number = None
    
    def xǁAdaptiveLearningRateǁreset__mutmut_2(self):
        """Reset round counter"""
        self.round_number = 1
    
    xǁAdaptiveLearningRateǁreset__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁAdaptiveLearningRateǁreset__mutmut_1': xǁAdaptiveLearningRateǁreset__mutmut_1, 
        'xǁAdaptiveLearningRateǁreset__mutmut_2': xǁAdaptiveLearningRateǁreset__mutmut_2
    }
    
    def reset(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁAdaptiveLearningRateǁreset__mutmut_orig"), object.__getattribute__(self, "xǁAdaptiveLearningRateǁreset__mutmut_mutants"), args, kwargs, self)
        return result 
    
    reset.__signature__ = _mutmut_signature(xǁAdaptiveLearningRateǁreset__mutmut_orig)
    xǁAdaptiveLearningRateǁreset__mutmut_orig.__name__ = 'xǁAdaptiveLearningRateǁreset'


class FLOrchestrator(ABC):
    """Abstract base class for FL orchestrators"""
    
    def xǁFLOrchestratorǁ__init____mutmut_orig(self, model: np.ndarray, initial_lr: float = 0.1):
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
    
    def xǁFLOrchestratorǁ__init____mutmut_1(self, model: np.ndarray, initial_lr: float = 1.1):
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
    
    def xǁFLOrchestratorǁ__init____mutmut_2(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = None
        self.lr_scheduler = AdaptiveLearningRate(initial_lr)
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = []
    
    def xǁFLOrchestratorǁ__init____mutmut_3(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = None
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = []
    
    def xǁFLOrchestratorǁ__init____mutmut_4(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = AdaptiveLearningRate(None)
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = []
    
    def xǁFLOrchestratorǁ__init____mutmut_5(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = AdaptiveLearningRate(initial_lr)
        self.byzantine_detector = None
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = []
    
    def xǁFLOrchestratorǁ__init____mutmut_6(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = AdaptiveLearningRate(initial_lr)
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = None
        self.round_stats: List[TrainingRoundStats] = []
    
    def xǁFLOrchestratorǁ__init____mutmut_7(self, model: np.ndarray, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model parameters (numpy array)
            initial_lr: Initial learning rate
        """
        self.model = model.copy()
        self.lr_scheduler = AdaptiveLearningRate(initial_lr)
        self.byzantine_detector = ByzantineDetector()
        self.convergence_detector = ConvergenceDetector()
        self.round_stats: List[TrainingRoundStats] = None
    
    xǁFLOrchestratorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLOrchestratorǁ__init____mutmut_1': xǁFLOrchestratorǁ__init____mutmut_1, 
        'xǁFLOrchestratorǁ__init____mutmut_2': xǁFLOrchestratorǁ__init____mutmut_2, 
        'xǁFLOrchestratorǁ__init____mutmut_3': xǁFLOrchestratorǁ__init____mutmut_3, 
        'xǁFLOrchestratorǁ__init____mutmut_4': xǁFLOrchestratorǁ__init____mutmut_4, 
        'xǁFLOrchestratorǁ__init____mutmut_5': xǁFLOrchestratorǁ__init____mutmut_5, 
        'xǁFLOrchestratorǁ__init____mutmut_6': xǁFLOrchestratorǁ__init____mutmut_6, 
        'xǁFLOrchestratorǁ__init____mutmut_7': xǁFLOrchestratorǁ__init____mutmut_7
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLOrchestratorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁFLOrchestratorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁFLOrchestratorǁ__init____mutmut_orig)
    xǁFLOrchestratorǁ__init____mutmut_orig.__name__ = 'xǁFLOrchestratorǁ__init__'
    
    @abstractmethod
    def aggregate_updates(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates from multiple nodes.
        
        Returns:
            Aggregated gradient
        """
        pass
    
    def xǁFLOrchestratorǁupdate_model__mutmut_orig(self, gradient: np.ndarray, learning_rate: float):
        """Update model with gradient descent"""
        self.model = self.model - learning_rate * gradient
    
    def xǁFLOrchestratorǁupdate_model__mutmut_1(self, gradient: np.ndarray, learning_rate: float):
        """Update model with gradient descent"""
        self.model = None
    
    def xǁFLOrchestratorǁupdate_model__mutmut_2(self, gradient: np.ndarray, learning_rate: float):
        """Update model with gradient descent"""
        self.model = self.model + learning_rate * gradient
    
    def xǁFLOrchestratorǁupdate_model__mutmut_3(self, gradient: np.ndarray, learning_rate: float):
        """Update model with gradient descent"""
        self.model = self.model - learning_rate / gradient
    
    xǁFLOrchestratorǁupdate_model__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLOrchestratorǁupdate_model__mutmut_1': xǁFLOrchestratorǁupdate_model__mutmut_1, 
        'xǁFLOrchestratorǁupdate_model__mutmut_2': xǁFLOrchestratorǁupdate_model__mutmut_2, 
        'xǁFLOrchestratorǁupdate_model__mutmut_3': xǁFLOrchestratorǁupdate_model__mutmut_3
    }
    
    def update_model(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLOrchestratorǁupdate_model__mutmut_orig"), object.__getattribute__(self, "xǁFLOrchestratorǁupdate_model__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_model.__signature__ = _mutmut_signature(xǁFLOrchestratorǁupdate_model__mutmut_orig)
    xǁFLOrchestratorǁupdate_model__mutmut_orig.__name__ = 'xǁFLOrchestratorǁupdate_model'
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_orig(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.loss,
            stats.accuracy,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_1(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(None)
        
        self.convergence_detector.update(
            stats.loss,
            stats.accuracy,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_2(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            None,
            stats.accuracy,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_3(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.loss,
            None,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_4(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.loss,
            stats.accuracy,
            None
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_5(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.accuracy,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_6(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.loss,
            stats.gradient_norm
        )
    
    def xǁFLOrchestratorǁrecord_stats__mutmut_7(self, stats: TrainingRoundStats):
        """Record round statistics"""
        self.round_stats.append(stats)
        
        self.convergence_detector.update(
            stats.loss,
            stats.accuracy,
            )
    
    xǁFLOrchestratorǁrecord_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLOrchestratorǁrecord_stats__mutmut_1': xǁFLOrchestratorǁrecord_stats__mutmut_1, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_2': xǁFLOrchestratorǁrecord_stats__mutmut_2, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_3': xǁFLOrchestratorǁrecord_stats__mutmut_3, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_4': xǁFLOrchestratorǁrecord_stats__mutmut_4, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_5': xǁFLOrchestratorǁrecord_stats__mutmut_5, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_6': xǁFLOrchestratorǁrecord_stats__mutmut_6, 
        'xǁFLOrchestratorǁrecord_stats__mutmut_7': xǁFLOrchestratorǁrecord_stats__mutmut_7
    }
    
    def record_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLOrchestratorǁrecord_stats__mutmut_orig"), object.__getattribute__(self, "xǁFLOrchestratorǁrecord_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_stats.__signature__ = _mutmut_signature(xǁFLOrchestratorǁrecord_stats__mutmut_orig)
    xǁFLOrchestratorǁrecord_stats__mutmut_orig.__name__ = 'xǁFLOrchestratorǁrecord_stats'


class BatchAsyncOrchestrator(FLOrchestrator):
    """
    Batch asynchronous aggregation orchestrator.
    
    Aggregates when K < N updates received or timeout.
    """
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_orig(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
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
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_1(self, model: np.ndarray, k_threshold: float = 1.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
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
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_2(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 61.0, initial_lr: float = 0.1):
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
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_3(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 1.1):
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
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_4(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(None, initial_lr)
        self.k_threshold = k_threshold
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_5(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(model, None)
        self.k_threshold = k_threshold
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_6(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(initial_lr)
        self.k_threshold = k_threshold
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_7(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(model, )
        self.k_threshold = k_threshold
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_8(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.k_threshold = None
        self.timeout = timeout
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_9(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            k_threshold: Fraction of updates to receive before aggregating (0-1)
            timeout: Maximum time to wait for updates (seconds)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.k_threshold = k_threshold
        self.timeout = None
        self.pending_updates: List[ModelUpdate] = []
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_10(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
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
        self.pending_updates: List[ModelUpdate] = None
        self.last_aggregation = time.time()
    
    def xǁBatchAsyncOrchestratorǁ__init____mutmut_11(self, model: np.ndarray, k_threshold: float = 0.85, 
                 timeout: float = 60.0, initial_lr: float = 0.1):
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
        self.last_aggregation = None
    
    xǁBatchAsyncOrchestratorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁBatchAsyncOrchestratorǁ__init____mutmut_1': xǁBatchAsyncOrchestratorǁ__init____mutmut_1, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_2': xǁBatchAsyncOrchestratorǁ__init____mutmut_2, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_3': xǁBatchAsyncOrchestratorǁ__init____mutmut_3, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_4': xǁBatchAsyncOrchestratorǁ__init____mutmut_4, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_5': xǁBatchAsyncOrchestratorǁ__init____mutmut_5, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_6': xǁBatchAsyncOrchestratorǁ__init____mutmut_6, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_7': xǁBatchAsyncOrchestratorǁ__init____mutmut_7, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_8': xǁBatchAsyncOrchestratorǁ__init____mutmut_8, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_9': xǁBatchAsyncOrchestratorǁ__init____mutmut_9, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_10': xǁBatchAsyncOrchestratorǁ__init____mutmut_10, 
        'xǁBatchAsyncOrchestratorǁ__init____mutmut_11': xǁBatchAsyncOrchestratorǁ__init____mutmut_11
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁBatchAsyncOrchestratorǁ__init____mutmut_orig)
    xǁBatchAsyncOrchestratorǁ__init____mutmut_orig.__name__ = 'xǁBatchAsyncOrchestratorǁ__init__'
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_orig(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_1(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if updates:
            logger.warning("No updates to aggregate")
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_2(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning(None)
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_3(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning("XXNo updates to aggregateXX")
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_4(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning("no updates to aggregate")
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_5(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning("NO UPDATES TO AGGREGATE")
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_6(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning("No updates to aggregate")
            return np.zeros_like(None)
        
        # Filter Byzantine updates
        aggregated = self.byzantine_detector.filter_and_aggregate(
            updates, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_7(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate updates using Byzantine robust mean.
        
        Returns:
            Aggregated gradient ready for model update
        """
        
        if not updates:
            logger.warning("No updates to aggregate")
            return np.zeros_like(self.model)
        
        # Filter Byzantine updates
        aggregated = None
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_8(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            None, 
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_9(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            updates, 
            method=None
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_10(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            method=AggregationMethod.MEAN
        )
        
        return aggregated
    
    def xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_11(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            updates, 
            )
        
        return aggregated
    
    xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_1': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_1, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_2': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_2, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_3': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_3, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_4': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_4, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_5': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_5, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_6': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_6, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_7': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_7, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_8': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_8, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_9': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_9, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_10': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_10, 
        'xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_11': xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_11
    }
    
    def aggregate_updates(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_orig"), object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_mutants"), args, kwargs, self)
        return result 
    
    aggregate_updates.__signature__ = _mutmut_signature(xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_orig)
    xǁBatchAsyncOrchestratorǁaggregate_updates__mutmut_orig.__name__ = 'xǁBatchAsyncOrchestratorǁaggregate_updates'
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_orig(self, current_count: int, total_nodes: int) -> bool:
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
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_1(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count > int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_2(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(None):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_3(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes / self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_4(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return False
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_5(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = None
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_6(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() + self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_7(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed >= self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_8(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(None)
            return True
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_9(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return False
        
        return False
    
    def xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_10(self, current_count: int, total_nodes: int) -> bool:
        """Check if should aggregate now"""
        # Aggregate if threshold reached
        if current_count >= int(total_nodes * self.k_threshold):
            return True
        
        # Or if timeout exceeded
        elapsed = time.time() - self.last_aggregation
        if elapsed > self.timeout:
            logger.info(f"Timeout reached ({elapsed:.1f}s), aggregating anyway")
            return True
        
        return True
    
    xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_1': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_1, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_2': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_2, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_3': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_3, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_4': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_4, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_5': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_5, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_6': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_6, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_7': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_7, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_8': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_8, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_9': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_9, 
        'xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_10': xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_10
    }
    
    def should_aggregate(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_orig"), object.__getattribute__(self, "xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    should_aggregate.__signature__ = _mutmut_signature(xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_orig)
    xǁBatchAsyncOrchestratorǁshould_aggregate__mutmut_orig.__name__ = 'xǁBatchAsyncOrchestratorǁshould_aggregate'


class StreamingOrchestrator(FLOrchestrator):
    """
    Streaming aggregation orchestrator.
    
    Applies updates incrementally without rounds.
    """
    
    def xǁStreamingOrchestratorǁ__init____mutmut_orig(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
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
    
    def xǁStreamingOrchestratorǁ__init____mutmut_1(self, model: np.ndarray, momentum: float = 1.9, 
                 initial_lr: float = 0.01):
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
    
    def xǁStreamingOrchestratorǁ__init____mutmut_2(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 1.01):
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
    
    def xǁStreamingOrchestratorǁ__init____mutmut_3(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(None, initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_4(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, None)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_5(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_6(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, )
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_7(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = None
        self.velocity = np.zeros_like(model)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_8(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = momentum
        self.velocity = None
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_9(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(None)
        self.update_count = 0
    
    def xǁStreamingOrchestratorǁ__init____mutmut_10(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = None
    
    def xǁStreamingOrchestratorǁ__init____mutmut_11(self, model: np.ndarray, momentum: float = 0.9, 
                 initial_lr: float = 0.01):
        """
        Args:
            model: Initial model
            momentum: Momentum coefficient (0-1)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(model)
        self.update_count = 1
    
    xǁStreamingOrchestratorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁStreamingOrchestratorǁ__init____mutmut_1': xǁStreamingOrchestratorǁ__init____mutmut_1, 
        'xǁStreamingOrchestratorǁ__init____mutmut_2': xǁStreamingOrchestratorǁ__init____mutmut_2, 
        'xǁStreamingOrchestratorǁ__init____mutmut_3': xǁStreamingOrchestratorǁ__init____mutmut_3, 
        'xǁStreamingOrchestratorǁ__init____mutmut_4': xǁStreamingOrchestratorǁ__init____mutmut_4, 
        'xǁStreamingOrchestratorǁ__init____mutmut_5': xǁStreamingOrchestratorǁ__init____mutmut_5, 
        'xǁStreamingOrchestratorǁ__init____mutmut_6': xǁStreamingOrchestratorǁ__init____mutmut_6, 
        'xǁStreamingOrchestratorǁ__init____mutmut_7': xǁStreamingOrchestratorǁ__init____mutmut_7, 
        'xǁStreamingOrchestratorǁ__init____mutmut_8': xǁStreamingOrchestratorǁ__init____mutmut_8, 
        'xǁStreamingOrchestratorǁ__init____mutmut_9': xǁStreamingOrchestratorǁ__init____mutmut_9, 
        'xǁStreamingOrchestratorǁ__init____mutmut_10': xǁStreamingOrchestratorǁ__init____mutmut_10, 
        'xǁStreamingOrchestratorǁ__init____mutmut_11': xǁStreamingOrchestratorǁ__init____mutmut_11
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁStreamingOrchestratorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁStreamingOrchestratorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁStreamingOrchestratorǁ__init____mutmut_orig)
    xǁStreamingOrchestratorǁ__init____mutmut_orig.__name__ = 'xǁStreamingOrchestratorǁ__init__'
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_orig(self, updates: List[ModelUpdate]) -> np.ndarray:
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
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_1(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Apply streaming aggregation to a single update.
        
        Returns:
            Aggregated update (for single node case, just return gradient)
        """
        
        if updates:
            return np.zeros_like(self.model)
        
        # For streaming, typically one update at a time
        # Apply momentum
        update = updates[0]
        gradient = update.gradient
        
        self.velocity = self.momentum * self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_2(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Apply streaming aggregation to a single update.
        
        Returns:
            Aggregated update (for single node case, just return gradient)
        """
        
        if not updates:
            return np.zeros_like(None)
        
        # For streaming, typically one update at a time
        # Apply momentum
        update = updates[0]
        gradient = update.gradient
        
        self.velocity = self.momentum * self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_3(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Apply streaming aggregation to a single update.
        
        Returns:
            Aggregated update (for single node case, just return gradient)
        """
        
        if not updates:
            return np.zeros_like(self.model)
        
        # For streaming, typically one update at a time
        # Apply momentum
        update = None
        gradient = update.gradient
        
        self.velocity = self.momentum * self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_4(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Apply streaming aggregation to a single update.
        
        Returns:
            Aggregated update (for single node case, just return gradient)
        """
        
        if not updates:
            return np.zeros_like(self.model)
        
        # For streaming, typically one update at a time
        # Apply momentum
        update = updates[1]
        gradient = update.gradient
        
        self.velocity = self.momentum * self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_5(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        gradient = None
        
        self.velocity = self.momentum * self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_6(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.velocity = None
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_7(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.velocity = self.momentum * self.velocity - gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_8(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.velocity = self.momentum / self.velocity + gradient
        
        self.update_count += 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_9(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.update_count = 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_10(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.update_count -= 1
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_11(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        self.update_count += 2
        
        return self.velocity / self.update_count
    
    def xǁStreamingOrchestratorǁaggregate_updates__mutmut_12(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        return self.velocity * self.update_count
    
    xǁStreamingOrchestratorǁaggregate_updates__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁStreamingOrchestratorǁaggregate_updates__mutmut_1': xǁStreamingOrchestratorǁaggregate_updates__mutmut_1, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_2': xǁStreamingOrchestratorǁaggregate_updates__mutmut_2, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_3': xǁStreamingOrchestratorǁaggregate_updates__mutmut_3, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_4': xǁStreamingOrchestratorǁaggregate_updates__mutmut_4, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_5': xǁStreamingOrchestratorǁaggregate_updates__mutmut_5, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_6': xǁStreamingOrchestratorǁaggregate_updates__mutmut_6, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_7': xǁStreamingOrchestratorǁaggregate_updates__mutmut_7, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_8': xǁStreamingOrchestratorǁaggregate_updates__mutmut_8, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_9': xǁStreamingOrchestratorǁaggregate_updates__mutmut_9, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_10': xǁStreamingOrchestratorǁaggregate_updates__mutmut_10, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_11': xǁStreamingOrchestratorǁaggregate_updates__mutmut_11, 
        'xǁStreamingOrchestratorǁaggregate_updates__mutmut_12': xǁStreamingOrchestratorǁaggregate_updates__mutmut_12
    }
    
    def aggregate_updates(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁStreamingOrchestratorǁaggregate_updates__mutmut_orig"), object.__getattribute__(self, "xǁStreamingOrchestratorǁaggregate_updates__mutmut_mutants"), args, kwargs, self)
        return result 
    
    aggregate_updates.__signature__ = _mutmut_signature(xǁStreamingOrchestratorǁaggregate_updates__mutmut_orig)
    xǁStreamingOrchestratorǁaggregate_updates__mutmut_orig.__name__ = 'xǁStreamingOrchestratorǁaggregate_updates'


class HierarchicalOrchestrator(FLOrchestrator):
    """
    Hierarchical aggregation orchestrator.
    
    Uses edge aggregators for bandwidth efficiency at 1000+ nodes.
    """
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_orig(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_1(self, model: np.ndarray, num_zones: int = 11, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_2(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 1.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_3(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(None, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_4(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, None)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_5(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_6(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, )
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_7(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = None
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_8(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = None
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_9(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(None)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_10(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = None
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_11(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(None) for i in range(num_zones)}
    
    def xǁHierarchicalOrchestratorǁ__init____mutmut_12(self, model: np.ndarray, num_zones: int = 10, 
                 initial_lr: float = 0.1):
        """
        Args:
            model: Initial model
            num_zones: Number of edge aggregators (zones)
            initial_lr: Initial learning rate
        """
        super().__init__(model, initial_lr)
        self.num_zones = num_zones
        self.zone_updates: Dict[int, List[ModelUpdate]] = {i: [] for i in range(num_zones)}
        self.zone_aggregates: Dict[int, np.ndarray] = {i: np.zeros_like(model) for i in range(None)}
    
    xǁHierarchicalOrchestratorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁHierarchicalOrchestratorǁ__init____mutmut_1': xǁHierarchicalOrchestratorǁ__init____mutmut_1, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_2': xǁHierarchicalOrchestratorǁ__init____mutmut_2, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_3': xǁHierarchicalOrchestratorǁ__init____mutmut_3, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_4': xǁHierarchicalOrchestratorǁ__init____mutmut_4, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_5': xǁHierarchicalOrchestratorǁ__init____mutmut_5, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_6': xǁHierarchicalOrchestratorǁ__init____mutmut_6, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_7': xǁHierarchicalOrchestratorǁ__init____mutmut_7, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_8': xǁHierarchicalOrchestratorǁ__init____mutmut_8, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_9': xǁHierarchicalOrchestratorǁ__init____mutmut_9, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_10': xǁHierarchicalOrchestratorǁ__init____mutmut_10, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_11': xǁHierarchicalOrchestratorǁ__init____mutmut_11, 
        'xǁHierarchicalOrchestratorǁ__init____mutmut_12': xǁHierarchicalOrchestratorǁ__init____mutmut_12
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁHierarchicalOrchestratorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁHierarchicalOrchestratorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁHierarchicalOrchestratorǁ__init____mutmut_orig)
    xǁHierarchicalOrchestratorǁ__init____mutmut_orig.__name__ = 'xǁHierarchicalOrchestratorǁ__init__'
    
    def xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_orig(self, zone_id: int, update: ModelUpdate):
        """Add update to a specific zone"""
        if zone_id not in self.zone_updates:
            self.zone_updates[zone_id] = []
        self.zone_updates[zone_id].append(update)
    
    def xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_1(self, zone_id: int, update: ModelUpdate):
        """Add update to a specific zone"""
        if zone_id in self.zone_updates:
            self.zone_updates[zone_id] = []
        self.zone_updates[zone_id].append(update)
    
    def xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_2(self, zone_id: int, update: ModelUpdate):
        """Add update to a specific zone"""
        if zone_id not in self.zone_updates:
            self.zone_updates[zone_id] = None
        self.zone_updates[zone_id].append(update)
    
    def xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_3(self, zone_id: int, update: ModelUpdate):
        """Add update to a specific zone"""
        if zone_id not in self.zone_updates:
            self.zone_updates[zone_id] = []
        self.zone_updates[zone_id].append(None)
    
    xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_1': xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_1, 
        'xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_2': xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_2, 
        'xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_3': xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_3
    }
    
    def add_update_to_zone(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_orig"), object.__getattribute__(self, "xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_update_to_zone.__signature__ = _mutmut_signature(xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_orig)
    xǁHierarchicalOrchestratorǁadd_update_to_zone__mutmut_orig.__name__ = 'xǁHierarchicalOrchestratorǁadd_update_to_zone'
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_orig(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_1(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = None
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_2(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(None, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_3(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, None)
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_4(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get([])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_5(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, )
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_6(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_7(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(None)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_8(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = None
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_9(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            None,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_10(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=None
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_11(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_12(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            )
        
        self.zone_aggregates[zone_id] = aggregated
        
        return aggregated
    
    def xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_13(self, zone_id: int) -> np.ndarray:
        """Aggregate updates within a zone"""
        zone_updates = self.zone_updates.get(zone_id, [])
        
        if not zone_updates:
            return np.zeros_like(self.model)
        
        # Use Byzantine robust aggregation at edge level
        aggregated = self.byzantine_detector.filter_and_aggregate(
            zone_updates,
            method=AggregationMethod.MEAN
        )
        
        self.zone_aggregates[zone_id] = None
        
        return aggregated
    
    xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_1': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_1, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_2': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_2, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_3': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_3, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_4': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_4, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_5': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_5, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_6': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_6, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_7': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_7, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_8': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_8, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_9': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_9, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_10': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_10, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_11': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_11, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_12': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_12, 
        'xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_13': xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_13
    }
    
    def aggregate_zone(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_orig"), object.__getattribute__(self, "xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_mutants"), args, kwargs, self)
        return result 
    
    aggregate_zone.__signature__ = _mutmut_signature(xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_orig)
    xǁHierarchicalOrchestratorǁaggregate_zone__mutmut_orig.__name__ = 'xǁHierarchicalOrchestratorǁaggregate_zone'
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_orig(self, updates: List[ModelUpdate]) -> np.ndarray:
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
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_1(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate zone aggregates from all edges.
        
        Returns:
            Final aggregated gradient
        """
        
        # Collect zone aggregates
        zone_grads = None
        
        if not zone_grads:
            return np.zeros_like(self.model)
        
        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_2(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate zone aggregates from all edges.
        
        Returns:
            Final aggregated gradient
        """
        
        # Collect zone aggregates
        zone_grads = [
            self.zone_aggregates[i] 
            for i in range(None) 
            if i in self.zone_aggregates
        ]
        
        if not zone_grads:
            return np.zeros_like(self.model)
        
        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_3(self, updates: List[ModelUpdate]) -> np.ndarray:
        """
        Aggregate zone aggregates from all edges.
        
        Returns:
            Final aggregated gradient
        """
        
        # Collect zone aggregates
        zone_grads = [
            self.zone_aggregates[i] 
            for i in range(self.num_zones) 
            if i not in self.zone_aggregates
        ]
        
        if not zone_grads:
            return np.zeros_like(self.model)
        
        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_4(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        
        if zone_grads:
            return np.zeros_like(self.model)
        
        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_5(self, updates: List[ModelUpdate]) -> np.ndarray:
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
            return np.zeros_like(None)
        
        # Final aggregation: mean of zone aggregates
        return np.mean(np.array(zone_grads), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_6(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(None, axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_7(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(np.array(zone_grads), axis=None)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_8(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_9(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(np.array(zone_grads), )
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_10(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(np.array(None), axis=0)
    
    def xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_11(self, updates: List[ModelUpdate]) -> np.ndarray:
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
        return np.mean(np.array(zone_grads), axis=1)
    
    xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_1': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_1, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_2': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_2, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_3': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_3, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_4': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_4, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_5': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_5, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_6': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_6, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_7': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_7, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_8': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_8, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_9': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_9, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_10': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_10, 
        'xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_11': xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_11
    }
    
    def aggregate_updates(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_orig"), object.__getattribute__(self, "xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_mutants"), args, kwargs, self)
        return result 
    
    aggregate_updates.__signature__ = _mutmut_signature(xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_orig)
    xǁHierarchicalOrchestratorǁaggregate_updates__mutmut_orig.__name__ = 'xǁHierarchicalOrchestratorǁaggregate_updates'


class FLTrainingSession:
    """Manages a complete federated learning training session"""
    
    def xǁFLTrainingSessionǁ__init____mutmut_orig(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
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
    
    def xǁFLTrainingSessionǁ__init____mutmut_1(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 101):
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
    
    def xǁFLTrainingSessionǁ__init____mutmut_2(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = None
        self.orchestrator = orchestrator
        self.max_rounds = max_rounds
        self.current_round = 0
        self.convergence_round = None
    
    def xǁFLTrainingSessionǁ__init____mutmut_3(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = model.copy()
        self.orchestrator = None
        self.max_rounds = max_rounds
        self.current_round = 0
        self.convergence_round = None
    
    def xǁFLTrainingSessionǁ__init____mutmut_4(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = model.copy()
        self.orchestrator = orchestrator
        self.max_rounds = None
        self.current_round = 0
        self.convergence_round = None
    
    def xǁFLTrainingSessionǁ__init____mutmut_5(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = model.copy()
        self.orchestrator = orchestrator
        self.max_rounds = max_rounds
        self.current_round = None
        self.convergence_round = None
    
    def xǁFLTrainingSessionǁ__init____mutmut_6(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
        """
        Args:
            model: Initial model
            orchestrator: FL aggregation orchestrator
            max_rounds: Maximum training rounds
        """
        self.model = model.copy()
        self.orchestrator = orchestrator
        self.max_rounds = max_rounds
        self.current_round = 1
        self.convergence_round = None
    
    def xǁFLTrainingSessionǁ__init____mutmut_7(self, model: np.ndarray, 
                 orchestrator: FLOrchestrator,
                 max_rounds: int = 100):
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
        self.convergence_round = ""
    
    xǁFLTrainingSessionǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLTrainingSessionǁ__init____mutmut_1': xǁFLTrainingSessionǁ__init____mutmut_1, 
        'xǁFLTrainingSessionǁ__init____mutmut_2': xǁFLTrainingSessionǁ__init____mutmut_2, 
        'xǁFLTrainingSessionǁ__init____mutmut_3': xǁFLTrainingSessionǁ__init____mutmut_3, 
        'xǁFLTrainingSessionǁ__init____mutmut_4': xǁFLTrainingSessionǁ__init____mutmut_4, 
        'xǁFLTrainingSessionǁ__init____mutmut_5': xǁFLTrainingSessionǁ__init____mutmut_5, 
        'xǁFLTrainingSessionǁ__init____mutmut_6': xǁFLTrainingSessionǁ__init____mutmut_6, 
        'xǁFLTrainingSessionǁ__init____mutmut_7': xǁFLTrainingSessionǁ__init____mutmut_7
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLTrainingSessionǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁFLTrainingSessionǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁFLTrainingSessionǁ__init____mutmut_orig)
    xǁFLTrainingSessionǁ__init____mutmut_orig.__name__ = 'xǁFLTrainingSessionǁ__init__'
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_orig(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_1(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = None
        
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_2(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = None
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_3(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = None
        agg_time = (time.time() - agg_start) * 1000  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_4(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(None)
        agg_time = (time.time() - agg_start) * 1000  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_5(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(updates)
        agg_time = None  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_6(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(updates)
        agg_time = (time.time() - agg_start) / 1000  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_7(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(updates)
        agg_time = (time.time() + agg_start) * 1000  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_8(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
        """
        Execute one training round.
        
        Returns:
            Statistics for this round
        """
        
        round_start = time.time()
        
        # Aggregate updates
        agg_start = time.time()
        gradient = self.orchestrator.aggregate_updates(updates)
        agg_time = (time.time() - agg_start) * 1001  # ms
        
        # Get learning rate
        gradient_norm = np.linalg.norm(gradient)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_9(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        gradient_norm = None
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_10(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        gradient_norm = np.linalg.norm(None)
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_11(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        avg_staleness = None
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_12(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        avg_staleness = np.mean(None) if updates else 0
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_13(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        avg_staleness = np.mean([u.staleness for u in updates]) if updates else 1
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_14(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        lr = None
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_15(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        lr = self.orchestrator.lr_scheduler.get_lr(None, gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_16(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, None)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_17(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        lr = self.orchestrator.lr_scheduler.get_lr(gradient_norm)
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_18(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        lr = self.orchestrator.lr_scheduler.get_lr(avg_staleness, )
        
        # Update model
        self.orchestrator.update_model(gradient, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_19(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        self.orchestrator.update_model(None, lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_20(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        self.orchestrator.update_model(gradient, None)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_21(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        self.orchestrator.update_model(lr)
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_22(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        self.orchestrator.update_model(gradient, )
        self.model = self.orchestrator.model.copy()
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_23(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        self.model = None
        
        # Check convergence
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_24(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = None
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_25(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged or self.convergence_round is None:
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_26(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is not None:
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_27(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = None
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_28(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(None)
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_29(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = None  # ms
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_30(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) / 1000  # ms
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_31(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() + round_start) * 1000  # ms
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_32(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1001  # ms
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_33(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = None
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_34(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=None,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_35(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=None,
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_36(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=None,  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_37(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=None,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_38(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            loss=None,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_39(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            accuracy=None,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_40(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            aggregation_time_ms=None,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_41(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            total_round_time_ms=None,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_42(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            learning_rate=None,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_43(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            gradient_norm=None,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_44(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=None
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_45(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_46(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_47(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_48(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_49(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_50(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_51(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_52(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_53(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_54(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_55(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_56(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(None, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_57(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, None),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_58(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_59(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, ),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_60(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(1, len(updates) - 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_61(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) + 1),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_62(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 2),  # Approximate
            byzantine_detected=0,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_63(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
        if is_converged and self.convergence_round is None:
            self.convergence_round = self.current_round
            logger.info(f"Convergence detected at round {self.current_round}: {reason}")
        
        # Record stats
        round_time = (time.time() - round_start) * 1000  # ms
        
        stats = TrainingRoundStats(
            round_number=self.current_round,
            updates_received=len(updates),
            updates_used=max(0, len(updates) - 1),  # Approximate
            byzantine_detected=1,  # Would be populated by detector
            loss=loss,
            accuracy=accuracy,
            aggregation_time_ms=agg_time,
            total_round_time_ms=round_time,
            learning_rate=lr,
            gradient_norm=gradient_norm,
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_64(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(None)
        self.current_round += 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_65(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round = 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_66(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round -= 1
        
        return stats
    
    def xǁFLTrainingSessionǁtraining_round__mutmut_67(self, updates: List[ModelUpdate], 
                      loss: float, accuracy: float) -> TrainingRoundStats:
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
        is_converged, reason = self.orchestrator.convergence_detector.check_convergence()
        
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
            converged=is_converged
        )
        
        self.orchestrator.record_stats(stats)
        self.current_round += 2
        
        return stats
    
    xǁFLTrainingSessionǁtraining_round__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLTrainingSessionǁtraining_round__mutmut_1': xǁFLTrainingSessionǁtraining_round__mutmut_1, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_2': xǁFLTrainingSessionǁtraining_round__mutmut_2, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_3': xǁFLTrainingSessionǁtraining_round__mutmut_3, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_4': xǁFLTrainingSessionǁtraining_round__mutmut_4, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_5': xǁFLTrainingSessionǁtraining_round__mutmut_5, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_6': xǁFLTrainingSessionǁtraining_round__mutmut_6, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_7': xǁFLTrainingSessionǁtraining_round__mutmut_7, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_8': xǁFLTrainingSessionǁtraining_round__mutmut_8, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_9': xǁFLTrainingSessionǁtraining_round__mutmut_9, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_10': xǁFLTrainingSessionǁtraining_round__mutmut_10, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_11': xǁFLTrainingSessionǁtraining_round__mutmut_11, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_12': xǁFLTrainingSessionǁtraining_round__mutmut_12, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_13': xǁFLTrainingSessionǁtraining_round__mutmut_13, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_14': xǁFLTrainingSessionǁtraining_round__mutmut_14, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_15': xǁFLTrainingSessionǁtraining_round__mutmut_15, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_16': xǁFLTrainingSessionǁtraining_round__mutmut_16, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_17': xǁFLTrainingSessionǁtraining_round__mutmut_17, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_18': xǁFLTrainingSessionǁtraining_round__mutmut_18, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_19': xǁFLTrainingSessionǁtraining_round__mutmut_19, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_20': xǁFLTrainingSessionǁtraining_round__mutmut_20, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_21': xǁFLTrainingSessionǁtraining_round__mutmut_21, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_22': xǁFLTrainingSessionǁtraining_round__mutmut_22, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_23': xǁFLTrainingSessionǁtraining_round__mutmut_23, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_24': xǁFLTrainingSessionǁtraining_round__mutmut_24, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_25': xǁFLTrainingSessionǁtraining_round__mutmut_25, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_26': xǁFLTrainingSessionǁtraining_round__mutmut_26, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_27': xǁFLTrainingSessionǁtraining_round__mutmut_27, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_28': xǁFLTrainingSessionǁtraining_round__mutmut_28, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_29': xǁFLTrainingSessionǁtraining_round__mutmut_29, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_30': xǁFLTrainingSessionǁtraining_round__mutmut_30, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_31': xǁFLTrainingSessionǁtraining_round__mutmut_31, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_32': xǁFLTrainingSessionǁtraining_round__mutmut_32, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_33': xǁFLTrainingSessionǁtraining_round__mutmut_33, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_34': xǁFLTrainingSessionǁtraining_round__mutmut_34, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_35': xǁFLTrainingSessionǁtraining_round__mutmut_35, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_36': xǁFLTrainingSessionǁtraining_round__mutmut_36, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_37': xǁFLTrainingSessionǁtraining_round__mutmut_37, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_38': xǁFLTrainingSessionǁtraining_round__mutmut_38, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_39': xǁFLTrainingSessionǁtraining_round__mutmut_39, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_40': xǁFLTrainingSessionǁtraining_round__mutmut_40, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_41': xǁFLTrainingSessionǁtraining_round__mutmut_41, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_42': xǁFLTrainingSessionǁtraining_round__mutmut_42, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_43': xǁFLTrainingSessionǁtraining_round__mutmut_43, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_44': xǁFLTrainingSessionǁtraining_round__mutmut_44, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_45': xǁFLTrainingSessionǁtraining_round__mutmut_45, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_46': xǁFLTrainingSessionǁtraining_round__mutmut_46, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_47': xǁFLTrainingSessionǁtraining_round__mutmut_47, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_48': xǁFLTrainingSessionǁtraining_round__mutmut_48, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_49': xǁFLTrainingSessionǁtraining_round__mutmut_49, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_50': xǁFLTrainingSessionǁtraining_round__mutmut_50, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_51': xǁFLTrainingSessionǁtraining_round__mutmut_51, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_52': xǁFLTrainingSessionǁtraining_round__mutmut_52, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_53': xǁFLTrainingSessionǁtraining_round__mutmut_53, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_54': xǁFLTrainingSessionǁtraining_round__mutmut_54, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_55': xǁFLTrainingSessionǁtraining_round__mutmut_55, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_56': xǁFLTrainingSessionǁtraining_round__mutmut_56, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_57': xǁFLTrainingSessionǁtraining_round__mutmut_57, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_58': xǁFLTrainingSessionǁtraining_round__mutmut_58, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_59': xǁFLTrainingSessionǁtraining_round__mutmut_59, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_60': xǁFLTrainingSessionǁtraining_round__mutmut_60, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_61': xǁFLTrainingSessionǁtraining_round__mutmut_61, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_62': xǁFLTrainingSessionǁtraining_round__mutmut_62, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_63': xǁFLTrainingSessionǁtraining_round__mutmut_63, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_64': xǁFLTrainingSessionǁtraining_round__mutmut_64, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_65': xǁFLTrainingSessionǁtraining_round__mutmut_65, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_66': xǁFLTrainingSessionǁtraining_round__mutmut_66, 
        'xǁFLTrainingSessionǁtraining_round__mutmut_67': xǁFLTrainingSessionǁtraining_round__mutmut_67
    }
    
    def training_round(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLTrainingSessionǁtraining_round__mutmut_orig"), object.__getattribute__(self, "xǁFLTrainingSessionǁtraining_round__mutmut_mutants"), args, kwargs, self)
        return result 
    
    training_round.__signature__ = _mutmut_signature(xǁFLTrainingSessionǁtraining_round__mutmut_orig)
    xǁFLTrainingSessionǁtraining_round__mutmut_orig.__name__ = 'xǁFLTrainingSessionǁtraining_round'
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_orig(self) -> bool:
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
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_1(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is None:
            logger.info(f"Training converged")
            return False
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_2(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(None)
            return False
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_3(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return True
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_4(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return False
        
        # Stop if max rounds reached
        if self.current_round > self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_5(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return False
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(None)
            return False
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_6(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return False
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return True
        
        return True
    
    def xǁFLTrainingSessionǁshould_continue__mutmut_7(self) -> bool:
        """Check if training should continue"""
        
        # Stop if converged
        if self.convergence_round is not None:
            logger.info(f"Training converged")
            return False
        
        # Stop if max rounds reached
        if self.current_round >= self.max_rounds:
            logger.info(f"Max rounds ({self.max_rounds}) reached")
            return False
        
        return False
    
    xǁFLTrainingSessionǁshould_continue__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁFLTrainingSessionǁshould_continue__mutmut_1': xǁFLTrainingSessionǁshould_continue__mutmut_1, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_2': xǁFLTrainingSessionǁshould_continue__mutmut_2, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_3': xǁFLTrainingSessionǁshould_continue__mutmut_3, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_4': xǁFLTrainingSessionǁshould_continue__mutmut_4, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_5': xǁFLTrainingSessionǁshould_continue__mutmut_5, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_6': xǁFLTrainingSessionǁshould_continue__mutmut_6, 
        'xǁFLTrainingSessionǁshould_continue__mutmut_7': xǁFLTrainingSessionǁshould_continue__mutmut_7
    }
    
    def should_continue(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁFLTrainingSessionǁshould_continue__mutmut_orig"), object.__getattribute__(self, "xǁFLTrainingSessionǁshould_continue__mutmut_mutants"), args, kwargs, self)
        return result 
    
    should_continue.__signature__ = _mutmut_signature(xǁFLTrainingSessionǁshould_continue__mutmut_orig)
    xǁFLTrainingSessionǁshould_continue__mutmut_orig.__name__ = 'xǁFLTrainingSessionǁshould_continue'


def x_create_orchestrator__mutmut_orig(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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


def x_create_orchestrator__mutmut_1(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
    """
    Factory function to create FL orchestrator.
    
    Args:
        orchestrator_type: "batch", "streaming", or "hierarchical"
        model: Initial model
        **kwargs: Additional arguments for orchestrator
    
    Returns:
        FLOrchestrator instance
    """
    
    if orchestrator_type != "batch":
        return BatchAsyncOrchestrator(model, **kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_2(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
    """
    Factory function to create FL orchestrator.
    
    Args:
        orchestrator_type: "batch", "streaming", or "hierarchical"
        model: Initial model
        **kwargs: Additional arguments for orchestrator
    
    Returns:
        FLOrchestrator instance
    """
    
    if orchestrator_type == "XXbatchXX":
        return BatchAsyncOrchestrator(model, **kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_3(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
    """
    Factory function to create FL orchestrator.
    
    Args:
        orchestrator_type: "batch", "streaming", or "hierarchical"
        model: Initial model
        **kwargs: Additional arguments for orchestrator
    
    Returns:
        FLOrchestrator instance
    """
    
    if orchestrator_type == "BATCH":
        return BatchAsyncOrchestrator(model, **kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_4(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return BatchAsyncOrchestrator(None, **kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_5(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return BatchAsyncOrchestrator(**kwargs)
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_6(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return BatchAsyncOrchestrator(model, )
    elif orchestrator_type == "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_7(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type != "streaming":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_8(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type == "XXstreamingXX":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_9(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type == "STREAMING":
        return StreamingOrchestrator(model, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_10(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return StreamingOrchestrator(None, **kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_11(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return StreamingOrchestrator(**kwargs)
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_12(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return StreamingOrchestrator(model, )
    elif orchestrator_type == "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_13(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type != "hierarchical":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_14(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type == "XXhierarchicalXX":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_15(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
    elif orchestrator_type == "HIERARCHICAL":
        return HierarchicalOrchestrator(model, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_16(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return HierarchicalOrchestrator(None, **kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_17(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return HierarchicalOrchestrator(**kwargs)
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_18(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        return HierarchicalOrchestrator(model, )
    else:
        raise ValueError(f"Unknown orchestrator type: {orchestrator_type}")


def x_create_orchestrator__mutmut_19(orchestrator_type: str, model: np.ndarray, 
                       **kwargs) -> FLOrchestrator:
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
        raise ValueError(None)

x_create_orchestrator__mutmut_mutants : ClassVar[MutantDict] = {
'x_create_orchestrator__mutmut_1': x_create_orchestrator__mutmut_1, 
    'x_create_orchestrator__mutmut_2': x_create_orchestrator__mutmut_2, 
    'x_create_orchestrator__mutmut_3': x_create_orchestrator__mutmut_3, 
    'x_create_orchestrator__mutmut_4': x_create_orchestrator__mutmut_4, 
    'x_create_orchestrator__mutmut_5': x_create_orchestrator__mutmut_5, 
    'x_create_orchestrator__mutmut_6': x_create_orchestrator__mutmut_6, 
    'x_create_orchestrator__mutmut_7': x_create_orchestrator__mutmut_7, 
    'x_create_orchestrator__mutmut_8': x_create_orchestrator__mutmut_8, 
    'x_create_orchestrator__mutmut_9': x_create_orchestrator__mutmut_9, 
    'x_create_orchestrator__mutmut_10': x_create_orchestrator__mutmut_10, 
    'x_create_orchestrator__mutmut_11': x_create_orchestrator__mutmut_11, 
    'x_create_orchestrator__mutmut_12': x_create_orchestrator__mutmut_12, 
    'x_create_orchestrator__mutmut_13': x_create_orchestrator__mutmut_13, 
    'x_create_orchestrator__mutmut_14': x_create_orchestrator__mutmut_14, 
    'x_create_orchestrator__mutmut_15': x_create_orchestrator__mutmut_15, 
    'x_create_orchestrator__mutmut_16': x_create_orchestrator__mutmut_16, 
    'x_create_orchestrator__mutmut_17': x_create_orchestrator__mutmut_17, 
    'x_create_orchestrator__mutmut_18': x_create_orchestrator__mutmut_18, 
    'x_create_orchestrator__mutmut_19': x_create_orchestrator__mutmut_19
}

def create_orchestrator(*args, **kwargs):
    result = _mutmut_trampoline(x_create_orchestrator__mutmut_orig, x_create_orchestrator__mutmut_mutants, args, kwargs)
    return result 

create_orchestrator.__signature__ = _mutmut_signature(x_create_orchestrator__mutmut_orig)
x_create_orchestrator__mutmut_orig.__name__ = 'x_create_orchestrator'
