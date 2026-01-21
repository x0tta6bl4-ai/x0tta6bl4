"""
LoRA Adapter Management

Handles loading, saving, and managing LoRA adapters.
"""

import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict

from src.ml.lora.config import LoRAConfig

logger = logging.getLogger(__name__)

# Optional PEFT import
try:
    from peft import PeftModel, LoraConfig, get_peft_model
    PEFT_AVAILABLE = True
except ImportError:
    PEFT_AVAILABLE = False
    PeftModel = None
    LoraConfig = None
    get_peft_model = None
    logger.warning("⚠️ PEFT not available. Install with: pip install peft")


@dataclass
class LoRAAdapter:
    """
    LoRA adapter metadata and configuration.
    
    Represents a trained LoRA adapter that can be applied to a base model.
    """
    adapter_id: str
    base_model_name: str
    config: LoRAConfig
    version: str = "1.0"
    metadata: Dict[str, Any] = None
    adapter_path: Optional[Path] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided"""
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "adapter_id": self.adapter_id,
            "base_model_name": self.base_model_name,
            "config": asdict(self.config),
            "version": self.version,
            "metadata": self.metadata,
            "adapter_path": str(self.adapter_path) if self.adapter_path else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoRAAdapter':
        """Create from dictionary"""
        config = LoRAConfig(**data.get("config", {}))
        adapter = cls(
            adapter_id=data["adapter_id"],
            base_model_name=data["base_model_name"],
            config=config,
            version=data.get("version", "1.0"),
            metadata=data.get("metadata", {}),
            adapter_path=Path(data["adapter_path"]) if data.get("adapter_path") else None
        )
        return adapter


def save_lora_adapter(
    adapter: LoRAAdapter,
    save_path: Path,
    model: Optional[Any] = None
) -> bool:
    """
    Save LoRA adapter to disk.
    
    Args:
        adapter: LoRAAdapter instance
        save_path: Path to save adapter
        model: PEFT model (optional, for saving weights)
    
    Returns:
        True if saved successfully
    """
    try:
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata_file = save_path / "adapter_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(adapter.to_dict(), f, indent=2)
        
        # Save PEFT model if provided
        if model and PEFT_AVAILABLE and hasattr(model, 'save_pretrained'):
            try:
                model.save_pretrained(str(save_path))
                logger.info(f"💾 Saved PEFT model to {save_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save PEFT model: {e}")
        
        adapter.adapter_path = save_path
        logger.info(f"💾 Saved LoRA adapter {adapter.adapter_id} to {save_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save LoRA adapter: {e}")
        return False


def load_lora_adapter(
    load_path: Path,
    base_model: Optional[Any] = None
) -> Optional[LoRAAdapter]:
    """
    Load LoRA adapter from disk.
    
    Args:
        load_path: Path to adapter directory
        base_model: Base model (optional, for loading PEFT model)
    
    Returns:
        LoRAAdapter instance or None if failed
    """
    try:
        # Load metadata
        metadata_file = load_path / "adapter_metadata.json"
        if not metadata_file.exists():
            logger.error(f"❌ Adapter metadata not found: {metadata_file}")
            return None
        
        with open(metadata_file, 'r') as f:
            data = json.load(f)
        
        adapter = LoRAAdapter.from_dict(data)
        adapter.adapter_path = load_path
        
        # Load PEFT model if base_model provided
        if base_model and PEFT_AVAILABLE:
            try:
                from peft import PeftModel
                peft_model = PeftModel.from_pretrained(base_model, str(load_path))
                logger.info(f"📂 Loaded PEFT model from {load_path}")
                # Store model reference in adapter metadata
                adapter.metadata['_peft_model_loaded'] = True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load PEFT model: {e}")
        
        logger.info(f"📂 Loaded LoRA adapter {adapter.adapter_id} from {load_path}")
        return adapter
        
    except Exception as e:
        logger.error(f"❌ Failed to load LoRA adapter: {e}")
        return None


def apply_lora_adapter(
    base_model: Any,
    adapter: LoRAAdapter
) -> Optional[Any]:
    """
    Apply LoRA adapter to base model.
    
    Args:
        base_model: Base model (HuggingFace model)
        adapter: LoRAAdapter instance
    
    Returns:
        Model with LoRA adapter applied or None if failed
    """
    if not PEFT_AVAILABLE:
        logger.error("❌ PEFT not available, cannot apply adapter")
        return None
    
    if not adapter.adapter_path or not adapter.adapter_path.exists():
        logger.error(f"❌ Adapter path not found: {adapter.adapter_path}")
        return None
    
    try:
        from peft import PeftModel
        peft_model = PeftModel.from_pretrained(base_model, str(adapter.adapter_path))
        logger.info(f"✅ Applied LoRA adapter {adapter.adapter_id} to model")
        return peft_model
    except Exception as e:
        logger.error(f"❌ Failed to apply LoRA adapter: {e}")
        return None

