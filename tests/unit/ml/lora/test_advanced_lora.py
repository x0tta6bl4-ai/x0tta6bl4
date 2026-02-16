"""
Unit tests for Advanced LoRA Features
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from src.ml.lora.adapter import LoRAAdapter
    from src.ml.lora.advanced import (LoRAComposer, LoRACompositionConfig,
                                      LoRAIncrementalTrainer,
                                      LoRAPerformanceMonitor,
                                      LoRAQuantizationConfig, LoRAQuantizer)
    from src.ml.lora.config import LoRAConfig

    ADVANCED_LORA_AVAILABLE = True
except ImportError:
    ADVANCED_LORA_AVAILABLE = False


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRAComposer:
    """Tests for LoRA Adapter Composition"""

    def test_composer_initialization(self):
        """Test LoRA composer initialization"""
        base_model = Mock()
        composer = LoRAComposer(base_model)

        assert composer.base_model is base_model
        assert len(composer.adapters) == 0
        assert composer.composition_config is None

    def test_register_adapter(self):
        """Test registering adapters"""
        base_model = Mock()
        composer = LoRAComposer(base_model)

        config = LoRAConfig()
        adapter1 = LoRAAdapter(
            adapter_id="adapter_001", base_model_name="test_model", config=config
        )

        composer.register_adapter(adapter1, Path("/tmp/adapter1"))

        assert "adapter_001" in composer.adapters
        assert composer.adapters["adapter_001"] == adapter1

    def test_compose_linear_missing_adapters(self):
        """Test composition fails with missing adapters"""
        base_model = Mock()
        composer = LoRAComposer(base_model)

        result = composer.compose_linear(["missing_001", "missing_002"])

        assert result is None

    def test_compose_linear_weight_mismatch(self):
        """Test composition fails with mismatched weights"""
        base_model = Mock()
        composer = LoRAComposer(base_model)

        config = LoRAConfig()
        adapter1 = LoRAAdapter(
            adapter_id="adapter_001", base_model_name="test_model", config=config
        )

        composer.register_adapter(adapter1, Path("/tmp/adapter1"))

        result = composer.compose_linear(["adapter_001"], weights=[0.5, 0.5])

        assert result is None

    def test_merge_adapters(self):
        """Test adapter merging"""
        base_model = Mock()
        composer = LoRAComposer(base_model)

        config = LoRAConfig()
        adapter1 = LoRAAdapter(
            adapter_id="adapter_001", base_model_name="test_model", config=config
        )

        composer.register_adapter(adapter1, Path("/tmp/adapter1"))

        with patch("src.ml.lora.advanced.PEFT_AVAILABLE", False):
            result = composer.merge_adapters(["adapter_001"])
            assert result is None


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRAQuantizer:
    """Tests for LoRA Quantization"""

    def test_quantizer_initialization(self):
        """Test quantizer initialization"""
        config = LoRAQuantizationConfig()
        quantizer = LoRAQuantizer(config)

        assert quantizer.config is not None
        assert quantizer.config.quantization_type == "int8"

    def test_quantizer_default_config(self):
        """Test quantizer with default config"""
        quantizer = LoRAQuantizer()

        assert quantizer.config.enabled == False
        assert quantizer.config.quantization_type == "int8"

    def test_quantize_adapter_pytorch_unavailable(self):
        """Test quantization fails without PyTorch"""
        with patch("src.ml.lora.advanced.TORCH_AVAILABLE", False):
            quantizer = LoRAQuantizer()
            model = Mock()

            result = quantizer.quantize_adapter(model, "int8")
            assert result is None

    def test_quantize_adapter_int8(self):
        """Test INT8 quantization"""
        quantizer = LoRAQuantizer()
        model = Mock()

        with patch("src.ml.lora.advanced.TORCH_AVAILABLE", True):
            with patch("src.ml.lora.advanced.BITSANDBYTES_AVAILABLE", False):
                result = quantizer.quantize_adapter(model, "int8")
                assert result == model


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRAIncrementalTrainer:
    """Tests for Incremental LoRA Training"""

    def test_incremental_trainer_initialization(self):
        """Test incremental trainer initialization"""
        base_model = Mock()
        trainer = LoRAIncrementalTrainer(base_model)

        assert trainer.base_model is base_model
        assert len(trainer.training_history) == 0
        assert trainer.checkpoint_dir.exists()

    def test_save_checkpoint(self):
        """Test saving checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_model = Mock()
            trainer = LoRAIncrementalTrainer(base_model)
            trainer.checkpoint_dir = Path(tmpdir)

            success = trainer.save_checkpoint(
                "test_checkpoint", {"model_state": "dummy"}, {"loss": 0.5, "epochs": 1}
            )

            assert success == True
            assert (
                Path(tmpdir) / "test_checkpoint" / "checkpoint_metadata.json"
            ).exists()

    def test_load_checkpoint_missing(self):
        """Test loading missing checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_model = Mock()
            trainer = LoRAIncrementalTrainer(base_model)

            checkpoint = trainer.load_checkpoint(Path(tmpdir))
            assert checkpoint is None

    def test_load_checkpoint_valid(self):
        """Test loading valid checkpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_model = Mock()
            trainer = LoRAIncrementalTrainer(base_model)
            trainer.checkpoint_dir = Path(tmpdir)

            # Save checkpoint
            trainer.save_checkpoint(
                "test_checkpoint", {"state": "dummy"}, {"loss": 0.5}
            )

            # Load checkpoint
            checkpoint_path = Path(tmpdir) / "test_checkpoint"
            loaded = trainer.load_checkpoint(checkpoint_path)

            assert loaded is not None
            assert "checkpoint_name" in loaded
            assert "training_stats" in loaded

    def test_resume_training(self):
        """Test resuming training"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_model = Mock()
            trainer = LoRAIncrementalTrainer(base_model)
            trainer.checkpoint_dir = Path(tmpdir)

            # Save checkpoint
            trainer.save_checkpoint(
                "test_checkpoint", {"state": "dummy"}, {"loss": 0.5, "epochs": 3}
            )

            # Resume training
            checkpoint_path = Path(tmpdir) / "test_checkpoint"
            result = trainer.resume_training(checkpoint_path, additional_epochs=2)

            assert result["success"] == True
            assert result["additional_epochs"] == 2
            assert result["previous_epochs"] == 3


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRAPerformanceMonitor:
    """Tests for LoRA Performance Monitoring"""

    def test_monitor_initialization(self):
        """Test performance monitor initialization"""
        monitor = LoRAPerformanceMonitor()

        assert len(monitor.metrics) == 4
        assert all(len(v) == 0 for v in monitor.metrics.values())

    def test_record_inference(self):
        """Test recording inference metrics"""
        monitor = LoRAPerformanceMonitor()

        monitor.record_inference(10.5, 256.3, 95.2)
        monitor.record_inference(11.2, 257.1, 94.8)

        assert len(monitor.metrics["inference_latency_ms"]) == 2
        assert len(monitor.metrics["memory_usage_mb"]) == 2
        assert len(monitor.metrics["throughput_samples_per_sec"]) == 2

    def test_record_adapter_overhead(self):
        """Test recording adapter overhead"""
        monitor = LoRAPerformanceMonitor()

        monitor.record_adapter_overhead(2.5)
        monitor.record_adapter_overhead(3.1)

        assert len(monitor.metrics["adapter_overhead_percent"]) == 2

    def test_get_summary(self):
        """Test getting performance summary"""
        monitor = LoRAPerformanceMonitor()

        # Record some metrics
        monitor.record_inference(10.0, 256.0, 100.0)
        monitor.record_inference(12.0, 264.0, 98.0)
        monitor.record_adapter_overhead(2.5)
        monitor.record_adapter_overhead(2.8)

        summary = monitor.get_summary()

        assert "inference_latency_ms_mean" in summary
        assert "inference_latency_ms_std" in summary
        assert "memory_usage_mb_mean" in summary
        assert "adapter_overhead_percent_mean" in summary

        # Verify statistics
        assert summary["inference_latency_ms_mean"] == 11.0
        assert summary["memory_usage_mb_mean"] == 260.0

    def test_get_summary_empty(self):
        """Test getting summary with no data"""
        monitor = LoRAPerformanceMonitor()

        summary = monitor.get_summary()

        assert len(summary) == 0


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRACompositionConfig:
    """Tests for LoRA Composition Configuration"""

    def test_composition_config_defaults(self):
        """Test composition config with defaults"""
        config = LoRACompositionConfig(adapters=["adapter_001", "adapter_002"])

        assert config.adapters == ["adapter_001", "adapter_002"]
        assert config.weights is None
        assert config.fusion_method == "linear"
        assert config.normalize_weights == True

    def test_composition_config_with_weights(self):
        """Test composition config with weights"""
        config = LoRACompositionConfig(
            adapters=["adapter_001", "adapter_002"], weights=[0.3, 0.7]
        )

        assert config.weights == [0.3, 0.7]


@pytest.mark.skipif(not ADVANCED_LORA_AVAILABLE, reason="Advanced LoRA not available")
class TestLoRAQuantizationConfig:
    """Tests for LoRA Quantization Configuration"""

    def test_quantization_config_defaults(self):
        """Test quantization config with defaults"""
        config = LoRAQuantizationConfig()

        assert config.enabled == False
        assert config.quantization_type == "int8"
        assert config.dynamic == True
        assert config.optimize_memory == True

    def test_quantization_config_custom(self):
        """Test quantization config with custom values"""
        config = LoRAQuantizationConfig(
            enabled=True, quantization_type="fp16", dynamic=False
        )

        assert config.enabled == True
        assert config.quantization_type == "fp16"
        assert config.dynamic == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
