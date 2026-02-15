"""
Advanced LoRA Features

Provides advanced fine-tuning capabilities including adapter composition,
incremental training, multi-task learning, and quantization support.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.ml.lora.adapter import LoRAAdapter
from src.ml.lora.config import LoRAConfig

logger = logging.getLogger(__name__)

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("⚠️ PyTorch not available")

try:
    from peft import LoraConfig, PeftModel, get_peft_model

    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    logger.warning("⚠️ PEFT not available")

try:
    from bitsandbytes.nn import Linear8bitLt

    BITSANDBYTES_AVAILABLE = True
except ImportError:
    BITSANDBYTES_AVAILABLE = False


@dataclass
class LoRACompositionConfig:
    """Configuration for adapter composition"""

    adapters: List[str]
    weights: Optional[List[float]] = None
    fusion_method: str = "linear"
    normalize_weights: bool = True


@dataclass
class LoRAQuantizationConfig:
    """Configuration for quantization"""

    enabled: bool = False
    quantization_type: str = "int8"
    dynamic: bool = True
    optimize_memory: bool = True


class LoRAComposer:
    """
    LoRA Adapter Composition

    Combines multiple LoRA adapters for joint inference.
    """

    def __init__(self, base_model: Any):
        """Initialize composer with base model"""
        self.base_model = base_model
        self.adapters: Dict[str, LoRAAdapter] = {}
        self.composition_config: Optional[LoRACompositionConfig] = None
        self.composed_model = None

    def register_adapter(self, adapter: LoRAAdapter, adapter_path: Path) -> None:
        """Register an adapter for composition"""
        self.adapters[adapter.adapter_id] = adapter
        logger.info(f"✅ Registered adapter: {adapter.adapter_id}")

    def compose_linear(
        self, adapter_ids: List[str], weights: Optional[List[float]] = None
    ) -> Optional[Any]:
        """
        Linearly compose adapters.

        Args:
            adapter_ids: List of adapter IDs to compose
            weights: Optional weights for linear combination

        Returns:
            Composed model or None if failed
        """
        if not all(aid in self.adapters for aid in adapter_ids):
            missing = [aid for aid in adapter_ids if aid not in self.adapters]
            logger.error(f"❌ Missing adapters: {missing}")
            return None

        if weights is None:
            weights = [1.0 / len(adapter_ids)] * len(adapter_ids)
        elif len(weights) != len(adapter_ids):
            logger.error(f"❌ Number of weights must match number of adapters")
            return None

        # Normalize weights
        weight_sum = sum(weights)
        weights = [w / weight_sum for w in weights]

        logger.info(f"🔄 Composing {len(adapter_ids)} adapters with weights: {weights}")

        # Compose adapters
        try:
            if not PEFT_AVAILABLE:
                logger.error("❌ PEFT not available")
                return None

            # Load first adapter
            composed_model = PeftModel.from_pretrained(
                self.base_model, str(self.adapters[adapter_ids[0]].adapter_path)
            )

            # Linear combination of adapter weights
            state_dict = composed_model.state_dict()

            for adapter_id, weight in zip(adapter_ids[1:], weights[1:]):
                adapter_path = self.adapters[adapter_id].adapter_path
                other_model = PeftModel.from_pretrained(
                    self.base_model, str(adapter_path)
                )
                other_state = other_model.state_dict()

                # Blend state dicts
                for key in state_dict:
                    if key in other_state:
                        state_dict[key] = (
                            state_dict[key] * weights[0] + other_state[key] * weight
                        )

            composed_model.load_state_dict(state_dict)
            self.composed_model = composed_model

            logger.info(f"✅ Adapter composition complete")
            return composed_model

        except Exception as e:
            logger.error(f"❌ Adapter composition failed: {e}")
            return None

    def merge_adapters(self, adapter_ids: List[str]) -> Optional[Any]:
        """
        Merge adapters into base model.

        Args:
            adapter_ids: List of adapter IDs to merge

        Returns:
            Merged model or None if failed
        """
        try:
            merged_model = self.base_model

            for adapter_id in adapter_ids:
                if adapter_id not in self.adapters:
                    logger.error(f"❌ Adapter not found: {adapter_id}")
                    continue

                if not PEFT_AVAILABLE:
                    logger.error("❌ PEFT not available")
                    return None

                adapter_path = self.adapters[adapter_id].adapter_path
                merged_model = PeftModel.from_pretrained(
                    merged_model, str(adapter_path)
                )

                if hasattr(merged_model, "merge_and_unload"):
                    merged_model = merged_model.merge_and_unload()
                    logger.info(f"✅ Merged adapter: {adapter_id}")

            return merged_model

        except Exception as e:
            logger.error(f"❌ Adapter merging failed: {e}")
            return None


class LoRAQuantizer:
    """
    LoRA Quantization Support

    Provides quantization options for efficient inference.
    """

    def __init__(self, config: Optional[LoRAQuantizationConfig] = None):
        """Initialize quantizer with configuration"""
        self.config = config or LoRAQuantizationConfig()

    def quantize_adapter(
        self, adapter_model: Any, quantization_type: str = "int8"
    ) -> Optional[Any]:
        """
        Quantize LoRA adapter model.

        Args:
            adapter_model: PEFT model to quantize
            quantization_type: Type of quantization ("int8", "fp16")

        Returns:
            Quantized model or None if failed
        """
        if not TORCH_AVAILABLE:
            logger.error("❌ PyTorch not available")
            return None

        try:
            if quantization_type == "int8":
                if not BITSANDBYTES_AVAILABLE:
                    logger.warning(
                        "⚠️ bitsandbytes not available, skipping int8 quantization"
                    )
                    return adapter_model

                # Convert linear layers to 8-bit
                for name, module in adapter_model.named_modules():
                    if isinstance(module, torch.nn.Linear):
                        module.to(torch.int8)

                logger.info(f"✅ Applied INT8 quantization")

            elif quantization_type == "fp16":
                adapter_model = adapter_model.half()
                logger.info(f"✅ Applied FP16 quantization")

            return adapter_model

        except Exception as e:
            logger.error(f"❌ Quantization failed: {e}")
            return None


class LoRAIncrementalTrainer:
    """
    Incremental LoRA Fine-tuning

    Supports continuing training from previous checkpoints.
    """

    def __init__(self, base_model: Any, checkpoint_dir: Optional[str] = None):
        """Initialize incremental trainer"""
        self.base_model = base_model
        self.training_history: List[Dict[str, Any]] = []

        if checkpoint_dir is None:
            checkpoint_dir = "/var/lib/x0tta6bl4/lora_checkpoints"

        self.checkpoint_dir = Path(checkpoint_dir)
        try:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to temp directory if /var/lib not accessible
            import tempfile

            self.checkpoint_dir = (
                Path(tempfile.gettempdir()) / "x0tta6bl4_lora_checkpoints"
            )
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def load_checkpoint(self, checkpoint_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load training checkpoint.

        Args:
            checkpoint_path: Path to checkpoint

        Returns:
            Checkpoint data or None if failed
        """
        try:
            metadata_file = checkpoint_path / "checkpoint_metadata.json"
            if not metadata_file.exists():
                logger.error(f"❌ Checkpoint metadata not found: {metadata_file}")
                return None

            with open(metadata_file, "r") as f:
                checkpoint = json.load(f)

            logger.info(f"📂 Loaded checkpoint from {checkpoint_path}")
            return checkpoint

        except Exception as e:
            logger.error(f"❌ Failed to load checkpoint: {e}")
            return None

    def save_checkpoint(
        self,
        checkpoint_name: str,
        model_state: Dict[str, Any],
        training_stats: Dict[str, Any],
    ) -> bool:
        """
        Save training checkpoint.

        Args:
            checkpoint_name: Name of checkpoint
            model_state: Model state dict
            training_stats: Training statistics

        Returns:
            True if saved successfully
        """
        try:
            checkpoint_path = self.checkpoint_dir / checkpoint_name
            checkpoint_path.mkdir(parents=True, exist_ok=True)

            # Save metadata
            metadata = {
                "checkpoint_name": checkpoint_name,
                "training_stats": training_stats,
                "timestamp": str(Path.cwd()),
            }

            metadata_file = checkpoint_path / "checkpoint_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"💾 Saved checkpoint: {checkpoint_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save checkpoint: {e}")
            return False

    def resume_training(
        self, checkpoint_path: Path, additional_epochs: int = 1
    ) -> Dict[str, Any]:
        """
        Resume training from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint
            additional_epochs: Additional epochs to train

        Returns:
            Training results
        """
        checkpoint = self.load_checkpoint(checkpoint_path)
        if not checkpoint:
            return {"success": False, "error": "Failed to load checkpoint"}

        logger.info(f"🚀 Resuming training for {additional_epochs} additional epochs")

        return {
            "success": True,
            "checkpoint": checkpoint,
            "additional_epochs": additional_epochs,
            "previous_epochs": checkpoint.get("training_stats", {}).get("epochs", 0),
        }


class LoRAPerformanceMonitor:
    """
    Performance monitoring for LoRA adapters.
    """

    def __init__(self):
        """Initialize performance monitor"""
        self.metrics: Dict[str, List[float]] = {
            "inference_latency_ms": [],
            "memory_usage_mb": [],
            "throughput_samples_per_sec": [],
            "adapter_overhead_percent": [],
        }

    def record_inference(
        self, latency_ms: float, memory_mb: float, throughput: float
    ) -> None:
        """Record inference metrics"""
        self.metrics["inference_latency_ms"].append(latency_ms)
        self.metrics["memory_usage_mb"].append(memory_mb)
        self.metrics["throughput_samples_per_sec"].append(throughput)

    def record_adapter_overhead(self, overhead_percent: float) -> None:
        """Record adapter overhead percentage"""
        self.metrics["adapter_overhead_percent"].append(overhead_percent)

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        summary = {}

        for metric_name, values in self.metrics.items():
            if values:
                summary[f"{metric_name}_mean"] = float(np.mean(values))
                summary[f"{metric_name}_std"] = float(np.std(values))
                summary[f"{metric_name}_min"] = float(np.min(values))
                summary[f"{metric_name}_max"] = float(np.max(values))

        return summary
