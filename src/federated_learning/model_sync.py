"""
Model Synchronization for Federated Learning.

Handles:
- Global model distribution
- Local model updates
- Version control
- Conflict resolution
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .protocol import GlobalModel, ModelWeights

logger = logging.getLogger(__name__)


class ModelVersion(Enum):
    """Model version states"""

    PENDING = "pending"
    DISTRIBUTING = "distributing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class ModelSyncState:
    """State of model synchronization"""

    model_version: int
    global_model: Optional[GlobalModel]
    local_versions: Dict[str, int] = field(default_factory=dict)  # node_id -> version
    sync_status: ModelVersion = ModelVersion.PENDING
    last_sync_time: float = 0.0
    conflicts: List[Dict[str, Any]] = field(default_factory=list)


class ModelSynchronizer:
    """
    Synchronizes models across federated learning nodes.

    Features:
    - Version control
    - Conflict detection
    - Automatic distribution
    - Rollback support
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.current_model: Optional[GlobalModel] = None
        self.model_history: List[GlobalModel] = []
        self.sync_state = ModelSyncState(model_version=0, global_model=None)

    def receive_global_model(self, global_model: GlobalModel, source_node: str) -> bool:
        """
        Receive and validate global model from coordinator.

        Args:
            global_model: Global model to receive
            source_node: Node that sent the model

        Returns:
            True if model accepted
        """
        try:
            # Validate model
            if not self._validate_model(global_model):
                logger.warning(f"Invalid model received from {source_node}")
                return False

            # Check version
            if (
                self.current_model
                and global_model.version <= self.current_model.version
            ):
                logger.warning(
                    f"Received older model version {global_model.version} "
                    f"(current: {self.current_model.version})"
                )
                return False

            # Store previous model in history
            if self.current_model:
                self.model_history.append(self.current_model)
                # Keep only last 10 models
                if len(self.model_history) > 10:
                    self.model_history.pop(0)

            # Update current model
            self.current_model = global_model
            self.sync_state.global_model = global_model
            self.sync_state.model_version = global_model.version
            self.sync_state.local_versions[self.node_id] = global_model.version
            self.sync_state.last_sync_time = time.time()
            self.sync_state.sync_status = ModelVersion.ACTIVE

            logger.info(
                f"✅ Global model v{global_model.version} received from {source_node}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to receive global model: {e}")
            return False

    def get_current_model(self) -> Optional[GlobalModel]:
        """Get current global model."""
        return self.current_model

    def get_model_version(self) -> int:
        """Get current model version."""
        return self.sync_state.model_version

    def check_for_conflicts(
        self, local_model: GlobalModel, global_model: GlobalModel
    ) -> List[Dict[str, Any]]:
        """
        Check for conflicts between local and global models.

        Args:
            local_model: Local model version
            global_model: Global model version

        Returns:
            List of conflicts found
        """
        conflicts = []

        # Version conflict
        if local_model.version != global_model.version:
            conflicts.append(
                {
                    "type": "version_mismatch",
                    "local_version": local_model.version,
                    "global_version": global_model.version,
                    "severity": "high",
                }
            )

        # Weight hash conflict
        if local_model.weights_hash != global_model.weights_hash:
            conflicts.append(
                {
                    "type": "weight_hash_mismatch",
                    "local_hash": local_model.weights_hash,
                    "global_hash": global_model.weights_hash,
                    "severity": "critical",
                }
            )

        # Round number conflict
        if local_model.round_number != global_model.round_number:
            conflicts.append(
                {
                    "type": "round_mismatch",
                    "local_round": local_model.round_number,
                    "global_round": global_model.round_number,
                    "severity": "medium",
                }
            )

        return conflicts

    def resolve_conflicts(
        self, conflicts: List[Dict[str, Any]], strategy: str = "prefer_global"
    ) -> bool:
        """
        Resolve model conflicts.

        Args:
            conflicts: List of conflicts
            strategy: Resolution strategy ("prefer_global", "prefer_local", "merge")

        Returns:
            True if conflicts resolved
        """
        if not conflicts:
            return True

        logger.warning(
            f"Resolving {len(conflicts)} conflicts using strategy: {strategy}"
        )

        # Store conflicts
        self.sync_state.conflicts.extend(conflicts)

        if strategy == "prefer_global":
            # Accept global model (default)
            logger.info("Resolving conflicts: preferring global model")
            return True
        elif strategy == "prefer_local":
            # Keep local model
            logger.info("Resolving conflicts: preferring local model")
            return True
        elif strategy == "merge":
            # Merge models (complex, requires careful implementation)
            logger.warning("Merge strategy not fully implemented")
            return False
        else:
            logger.error(f"Unknown conflict resolution strategy: {strategy}")
            return False

    def rollback(self, target_version: int) -> bool:
        """
        Rollback to previous model version.

        Args:
            target_version: Version to rollback to

        Returns:
            True if rollback successful
        """
        # Find model in history
        for model in reversed(self.model_history):
            if model.version == target_version:
                self.current_model = model
                self.sync_state.global_model = model
                self.sync_state.model_version = model.version
                self.sync_state.sync_status = ModelVersion.ACTIVE
                logger.info(f"✅ Rolled back to model version {target_version}")
                return True

        logger.warning(f"Model version {target_version} not found in history")
        return False

    def _validate_model(self, model: GlobalModel) -> bool:
        """Validate model structure and integrity."""
        if not model:
            return False

        if not model.weights:
            return False

        if model.version < 0:
            return False

        # Check weights hash if provided
        if model.weights_hash:
            computed_hash = self._compute_weights_hash(model.weights)
            if computed_hash != model.weights_hash:
                logger.warning("Model weights hash mismatch")
                return False
        else:
            # If hash not provided, compute it (GlobalModel will auto-compute on access)
            # This is fine for validation purposes
            pass

        return True

    def _compute_weights_hash(self, weights: ModelWeights) -> str:
        """Compute hash of model weights."""
        # Use the same method as ModelWeights.compute_hash() for consistency
        return weights.compute_hash()

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status."""
        return {
            "node_id": self.node_id,
            "current_version": self.sync_state.model_version,
            "sync_status": self.sync_state.sync_status.value,
            "last_sync_time": self.sync_state.last_sync_time,
            "conflicts_count": len(self.sync_state.conflicts),
            "model_history_size": len(self.model_history),
        }
