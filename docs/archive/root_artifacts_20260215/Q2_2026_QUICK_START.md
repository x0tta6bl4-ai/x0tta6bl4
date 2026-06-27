# 🚀 Q2 2026: Quick Start Guide

**Версия:** x0tta6bl4 v3.2  
**Дата:** 2025-12-28

---

## ⚡ Быстрый Старт

### 1. Проверка Импортов

```bash
# Все компоненты Q2 должны импортироваться без ошибок
python3 -c "from src.core.q2_integration import get_q2_integration; print('✅ Q2 Integration')"
python3 -c "from src.rag.pipeline import RAGPipeline; print('✅ RAG Pipeline')"
python3 -c "from src.ml.lora.trainer import LoRATrainer; print('✅ LoRA Trainer')"
python3 -c "from src.network.ebpf.cilium_integration import CiliumLikeIntegration; print('✅ Cilium')"
python3 -c "from src.federated_learning.aggregators_enhanced import get_enhanced_aggregator; print('✅ Enhanced Aggregators')"
```

### 2. Запуск Приложения

```bash
# Q2 компоненты автоматически инициализируются при старте
python3 scripts/start_production.py
```

### 3. Использование Q2 Компонентов

```python
from src.core.q2_integration import get_q2_integration

# Получить Q2 Integration instance
q2 = get_q2_integration()

if q2:
    # RAG Pipeline - Knowledge Retrieval
    q2.add_knowledge(
        text="Your knowledge document...",
        document_id="doc_001",
        metadata={"topic": "networking"}
    )
    context = q2.query_knowledge("search query", top_k=10)
    
    # Network Observability
    metrics = q2.get_network_metrics()
    flows = q2.get_network_flows(limit=100)
    
    # Enhanced FL Aggregators
    aggregator = q2.get_enhanced_aggregator("enhanced_fedavg")
```

---

## 📚 Компоненты Q2

### 1. RAG Pipeline

```python
from src.rag.pipeline import RAGPipeline

pipeline = RAGPipeline(top_k=10, rerank_top_k=5)
pipeline.add_document(text="...", document_id="doc_001")
result = pipeline.retrieve("query")
```

### 2. LoRA Fine-tuning

```python
from src.ml.lora.trainer import LoRATrainer
from src.ml.lora.config import LoRAConfig

trainer = LoRATrainer(
    base_model_name="meta-llama/Llama-2-7b-hf",
    config=LoRAConfig()
)
result = trainer.train(train_dataset, adapter_id="mesh_v1")
```

### 3. Cilium eBPF Integration

```python
from src.network.ebpf.cilium_integration import CiliumLikeIntegration

cilium = CiliumLikeIntegration(
    interface="eth0",
    enable_flow_monitoring=True
)
metrics = cilium.get_metrics()
```

### 4. Enhanced FL Aggregators

```python
from src.federated_learning.aggregators_enhanced import get_enhanced_aggregator

aggregator = get_enhanced_aggregator("enhanced_fedavg")
result = aggregator.aggregate(updates)
```

---

## 🔗 Интеграция с Существующими Компонентами

### MAPE-K Knowledge + RAG

RAG автоматически используется через Knowledge Storage v2.0 для поиска паттернов восстановления.

### FL Coordinator + Enhanced Aggregators

Enhanced aggregators автоматически используются в FL Coordinator при выборе метода агрегации.

### Network Stack + Cilium

Cilium eBPF Integration предоставляет network observability для всего mesh.

---

## 📖 Документация

- **Usage Guide:** `docs/Q2_COMPONENTS_USAGE.md`
- **Examples:** `examples/q2_components_usage.py`
- **Master Summary:** `Q2_2026_MASTER_SUMMARY.md`
- **Production Checklist:** `Q2_2026_PRODUCTION_CHECKLIST.md`

---

## ✅ Production Ready

Все компоненты Q2:
- ✅ Production-ready код
- ✅ Comprehensive тесты
- ✅ Parameter validation
- ✅ Error handling
- ✅ Полная документация
- ✅ Автоматическая инициализация

---

**Mesh обновлён. Готов к использованию.**  
**Проснись. Используй. Масштабируй.**  
**x0tta6bl4 вечен.**

