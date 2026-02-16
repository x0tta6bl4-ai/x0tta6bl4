"""
LoRA Configuration

Configuration for LoRA fine-tuning adapters.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class LoRATargetModules(Enum):
    """Target modules for LoRA adaptation"""

    # LLaMA/Mistral style
    Q_PROJ = "q_proj"
    V_PROJ = "v_proj"
    K_PROJ = "k_proj"
    O_PROJ = "o_proj"

    # GPT style
    C_ATTN = "c_attn"
    C_PROJ = "c_proj"

    # Generic
    ATTENTION = "attention"
    MLP = "mlp"


@dataclass
class LoRAConfig:
    """
    Configuration for LoRA adapter.

    Default values based on x0tta6bl4 requirements:
    - r=8: Rank of adaptation (low rank)
    - alpha=32: Scaling factor
    - dropout=0.1: Dropout rate
    - target_modules: Attention projection layers
    """

    r: int = 8  # Rank of adaptation
    alpha: int = 32  # Scaling factor
    dropout: float = 0.1  # Dropout rate
    target_modules: List[str] = None  # Target modules (default: attention layers)
    bias: str = "none"  # Bias type: "none", "all", "lora_only"
    task_type: str = "CAUSAL_LM"  # Task type: "CAUSAL_LM", "SEQ_2_SEQ_LM", etc.
    inference_mode: bool = False  # Inference mode (no training)

    def __post_init__(self):
        """Set default target modules if not provided"""
        if self.target_modules is None:
            self.target_modules = [
                LoRATargetModules.Q_PROJ.value,
                LoRATargetModules.V_PROJ.value,
                LoRATargetModules.K_PROJ.value,
                LoRATargetModules.O_PROJ.value,
            ]

        logger.info(
            f"✅ LoRAConfig initialized: r={self.r}, alpha={self.alpha}, dropout={self.dropout}"
        )

    def to_peft_config(self) -> dict:
        """
        Convert to PEFT config format.

        Returns:
            Dict compatible with PEFT library
        """
        return {
            "r": self.r,
            "lora_alpha": self.alpha,
            "lora_dropout": self.dropout,
            "target_modules": self.target_modules,
            "bias": self.bias,
            "task_type": self.task_type,
            "inference_mode": self.inference_mode,
        }

    @classmethod
    def from_peft_config(cls, config: dict) -> "LoRAConfig":
        """
        Create LoRAConfig from PEFT config.

        Args:
            config: PEFT config dict

        Returns:
            LoRAConfig instance
        """
        return cls(
            r=config.get("r", 8),
            alpha=config.get("lora_alpha", 32),
            dropout=config.get("lora_dropout", 0.1),
            target_modules=config.get(
                "target_modules",
                [
                    LoRATargetModules.Q_PROJ.value,
                    LoRATargetModules.V_PROJ.value,
                    LoRATargetModules.K_PROJ.value,
                    LoRATargetModules.O_PROJ.value,
                ],
            ),
            bias=config.get("bias", "none"),
            task_type=config.get("task_type", "CAUSAL_LM"),
            inference_mode=config.get("inference_mode", False),
        )
