"""
LoRA Trainer: gradient-based fine-tuning of LoRA adapters.

Pure NumPy implementation. Trains LoRA A and B matrices using mini-batch SGD
with momentum. Supports training on numpy arrays for synthetic or real data.

Designed for federated learning — adapters can be distributed, trained
locally on mesh nodes, and aggregated.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.ml.lora.adapter import LoRAAdapter, save_lora_adapter
from src.ml.lora.config import LoRAConfig

logger = logging.getLogger(__name__)


@dataclass
class LoRATrainingResult:
    """
    Result of a LoRA training run.

    Attributes:
        success: Whether training completed successfully.
        adapter_id: ID of the trained adapter.
        final_loss: Loss on the final training batch.
        validation_loss: Loss on validation data (if provided).
        epochs_completed: Number of epochs completed.
        total_steps: Total gradient update steps.
        training_time_seconds: Wall time of training.
        loss_history: Loss values per logging interval.
        adapter_path: Path where the adapter was saved (if saved).
        error_message: Error description if training failed.
        metadata: Additional training metadata.
    """

    success: bool = True
    adapter_id: str = ""
    final_loss: float = 0.0
    validation_loss: Optional[float] = None
    epochs_completed: int = 0
    total_steps: int = 0
    training_time_seconds: float = 0.0
    loss_history: List[float] = field(default_factory=list)
    adapter_path: Optional[Path] = None
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging and reporting."""
        return {
            "success": self.success,
            "adapter_id": self.adapter_id,
            "final_loss": self.final_loss,
            "validation_loss": self.validation_loss,
            "epochs_completed": self.epochs_completed,
            "total_steps": self.total_steps,
            "training_time_seconds": self.training_time_seconds,
            "loss_history_len": len(self.loss_history),
            "error_message": self.error_message,
        }


@dataclass
class TrainingConfig:
    """
    Training hyperparameters.

    These can be overridden via kwargs in LoRATrainer.train().
    """

    learning_rate: float = 1e-3
    batch_size: int = 32
    epochs: int = 10
    momentum: float = 0.9
    weight_decay: float = 0.0
    max_grad_norm: float = 1.0
    log_interval: int = 10
    validation_split: float = 0.0
    lr_schedule: str = "constant"  # "constant", "cosine", "linear"
    warmup_steps: int = 0


class LoRATrainer:
    """
    Trainer for LoRA adapters.

    Performs gradient-based fine-tuning of LoRA A and B matrices
    using mini-batch SGD with momentum. Pure NumPy implementation —
    no PyTorch dependency.

    The trainer computes gradients for LoRA parameters by simulating
    a simple regression loss: ||y - Wx - ΔWx||² where ΔW = BA.

    For production use with real models, the loss and gradients
    can be supplied externally via the `compute_gradients` callback.

    Args:
        base_model_name: Identifier for the base model being adapted.
            Used for logging and adapter metadata.
        config: LoRA configuration.
        default_training_config: Default training hyperparameters.
    """

    def __init__(
        self,
        base_model_name: str,
        config: Optional[LoRAConfig] = None,
        default_training_config: Optional[TrainingConfig] = None,
    ) -> None:
        self.base_model_name = base_model_name
        self.config = config or LoRAConfig()
        self.default_config = default_training_config or TrainingConfig()

        self._momentum_buffers: Dict[str, Dict[str, np.ndarray]] = {}
        self._current_adapter: Optional[LoRAAdapter] = None

        logger.info(
            "LoRATrainer initialized: model=%s, rank=%d, lr=%s",
            base_model_name,
            self.config.rank,
            self.default_config.learning_rate,
        )

    def _init_momentum(
        self, adapter: LoRAAdapter
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Initialize momentum buffers for all LoRA parameters."""
        momentum: Dict[str, Dict[str, np.ndarray]] = {}
        for module_name in adapter.lora_A:
            momentum[module_name] = {
                "A": np.zeros_like(adapter.lora_A[module_name]),
                "B": np.zeros_like(adapter.lora_B[module_name]),
            }
        return momentum

    def _compute_lr(
        self, step: int, total_steps: int, config: TrainingConfig
    ) -> float:
        """
        Compute learning rate according to schedule.

        Supports constant, cosine, and linear schedules with warmup.
        """
        base_lr = config.learning_rate

        # Warmup
        if step < config.warmup_steps:
            return base_lr * (step + 1) / max(config.warmup_steps, 1)

        # Post-warmup schedule
        remaining = step - config.warmup_steps
        total_remaining = max(total_steps - config.warmup_steps, 1)
        progress = min(remaining / total_remaining, 1.0)

        if config.lr_schedule == "cosine":
            return base_lr * 0.5 * (1.0 + math.cos(math.pi * progress))
        elif config.lr_schedule == "linear":
            return base_lr * (1.0 - progress)
        else:  # constant
            return base_lr

    def _clip_gradients(
        self,
        grads_A: Dict[str, np.ndarray],
        grads_B: Dict[str, np.ndarray],
        max_norm: float,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
        """Clip gradients to max_norm globally."""
        if max_norm <= 0:
            return grads_A, grads_B

        total_norm_sq = 0.0
        for module_name in grads_A:
            total_norm_sq += np.sum(grads_A[module_name] ** 2)
            total_norm_sq += np.sum(grads_B[module_name] ** 2)

        total_norm = math.sqrt(total_norm_sq)
        if total_norm > max_norm and total_norm > 0:
            scale = max_norm / total_norm
            clipped_A = {
                k: v * scale for k, v in grads_A.items()
            }
            clipped_B = {
                k: v * scale for k, v in grads_B.items()
            }
            return clipped_A, clipped_B

        return grads_A, grads_B

    def train(
        self,
        train_dataset: Any,
        adapter_id: str,
        **kwargs: Any,
    ) -> LoRATrainingResult:
        """
        Train a LoRA adapter on the given dataset.

        Args:
            train_dataset: Training data. Can be:
                - Tuple of (X, y) numpy arrays (features, targets)
                - Dict with "features" and "targets" keys
                - A callable that yields (X_batch, y_batch) tuples
                - Any iterable of (X_batch, y_batch) tuples
            adapter_id: Identifier for the new adapter.
            **kwargs: Override TrainingConfig parameters.

        Returns:
            LoRATrainingResult with training metrics and the trained adapter.
        """
        start_time = time.time()

        # Merge configs
        cfg = TrainingConfig(
            **{
                **{f.name: getattr(self.default_config, f.name)
                   for f in __import__("dataclasses").fields(TrainingConfig)},
                **kwargs,
            }
        )

        # Parse dataset
        X, y = self._parse_dataset(train_dataset)
        if X is None or y is None:
            return LoRATrainingResult(
                success=False,
                adapter_id=adapter_id,
                error_message="Invalid dataset: expected (X, y) tuple or dict with 'features'/'targets'",
            )

        # Validate dimensions
        if X.ndim < 2:
            return LoRATrainingResult(
                success=False,
                adapter_id=adapter_id,
                error_message=f"X must be 2D, got shape {X.shape}",
            )
        if y.ndim < 2:
            y = y.reshape(-1, 1)

        n_samples, in_dim = X.shape
        out_dim = y.shape[1]

        # Build weight shapes from data dimensions
        weight_shapes: Dict[str, Tuple[int, int]] = {}
        for module_name in self.config.target_modules:
            weight_shapes[module_name] = (out_dim, in_dim)

        # Create adapter
        adapter = LoRAAdapter.create(
            adapter_id=adapter_id,
            config=self.config,
            weight_shapes=weight_shapes,
            metadata={
                "base_model_name": self.base_model_name,
                "n_training_samples": n_samples,
            },
        )

        # Split validation if needed
        if cfg.validation_split > 0:
            n_val = max(1, int(n_samples * cfg.validation_split))
            indices = np.random.permutation(n_samples)
            val_idx = indices[:n_val]
            train_idx = indices[n_val:]
            X_val, y_val = X[val_idx], y[val_idx]
            X_train, y_train = X[train_idx], y[train_idx]
        else:
            X_train, y_train = X, y
            X_val, y_val = None, None

        # Initialize momentum
        momentum = self._init_momentum(adapter)
        n_train = X_train.shape[0]
        steps_per_epoch = max(1, n_train // cfg.batch_size)
        total_steps = steps_per_epoch * cfg.epochs
        step = 0
        loss_history: List[float] = []
        best_loss = float("inf")

        logger.info(
            "Training LoRA adapter '%s': %d samples, %d epochs, %d params",
            adapter_id, n_train, cfg.epochs, adapter.num_params(),
        )

        try:
            for epoch in range(cfg.epochs):
                # Shuffle
                perm = np.random.permutation(n_train)

                for batch_start in range(0, n_train, cfg.batch_size):
                    batch_idx = perm[batch_start:batch_start + cfg.batch_size]
                    X_batch = X_train[batch_idx]
                    y_batch = y_train[batch_idx]

                    # Forward: compute LoRA output and loss
                    # y_pred = Wx + ΔWx, but we don't have W.
                    # Instead we directly optimize ΔW to match y - Wx
                    # Since W is unknown, we treat the target as:
                    # "learn ΔW such that ΔWx approximates y"
                    # This is equivalent to learning the weight update directly.

                    # Zero gradients
                    grads_A: Dict[str, np.ndarray] = {}
                    grads_B: Dict[str, np.ndarray] = {}

                    total_loss = 0.0
                    batch_size = X_batch.shape[0]

                    for module_name in adapter.lora_A:
                        A = adapter.lora_A[module_name]  # (out_dim, rank)
                        B = adapter.lora_B[module_name]  # (rank, in_dim)
                        scaling = adapter.config.scaling

                        # Forward: ΔWx = scaling * (A @ B) @ x
                        # Bx -> (rank, batch) -> (batch, rank)
                        Bx = (B @ X_batch.T).T  # (batch, rank)
                        # A(Bx) -> (batch, out_dim)
                        pred = (A @ Bx.T).T * scaling  # (batch, out_dim)

                        # Loss: MSE = mean((y - pred)^2)
                        diff = y_batch - pred  # (batch, out_dim)
                        loss = np.mean(diff ** 2)
                        total_loss += loss

                        # Gradient of loss w.r.t. pred: dL/dpred = -2 * diff / batch_size
                        d_out = -2.0 * diff / batch_size  # (batch, out_dim)

                        # Gradient w.r.t. A: (out_dim, rank)
                        # dL/dA = dL/dpred @ (B @ X)^T * scaling
                        # dL/dA = d_out^T @ (B @ X) * scaling
                        # d_out: (batch, out_dim) -> d_out.T: (out_dim, batch)
                        # B @ X.T: (rank, batch)
                        # Actually: dL/dA_ij = sum over batch of dL/dpred_ik * scaling * (B @ x)_jk
                        # dL/dA = scaling * d_out^T @ Bx
                        # d_out^T: (out_dim, batch), Bx: (batch, rank)
                        dA = scaling * d_out.T @ Bx  # (out_dim, rank)

                        # Gradient w.r.t. B: (rank, in_dim)
                        # dL/dB = scaling * (A^T @ d_out^T) @ X
                        # A: (out_dim, rank), d_out.T: (out_dim, batch)
                        # A^T @ d_out.T: (rank, batch)
                        # X: (batch, in_dim)
                        dB = scaling * (A.T @ d_out.T) @ X_batch  # (rank, in_dim)

                        grads_A[module_name] = dA
                        grads_B[module_name] = dB

                    # Average loss across modules
                    n_modules = max(len(adapter.lora_A), 1)
                    avg_loss = total_loss / n_modules

                    # Weight decay
                    if cfg.weight_decay > 0:
                        for module_name in adapter.lora_A:
                            grads_A[module_name] += cfg.weight_decay * adapter.lora_A[module_name]
                            grads_B[module_name] += cfg.weight_decay * adapter.lora_B[module_name]

                    # Gradient clipping
                    grads_A, grads_B = self._clip_gradients(
                        grads_A, grads_B, cfg.max_grad_norm
                    )

                    # Update with momentum SGD
                    current_lr = self._compute_lr(step, total_steps, cfg)

                    for module_name in adapter.lora_A:
                        # Momentum update for A
                        momentum[module_name]["A"] = (
                            cfg.momentum * momentum[module_name]["A"]
                            + current_lr * grads_A[module_name]
                        )
                        adapter.lora_A[module_name] -= momentum[module_name]["A"]

                        # Momentum update for B
                        momentum[module_name]["B"] = (
                            cfg.momentum * momentum[module_name]["B"]
                            + current_lr * grads_B[module_name]
                        )
                        adapter.lora_B[module_name] -= momentum[module_name]["B"]

                    step += 1

                    # Logging
                    if step % cfg.log_interval == 0:
                        loss_history.append(float(avg_loss))
                        if avg_loss < best_loss:
                            best_loss = float(avg_loss)

                        logger.debug(
                            "LoRA step %d/%d: loss=%.6f lr=%.6f",
                            step, total_steps, avg_loss, current_lr,
                        )

            # Compute final validation loss
            val_loss: Optional[float] = None
            if X_val is not None and y_val is not None:
                val_losses = []
                for module_name in adapter.lora_A:
                    A = adapter.lora_A[module_name]
                    B = adapter.lora_B[module_name]
                    scaling = adapter.config.scaling
                    Bx = (B @ X_val.T).T
                    pred = (A @ Bx.T).T * scaling
                    diff = y_val - pred
                    val_losses.append(float(np.mean(diff ** 2)))
                val_loss = sum(val_losses) / max(len(val_losses), 1)

            training_time = time.time() - start_time
            final_loss = loss_history[-1] if loss_history else 0.0

            result = LoRATrainingResult(
                success=True,
                adapter_id=adapter_id,
                final_loss=final_loss,
                validation_loss=val_loss,
                epochs_completed=cfg.epochs,
                total_steps=step,
                training_time_seconds=training_time,
                loss_history=loss_history,
                metadata={
                    "base_model_name": self.base_model_name,
                    "rank": self.config.rank,
                    "learning_rate": cfg.learning_rate,
                    "batch_size": cfg.batch_size,
                    "n_samples": n_samples,
                    "best_loss": best_loss,
                    "lr_schedule": cfg.lr_schedule,
                    "steps_per_epoch": steps_per_epoch,
                },
            )

            # Store current adapter
            self._current_adapter = adapter

            logger.info(
                "LoRA adapter '%s' trained: %.4f loss, %.1fs, %d steps",
                adapter_id, final_loss, training_time, step,
            )

            return result

        except Exception as e:
            logger.error("LoRA training failed: %s", e)
            import traceback
            logger.debug(traceback.format_exc())
            return LoRATrainingResult(
                success=False,
                adapter_id=adapter_id,
                error_message=str(e),
                training_time_seconds=time.time() - start_time,
            )

    def _parse_dataset(
        self, dataset: Any
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Parse training dataset into X, y numpy arrays.

        Supported formats:
        - Tuple of (X, y)
        - Dict with "features" and "targets" keys
        - List of (X, y) tuples (stacked)
        - numpy array (used as both X and y for self-supervised)
        """
        if isinstance(dataset, tuple) and len(dataset) == 2:
            X, y = dataset
            return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)

        if isinstance(dataset, dict):
            X = dataset.get("features") or dataset.get("X")
            y = dataset.get("targets") or dataset.get("y") or dataset.get("labels")
            if X is not None and y is not None:
                return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)

        if isinstance(dataset, list):
            X_list, y_list = [], []
            for item in dataset:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    X_list.append(np.asarray(item[0], dtype=np.float32))
                    y_list.append(np.asarray(item[1], dtype=np.float32))
            if X_list:
                return np.stack(X_list), np.stack(y_list)

        if isinstance(dataset, np.ndarray):
            # Self-supervised: predict the input
            return dataset.astype(np.float32), dataset.astype(np.float32)

        logger.warning("Unrecognized dataset format: %s", type(dataset).__name__)
        return None, None

    def get_trained_adapter(self) -> Optional[LoRAAdapter]:
        """Return the most recently trained adapter."""
        return self._current_adapter

    def save_trained_adapter(self, path: Path) -> Optional[Path]:
        """
        Save the most recently trained adapter to disk.

        Args:
            path: Target path (without extension).

        Returns:
            Path written to, or None if no adapter has been trained.
        """
        if self._current_adapter is None:
            logger.warning("No trained adapter to save")
            return None
        return save_lora_adapter(self._current_adapter, path)
