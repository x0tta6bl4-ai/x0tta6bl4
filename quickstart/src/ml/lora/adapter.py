"""
LoRA Adapter: low-rank weight decomposition for model fine-tuning.

Pure NumPy implementation. Stores LoRA A and B matrices for each target
module and provides the forward pass: h = Wx + scaling * BAx.

Supports serialization to/from disk for federated distribution.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.ml.lora.config import LoRAConfig

logger = logging.getLogger(__name__)

# Allowed file extensions for adapter weights
_LORA_WEIGHTS_EXT = ".npz"
_LORA_META_EXT = ".json"


@dataclass
class LoRAAdapter:
    """
    LoRA adapter storing low-rank weight matrices A and B.

    For each target module with original weight shape (out_dim, in_dim),
    we store:
        A: shape (out_dim, rank)  — random initialization
        B: shape (rank, in_dim)   — zero initialization

    So the LoRA update is: ΔW = B @ A  (shape: out_dim × in_dim)
    And the forward pass:  h = Wx + (α/r) * (B @ A) @ x

    Attributes:
        adapter_id: Unique identifier for this adapter.
        config: The LoRAConfig used to create this adapter.
        lora_A: Dict of {module_name: np.ndarray of shape (out_dim, rank)}
        lora_B: Dict of {module_name: np.ndarray of shape (rank, in_dim)}
        weight_shapes: Dict of {module_name: (out_dim, in_dim)} — for reference.
        created_at: Unix timestamp of creation.
        metadata: Optional user-defined metadata dict.
    """

    adapter_id: str
    config: LoRAConfig
    lora_A: Dict[str, np.ndarray] = field(default_factory=dict)
    lora_B: Dict[str, np.ndarray] = field(default_factory=dict)
    weight_shapes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        adapter_id: str,
        config: LoRAConfig,
        weight_shapes: Dict[str, Tuple[int, int]],
        rng: Optional[np.random.Generator] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LoRAAdapter:
        """
        Create a new LoRA adapter with randomly initialized A and zero B matrices.

        Args:
            adapter_id: Unique identifier.
            config: LoRA configuration.
            weight_shapes: Dict mapping module name to (out_dim, in_dim).
            rng: NumPy random generator (creates default if None).
            metadata: Optional metadata dict.

        Returns:
            Initialized LoRAAdapter.
        """
        if rng is None:
            rng = np.random.default_rng()

        lora_A: Dict[str, np.ndarray] = {}
        lora_B: Dict[str, np.ndarray] = {}
        rank = config.rank

        for module_name, (out_dim, in_dim) in weight_shapes.items():
            # A: (out_dim, rank) — random normal, scaled by init_scale_a
            lora_A[module_name] = rng.normal(
                0, config.init_scale_a, size=(out_dim, rank)
            ).astype(np.float32)
            # B: (rank, in_dim) — zeros, so initial fine-tune starts from base weights
            lora_B[module_name] = np.zeros((rank, in_dim), dtype=np.float32)

        return cls(
            adapter_id=adapter_id,
            config=config,
            lora_A=lora_A,
            lora_B=lora_B,
            weight_shapes=weight_shapes,
            metadata=metadata or {},
        )

    def forward(
        self,
        module_name: str,
        x: np.ndarray,
    ) -> np.ndarray:
        """
        Compute the LoRA update for a given module's input.

        Args:
            module_name: Target module name.
            x: Input tensor of shape (batch_size, ..., in_dim).

        Returns:
            LoRA contribution: scaling * (B @ A) @ x.
            Same shape as x: (batch_size, ..., out_dim).
        """
        if module_name not in self.lora_A or module_name not in self.lora_B:
            return np.zeros_like(x, dtype=np.float32)

        A = self.lora_A[module_name]  # (out_dim, rank)
        B = self.lora_B[module_name]  # (rank, in_dim)

        # ΔW = B @ A -> (rank, in_dim) @ (out_dim, rank)^T ... actually let's think
        # A is (out_dim, rank) and B is (rank, in_dim)
        # ΔW = A @ B? No...
        # Standard LoRA: W' = W + BA where A: (rank, in_dim) and B: (out_dim, rank)
        # h = Wx + BAx = Wx + B(Ax)
        # But our naming convention differs from the paper's naming.
        # Let's use: lora_A = down projection (in_dim -> rank), lora_B = up projection (rank -> out_dim)
        # So the forward is: B @ (A @ x) where A: (rank, in_dim), B: (out_dim, rank)

        # Wait, looking at our initialization:
        # lora_A shape: (out_dim, rank) — this is the UP projection in standard notation
        # lora_B shape: (rank, in_dim) — this is the DOWN projection
        # That's wrong naming compared to standard LoRA convention.
        # Standard: A is down (in_dim, rank), B is up (rank, out_dim)
        # Forward: h = Wx + (B @ A) @ x where A: (d, r), B: (r, k)
        #
        # But we named A as (out_dim, rank). Let's compute correctly:
        # We have A: (out_dim, rank) = up   ← we want this as the outer
        # We have B: (rank, in_dim) = down  ← we want this as the inner
        # LoRA update = A @ (B @ x) = (out_dim, rank) @ ((rank, in_dim) @ input)
        # This gives (out_dim, ...) which is correct for the weight update.

        # Actually the paper says:
        # W' = W + BA where B: (d, r), A: (r, k)
        # h = Wx + BAx
        #
        # In our naming: lora_A (out_dim, rank) acts as B in the paper
        # lora_B (rank, in_dim) acts as A in the paper
        #
        # So h = Wx + scaling * lora_A @ (lora_B @ x)

        # For x shape (batch_size, ..., in_dim), we need last dim = in_dim
        orig_shape = x.shape
        flat_x = x.reshape(-1, orig_shape[-1])  # (N, in_dim)

        # Down: (rank, in_dim) @ (N, in_dim)^T -> (N, rank)
        # Actually: lora_B @ x.T gives (rank, N) then transpose back
        down = (self.lora_B[module_name] @ flat_x.T).T  # (N, rank)

        # Up: (out_dim, rank) @ (N, rank)^T -> (N, out_dim)
        up = (self.lora_A[module_name] @ down.T).T  # (N, out_dim)

        # Reshape to match input (except last dim -> out_dim)
        new_shape = orig_shape[:-1] + (up.shape[-1],)
        result = up.reshape(new_shape)

        return result * self.config.scaling

    def get_delta_weights(self, module_name: str) -> np.ndarray:
        """
        Get the full ΔW matrix for a module.

        ΔW = A @ B (where A is the up-projection, B is the down-projection).
        Returns shape (out_dim, in_dim).
        """
        if module_name not in self.lora_A or module_name not in self.lora_B:
            return np.zeros(
                self.weight_shapes.get(module_name, (0, 0)), dtype=np.float32
            )

        A = self.lora_A[module_name]  # (out_dim, rank)
        B = self.lora_B[module_name]  # (rank, in_dim)

        return (A @ B) * self.config.scaling

    def get_weights(self) -> Dict[str, Dict[str, List[float]]]:
        """
        Export weights as nested dicts (for FL communication).

        Returns:
            {module_name: {"lora_A": [...], "lora_B": [...]}}
            with lists of floats for serialization.
        """
        result: Dict[str, Dict[str, List[float]]] = {}
        for module_name in self.lora_A:
            result[module_name] = {
                "lora_A": self.lora_A[module_name].flatten().tolist(),
                "lora_B": self.lora_B[module_name].flatten().tolist(),
            }
        return result

    def set_weights(self, weights: Dict[str, Dict[str, List[float]]]) -> None:
        """
        Load weights from nested dicts (after FL aggregation).

        Args:
            weights: {module_name: {"lora_A": [...], "lora_B": [...]}}
        """
        for module_name, module_weights in weights.items():
            if module_name not in self.lora_A or module_name not in self.lora_B:
                logger.warning(
                    "Module %s not in adapter, skipping weight set", module_name
                )
                continue

            expected_A_size = self.lora_A[module_name].size
            expected_B_size = self.lora_B[module_name].size

            A_flat = module_weights.get("lora_A", [])
            B_flat = module_weights.get("lora_B", [])

            if len(A_flat) != expected_A_size:
                logger.error(
                    "LoRA A size mismatch for %s: got %d, expected %d",
                    module_name, len(A_flat), expected_A_size,
                )
                continue
            if len(B_flat) != expected_B_size:
                logger.error(
                    "LoRA B size mismatch for %s: got %d, expected %d",
                    module_name, len(B_flat), expected_B_size,
                )
                continue

            self.lora_A[module_name] = np.array(A_flat, dtype=np.float32).reshape(
                self.lora_A[module_name].shape
            )
            self.lora_B[module_name] = np.array(B_flat, dtype=np.float32).reshape(
                self.lora_B[module_name].shape
            )

    def module_names(self) -> List[str]:
        """Return list of target module names."""
        return list(self.lora_A.keys())

    def num_params(self) -> int:
        """Total number of trainable LoRA parameters."""
        total = 0
        for name in self.lora_A:
            total += self.lora_A[name].size + self.lora_B[name].size
        return total

    def copy(self) -> LoRAAdapter:
        """Return a deep copy."""
        return LoRAAdapter(
            adapter_id=self.adapter_id,
            config=self.config.copy(),
            lora_A={k: v.copy() for k, v in self.lora_A.items()},
            lora_B={k: v.copy() for k, v in self.lora_B.items()},
            weight_shapes=dict(self.weight_shapes),
            created_at=self.created_at,
            metadata=dict(self.metadata),
        )

    def checksum(self) -> str:
        """SHA-256 checksum of flattened weights (for integrity verification)."""
        hasher = hashlib.sha256()
        for module_name in sorted(self.lora_A.keys()):
            hasher.update(self.lora_A[module_name].tobytes())
            hasher.update(self.lora_B[module_name].tobytes())
        return hasher.hexdigest()


def save_lora_adapter(
    adapter: LoRAAdapter,
    path: Path,
    compress: bool = True,
) -> Path:
    """
    Save a LoRA adapter to disk.

    Creates two files:
        <path>.json — metadata (config, shapes, adapter_id)
        <path>.npz  — weight matrices (compressed NumPy archive)

    Args:
        adapter: The adapter to save.
        path: Target path (without extension).
        compress: Whether to use compressed NumPy archive.

    Returns:
        The path that was written to (with extension stripped).

    Raises:
        OSError: If writing fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Metadata JSON
    meta = {
        "adapter_id": adapter.adapter_id,
        "config": adapter.config.to_dict(),
        "weight_shapes": {
            k: list(v) for k, v in adapter.weight_shapes.items()
        },
        "module_names": list(adapter.lora_A.keys()),
        "created_at": adapter.created_at,
        "metadata": adapter.metadata,
        "num_params": adapter.num_params(),
    }
    meta_path = path.with_suffix(_LORA_META_EXT)
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    # Weights as NPZ
    weights: Dict[str, np.ndarray] = {}
    for module_name in adapter.lora_A:
        weights[f"{module_name}_A"] = adapter.lora_A[module_name]
        weights[f"{module_name}_B"] = adapter.lora_B[module_name]

    weights_path = path.with_suffix(_LORA_WEIGHTS_EXT)
    if compress:
        np.savez_compressed(weights_path, **weights)
    else:
        np.savez(weights_path, **weights)

    logger.info(
        "LoRA adapter '%s' saved: %s (%d params, %d modules)",
        adapter.adapter_id, path, adapter.num_params(), len(adapter.lora_A),
    )
    return path


def load_lora_adapter(path: Path) -> LoRAAdapter:
    """
    Load a LoRA adapter from disk.

    Expects two files:
        <path>.json — metadata
        <path>.npz  — weight matrices

    Args:
        path: Base path (with or without extension).

    Returns:
        Loaded LoRAAdapter.

    Raises:
        FileNotFoundError: If either file is missing.
        ValueError: If the files are malformed.
    """
    path = Path(path)

    # Strip extension if given
    if path.suffix in (_LORA_META_EXT, _LORA_WEIGHTS_EXT):
        path = path.with_suffix("")

    meta_path = path.with_suffix(_LORA_META_EXT)
    weights_path = path.with_suffix(_LORA_WEIGHTS_EXT)

    if not meta_path.exists():
        raise FileNotFoundError(f"LoRA metadata not found: {meta_path}")
    if not weights_path.exists():
        raise FileNotFoundError(f"LoRA weights not found: {weights_path}")

    with open(meta_path) as f:
        meta = json.load(f)

    config = LoRAConfig.from_dict(meta["config"])
    weight_shapes = {
        k: tuple(v) for k, v in meta["weight_shapes"].items()
    }

    # Load weights
    loaded = np.load(weights_path, allow_pickle=False)

    lora_A: Dict[str, np.ndarray] = {}
    lora_B: Dict[str, np.ndarray] = {}
    for module_name in meta["module_names"]:
        key_a = f"{module_name}_A"
        key_b = f"{module_name}_B"
        if key_a not in loaded or key_b not in loaded:
            raise ValueError(
                f"Missing weights for module {module_name} in {weights_path}"
            )
        lora_A[module_name] = loaded[key_a]
        lora_B[module_name] = loaded[key_b]

    loaded.close()

    adapter = LoRAAdapter(
        adapter_id=meta["adapter_id"],
        config=config,
        lora_A=lora_A,
        lora_B=lora_B,
        weight_shapes=weight_shapes,
        created_at=meta.get("created_at", 0.0),
        metadata=meta.get("metadata", {}),
    )

    logger.info(
        "LoRA adapter '%s' loaded: %s (%d params, %d modules)",
        adapter.adapter_id, path, adapter.num_params(), len(adapter.lora_A),
    )
    return adapter
