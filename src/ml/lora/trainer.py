"""
LoRA Fine-tuning Trainer

Training scaffold for LoRA adapters.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from src.ml.lora.config import LoRAConfig
from src.ml.lora.adapter import LoRAAdapter, save_lora_adapter

logger = logging.getLogger(__name__)

# Monitoring metrics
try:
    from src.monitoring import record_lora_training_update
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    def record_lora_training_update(*args, **kwargs): pass

# Optional imports
try:
    import torch
    import torch.nn as nn
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    TrainingArguments = None
    Trainer = None
    DataCollatorForLanguageModeling = None
    logger.warning("⚠️ PyTorch/Transformers not available")

try:
    from peft import LoraConfig, get_peft_model, TaskType
    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    LoraConfig = None
    get_peft_model = None
    TaskType = None
    logger.warning("⚠️ PEFT not available. Install with: pip install peft")


@dataclass
class LoRATrainingResult:
    """Result of LoRA training"""
    adapter_id: str
    base_model_name: str
    config: LoRAConfig
    training_loss: List[float] = field(default_factory=list)
    validation_loss: Optional[float] = None
    training_time_seconds: float = 0.0
    epochs_completed: int = 0
    steps_completed: int = 0
    success: bool = False
    error_message: Optional[str] = None
    adapter_path: Optional[Path] = None


class LoRATrainer:
    """
    LoRA fine-tuning trainer scaffold.
    
    Provides training infrastructure for LoRA adapters.
    """
    
    def __init__(
        self,
        base_model_name: str = "meta-llama/Llama-2-7b-hf",
        config: Optional[LoRAConfig] = None,
        output_dir: Path = Path("/var/lib/x0tta6bl4/lora_adapters")
    ):
        """
        Initialize LoRA trainer.
        
        Args:
            base_model_name: Base model name (HuggingFace)
            config: LoRA configuration
            output_dir: Output directory for adapters
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch not available. Install: pip install torch transformers")
        
        if not PEFT_AVAILABLE:
            raise ImportError("PEFT not available. Install: pip install peft")
        
        self.base_model_name = base_model_name
        self.config = config or LoRAConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.base_model = None
        self.tokenizer = None
        self.peft_model = None
        
        logger.info(f"✅ LoRATrainer initialized for {base_model_name}")
    
    def load_base_model(self) -> bool:
        """
        Load base model and tokenizer.
        
        Returns:
            True if loaded successfully
        """
        try:
            logger.info(f"📂 Loading base model: {self.base_model_name}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
            
            logger.info("✅ Base model loaded")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load base model: {e}")
            return False
    
    def setup_lora(self) -> bool:
        """
        Setup LoRA adapter on base model.
        
        Returns:
            True if setup successfully
        """
        if self.base_model is None:
            logger.error("❌ Base model not loaded. Call load_base_model() first.")
            return False
        
        try:
            # Create PEFT config
            peft_config = LoraConfig(
                r=self.config.r,
                lora_alpha=self.config.alpha,
                lora_dropout=self.config.dropout,
                target_modules=self.config.target_modules,
                bias=self.config.bias,
                task_type=TaskType.CAUSAL_LM
            )
            
            # Apply LoRA
            self.peft_model = get_peft_model(self.base_model, peft_config)
            
            # Print trainable parameters
            trainable_params = sum(p.numel() for p in self.peft_model.parameters() if p.requires_grad)
            total_params = sum(p.numel() for p in self.peft_model.parameters())
            
            logger.info(f"✅ LoRA adapter setup complete")
            logger.info(f"   Trainable params: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
            logger.info(f"   Total params: {total_params:,}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup LoRA: {e}")
            return False
    
    def train(
        self,
        train_dataset: Any,
        adapter_id: str,
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        validation_dataset: Optional[Any] = None,
        save_steps: int = 500,
        logging_steps: int = 100
    ) -> LoRATrainingResult:
        """
        Train LoRA adapter.
        
        Args:
            train_dataset: Training dataset
            adapter_id: Adapter identifier
            num_epochs: Number of training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            validation_dataset: Validation dataset (optional)
            save_steps: Save checkpoint every N steps
            logging_steps: Log metrics every N steps
        
        Returns:
            LoRATrainingResult
        
        Raises:
            ValueError: If adapter_id is empty or invalid parameters
            RuntimeError: If model not loaded or LoRA not setup
        """
        if not adapter_id or not adapter_id.strip():
            raise ValueError("Adapter ID cannot be empty")
        if num_epochs < 1:
            raise ValueError("num_epochs must be >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if learning_rate <= 0:
            raise ValueError("learning_rate must be > 0")
        """
        Train LoRA adapter.
        
        Args:
            train_dataset: Training dataset
            adapter_id: Adapter identifier
            num_epochs: Number of training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            validation_dataset: Validation dataset (optional)
            save_steps: Save checkpoint every N steps
            logging_steps: Log metrics every N steps
        
        Returns:
            LoRATrainingResult
        """
        if self.peft_model is None:
            logger.error("❌ LoRA not setup. Call setup_lora() first.")
            return LoRATrainingResult(
                adapter_id=adapter_id,
                base_model_name=self.base_model_name,
                config=self.config,
                success=False,
                error_message="LoRA not setup"
            )
        
        start_time = time.time()
        result = LoRATrainingResult(
            adapter_id=adapter_id,
            base_model_name=self.base_model_name,
            config=self.config
        )
        
        try:
            # Prepare output directory
            adapter_output_dir = self.output_dir / adapter_id
            adapter_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=str(adapter_output_dir),
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size if validation_dataset else None,
                learning_rate=learning_rate,
                logging_steps=logging_steps,
                save_steps=save_steps,
                evaluation_strategy="epoch" if validation_dataset else "no",
                save_total_limit=3,
                load_best_model_at_end=True if validation_dataset else False,
                fp16=torch.cuda.is_available(),
                report_to="none"  # Disable wandb/tensorboard for scaffold
            )
            
            # Data collator
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False  # Causal LM, not masked LM
            )
            
            # Trainer
            trainer = Trainer(
                model=self.peft_model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=validation_dataset,
                data_collator=data_collator
            )
            
            # Train
            logger.info(f"🚀 Starting LoRA training for adapter {adapter_id}")
            train_result = trainer.train()
            
            # Extract training loss
            if hasattr(train_result, 'training_loss'):
                result.training_loss = [train_result.training_loss]  # Simplified
            if hasattr(train_result, 'log_history'):
                result.training_loss = [
                    log.get('loss', 0.0) for log in train_result.log_history
                    if 'loss' in log
                ]
            
            # Record training metrics per epoch
            for epoch in range(num_epochs):
                loss = result.training_loss[epoch] if epoch < len(result.training_loss) else result.training_loss[-1]
                record_lora_training_update(adapter_id, loss, epoch)
            
            # Validation loss
            if validation_dataset:
                eval_result = trainer.evaluate()
                result.validation_loss = eval_result.get('eval_loss', None)
            
            # Save adapter
            trainer.save_model()
            result.adapter_path = adapter_output_dir
            
            # Create adapter metadata
            adapter = LoRAAdapter(
                adapter_id=adapter_id,
                base_model_name=self.base_model_name,
                config=self.config,
                metadata={
                    'num_epochs': num_epochs,
                    'batch_size': batch_size,
                    'learning_rate': learning_rate,
                    'training_loss': result.training_loss[-1] if result.training_loss else None,
                    'validation_loss': result.validation_loss
                }
            )
            save_lora_adapter(adapter, adapter_output_dir, self.peft_model)
            
            result.training_time_seconds = time.time() - start_time
            result.epochs_completed = num_epochs
            result.steps_completed = len(train_dataset) // batch_size * num_epochs
            result.success = True
            
            logger.info(f"✅ LoRA training complete: {adapter_id} ({result.training_time_seconds:.1f}s)")
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            result.training_time_seconds = time.time() - start_time
            logger.error(f"❌ LoRA training failed: {e}")
        
        return result
    
    def get_trainable_parameters(self) -> Dict[str, int]:
        """
        Get trainable parameter statistics.
        
        Returns:
            Dict with parameter counts
        """
        if self.peft_model is None:
            return {}
        
        trainable = sum(p.numel() for p in self.peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.peft_model.parameters())
        frozen = total - trainable
        
        return {
            'trainable': trainable,
            'frozen': frozen,
            'total': total,
            'trainable_percent': 100 * trainable / total if total > 0 else 0
        }

