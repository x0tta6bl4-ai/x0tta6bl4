"""
LoRA: Low-Rank Adaptation for x0tta6bl4.

Pure NumPy implementation of LoRA (Hu et al., 2021).
No PyTorch dependency — works with the project's existing NumPy stack.

Used by federated learning for distributed adapter training across mesh nodes.
"""
from __future__ import annotations

from src.ml.lora.config import LoRAConfig
from src.ml.lora.adapter import LoRAAdapter, load_lora_adapter, save_lora_adapter
from src.ml.lora.trainer import LoRATrainer, LoRATrainingResult

__all__ = [
    "LoRAConfig",
    "LoRAAdapter",
    "LoRATrainer",
    "LoRATrainingResult",
    "load_lora_adapter",
    "save_lora_adapter",
]

