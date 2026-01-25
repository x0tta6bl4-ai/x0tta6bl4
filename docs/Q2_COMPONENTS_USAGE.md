# 📚 Q2 2026 Components Usage Guide

**Версия:** x0tta6bl4 v3.2  
**Дата:** 2025-12-28

---

## 📋 Содержание

1. [RAG Pipeline](#rag-pipeline)
2. [LoRA Fine-tuning](#lora-fine-tuning)
3. [Cilium eBPF Integration](#cilium-ebpf-integration)
4. [Enhanced FL Aggregators](#enhanced-fl-aggregators)
5. [Q2 Integration (Unified)](#q2-integration-unified)
6. [Интеграция с MAPE-K](#интеграция-с-mape-k)

---

## 🔍 RAG Pipeline

### Базовое использование

```python
from src.rag.pipeline import RAGPipeline

# Инициализация
pipeline = RAGPipeline(
    top_k=10,
    rerank_top_k=5,
    similarity_threshold=0.7
)

# Добавление документов
pipeline.add_document(
    text="Your document text here...",
    document_id="doc_001",
    metadata={"topic": "networking", "type": "documentation"}
)

# Поиск
result = pipeline.retrieve("search query")
print(f"Found {len(result.retrieved_chunks)} chunks")
print(f"Context: {result.context}")

# Удобный метод
context = pipeline.query("search query", top_k=5)
```

### Стратегии Chunking

```python
from src.rag.chunker import ChunkingStrategy, DocumentChunker

# FIXED_SIZE - фиксированный размер
chunker = DocumentChunker(
    strategy=ChunkingStrategy.FIXED_SIZE,
    chunk_size=512,
    chunk_overlap=50
)

# SENTENCE - по предложениям
chunker = DocumentChunker(
    strategy=ChunkingStrategy.SENTENCE,
    chunk_size=100
)

# PARAGRAPH - по параграфам
chunker = DocumentChunker(
    strategy=ChunkingStrategy.PARAGRAPH,
    chunk_size=200
)

# RECURSIVE - рекурсивное разбиение
chunker = DocumentChunker(
    strategy=ChunkingStrategy.RECURSIVE,
    chunk_size=512
)
```

### Сохранение и загрузка

```python
# Сохранение
pipeline.save(Path("data/rag_pipeline"))

# Загрузка
pipeline.load(Path("data/rag_pipeline"))
```

---

## 🎯 LoRA Fine-tuning

### Инициализация

```python
from src.ml.lora.trainer import LoRATrainer
from src.ml.lora.config import LoRAConfig, LoRATargetModules

# Конфигурация
config = LoRAConfig(
    r=8,                    # Rank
    alpha=32,               # Alpha scaling
    dropout=0.1,             # Dropout rate
    target_modules=LoRATargetModules.LLAMA
)

# Инициализация trainer
trainer = LoRATrainer(
    base_model_name="meta-llama/Llama-2-7b-hf",
    config=config
)
```

### Обучение

```python
# Обучение adapter
result = trainer.train(
    train_dataset=train_dataset,
    adapter_id="mesh_optimizer_v1",
    num_epochs=3,
    batch_size=4,
    learning_rate=2e-4,
    validation_dataset=val_dataset,
    save_steps=500,
    logging_steps=100
)

print(f"Training completed: {result.success}")
print(f"Final loss: {result.final_loss}")
```

### Управление Adapters

```python
from src.ml.lora.adapter import save_lora_adapter, load_lora_adapter

# Сохранение
save_lora_adapter(adapter, Path("models/adapters/mesh_v1"))

# Загрузка
adapter = load_lora_adapter(Path("models/adapters/mesh_v1"))
```

---

## 🌐 Cilium eBPF Integration

### Инициализация

```python
from src.network.ebpf.cilium_integration import CiliumEBPFIntegration

# Инициализация
cilium = CiliumEBPFIntegration(
    interface="eth0",
    enable_xdp_counter=True,
    enable_flow_monitoring=True,
    enable_policy_enforcement=True
)
```

### Получение метрик

```python
# Network metrics
metrics = cilium.get_metrics()
print(f"Active policies: {metrics['active_policies_count']}")
print(f"Flow rate: {metrics['flow_rate_per_second']} flows/s")

# Flow history
flows = cilium.get_flow_history(limit=100)
for flow in flows:
    print(f"{flow.event_type}: {flow.source_ip} -> {flow.destination_ip}")
```

### Network Policies

```python
from src.network.ebpf.cilium_integration import NetworkPolicy

# Добавление policy
policy = NetworkPolicy(
    policy_id="allow-mesh-traffic",
    rules=[{
        "action": "ALLOW",
        "match": {
            "protocol": "TCP",
            "source_labels": {"app": "mesh"}
        }
    }],
    action="ALLOW",
    priority=100
)

cilium.add_network_policy(policy)

# Удаление policy
cilium.remove_network_policy("allow-mesh-traffic")
```

---

## 🤝 Enhanced FL Aggregators

### Базовое использование

```python
from src.federated_learning.aggregators_enhanced import (
    get_enhanced_aggregator,
    EnhancedFedAvgAggregator,
    AdaptiveAggregator
)

# Получение enhanced aggregator
aggregator = get_enhanced_aggregator("enhanced_fedavg")

# Агрегация
result = aggregator.aggregate(updates)
print(f"Success: {result.success}")
print(f"Quality score: {result.metadata['metrics']['quality_score']}")
```

### Adaptive Aggregator

```python
# Adaptive aggregator автоматически выбирает стратегию
adaptive = AdaptiveAggregator(
    trust_threshold=0.8,
    outlier_threshold=2.0
)

result = adaptive.aggregate(updates)

# Статистика стратегий
stats = adaptive.get_strategy_stats()
print(f"Strategy usage: {stats['strategy_usage']}")
```

### Метрики

```python
# Получение статистики агрегации
stats = aggregator.get_aggregation_stats()
print(f"Total aggregations: {stats['total_aggregations']}")
print(f"Avg quality score: {stats['avg_quality_score']}")
print(f"Avg convergence score: {stats['avg_convergence_score']}")
```

---

## 🔗 Q2 Integration (Unified)

### Инициализация

```python
from src.core.q2_integration import initialize_q2_integration

# Инициализация всех компонентов
q2 = initialize_q2_integration(
    enable_rag=True,
    enable_lora=True,
    enable_cilium=True,
    enable_enhanced_aggregators=True,
    rag_data_path=Path("data/rag"),
    lora_models_path=Path("models/lora")
)
```

### RAG Pipeline

```python
# Добавление знаний
q2.add_knowledge(
    text="Knowledge document text...",
    document_id="knowledge_001",
    metadata={"type": "knowledge"}
)

# Поиск
context = q2.query_knowledge("search query", top_k=10)

# Полный результат
result = q2.retrieve_knowledge("search query")
```

### LoRA Fine-tuning

```python
# Инициализация trainer
q2.initialize_lora_trainer(
    base_model_name="meta-llama/Llama-2-7b-hf",
    config=LoRAConfig()
)

# Обучение
result = q2.train_lora_adapter(
    train_dataset=train_dataset,
    adapter_id="mesh_v1",
    num_epochs=3,
    batch_size=4
)
```

### Network Observability

```python
# Network flows
flows = q2.get_network_flows(limit=100)

# Network metrics
metrics = q2.get_network_metrics()

# Network policies
policy = NetworkPolicy(...)
q2.add_network_policy(policy)
```

### Enhanced Aggregators

```python
# Получение aggregator
aggregator = q2.get_enhanced_aggregator("enhanced_fedavg")
```

### Shutdown

```python
# Корректное завершение
q2.shutdown()
```

---

## 🔄 Интеграция с MAPE-K

### RAG в Knowledge Base

```python
from src.rag.pipeline import RAGPipeline
from src.self_healing.mape_k import MAPEKKnowledge

# Инициализация
rag = RAGPipeline()
knowledge = MAPEKKnowledge()

# Добавление знаний о восстановлении
rag.add_document(
    text="When CPU > 90%, restart service",
    document_id="recovery_cpu",
    metadata={"issue": "High CPU", "action": "Restart service"}
)

# Поиск паттернов восстановления
def search_recovery(issue: str) -> str:
    result = rag.retrieve(f"recovery for {issue}")
    if result.retrieved_chunks:
        return result.retrieved_chunks[0].metadata.get("action", "Unknown")
    return "No action found"

# Использование в MAPE-K
issue = "High CPU"
action = search_recovery(issue)
knowledge.record(metrics, issue, action, success=True)
```

---

## 📊 Примеры использования

Полные примеры доступны в:
- `examples/q2_components_usage.py`

Запуск:
```bash
python examples/q2_components_usage.py
```

---

## 🚀 Production Best Practices

### RAG Pipeline
- Используйте `RECURSIVE` chunking для больших документов
- Настройте `similarity_threshold` для вашего use case
- Сохраняйте pipeline state регулярно

### LoRA Fine-tuning
- Начните с малых `r` (4-8) для быстрого обучения
- Используйте validation dataset для мониторинга overfitting
- Сохраняйте checkpoints регулярно

### Cilium Integration
- Мониторьте flow rate для обнаружения аномалий
- Используйте network policies для security
- Экспортируйте метрики в Prometheus

### Enhanced Aggregators
- Используйте `adaptive` для автоматического выбора стратегии
- Мониторьте quality/convergence scores
- Настройте trust thresholds для вашего окружения

---

## 📝 Дополнительная документация

- `Q2_2026_COMPREHENSIVE_SUMMARY.md` - Полный обзор Q2 компонентов
- `Q2_RAG_PIPELINE_MVP.md` - Детали RAG Pipeline
- `Q2_LORA_SCAFFOLD.md` - Детали LoRA Fine-tuning
- `Q2_EBPF_CILIUM_INTEGRATION.md` - Детали Cilium Integration
- `Q2_FL_AGGREGATOR_IMPROVEMENTS.md` - Детали Enhanced Aggregators

---

**Mesh обновлён. Документация готова. Примеры работают.**  
**Проснись. Используй. Интегрируй.**  
**x0tta6bl4 вечен.**

