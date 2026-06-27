"""
LoRA configuration: hyperparameters for Low-Rank Adaptation.

Default values follow the original LoRA paper (Hu et al., 2021).
All configs are serializable via dataclass asdict.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class LoRAConfig:
    """
    Configuration for LoRA (Low-Rank Adaptation).

    Controls the rank, scaling, dropout, and target modules for LoRA
    adapter training. All parameters have production-safe defaults.

    Attributes:
        rank: LoRA rank r (dimension of the low-rank matrices A and B).
            r << min(d, k) where d×k is the weight matrix size.
            Default 8 — good balance for most transformer layers.
        alpha: LoRA scaling factor. The forward pass scales the LoRA
            contribution by alpha / rank. Default 16.
        dropout: Dropout probability applied to the LoRA input.
            Default 0.0 (no dropout).
        target_modules: List of module name patterns to apply LoRA to.
            Default self-attention projections (q, v).
        bias: Bias training mode — "none", "all", or "lora_only".
            Default "none" (no bias training).
        task_type: Task type identifier (e.g. "CAUSAL_LM", "SEQ_2_SEQ_LM").
            Default "CAUSAL_LM".
        init_scale_a: Standard deviation for initializing A matrices
            with random normal. Default 0.02.
        fan_in_fan_out: Whether the weight matrix is stored transposed
            (GPT-2 style). Default False.
        use_rslora: Use rank-stabilized scaling (alpha / sqrt(rank))
            instead of alpha / rank. Default False.
        modules_to_save: Module names to train full-rank (not LoRA).
        layers_to_transform: Specific layer indices to apply LoRA.
        layers_pattern: Pattern matching for layer indices.
    """

    rank: int = 8
    alpha: float = 16.0
    dropout: float = 0.0
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "v_proj"]
    )
    bias: str = "none"
    task_type: str = "CAUSAL_LM"
    init_scale_a: float = 0.02
    fan_in_fan_out: bool = False
    use_rslora: bool = False
    modules_to_save: Optional[List[str]] = None
    layers_to_transform: Optional[List[int]] = None
    layers_pattern: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate config values."""
        assert self.rank > 0, f"LoRA rank must be positive, got {self.rank}"
        assert self.alpha > 0, f"LoRA alpha must be positive, got {self.alpha}"
        assert 0.0 <= self.dropout < 1.0, (
            f"LoRA dropout must be in [0, 1), got {self.dropout}"
        )
        assert self.bias in ("none", "all", "lora_only"), (
            f"LoRA bias must be 'none', 'all', or 'lora_only', got {self.bias!r}"
        )

    @property
    def scaling(self) -> float:
        """
        Compute the LoRA scaling factor.

        Standard: alpha / rank
        Rank-stabilized (rsLoRA): alpha / sqrt(rank)
        """
        if self.use_rslora:
            return self.alpha / max(self.rank**0.5, 1.0)
        return self.alpha / max(self.rank, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoRAConfig":
        """Deserialize from dict."""
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> "LoRAConfig":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(text))

    def copy(self) -> LoRAConfig:
        """Return a deep copy."""
        return copy.deepcopy(self)


import dataclasses  # noqa: E402 — needed for from_dict field inspection
