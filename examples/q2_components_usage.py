"""
Примеры использования Q2 2026 компонентов

Демонстрирует использование:
- RAG Pipeline для knowledge retrieval
- LoRA Fine-tuning для model adaptation
- Cilium eBPF Integration для network observability
- Enhanced FL Aggregators для federated learning
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Пример 1: RAG Pipeline для Knowledge Retrieval
# ============================================================================

def example_rag_pipeline():
    """Пример использования RAG Pipeline для поиска знаний."""
    try:
        from src.rag.pipeline import RAGPipeline
        
        # Инициализация
        pipeline = RAGPipeline(
            top_k=10,
            rerank_top_k=5,
            similarity_threshold=0.7
        )
        
        # Добавление документов
        pipeline.add_document(
            text="MAPE-K cycle consists of Monitor, Analyze, Plan, Execute, and Knowledge phases.",
            document_id="mapek_intro",
            metadata={"topic": "self-healing", "type": "documentation"}
        )
        
        pipeline.add_document(
            text="Federated Learning allows training models across distributed nodes without sharing raw data.",
            document_id="fl_intro",
            metadata={"topic": "federated-learning", "type": "documentation"}
        )
        
        # Поиск
        result = pipeline.retrieve("How does MAPE-K cycle work?")
        print(f"Найдено {len(result.retrieved_chunks)} chunks")
        print(f"Context: {result.context[:200]}...")
        
        # Удобный метод query
        context = pipeline.query("federated learning privacy")
        print(f"Context: {context[:200]}...")
        
        # Статистика
        stats = pipeline.get_stats()
        print(f"Pipeline stats: {stats}")
        
    except ImportError as e:
        logger.warning(f"RAG Pipeline not available: {e}")


# ============================================================================
# Пример 2: LoRA Fine-tuning
# ============================================================================

def example_lora_training():
    """Пример использования LoRA Fine-tuning."""
    try:
        from src.ml.lora.trainer import LoRATrainer
        from src.ml.lora.config import LoRAConfig, LoRATargetModules
        
        # Конфигурация LoRA
        config = LoRAConfig(
            r=8,
            alpha=32,
            dropout=0.1,
            target_modules=LoRATargetModules.LLAMA
        )
        
        # Инициализация trainer
        trainer = LoRATrainer(
            base_model_name="meta-llama/Llama-2-7b-hf",
            config=config
        )
        
        # Подготовка данных (пример)
        # train_dataset = prepare_dataset(...)
        
        # Обучение
        # result = trainer.train(
        #     train_dataset=train_dataset,
        #     adapter_id="mesh_optimizer_v1",
        #     num_epochs=3,
        #     batch_size=4,
        #     learning_rate=2e-4
        # )
        
        print("LoRA Trainer initialized successfully")
        print(f"Trainable parameters: {trainer.get_trainable_parameters()}")
        
    except ImportError as e:
        logger.warning(f"LoRA Trainer not available: {e}")


# ============================================================================
# Пример 3: Cilium eBPF Integration
# ============================================================================

def example_cilium_integration():
    """Пример использования Cilium eBPF Integration."""
    try:
        from src.network.ebpf.cilium_integration import (
            CiliumEBPFIntegration,
            FlowEvent,
            FlowEventType
        )
        
        # Инициализация
        cilium = CiliumEBPFIntegration(
            interface="eth0",
            enable_xdp_counter=True,
            enable_flow_monitoring=True,
            enable_policy_enforcement=True
        )
        
        # Получение метрик
        metrics = cilium.get_metrics()
        print(f"Network metrics: {metrics}")
        
        # Получение flow history
        flows = cilium.get_flow_history(limit=10)
        print(f"Recent flows: {len(flows)}")
        
        # Добавление network policy (пример)
        # from src.network.ebpf.cilium_integration import NetworkPolicy
        # policy = NetworkPolicy(
        #     policy_id="allow-mesh-traffic",
        #     rules=[{"action": "ALLOW", "match": {"protocol": "TCP"}}],
        #     action="ALLOW",
        #     priority=100
        # )
        # cilium.add_network_policy(policy)
        
    except ImportError as e:
        logger.warning(f"Cilium Integration not available: {e}")


# ============================================================================
# Пример 4: Enhanced FL Aggregators
# ============================================================================

def example_enhanced_aggregators():
    """Пример использования Enhanced FL Aggregators."""
    try:
        from src.federated_learning.aggregators_enhanced import (
            get_enhanced_aggregator,
            EnhancedFedAvgAggregator,
            AdaptiveAggregator
        )
        from src.federated_learning.protocol import (
            ModelUpdate,
            ModelWeights
        )
        
        # Получение enhanced aggregator
        aggregator = get_enhanced_aggregator("enhanced_fedavg")
        
        # Создание mock updates
        updates = [
            ModelUpdate(
                node_id=f"node-{i}",
                round_number=1,
                weights=ModelWeights(layer_weights={"layer1": [float(i), float(i+1)]}),
                num_samples=100,
                training_loss=0.5
            )
            for i in range(3)
        ]
        
        # Агрегация
        result = aggregator.aggregate(updates)
        
        print(f"Aggregation success: {result.success}")
        print(f"Metrics: {result.metadata.get('metrics', {})}")
        
        # Adaptive aggregator
        adaptive = AdaptiveAggregator()
        result = adaptive.aggregate(updates)
        print(f"Adaptive aggregation success: {result.success}")
        
        # Статистика
        stats = adaptive.get_strategy_stats()
        print(f"Strategy stats: {stats}")
        
    except ImportError as e:
        logger.warning(f"Enhanced Aggregators not available: {e}")


# ============================================================================
# Пример 5: Q2 Integration (Unified Interface)
# ============================================================================

def example_q2_integration():
    """Пример использования Q2 Integration для всех компонентов."""
    try:
        from src.core.q2_integration import initialize_q2_integration, get_q2_integration
        
        # Инициализация
        q2 = initialize_q2_integration(
            enable_rag=True,
            enable_lora=True,
            enable_cilium=True,
            enable_enhanced_aggregators=True
        )
        
        # RAG Pipeline
        q2.add_knowledge(
            text="Example knowledge document",
            document_id="example_001",
            metadata={"type": "example"}
        )
        
        context = q2.query_knowledge("example query", top_k=5)
        print(f"RAG context: {context[:100]}...")
        
        # Network metrics
        metrics = q2.get_network_metrics()
        print(f"Network metrics: {metrics}")
        
        # Enhanced aggregator
        aggregator = q2.get_enhanced_aggregator("enhanced_fedavg")
        if aggregator:
            print("Enhanced aggregator obtained")
        
        # Shutdown
        q2.shutdown()
        
    except ImportError as e:
        logger.warning(f"Q2 Integration not available: {e}")


# ============================================================================
# Пример 6: Интеграция с MAPE-K Knowledge
# ============================================================================

def example_mapek_rag_integration():
    """Пример интеграции RAG с MAPE-K Knowledge."""
    try:
        from src.rag.pipeline import RAGPipeline
        from src.self_healing.mape_k import MAPEKKnowledge
        
        # Инициализация RAG
        rag = RAGPipeline()
        
        # Добавление знаний о восстановлении
        rag.add_document(
            text="When CPU usage exceeds 90%, restart the service using systemctl restart x0tta6bl4",
            document_id="recovery_cpu_high",
            metadata={"issue": "High CPU", "action": "Restart service", "success_rate": 0.95}
        )
        
        rag.add_document(
            text="When memory usage exceeds 85%, clear cache using cache.clear() method",
            document_id="recovery_memory_high",
            metadata={"issue": "High Memory", "action": "Clear cache", "success_rate": 0.88}
        )
        
        # MAPE-K Knowledge с RAG
        knowledge = MAPEKKnowledge()
        
        # При поиске паттернов используем RAG
        def search_recovery_pattern(issue: str) -> str:
            result = rag.retrieve(f"recovery strategy for {issue}")
            if result.retrieved_chunks:
                # Извлекаем action из metadata
                for chunk in result.retrieved_chunks:
                    action = chunk.metadata.get("action")
                    if action:
                        return action
            return "No action found"
        
        # Пример использования
        issue = "High CPU"
        action = search_recovery_pattern(issue)
        print(f"For issue '{issue}', recommended action: {action}")
        
    except ImportError as e:
        logger.warning(f"MAPE-K RAG integration not available: {e}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Q2 2026 Components Usage Examples")
    print("=" * 70)
    
    print("\n1. RAG Pipeline Example:")
    print("-" * 70)
    example_rag_pipeline()
    
    print("\n2. LoRA Fine-tuning Example:")
    print("-" * 70)
    example_lora_training()
    
    print("\n3. Cilium eBPF Integration Example:")
    print("-" * 70)
    example_cilium_integration()
    
    print("\n4. Enhanced FL Aggregators Example:")
    print("-" * 70)
    example_enhanced_aggregators()
    
    print("\n5. Q2 Integration (Unified) Example:")
    print("-" * 70)
    example_q2_integration()
    
    print("\n6. MAPE-K RAG Integration Example:")
    print("-" * 70)
    example_mapek_rag_integration()
    
    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)

