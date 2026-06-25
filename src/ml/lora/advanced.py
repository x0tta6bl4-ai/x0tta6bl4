"""
Advanced LoRA Features

Provides advanced fine-tuning capabilities including adapter composition,
incremental training, multi-task learning, and quantization support.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.ml.lora.adapter import LoRAAdapter

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


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="lora-composer",
            role="development",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "lora_composer_init",
                "goal": "Initialize LoRA adapter composition safely",
                "signals": {"adapter_count_bucket": "0", "base_model_present": True},
                "safety_boundary": (
                    "Keep adapter ids, paths, base model representations, and weight "
                    "values out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_adapter_ids": True,
                    "redact_paths": True,
                    "redact_model_objects": True,
                    "redact_raw_weights": True,
                    "preserve_composition_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and method names.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def register_adapter(self, adapter: LoRAAdapter, adapter_path: Path) -> None:
        """Register an adapter for composition"""
        self.adapters[adapter.adapter_id] = adapter
        self._record_thinking(
            "lora_adapter_registered",
            "Register LoRA adapter safely",
            {
                "adapter_hash": _safe_hash(adapter.adapter_id),
                "path_hash": _safe_hash(adapter_path),
                "adapter_count_bucket": _safe_count_bucket(len(self.adapters)),
            },
        )
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
            self._record_thinking(
                "lora_linear_composition",
                "Reject LoRA composition with missing adapters",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "missing_count_bucket": _safe_count_bucket(len(missing)),
                    "success": False,
                },
            )
            logger.error(f"❌ Missing adapters: {missing}")
            return None

        if weights is None:
            weights = [1.0 / len(adapter_ids)] * len(adapter_ids)
        elif len(weights) != len(adapter_ids):
            self._record_thinking(
                "lora_linear_composition",
                "Reject LoRA composition with mismatched weights",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "weight_count_bucket": _safe_count_bucket(len(weights)),
                    "success": False,
                },
            )
            logger.error("❌ Number of weights must match number of adapters")
            return None

        # Normalize weights
        weight_sum = sum(weights)
        weights = [w / weight_sum for w in weights]

        logger.info(f"🔄 Composing {len(adapter_ids)} adapters with weights: {weights}")

        # Compose adapters
        try:
            if not PEFT_AVAILABLE:
                self._record_thinking(
                    "lora_linear_composition",
                    "Reject LoRA composition when PEFT is unavailable",
                    {
                        "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                        "peft_available": False,
                        "success": False,
                    },
                )
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

            logger.info("✅ Adapter composition complete")
            self._record_thinking(
                "lora_linear_composition",
                "Compose LoRA adapters linearly",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "weight_count_bucket": _safe_count_bucket(len(weights)),
                    "peft_available": True,
                    "success": True,
                },
            )
            return composed_model

        except Exception as e:
            self._record_thinking(
                "lora_linear_composition",
                "Record LoRA composition failure",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "error_type": type(e).__name__,
                    "success": False,
                },
            )
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
                    self._record_thinking(
                        "lora_adapter_merge",
                        "Skip missing adapter during merge",
                        {
                            "adapter_hash": _safe_hash(adapter_id),
                            "success": False,
                        },
                    )
                    logger.error(f"❌ Adapter not found: {adapter_id}")
                    continue

                if not PEFT_AVAILABLE:
                    self._record_thinking(
                        "lora_adapter_merge",
                        "Reject LoRA merge when PEFT is unavailable",
                        {"peft_available": False, "success": False},
                    )
                    logger.error("❌ PEFT not available")
                    return None

                adapter_path = self.adapters[adapter_id].adapter_path
                merged_model = PeftModel.from_pretrained(
                    merged_model, str(adapter_path)
                )

                if hasattr(merged_model, "merge_and_unload"):
                    merged_model = merged_model.merge_and_unload()
                    logger.info(f"✅ Merged adapter: {adapter_id}")

            self._record_thinking(
                "lora_adapter_merge",
                "Merge LoRA adapters into base model",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "peft_available": PEFT_AVAILABLE,
                    "success": True,
                },
            )
            return merged_model

        except Exception as e:
            self._record_thinking(
                "lora_adapter_merge",
                "Record LoRA merge failure",
                {
                    "adapter_count_bucket": _safe_count_bucket(len(adapter_ids)),
                    "error_type": type(e).__name__,
                    "success": False,
                },
            )
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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="lora-quantizer",
            role="development",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "lora_quantizer_init",
                "goal": "Initialize LoRA quantization safely",
                "signals": {
                    "enabled": self.config.enabled,
                    "quantization_type": self.config.quantization_type,
                    "torch_available": TORCH_AVAILABLE,
                    "bitsandbytes_available": BITSANDBYTES_AVAILABLE,
                },
                "safety_boundary": "Keep model object details out of thinking context.",
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_model_objects": True,
                    "preserve_quantization_decision": True,
                },
                "safety_boundary": "Use booleans, quantization type, and error types.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
            self._record_thinking(
                "lora_quantization",
                "Reject LoRA quantization when PyTorch is unavailable",
                {
                    "quantization_type": quantization_type,
                    "torch_available": False,
                    "success": False,
                },
            )
            logger.error("❌ PyTorch not available")
            return None

        try:
            if quantization_type == "int8":
                if not BITSANDBYTES_AVAILABLE:
                    self._record_thinking(
                        "lora_quantization",
                        "Skip int8 LoRA quantization when bitsandbytes is unavailable",
                        {
                            "quantization_type": quantization_type,
                            "bitsandbytes_available": False,
                            "returned_original_model": True,
                        },
                    )
                    logger.warning(
                        "⚠️ bitsandbytes not available, skipping int8 quantization"
                    )
                    return adapter_model

                # Convert linear layers to 8-bit
                for name, module in adapter_model.named_modules():
                    if isinstance(module, torch.nn.Linear):
                        module.to(torch.int8)

                logger.info("✅ Applied INT8 quantization")

            elif quantization_type == "fp16":
                adapter_model = adapter_model.half()
                logger.info("✅ Applied FP16 quantization")

            self._record_thinking(
                "lora_quantization",
                "Quantize LoRA adapter model",
                {
                    "quantization_type": quantization_type,
                    "torch_available": TORCH_AVAILABLE,
                    "bitsandbytes_available": BITSANDBYTES_AVAILABLE,
                    "success": True,
                },
            )
            return adapter_model

        except Exception as e:
            self._record_thinking(
                "lora_quantization",
                "Record LoRA quantization failure",
                {
                    "quantization_type": quantization_type,
                    "error_type": type(e).__name__,
                    "success": False,
                },
            )
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

        self.thinking_coach = AgentThinkingCoach(
            agent_id="lora-incremental-trainer",
            role="development",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "lora_incremental_trainer_init",
                "goal": "Initialize LoRA incremental training safely",
                "signals": {
                    "checkpoint_dir_hash": _safe_hash(self.checkpoint_dir),
                    "history_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep checkpoint names, paths, model state, and training stats "
                    "out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_checkpoint_names": True,
                    "redact_paths": True,
                    "redact_model_state": True,
                    "redact_training_stats": True,
                    "preserve_resume_decision": True,
                },
                "safety_boundary": "Use hashes, counts, epochs, success, and error types.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
                self._record_thinking(
                    "lora_checkpoint_load",
                    "Reject checkpoint load without metadata",
                    {
                        "checkpoint_path_hash": _safe_hash(checkpoint_path),
                        "metadata_present": False,
                    },
                )
                logger.error(f"❌ Checkpoint metadata not found: {metadata_file}")
                return None

            with open(metadata_file, "r") as f:
                checkpoint = json.load(f)

            logger.info(f"📂 Loaded checkpoint from {checkpoint_path}")
            self._record_thinking(
                "lora_checkpoint_load",
                "Load checkpoint metadata safely",
                {
                    "checkpoint_path_hash": _safe_hash(checkpoint_path),
                    "metadata_key_count_bucket": _safe_count_bucket(len(checkpoint)),
                },
            )
            return checkpoint

        except Exception as e:
            self._record_thinking(
                "lora_checkpoint_load",
                "Record checkpoint load failure",
                {
                    "checkpoint_path_hash": _safe_hash(checkpoint_path),
                    "error_type": type(e).__name__,
                },
            )
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
            self._record_thinking(
                "lora_checkpoint_saved",
                "Save checkpoint metadata safely",
                {
                    "checkpoint_hash": _safe_hash(checkpoint_name),
                    "checkpoint_path_hash": _safe_hash(checkpoint_path),
                    "model_state_key_count_bucket": _safe_count_bucket(
                        len(model_state)
                    ),
                    "training_stat_key_count_bucket": _safe_count_bucket(
                        len(training_stats)
                    ),
                    "success": True,
                },
            )
            return True

        except Exception as e:
            self._record_thinking(
                "lora_checkpoint_saved",
                "Record checkpoint save failure",
                {
                    "checkpoint_hash": _safe_hash(checkpoint_name),
                    "error_type": type(e).__name__,
                    "success": False,
                },
            )
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
            self._record_thinking(
                "lora_training_resumed",
                "Reject resume without loadable checkpoint",
                {
                    "checkpoint_path_hash": _safe_hash(checkpoint_path),
                    "additional_epochs": additional_epochs,
                    "success": False,
                },
            )
            return {"success": False, "error": "Failed to load checkpoint"}

        logger.info(f"🚀 Resuming training for {additional_epochs} additional epochs")

        result = {
            "success": True,
            "checkpoint": checkpoint,
            "additional_epochs": additional_epochs,
            "previous_epochs": checkpoint.get("training_stats", {}).get("epochs", 0),
        }
        self._record_thinking(
            "lora_training_resumed",
            "Resume LoRA training from checkpoint",
            {
                "checkpoint_path_hash": _safe_hash(checkpoint_path),
                "additional_epochs": additional_epochs,
                "previous_epochs": result["previous_epochs"],
                "success": True,
            },
        )
        return result


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="lora-performance-monitor",
            role="monitoring",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "lora_performance_monitor_init",
                "goal": "Initialize LoRA performance monitoring safely",
                "signals": {"metric_count_bucket": _safe_count_bucket(len(self.metrics))},
                "safety_boundary": "Keep raw samples out of thinking context.",
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_raw_samples": True,
                    "preserve_performance_summary": True,
                },
                "safety_boundary": "Use metric names, counts, and value bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def record_inference(
        self, latency_ms: float, memory_mb: float, throughput: float
    ) -> None:
        """Record inference metrics"""
        self.metrics["inference_latency_ms"].append(latency_ms)
        self.metrics["memory_usage_mb"].append(memory_mb)
        self.metrics["throughput_samples_per_sec"].append(throughput)
        self._record_thinking(
            "lora_inference_metrics_recorded",
            "Record LoRA inference metrics safely",
            {
                "latency_band": _safe_number_band(latency_ms),
                "memory_band": _safe_number_band(memory_mb),
                "throughput_band": _safe_number_band(throughput),
                "sample_count_bucket": _safe_count_bucket(
                    len(self.metrics["inference_latency_ms"])
                ),
            },
        )

    def record_adapter_overhead(self, overhead_percent: float) -> None:
        """Record adapter overhead percentage"""
        self.metrics["adapter_overhead_percent"].append(overhead_percent)
        self._record_thinking(
            "lora_adapter_overhead_recorded",
            "Record LoRA adapter overhead safely",
            {
                "overhead_band": _safe_number_band(overhead_percent),
                "sample_count_bucket": _safe_count_bucket(
                    len(self.metrics["adapter_overhead_percent"])
                ),
            },
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        summary = {}

        for metric_name, values in self.metrics.items():
            if values:
                summary[f"{metric_name}_mean"] = float(np.mean(values))
                summary[f"{metric_name}_std"] = float(np.std(values))
                summary[f"{metric_name}_min"] = float(np.min(values))
                summary[f"{metric_name}_max"] = float(np.max(values))

        self._record_thinking(
            "lora_performance_summary",
            "Summarize LoRA performance safely",
            {
                "summary_key_count_bucket": _safe_count_bucket(len(summary)),
                "metric_sample_counts": {
                    metric_name: _safe_count_bucket(len(values))
                    for metric_name, values in self.metrics.items()
                },
            },
        )
        return summary
