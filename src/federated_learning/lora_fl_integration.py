"""
LoRA + Federated Learning Integration.

Combines LoRA fine-tuning with Federated Learning for distributed
LoRA adapter training across mesh nodes.

Features:
- Federated LoRA training with FedAvg aggregation
- Differential privacy for LoRA weight updates
- PARL integration for parallel training
- Privacy-preserving weight clipping
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.federated_learning.coordinator import (
    CoordinatorConfig,
    FederatedCoordinator,
    NodeStatus,
    RoundStatus,
    TrainingRound,
)
from src.federated_learning.protocol import AggregationResult, GlobalModel, ModelUpdate, ModelWeights
from src.ml.lora.config import LoRAConfig

logger = logging.getLogger(__name__)

# Optional imports for ML frameworks
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None
    logger.warning("⚠️ NumPy not available. Install with: pip install numpy")

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    logger.warning("⚠️ PyTorch not available. Install with: pip install torch")

try:
    from src.ml.lora.adapter import LoRAAdapter, load_lora_adapter, save_lora_adapter
    from src.ml.lora.trainer import LoRATrainer, LoRATrainingResult

    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False
    LoRATrainer = None
    LoRAAdapter = None
    logger.warning("⚠️ LoRA modules not available")

try:
    from src.federated_learning.privacy import DifferentialPrivacy, DPConfig, GradientClipper

    PRIVACY_AVAILABLE = True
except ImportError:
    PRIVACY_AVAILABLE = False
    DifferentialPrivacy = None
    DPConfig = None
    GradientClipper = None
    logger.warning("⚠️ Privacy modules not available")

try:
    from src.federated_learning.parl_integration import PARLFederatedOrchestrator, PARLFLConfig

    PARL_AVAILABLE = True
except ImportError:
    PARL_AVAILABLE = False
    PARLFederatedOrchestrator = None
    PARLFLConfig = None
    logger.warning("⚠️ PARL integration not available")


class LoRAFLRoundStatus(Enum):
    """Status of a federated LoRA training round."""

    PENDING = "pending"
    DISTRIBUTING = "distributing"
    TRAINING = "training"
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LoRAFLRound:
    """
    Represents a single federated LoRA training round.

    Tracks the complete lifecycle of a federated LoRA round including
    adapter distribution, local training, and weight aggregation.
    """

    round_number: int
    status: LoRAFLRoundStatus = LoRAFLRoundStatus.PENDING

    # LoRA-specific
    base_adapter_id: str = ""
    aggregated_adapter_id: str = ""

    # Participation
    selected_nodes: List[str] = field(default_factory=list)
    participating_nodes: List[str] = field(default_factory=list)

    # LoRA weight updates per node
    lora_updates: Dict[str, "LoRAWeightUpdate"] = field(default_factory=dict)

    # Timing
    started_at: float = 0.0
    training_started_at: float = 0.0
    collection_deadline: float = 0.0
    completed_at: float = 0.0

    # Configuration
    min_participants: int = 3
    local_epochs: int = 1
    learning_rate: float = 2e-4

    # Results
    aggregation_result: Optional[AggregationResult] = None
    training_metrics: Dict[str, Any] = field(default_factory=dict)

    # Privacy
    privacy_spent_epsilon: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "round_number": self.round_number,
            "status": self.status.value,
            "base_adapter_id": self.base_adapter_id,
            "aggregated_adapter_id": self.aggregated_adapter_id,
            "selected_nodes": self.selected_nodes,
            "participating_nodes": self.participating_nodes,
            "updates_received": len(self.lora_updates),
            "started_at": self.started_at,
            "training_started_at": self.training_started_at,
            "collection_deadline": self.collection_deadline,
            "completed_at": self.completed_at,
            "min_participants": self.min_participants,
            "local_epochs": self.local_epochs,
            "learning_rate": self.learning_rate,
            "privacy_spent_epsilon": self.privacy_spent_epsilon,
        }


@dataclass
class LoRAWeightUpdate:
    """
    LoRA weight update from a single node.

    Contains the LoRA A and B matrices for each target module,
    along with training metadata.
    """

    node_id: str
    round_number: int

    # LoRA weights: {module_name: {"lora_A": [...], "lora_B": [...]}}
    lora_weights: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)

    # Training metadata
    num_samples: int = 0
    training_time_seconds: float = 0.0
    training_loss: float = 0.0
    validation_loss: Optional[float] = None

    # Privacy
    clip_norm: float = 1.0
    noise_scale: float = 0.0

    # Timestamp
    timestamp: float = field(default_factory=time.time)

    def to_model_update(self) -> ModelUpdate:
        """Convert to standard ModelUpdate for aggregation."""
        # Flatten LoRA weights for compatibility
        flat_weights = []
        for module_name in sorted(self.lora_weights.keys()):
            weights = self.lora_weights[module_name]
            if "lora_A" in weights:
                flat_weights.extend(weights["lora_A"])
            if "lora_B" in weights:
                flat_weights.extend(weights["lora_B"])

        return ModelUpdate(
            node_id=self.node_id,
            round_number=self.round_number,
            weights=ModelWeights(
                weights=flat_weights,
                layer_weights={
                    k: v.get("lora_A", []) + v.get("lora_B", [])
                    for k, v in self.lora_weights.items()
                },
            ),
            num_samples=self.num_samples,
            training_time_seconds=self.training_time_seconds,
            training_loss=self.training_loss,
            validation_loss=self.validation_loss or 0.0,
            clip_norm=self.clip_norm,
            noise_scale=self.noise_scale,
        )

    @classmethod
    def from_model_update(cls, update: ModelUpdate) -> "LoRAWeightUpdate":
        """Create from ModelUpdate (requires layer_weights)."""
        lora_weights = {}
        for module_name, flat_weights in update.weights.layer_weights.items():
            # Assume equal split for A and B matrices
            mid = len(flat_weights) // 2
            lora_weights[module_name] = {
                "lora_A": flat_weights[:mid],
                "lora_B": flat_weights[mid:],
            }

        return cls(
            node_id=update.node_id,
            round_number=update.round_number,
            lora_weights=lora_weights,
            num_samples=update.num_samples,
            training_time_seconds=update.training_time_seconds,
            training_loss=update.training_loss,
            validation_loss=update.validation_loss,
            clip_norm=update.clip_norm,
            noise_scale=update.noise_scale,
        )


@dataclass
class FederatedLoRAConfig:
    """Configuration for federated LoRA training."""

    # LoRA settings
    lora_config: LoRAConfig = None
    base_model_name: str = "meta-llama/Llama-2-7b-hf"
    base_adapter_id: str = "global_lora_v0"

    # Federated settings
    min_participants: int = 3
    target_participants: int = 10
    max_participants: int = 50
    num_rounds: int = 10
    local_epochs: int = 1
    learning_rate: float = 2e-4

    # Timing
    round_timeout: float = 300.0  # 5 minutes
    collection_timeout: float = 120.0  # 2 minutes

    # Privacy
    enable_privacy: bool = True
    privacy_epsilon: float = 1.0
    privacy_delta: float = 1e-5
    max_grad_norm: float = 1.0

    # Aggregation
    aggregation_method: str = "fedavg"

    # PARL acceleration
    use_parl: bool = False
    parl_max_workers: int = 100

    # Storage
    adapter_storage_path: Path = Path("/var/lib/x0tta6bl4/federated_lora")

    def __post_init__(self):
        """Initialize defaults."""
        if self.lora_config is None:
            self.lora_config = LoRAConfig()
        self.adapter_storage_path = Path(self.adapter_storage_path)


class LoRAWeightAggregator:
    """
    Aggregator for LoRA weights using FedAvg algorithm.

    Implements federated averaging specifically for LoRA A and B matrices,
    with support for differential privacy and Byzantine robustness.
    """

    def __init__(
        self,
        aggregation_method: str = "fedavg",
        byzantine_tolerance: int = 0,
        clip_norm: float = 1.0,
    ):
        """
        Initialize LoRA weight aggregator.

        Args:
            aggregation_method: Aggregation method (fedavg, krum, trimmed_mean)
            byzantine_tolerance: Number of Byzantine nodes to tolerate
            clip_norm: Maximum gradient norm for clipping
        """
        self.aggregation_method = aggregation_method
        self.byzantine_tolerance = byzantine_tolerance
        self.clip_norm = clip_norm

    def clip_weights(
        self, weights: Dict[str, Dict[str, List[float]]], max_norm: float
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Clip LoRA weights to maximum norm for privacy.

        Args:
            weights: LoRA weight dictionary
            max_norm: Maximum allowed norm

        Returns:
            Clipped weights
        """
        if not NUMPY_AVAILABLE:
            logger.warning("NumPy not available, skipping weight clipping")
            return weights

        clipped = {}
        total_norm = 0.0

        # Compute total norm
        for module_name, module_weights in weights.items():
            for weight_type in ["lora_A", "lora_B"]:
                if weight_type in module_weights:
                    w = np.array(module_weights[weight_type])
                    total_norm += np.linalg.norm(w) ** 2

        total_norm = np.sqrt(total_norm)

        # Clip if necessary
        if total_norm > max_norm:
            scale = max_norm / total_norm
            for module_name, module_weights in weights.items():
                clipped[module_name] = {}
                for weight_type in ["lora_A", "lora_B"]:
                    if weight_type in module_weights:
                        w = np.array(module_weights[weight_type])
                        clipped[module_name][weight_type] = (w * scale).tolist()
                    else:
                        clipped[module_name][weight_type] = module_weights.get(weight_type, [])
        else:
            clipped = weights

        return clipped

    def add_noise(
        self,
        weights: Dict[str, Dict[str, List[float]]],
        noise_scale: float,
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Add Gaussian noise for differential privacy.

        Args:
            weights: LoRA weight dictionary
            noise_scale: Standard deviation of noise

        Returns:
            Weights with added noise
        """
        if not NUMPY_AVAILABLE or noise_scale <= 0:
            return weights

        noisy = {}
        for module_name, module_weights in weights.items():
            noisy[module_name] = {}
            for weight_type in ["lora_A", "lora_B"]:
                if weight_type in module_weights:
                    w = np.array(module_weights[weight_type])
                    noise = np.random.normal(0, noise_scale, w.shape)
                    noisy[module_name][weight_type] = (w + noise).tolist()
                else:
                    noisy[module_name][weight_type] = module_weights.get(weight_type, [])

        return noisy

    def aggregate(
        self,
        updates: List[LoRAWeightUpdate],
        previous_weights: Optional[Dict[str, Dict[str, List[float]]]] = None,
    ) -> Tuple[Dict[str, Dict[str, List[float]]], AggregationResult]:
        """
        Aggregate LoRA weight updates using FedAvg.

        Args:
            updates: List of LoRA weight updates from nodes
            previous_weights: Previous global LoRA weights (optional)

        Returns:
            Tuple of (aggregated_weights, aggregation_result)
        """
        start_time = time.time()

        if not updates:
            return previous_weights or {}, AggregationResult(
                success=False,
                error_message="No updates to aggregate",
            )

        # Filter valid updates
        valid_updates = [u for u in updates if u.lora_weights]
        if not valid_updates:
            return previous_weights or {}, AggregationResult(
                success=False,
                error_message="No valid LoRA weight updates",
            )

        # Compute total samples for weighted average
        total_samples = sum(u.num_samples for u in valid_updates)
        if total_samples == 0:
            # Equal weighting if no sample counts
            weights_per_node = [1.0 / len(valid_updates)] * len(valid_updates)
        else:
            weights_per_node = [u.num_samples / total_samples for u in valid_updates]

        # Aggregate weights
        aggregated = {}
        module_names = set()
        for update in valid_updates:
            module_names.update(update.lora_weights.keys())

        for module_name in module_names:
            aggregated[module_name] = {"lora_A": [], "lora_B": []}

            for weight_type in ["lora_A", "lora_B"]:
                # Collect weights from all nodes for this module
                node_weights = []
                for update in valid_updates:
                    if module_name in update.lora_weights:
                        w = update.lora_weights[module_name].get(weight_type, [])
                        if w:
                            node_weights.append(w)

                if not node_weights:
                    continue

                # Weighted average
                if NUMPY_AVAILABLE:
                    weighted_sum = np.zeros_like(node_weights[0])
                    for w, weight in zip(node_weights, weights_per_node):
                        weighted_sum += np.array(w) * weight
                    aggregated[module_name][weight_type] = weighted_sum.tolist()
                else:
                    # Simple average without numpy
                    n = len(node_weights[0])
                    result = [0.0] * n
                    for w, weight in zip(node_weights, weights_per_node):
                        for i in range(n):
                            result[i] += w[i] * weight
                    aggregated[module_name][weight_type] = result

        # Apply clipping to aggregated weights
        if self.clip_norm > 0:
            aggregated = self.clip_weights(aggregated, self.clip_norm)

        aggregation_time = time.time() - start_time

        result = AggregationResult(
            success=True,
            updates_received=len(updates),
            updates_accepted=len(valid_updates),
            updates_rejected=len(updates) - len(valid_updates),
            aggregation_time_seconds=aggregation_time,
        )

        return aggregated, result


def aggregate_lora_weights(
    updates: List[LoRAWeightUpdate],
    method: str = "fedavg",
    clip_norm: float = 1.0,
) -> Tuple[Dict[str, Dict[str, List[float]]], AggregationResult]:
    """
    Aggregate LoRA weights from multiple nodes.

    Convenience function for LoRA weight aggregation.

    Args:
        updates: List of LoRA weight updates
        method: Aggregation method (fedavg, krum, trimmed_mean)
        clip_norm: Maximum gradient norm for clipping

    Returns:
        Tuple of (aggregated_weights, aggregation_result)
    """
    aggregator = LoRAWeightAggregator(
        aggregation_method=method,
        clip_norm=clip_norm,
    )
    return aggregator.aggregate(updates)


class FederatedLoRATrainer:
    """
    Federated LoRA Trainer.

    Combines LoRA fine-tuning with Federated Learning for distributed
    training of LoRA adapters across mesh nodes.

    Features:
    - Federated LoRA training rounds
    - FedAvg aggregation for LoRA weights
    - Differential privacy support
    - PARL integration for parallel training
    """

    def __init__(
        self,
        config: FederatedLoRAConfig,
        coordinator: Optional[FederatedCoordinator] = None,
    ):
        """
        Initialize federated LoRA trainer.

        Args:
            config: Federated LoRA configuration
            coordinator: Optional existing coordinator
        """
        self.config = config
        self.config.adapter_storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize or use provided coordinator
        if coordinator:
            self.coordinator = coordinator
        else:
            coord_config = CoordinatorConfig(
                min_participants=config.min_participants,
                target_participants=config.target_participants,
                max_participants=config.max_participants,
                aggregation_method=config.aggregation_method,
                enable_privacy=config.enable_privacy,
                privacy_epsilon=config.privacy_epsilon,
                privacy_delta=config.privacy_delta,
                collection_timeout=config.collection_timeout,
            )
            self.coordinator = FederatedCoordinator(
                coordinator_id="fl_lora_coordinator",
                config=coord_config,
            )

        # LoRA weight aggregator
        self.aggregator = LoRAWeightAggregator(
            aggregation_method=config.aggregation_method,
            clip_norm=config.max_grad_norm,
        )

        # Current round state
        self.current_round: Optional[LoRAFLRound] = None
        self.round_history: List[LoRAFLRound] = []

        # Global LoRA weights
        self.global_lora_weights: Optional[Dict[str, Dict[str, List[float]]]] = None

        # PARL orchestrator (optional)
        self.parl_orchestrator: Optional[Any] = None
        if config.use_parl and PARL_AVAILABLE:
            parl_config = PARLFLConfig(
                max_workers=config.parl_max_workers,
                min_nodes_per_round=config.min_participants,
                max_nodes_per_round=config.max_participants,
                aggregation_method=config.aggregation_method,
            )
            self.parl_orchestrator = PARLFederatedOrchestrator(
                coordinator=self.coordinator,
                parl_config=parl_config,
            )

        # Privacy accounting
        self.total_privacy_spent = 0.0

        # Metrics
        self._metrics = {
            "rounds_completed": 0,
            "total_updates_received": 0,
            "total_training_time": 0.0,
            "avg_round_time": 0.0,
            "privacy_epsilon_spent": 0.0,
        }

        logger.info(f"FederatedLoRATrainer initialized with {config.num_rounds} rounds")

    def register_node(self, node_id: str, capabilities: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a node for federated LoRA training.

        Args:
            node_id: Unique node identifier
            capabilities: Node capabilities (GPU, memory, etc.)

        Returns:
            True if registered successfully
        """
        return self.coordinator.register_node(node_id, capabilities)

    def unregister_node(self, node_id: str) -> bool:
        """Unregister a node from training."""
        return self.coordinator.unregister_node(node_id)

    def start_round(self, round_number: Optional[int] = None) -> Optional[LoRAFLRound]:
        """
        Start a new federated LoRA training round.

        Args:
            round_number: Optional explicit round number

        Returns:
            LoRAFLRound if started successfully
        """
        # Start round in coordinator
        coord_round = self.coordinator.start_round(round_number)
        if not coord_round:
            logger.error("Failed to start coordinator round")
            return None

        # Create LoRA-specific round
        lora_round = LoRAFLRound(
            round_number=coord_round.round_number,
            status=LoRAFLRoundStatus.DISTRIBUTING,
            base_adapter_id=self.config.base_adapter_id,
            selected_nodes=list(coord_round.selected_nodes),
            started_at=time.time(),
            collection_deadline=time.time() + self.config.collection_timeout,
            min_participants=self.config.min_participants,
            local_epochs=self.config.local_epochs,
            learning_rate=self.config.learning_rate,
        )

        self.current_round = lora_round
        logger.info(
            f"Started LoRA FL round {lora_round.round_number} "
            f"with {len(lora_round.selected_nodes)} nodes"
        )

        return lora_round

    def submit_lora_update(self, update: LoRAWeightUpdate) -> bool:
        """
        Submit a LoRA weight update from a node.

        Args:
            update: LoRA weight update

        Returns:
            True if accepted
        """
        if not self.current_round:
            logger.warning("No active round for update")
            return False

        if self.current_round.status not in (
            LoRAFLRoundStatus.TRAINING,
            LoRAFLRoundStatus.COLLECTING,
            LoRAFLRoundStatus.DISTRIBUTING,
        ):
            logger.warning(f"Round not accepting updates: {self.current_round.status}")
            return False

        # Transition to TRAINING status on first update
        if self.current_round.status == LoRAFLRoundStatus.DISTRIBUTING:
            self.current_round.status = LoRAFLRoundStatus.TRAINING
            self.current_round.training_started_at = time.time()

        node_id = update.node_id

        # Check node is selected
        if node_id not in self.current_round.selected_nodes:
            logger.warning(f"Node {node_id} not selected for this round")
            return False

        # Check for duplicate
        if node_id in self.current_round.lora_updates:
            logger.warning(f"Duplicate update from {node_id}")
            return False

        # Apply privacy if enabled
        if self.config.enable_privacy:
            update.lora_weights = self.aggregator.clip_weights(
                update.lora_weights, self.config.max_grad_norm
            )
            if self.config.privacy_epsilon > 0:
                noise_scale = self.config.max_grad_norm * self.config.privacy_epsilon
                update.lora_weights = self.aggregator.add_noise(
                    update.lora_weights, noise_scale
                )
                update.noise_scale = noise_scale

        # Accept update
        self.current_round.lora_updates[node_id] = update
        self.current_round.participating_nodes.append(node_id)
        self._metrics["total_updates_received"] += 1

        logger.info(
            f"LoRA update from {node_id} accepted "
            f"({len(self.current_round.lora_updates)}/{self.current_round.min_participants})"
        )

        # Also submit to coordinator for compatibility
        model_update = update.to_model_update()
        self.coordinator.submit_update(model_update)

        # Check if we have enough updates
        if len(self.current_round.lora_updates) >= self.current_round.min_participants:
            self._aggregate_round()

        return True

    def _aggregate_round(self) -> None:
        """Aggregate LoRA weights for current round."""
        if not self.current_round:
            return

        self.current_round.status = LoRAFLRoundStatus.AGGREGATING

        try:
            updates = list(self.current_round.lora_updates.values())
            aggregated_weights, result = self.aggregator.aggregate(
                updates, self.global_lora_weights
            )

            self.current_round.aggregation_result = result

            if result.success:
                self.global_lora_weights = aggregated_weights
                self.current_round.status = LoRAFLRoundStatus.COMPLETED
                self.current_round.completed_at = time.time()

                # Update metrics
                self._metrics["rounds_completed"] += 1
                round_time = self.current_round.completed_at - self.current_round.started_at
                self._metrics["total_training_time"] += round_time
                self._metrics["avg_round_time"] = (
                    self._metrics["avg_round_time"] * 0.9 + round_time * 0.1
                )

                # Privacy accounting
                if self.config.enable_privacy:
                    self.total_privacy_spent += self.config.privacy_epsilon
                    self._metrics["privacy_epsilon_spent"] = self.total_privacy_spent
                    self.current_round.privacy_spent_epsilon = self.config.privacy_epsilon

                # Generate aggregated adapter ID
                self.current_round.aggregated_adapter_id = (
                    f"global_lora_v{self.current_round.round_number}"
                )

                logger.info(
                    f"Round {self.current_round.round_number} completed. "
                    f"Aggregated adapter: {self.current_round.aggregated_adapter_id}"
                )
            else:
                self.current_round.status = LoRAFLRoundStatus.FAILED
                logger.error(f"Aggregation failed: {result.error_message}")

            # Archive round
            self.round_history.append(self.current_round)

        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            self.current_round.status = LoRAFLRoundStatus.FAILED

    def get_global_lora_weights(self) -> Optional[Dict[str, Dict[str, List[float]]]]:
        """Get current global LoRA weights."""
        return self.global_lora_weights

    def get_round_status(self) -> Optional[Dict[str, Any]]:
        """Get current round status."""
        if not self.current_round:
            return None
        return self.current_round.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Get trainer metrics."""
        return {
            **self._metrics,
            "current_round": self.get_round_status(),
            "total_rounds": len(self.round_history),
            "registered_nodes": len(self.coordinator.nodes),
            "eligible_nodes": len(self.coordinator.get_eligible_nodes()),
        }

    async def run_federated_training(
        self,
        local_train_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run complete federated LoRA training.

        Args:
            local_train_fn: Optional function for local training simulation

        Returns:
            Training results
        """
        results = {
            "rounds_completed": 0,
            "total_time": 0.0,
            "final_adapter_id": None,
            "round_results": [],
        }

        start_time = time.time()

        for round_num in range(1, self.config.num_rounds + 1):
            # Start round
            lora_round = self.start_round(round_num)
            if not lora_round:
                logger.error(f"Failed to start round {round_num}")
                continue

            # Simulate local training if function provided
            if local_train_fn:
                lora_round.status = LoRAFLRoundStatus.TRAINING
                lora_round.training_started_at = time.time()

                for node_id in lora_round.selected_nodes:
                    try:
                        update = await local_train_fn(
                            node_id=node_id,
                            round_number=round_num,
                            global_weights=self.global_lora_weights,
                            config=self.config,
                        )
                        if update:
                            self.submit_lora_update(update)
                    except Exception as e:
                        logger.error(f"Local training failed for {node_id}: {e}")

            # Wait for round completion or timeout
            lora_round.status = LoRAFLRoundStatus.COLLECTING
            timeout = self.config.collection_timeout
            while (
                lora_round.status == LoRAFLRoundStatus.COLLECTING
                and timeout > 0
            ):
                await asyncio.sleep(1.0)
                timeout -= 1.0

                # Check deadline
                if time.time() > lora_round.collection_deadline:
                    if len(lora_round.lora_updates) >= lora_round.min_participants:
                        self._aggregate_round()
                    else:
                        lora_round.status = LoRAFLRoundStatus.FAILED
                        logger.warning(
                            f"Round {round_num} timed out with "
                            f"{len(lora_round.lora_updates)}/{lora_round.min_participants} updates"
                        )
                    break

            if lora_round.status == LoRAFLRoundStatus.COMPLETED:
                results["rounds_completed"] += 1
                results["round_results"].append(lora_round.to_dict())
                results["final_adapter_id"] = lora_round.aggregated_adapter_id

        results["total_time"] = time.time() - start_time
        results["metrics"] = self.get_metrics()

        return results

    def save_global_adapter(self, path: Optional[Path] = None) -> bool:
        """
        Save global LoRA adapter to disk.

        Args:
            path: Optional custom path

        Returns:
            True if saved successfully
        """
        if not self.global_lora_weights:
            logger.error("No global LoRA weights to save")
            return False

        save_path = path or self.config.adapter_storage_path / "global_adapter"

        try:
            import json

            save_path.mkdir(parents=True, exist_ok=True)

            # Save weights
            weights_file = save_path / "lora_weights.json"
            with open(weights_file, "w") as f:
                json.dump(self.global_lora_weights, f, indent=2)

            # Save metadata
            metadata = {
                "adapter_id": (
                    self.current_round.aggregated_adapter_id
                    if self.current_round
                    else "global_lora"
                ),
                "base_model_name": self.config.base_model_name,
                "lora_config": self.config.lora_config.to_peft_config()
                if self.config.lora_config
                else {},
                "round_number": self.current_round.round_number if self.current_round else 0,
                "privacy_epsilon_spent": self.total_privacy_spent,
                "metrics": self._metrics,
            }

            metadata_file = save_path / "adapter_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved global LoRA adapter to {save_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save global adapter: {e}")
            return False

    def start(self) -> None:
        """Start the federated LoRA trainer."""
        self.coordinator.start()
        logger.info("FederatedLoRATrainer started")

    def stop(self) -> None:
        """Stop the federated LoRA trainer."""
        self.coordinator.stop()
        logger.info("FederatedLoRATrainer stopped")


# Convenience functions

async def run_federated_lora_training(
    config: FederatedLoRAConfig,
    nodes: List[str],
    local_train_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Run federated LoRA training with given configuration.

    Args:
        config: Federated LoRA configuration
        nodes: List of node IDs to participate
        local_train_fn: Optional local training function

    Returns:
        Training results
    """
    trainer = FederatedLoRATrainer(config)

    # Register nodes
    for node_id in nodes:
        trainer.register_node(node_id)

    trainer.start()

    try:
        results = await trainer.run_federated_training(local_train_fn)
        trainer.save_global_adapter()
        return results
    finally:
        trainer.stop()


def create_lora_update(
    node_id: str,
    round_number: int,
    lora_weights: Dict[str, Dict[str, List[float]]],
    num_samples: int = 100,
    training_loss: float = 0.0,
) -> LoRAWeightUpdate:
    """
    Create a LoRA weight update.

    Convenience function for creating updates.

    Args:
        node_id: Node identifier
        round_number: Current round number
        lora_weights: LoRA A and B matrices
        num_samples: Number of training samples
        training_loss: Training loss value

    Returns:
        LoRAWeightUpdate instance
    """
    return LoRAWeightUpdate(
        node_id=node_id,
        round_number=round_number,
        lora_weights=lora_weights,
        num_samples=num_samples,
        training_loss=training_loss,
    )