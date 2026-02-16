"""LoRA package exports with backward-compatible runtime adapter API."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from src.ml.lora.adapter import LoRAAdapter as PeftLoRAAdapter
from src.ml.lora.adapter import (apply_lora_adapter, load_lora_adapter,
                                 save_lora_adapter)
from src.ml.lora.advanced import (LoRAComposer, LoRACompositionConfig,
                                  LoRAIncrementalTrainer,
                                  LoRAPerformanceMonitor,
                                  LoRAQuantizationConfig, LoRAQuantizer)
from src.ml.lora.config import LoRAConfig as PeftLoRAConfig
from src.ml.lora.config import LoRATargetModules
from src.ml.lora.trainer import LoRATrainer, LoRATrainingResult


@dataclass
class LoRAConfig:
    """Backward-compatible runtime LoRA config used by MAPE-K ML integration."""

    rank: int = 8
    alpha: float = 32.0
    dropout: float = 0.1
    learning_rate: float = 0.001
    target_modules: List[str] = field(default_factory=lambda: ["analyzer", "planner"])

    def __init__(
        self,
        rank: int = 8,
        alpha: float = 32.0,
        dropout: float = 0.1,
        learning_rate: float = 0.001,
        target_modules: Optional[List[str]] = None,
        r: Optional[int] = None,
    ):
        self.rank = r if r is not None else rank
        self.alpha = alpha
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.target_modules = target_modules or ["analyzer", "planner"]

    @property
    def r(self) -> int:
        return self.rank

    @r.setter
    def r(self, value: int) -> None:
        self.rank = value


@dataclass
class _LoRAWeights:
    A: np.ndarray
    B: np.ndarray
    bias: Optional[np.ndarray] = None


class _LoRALayer:
    def __init__(self, input_dim: int, output_dim: int, config: LoRAConfig):
        self.config = config
        self.weights = _LoRAWeights(
            A=np.random.randn(input_dim, config.rank) * 0.01,
            B=np.zeros((config.rank, output_dim)),
        )

    def forward(self, x: np.ndarray, base_output: np.ndarray) -> np.ndarray:
        lora_out = (x @ self.weights.A) @ self.weights.B
        return base_output + (self.config.alpha / self.config.rank) * lora_out

    async def update(self, gradient: np.ndarray, lr: float):
        self.weights.B -= lr * gradient


class LoRAAdapter:
    """Backward-compatible runtime adapter with async adaptation methods."""

    def __init__(self, config: LoRAConfig):
        self.config = config
        self.lora_layers: Dict[str, _LoRALayer] = {}
        self.adaptation_history: List[Dict[str, Any]] = []

    def add_layer(self, name: str, input_dim: int, output_dim: int) -> None:
        self.lora_layers[name] = _LoRALayer(input_dim, output_dim, self.config)

    async def adapt_output(
        self,
        component: str,
        input_data: np.ndarray,
        base_output: np.ndarray,
    ) -> np.ndarray:
        layer = self.lora_layers.get(component)
        if layer is None:
            return base_output
        adapted = layer.forward(input_data, base_output)
        self.adaptation_history.append(
            {
                "component": component,
                "timestamp": datetime.now().isoformat(),
            }
        )
        return adapted

    async def fine_tune_on_trajectory(
        self,
        component: str,
        trajectories: List[Dict[str, Any]],
        target_metric: str = "reward",
    ) -> Dict[str, Any]:
        layer = self.lora_layers.get(component)
        if layer is None:
            return {"error": f"Component {component} not registered"}
        losses: List[float] = []
        for _ in range(10):
            epoch_loss = 0.0
            for trajectory in trajectories:
                loss = -float(trajectory.get(target_metric, 0.0))
                epoch_loss += loss
                grad = np.ones((1, layer.weights.B.shape[1])) * loss
                await layer.update(grad, self.config.learning_rate)
            losses.append(epoch_loss / len(trajectories) if trajectories else 0.0)
        return {
            "component": component,
            "epochs": 10,
            "final_loss": float(losses[-1]) if losses else 0.0,
        }

    def get_lora_weights(self, component: str):
        layer = self.lora_layers.get(component)
        return layer.weights if layer else None


__all__ = [
    "LoRAConfig",
    "LoRAAdapter",
    "PeftLoRAConfig",
    "PeftLoRAAdapter",
    "LoRATargetModules",
    "LoRATrainer",
    "LoRATrainingResult",
    "load_lora_adapter",
    "save_lora_adapter",
    "apply_lora_adapter",
    "LoRAComposer",
    "LoRACompositionConfig",
    "LoRAQuantizer",
    "LoRAQuantizationConfig",
    "LoRAIncrementalTrainer",
    "LoRAPerformanceMonitor",
]
