"""
Q2 2026 Components Integration

Integrates all Q2 components into main application:
- RAG Pipeline for knowledge retrieval
- LoRA Fine-tuning for model adaptation
- Cilium eBPF Integration for network observability
- Enhanced FL Aggregators for federated learning
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# RAG Pipeline
try:
    from src.rag.pipeline import RAGPipeline
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    RAGPipeline = None

# LoRA Fine-tuning
try:
    from src.ml.lora.trainer import LoRATrainer
    from src.ml.lora.config import LoRAConfig
    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False
    LoRATrainer = None
    LoRAConfig = None

# Cilium eBPF Integration
try:
    from src.network.ebpf.cilium_integration import CiliumLikeIntegration
    CILIUM_AVAILABLE = True
except ImportError:
    CILIUM_AVAILABLE = False
    CiliumLikeIntegration = None

# Enhanced FL Aggregators
try:
    from src.federated_learning.aggregators_enhanced import (
        get_enhanced_aggregator,
        EnhancedAggregator,
        AdaptiveAggregator
    )
    ENHANCED_AGGREGATORS_AVAILABLE = True
except ImportError:
    ENHANCED_AGGREGATORS_AVAILABLE = False
    get_enhanced_aggregator = None


class Q2Integration:
    """
    Q2 2026 Components Integration Manager.
    
    Provides unified interface for all Q2 components:
    - RAG Pipeline for knowledge retrieval
    - LoRA Fine-tuning for model adaptation
    - Cilium eBPF Integration for network observability
    - Enhanced FL Aggregators for federated learning
    """
    
    def __init__(
        self,
        enable_rag: bool = True,
        enable_lora: bool = True,
        enable_cilium: bool = True,
        enable_enhanced_aggregators: bool = True,
        rag_data_path: Optional[Path] = None,
        lora_models_path: Optional[Path] = None
    ):
        self.enable_rag = enable_rag and RAG_AVAILABLE
        self.enable_lora = enable_lora and LORA_AVAILABLE
        self.enable_cilium = enable_cilium and CILIUM_AVAILABLE
        self.enable_enhanced_aggregators = enable_enhanced_aggregators and ENHANCED_AGGREGATORS_AVAILABLE
        
        # RAG Pipeline
        self.rag_pipeline: Optional[RAGPipeline] = None
        if self.enable_rag:
            try:
                self.rag_pipeline = RAGPipeline(
                    top_k=10,
                    rerank_top_k=5,
                    similarity_threshold=0.7
                )
                if rag_data_path:
                    self.rag_pipeline.load(rag_data_path)
                logger.info("✅ RAG Pipeline initialized")
            except Exception as e:
                logger.warning(f"⚠️ RAG Pipeline initialization failed: {e}")
                self.rag_pipeline = None
        
        # LoRA Trainer
        self.lora_trainer: Optional[LoRATrainer] = None
        if self.enable_lora:
            try:
                # LoRA trainer is initialized on-demand when training starts
                logger.info("✅ LoRA Fine-tuning available")
            except Exception as e:
                logger.warning(f"⚠️ LoRA Trainer initialization failed: {e}")
        
        # Cilium eBPF Integration
        self.cilium_integration: Optional[CiliumLikeIntegration] = None
        if self.enable_cilium:
            try:
                self.cilium_integration = CiliumLikeIntegration(
                    interface="eth0",
                    enable_flow_observability=True,
                    enable_policy_enforcement=True
                )
                logger.info("✅ Cilium eBPF Integration initialized")
            except Exception as e:
                logger.warning(f"⚠️ Cilium eBPF Integration initialization failed: {e}")
                self.cilium_integration = None
        
        # Enhanced Aggregators (used by FL Coordinator)
        if self.enable_enhanced_aggregators:
            logger.info("✅ Enhanced FL Aggregators available")
        
        logger.info(f"Q2 Integration initialized: RAG={self.enable_rag}, LoRA={self.enable_lora}, Cilium={self.enable_cilium}, EnhancedAgg={self.enable_enhanced_aggregators}")
    
    # --- RAG Pipeline Methods ---
    
    def add_knowledge(self, text: str, document_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add knowledge to RAG pipeline.
        
        Args:
            text: Knowledge text
            document_id: Document identifier
            metadata: Optional metadata
        
        Returns:
            True if added successfully
        """
        if not self.rag_pipeline:
            logger.warning("RAG Pipeline not available")
            return False
        
        try:
            chunk_ids = self.rag_pipeline.add_document(text, document_id, metadata)
            logger.debug(f"Added knowledge document {document_id} ({len(chunk_ids)} chunks)")
            return True
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return False
    
    def query_knowledge(self, query: str, top_k: int = 10) -> str:
        """
        Query knowledge base using RAG pipeline.
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            Context string from retrieved documents
        """
        if not self.rag_pipeline:
            logger.warning("RAG Pipeline not available")
            return ""
        
        try:
            context = self.rag_pipeline.query(query, top_k=top_k)
            return context
        except Exception as e:
            logger.error(f"Failed to query knowledge: {e}")
            return ""
    
    def retrieve_knowledge(self, query: str, top_k: int = 10) -> Optional[Any]:
        """
        Retrieve knowledge with full RAG result.
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            RAGResult object or None
        """
        if not self.rag_pipeline:
            return None
        
        try:
            return self.rag_pipeline.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.error(f"Failed to retrieve knowledge: {e}")
            return None
    
    # --- LoRA Fine-tuning Methods ---
    
    def initialize_lora_trainer(
        self,
        base_model_name: str,
        config: Optional[LoRAConfig] = None
    ) -> bool:
        """
        Initialize LoRA trainer for fine-tuning.
        
        Args:
            base_model_name: Base model name (e.g., "meta-llama/Llama-2-7b-hf")
            config: LoRA configuration
        
        Returns:
            True if initialized successfully
        """
        if not self.enable_lora:
            logger.warning("LoRA Fine-tuning not available")
            return False
        
        try:
            self.lora_trainer = LoRATrainer(
                base_model_name=base_model_name,
                config=config or LoRAConfig()
            )
            logger.info(f"✅ LoRA Trainer initialized for {base_model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize LoRA trainer: {e}")
            return False
    
    def train_lora_adapter(
        self,
        train_dataset: Any,
        adapter_id: str,
        **training_kwargs
    ) -> Optional[Any]:
        """
        Train LoRA adapter.
        
        Args:
            train_dataset: Training dataset
            adapter_id: Adapter identifier
            **training_kwargs: Training parameters
        
        Returns:
            LoRATrainingResult or None
        """
        if not self.lora_trainer:
            logger.warning("LoRA Trainer not initialized. Call initialize_lora_trainer() first.")
            return None
        
        try:
            result = self.lora_trainer.train(
                train_dataset=train_dataset,
                adapter_id=adapter_id,
                **training_kwargs
            )
            logger.info(f"✅ LoRA adapter {adapter_id} trained successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to train LoRA adapter: {e}")
            return None
    
    # --- Cilium eBPF Integration Methods ---
    
    def get_network_flows(self, limit: int = 100) -> list:
        """
        Get network flows from Cilium integration.
        
        Args:
            limit: Maximum number of flows to return
        
        Returns:
            List of flow events
        """
        if not self.cilium_integration:
            return []
        
        try:
            return self.cilium_integration.get_flow_history(limit=limit)
        except Exception as e:
            logger.error(f"Failed to get network flows: {e}")
            return []
    
    def get_network_metrics(self) -> Dict[str, Any]:
        """
        Get network metrics from Cilium integration.
        
        Returns:
            Dictionary with network metrics
        """
        if not self.cilium_integration:
            return {}
        
        try:
            return self.cilium_integration.get_metrics()
        except Exception as e:
            logger.error(f"Failed to get network metrics: {e}")
            return {}
    
    def add_network_policy(self, policy: Any) -> bool:
        """
        Add network policy to Cilium integration.
        
        Args:
            policy: NetworkPolicy object
        
        Returns:
            True if added successfully
        """
        if not self.cilium_integration:
            return False
        
        try:
            return self.cilium_integration.add_network_policy(policy)
        except Exception as e:
            logger.error(f"Failed to add network policy: {e}")
            return False
    
    # --- Enhanced Aggregators Methods ---
    
    def get_enhanced_aggregator(self, method: str = "enhanced_fedavg") -> Optional[Any]:
        """
        Get enhanced aggregator for federated learning.
        
        Args:
            method: Aggregation method ("enhanced_fedavg", "adaptive", etc.)
        
        Returns:
            Enhanced aggregator instance or None
        """
        if not self.enable_enhanced_aggregators:
            return None
        
        try:
            return get_enhanced_aggregator(method)
        except Exception as e:
            logger.error(f"Failed to get enhanced aggregator: {e}")
            return None
    
    # --- Lifecycle Methods ---
    
    def shutdown(self):
        """Shutdown all Q2 components."""
        logger.info("Shutting down Q2 Integration...")
        
        if self.cilium_integration:
            try:
                self.cilium_integration.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down Cilium integration: {e}")
        
        if self.rag_pipeline:
            try:
                # Save RAG pipeline state if needed
                pass
            except Exception as e:
                logger.warning(f"Error saving RAG pipeline: {e}")
        
        logger.info("✅ Q2 Integration shutdown complete")


# Global instance
_q2_integration: Optional[Q2Integration] = None


def get_q2_integration() -> Optional[Q2Integration]:
    """Get global Q2 Integration instance."""
    return _q2_integration


def initialize_q2_integration(**kwargs) -> Q2Integration:
    """
    Initialize global Q2 Integration instance.
    
    Args:
        **kwargs: Q2Integration initialization parameters
    
    Returns:
        Q2Integration instance
    """
    global _q2_integration
    _q2_integration = Q2Integration(**kwargs)
    return _q2_integration

