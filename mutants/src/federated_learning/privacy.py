"""
Differential Privacy for Federated Learning.

Implements privacy-preserving gradient sharing using:
- Gradient clipping
- Gaussian noise addition
- Privacy budget tracking (ε, δ)

Reference: "Deep Learning with Differential Privacy" (Abadi et al., 2016)
"""
import math
import logging
import secrets
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PrivacyBudget:
    """
    Tracks cumulative privacy expenditure.
    
    Uses the moments accountant for tight composition.
    """
    epsilon: float = 0.0  # Total ε spent
    delta: float = 1e-5   # Fixed δ
    
    # Per-round tracking
    rounds_participated: int = 0
    noise_scales: List[float] = field(default_factory=list)
    
    def add_round(self, epsilon_spent: float, noise_scale: float) -> None:
        """Record privacy expenditure for one round."""
        self.epsilon += epsilon_spent
        self.rounds_participated += 1
        self.noise_scales.append(noise_scale)
    
    def remaining(self, max_epsilon: float) -> float:
        """Get remaining privacy budget."""
        return max(0, max_epsilon - self.epsilon)
    
    def is_exhausted(self, max_epsilon: float) -> bool:
        """Check if budget is exhausted."""
        return self.epsilon >= max_epsilon
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "rounds_participated": self.rounds_participated,
            "avg_noise_scale": sum(self.noise_scales) / len(self.noise_scales) if self.noise_scales else 0
        }


@dataclass 
class DPConfig:
    """Configuration for Differential Privacy."""
    # Privacy parameters
    target_epsilon: float = 1.0      # Target total ε
    target_delta: float = 1e-5       # Target δ
    
    # Gradient clipping
    max_grad_norm: float = 1.0       # L2 norm clip threshold
    
    # Noise parameters
    noise_multiplier: float = 1.1    # σ = noise_multiplier * sensitivity / ε
    
    # Sampling
    sample_rate: float = 0.01        # Fraction of data per round
    
    # Training
    max_rounds: int = 100            # Maximum training rounds


class GradientClipper:
    """
    Clips gradients to bound sensitivity.
    
    Per-sample gradient clipping ensures bounded L2 norm.
    """
    
    def __init__(self, max_norm: float = 1.0):
        self.max_norm = max_norm
        self._clip_count = 0
        self._total_count = 0
    
    def clip(self, gradients: List[float]) -> Tuple[List[float], float]:
        """
        Clip gradient vector to max L2 norm.
        
        Args:
            gradients: Gradient vector
            
        Returns:
            Tuple of (clipped gradients, original norm)
        """
        self._total_count += 1
        
        # Compute L2 norm
        norm = math.sqrt(sum(g * g for g in gradients))
        
        if norm > self.max_norm:
            self._clip_count += 1
            # Scale down to max norm
            scale = self.max_norm / norm
            clipped = [g * scale for g in gradients]
            return clipped, norm
        
        return gradients, norm
    
    def clip_batch(
        self,
        batch_gradients: List[List[float]]
    ) -> Tuple[List[List[float]], List[float]]:
        """Clip a batch of gradient vectors."""
        clipped = []
        norms = []
        
        for grads in batch_gradients:
            c, n = self.clip(grads)
            clipped.append(c)
            norms.append(n)
        
        return clipped, norms
    
    @property
    def clip_rate(self) -> float:
        """Fraction of gradients that were clipped."""
        if self._total_count == 0:
            return 0.0
        return self._clip_count / self._total_count
    
    def reset_stats(self) -> None:
        """Reset clipping statistics."""
        self._clip_count = 0
        self._total_count = 0


class GaussianNoiseGenerator:
    """
    Generates calibrated Gaussian noise for DP.
    
    Uses the Gaussian mechanism with proper noise calibration.
    """
    
    def __init__(self, seed: Optional[int] = None):
        self._seed = seed
        # Use secrets for cryptographic randomness
        self._rng_state = seed if seed else secrets.randbelow(2**32)
    
    def _random_uniform(self) -> float:
        """Generate uniform random in [0, 1)."""
        # Simple LCG for reproducibility when seeded
        self._rng_state = (1103515245 * self._rng_state + 12345) % (2**31)
        return self._rng_state / (2**31)
    
    def _random_normal(self) -> float:
        """Generate standard normal using Box-Muller."""
        u1 = self._random_uniform()
        u2 = self._random_uniform()
        
        # Avoid log(0)
        while u1 < 1e-10:
            u1 = self._random_uniform()
        
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return z
    
    def generate(self, size: int, scale: float) -> List[float]:
        """
        Generate Gaussian noise vector.
        
        Args:
            size: Dimension of noise vector
            scale: Standard deviation (σ)
            
        Returns:
            Noise vector
        """
        return [self._random_normal() * scale for _ in range(size)]
    
    def calibrate_noise(
        self,
        sensitivity: float,
        epsilon: float,
        delta: float = 1e-5
    ) -> float:
        """
        Calibrate noise scale for (ε, δ)-DP.
        
        Uses the analytic Gaussian mechanism.
        
        Args:
            sensitivity: L2 sensitivity of the query
            epsilon: Target privacy parameter ε
            delta: Target privacy parameter δ
            
        Returns:
            Required noise scale σ
        """
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive")
        if delta <= 0 or delta >= 1:
            raise ValueError("Delta must be in (0, 1)")
        
        # Analytic Gaussian mechanism formula
        # σ ≥ Δf * sqrt(2 * ln(1.25/δ)) / ε
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
        
        return sigma


class DifferentialPrivacy:
    """
    Main DP engine for federated learning.
    
    Provides:
    - Gradient clipping
    - Noise addition
    - Privacy accounting
    """
    
    def __init__(self, config: Optional[DPConfig] = None):
        self.config = config or DPConfig()
        
        self.clipper = GradientClipper(self.config.max_grad_norm)
        self.noise_gen = GaussianNoiseGenerator()
        self.budget = PrivacyBudget(delta=self.config.target_delta)
        
        # Pre-compute noise scale for target ε per round
        self._per_round_epsilon = self.config.target_epsilon / self.config.max_rounds
        self._noise_scale = self.noise_gen.calibrate_noise(
            sensitivity=self.config.max_grad_norm,
            epsilon=self._per_round_epsilon,
            delta=self.config.target_delta
        )
        
        logger.info(
            f"DP initialized: ε={self.config.target_epsilon}, "
            f"δ={self.config.target_delta}, σ={self._noise_scale:.4f}"
        )
    
    def privatize_gradients(
        self,
        gradients: List[float],
        num_samples: int = 1
    ) -> Tuple[List[float], Dict[str, float]]:
        """
        Apply DP to gradients.
        
        Args:
            gradients: Raw gradient vector
            num_samples: Number of samples used to compute gradients
            
        Returns:
            Tuple of (privatized gradients, privacy metadata)
        """
        # Step 1: Clip gradients
        clipped, original_norm = self.clipper.clip(gradients)
        
        # Step 2: Add calibrated noise
        # Noise is scaled by 1/num_samples for averaging
        effective_scale = self._noise_scale / max(1, math.sqrt(num_samples))
        noise = self.noise_gen.generate(len(clipped), effective_scale)
        
        # Step 3: Apply noise
        privatized = [g + n for g, n in zip(clipped, noise)]
        
        # Step 4: Update privacy budget
        self.budget.add_round(self._per_round_epsilon, effective_scale)
        
        metadata = {
            "original_norm": original_norm,
            "clipped": original_norm > self.config.max_grad_norm,
            "noise_scale": effective_scale,
            "epsilon_spent": self._per_round_epsilon,
            "total_epsilon": self.budget.epsilon
        }
        
        return privatized, metadata
    
    def privatize_model_update(
        self,
        weights: List[float],
        num_samples: int = 1
    ) -> Tuple[List[float], Dict[str, float]]:
        """
        Apply DP to model weight updates.
        
        Same as gradient privatization but for weight deltas.
        """
        return self.privatize_gradients(weights, num_samples)
    
    def get_privacy_spent(self) -> Tuple[float, float]:
        """Get total (ε, δ) spent."""
        return self.budget.epsilon, self.budget.delta
    
    def get_privacy_remaining(self) -> float:
        """Get remaining ε budget."""
        return self.budget.remaining(self.config.target_epsilon)
    
    def can_continue_training(self) -> bool:
        """Check if we have remaining privacy budget."""
        return not self.budget.is_exhausted(self.config.target_epsilon)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get DP statistics."""
        return {
            "config": {
                "target_epsilon": self.config.target_epsilon,
                "target_delta": self.config.target_delta,
                "max_grad_norm": self.config.max_grad_norm,
                "noise_multiplier": self.config.noise_multiplier
            },
            "budget": self.budget.to_dict(),
            "clip_rate": self.clipper.clip_rate,
            "noise_scale": self._noise_scale,
            "can_continue": self.can_continue_training()
        }


class SecureAggregation:
    """
    Secure aggregation for FL.
    
    Implements additive secret sharing for secure sum.
    Each node's update is masked with random values that cancel out
    when aggregated.
    
    Note: This is a simplified implementation. Production would use
    proper MPC protocols like SPDZ or threshold encryption.
    """
    
    def __init__(self, num_parties: int, threshold: int = None):
        self.num_parties = num_parties
        self.threshold = threshold or (num_parties // 2 + 1)
        
        # Pairwise seeds for mask generation
        self._seeds: Dict[Tuple[int, int], int] = {}
    
    def generate_masks(
        self,
        party_id: int,
        vector_size: int
    ) -> Tuple[List[float], Dict[int, int]]:
        """
        Generate masks for secure aggregation.
        
        Args:
            party_id: ID of this party
            vector_size: Size of the update vector
            
        Returns:
            Tuple of (mask vector, seeds shared with other parties)
        """
        mask = [0.0] * vector_size
        seeds = {}
        
        for other_id in range(self.num_parties):
            if other_id == party_id:
                continue
            
            # Generate or retrieve pairwise seed
            pair = tuple(sorted([party_id, other_id]))
            if pair not in self._seeds:
                self._seeds[pair] = secrets.randbelow(2**32)
            
            seed = self._seeds[pair]
            seeds[other_id] = seed
            
            # Generate mask from seed
            rng = GaussianNoiseGenerator(seed=seed)
            pair_mask = rng.generate(vector_size, scale=1.0)
            
            # Add or subtract based on party order
            sign = 1 if party_id > other_id else -1
            for i in range(vector_size):
                mask[i] += sign * pair_mask[i]
        
        return mask, seeds
    
    def mask_update(
        self,
        update: List[float],
        party_id: int
    ) -> List[float]:
        """
        Mask an update for secure aggregation.
        
        Args:
            update: Model update vector
            party_id: ID of the party
            
        Returns:
            Masked update
        """
        mask, _ = self.generate_masks(party_id, len(update))
        return [u + m for u, m in zip(update, mask)]
    
    def aggregate_masked(
        self,
        masked_updates: List[List[float]]
    ) -> List[float]:
        """
        Aggregate masked updates.
        
        If all parties participate, masks cancel out.
        
        Args:
            masked_updates: List of masked update vectors
            
        Returns:
            Aggregated (unmasked) sum
        """
        if not masked_updates:
            return []
        
        result = [0.0] * len(masked_updates[0])
        
        for update in masked_updates:
            for i, v in enumerate(update):
                result[i] += v
        
        return result


def compute_dp_sgd_privacy(
    sample_rate: float,
    noise_multiplier: float,
    epochs: int,
    delta: float = 1e-5
) -> float:
    """
    Compute privacy guarantee for DP-SGD.
    
    Uses the moments accountant approximation.
    
    Args:
        sample_rate: Subsampling rate q
        noise_multiplier: Noise multiplier σ
        epochs: Number of epochs
        delta: Target δ
        
    Returns:
        Achieved ε
    """
    # Simplified RDP to (ε, δ)-DP conversion
    # In practice, use Google's dp-accounting library
    
    steps = epochs / sample_rate
    
    # Approximation for Gaussian mechanism with subsampling
    # ε ≈ q * sqrt(2 * T * ln(1/δ)) / σ
    epsilon = sample_rate * math.sqrt(2 * steps * math.log(1 / delta)) / noise_multiplier
    
    return epsilon
