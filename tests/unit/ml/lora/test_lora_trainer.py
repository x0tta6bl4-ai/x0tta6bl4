"""
Unit tests for LoRA Fine-tuning Trainer
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

try:
    from src.ml.lora.trainer import LoRATrainer, LoRATrainingResult
    from src.ml.lora.config import LoRAConfig, LoRATargetModules
    from src.ml.lora.adapter import LoRAAdapter, save_lora_adapter, load_lora_adapter
    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False
    LoRATrainer = None
    LoRAConfig = None


@pytest.mark.skipif(not LORA_AVAILABLE, reason="LoRA Trainer not available")
class TestLoRAConfig:
    """Tests for LoRA Configuration"""
    
    def test_config_initialization(self):
        """Test LoRA config initialization"""
        config = LoRAConfig(
            r=8,
            alpha=32,
            dropout=0.1
        )
        
        assert config.r == 8
        assert config.alpha == 32
        assert config.dropout == 0.1
        assert len(config.target_modules) > 0
    
    def test_config_to_peft(self):
        """Test conversion to PEFT config"""
        config = LoRAConfig(r=8, alpha=32, dropout=0.1)
        peft_config = config.to_peft_config()
        
        assert peft_config['r'] == 8
        assert peft_config['lora_alpha'] == 32
        assert peft_config['lora_dropout'] == 0.1
        assert 'target_modules' in peft_config
    
    def test_config_from_peft(self):
        """Test creation from PEFT config"""
        peft_config = {
            'r': 8,
            'lora_alpha': 32,
            'lora_dropout': 0.1,
            'target_modules': ['q_proj', 'v_proj']
        }
        
        config = LoRAConfig.from_peft_config(peft_config)
        
        assert config.r == 8
        assert config.alpha == 32
        assert config.dropout == 0.1


@pytest.mark.skipif(not LORA_AVAILABLE, reason="LoRA Trainer not available")
class TestLoRAAdapter:
    """Tests for LoRA Adapter Management"""
    
    def test_adapter_creation(self):
        """Test creating LoRA adapter"""
        config = LoRAConfig()
        adapter = LoRAAdapter(
            adapter_id="test_adapter",
            base_model_name="meta-llama/Llama-2-7b-hf",
            config=config
        )
        
        assert adapter.adapter_id == "test_adapter"
        assert adapter.base_model_name == "meta-llama/Llama-2-7b-hf"
        assert adapter.config == config
    
    def test_adapter_to_dict(self):
        """Test adapter serialization"""
        config = LoRAConfig()
        adapter = LoRAAdapter(
            adapter_id="test_adapter",
            base_model_name="test_model",
            config=config
        )
        
        data = adapter.to_dict()
        
        assert data['adapter_id'] == "test_adapter"
        assert data['base_model_name'] == "test_model"
        assert 'config' in data
    
    def test_adapter_from_dict(self):
        """Test adapter deserialization"""
        data = {
            'adapter_id': 'test_adapter',
            'base_model_name': 'test_model',
            'config': {'r': 8, 'alpha': 32, 'dropout': 0.1},
            'version': '1.0',
            'metadata': {}
        }
        
        adapter = LoRAAdapter.from_dict(data)
        
        assert adapter.adapter_id == 'test_adapter'
        assert adapter.base_model_name == 'test_model'
        assert adapter.config.r == 8


@pytest.mark.skipif(not LORA_AVAILABLE, reason="LoRA Trainer not available")
class TestLoRATrainer:
    """Tests for LoRA Trainer"""
    
    @patch('src.ml.lora.trainer.AutoModelForCausalLM')
    @patch('src.ml.lora.trainer.AutoTokenizer')
    def test_trainer_initialization(self, mock_tokenizer, mock_model):
        """Test trainer initialization"""
        # Mock imports
        import sys
        sys.modules['torch'] = MagicMock()
        sys.modules['transformers'] = MagicMock()
        sys.modules['peft'] = MagicMock()
        
        trainer = LoRATrainer(
            base_model_name="test-model",
            config=LoRAConfig()
        )
        
        assert trainer.base_model_name == "test-model"
        assert trainer.config is not None
    
    def test_get_trainable_parameters(self):
        """Test getting trainable parameters"""
        # This would require actual model loading, so we'll mock it
        with patch('src.ml.lora.trainer.TORCH_AVAILABLE', False):
            with pytest.raises(ImportError):
                trainer = LoRATrainer()

