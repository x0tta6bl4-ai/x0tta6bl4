# Federated Learning Usage Examples

**Версия:** 1.0  
**Дата:** 2025-12-28

---

## 📚 Примеры использования

### 1. Базовое агрегирование

```python
from src.federated_learning.aggregators import FedAvgAggregator
from src.federated_learning.protocol import ModelUpdate, ModelWeights, GlobalModel

# Создать агрегатор
aggregator = FedAvgAggregator()

# Создать обновления от разных нод
updates = [
    ModelUpdate(
        node_id="node-1",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [1.0, 2.0, 3.0]}),
        num_samples=100,
        training_loss=0.5,
        validation_loss=0.6
    ),
    ModelUpdate(
        node_id="node-2",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [2.0, 3.0, 4.0]}),
        num_samples=150,
        training_loss=0.4,
        validation_loss=0.5
    ),
    ModelUpdate(
        node_id="node-3",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [3.0, 4.0, 5.0]}),
        num_samples=200,
        training_loss=0.3,
        validation_loss=0.4
    )
]

# Агрегировать
result = aggregator.aggregate(updates)

if result.success:
    global_model = result.global_model
    print(f"✅ Aggregation successful!")
    print(f"   Version: {global_model.version}")
    print(f"   Contributors: {global_model.num_contributors}")
    print(f"   Total samples: {global_model.total_samples}")
    print(f"   Avg training loss: {global_model.avg_training_loss:.4f}")
else:
    print(f"❌ Aggregation failed: {result.error_message}")
```

---

### 2. Privacy-Preserving Aggregation

```python
from src.federated_learning.secure_aggregators import SecureFedAvgAggregator
from src.federated_learning.privacy import DPConfig

# Настроить differential privacy
dp_config = DPConfig(
    target_epsilon=1.0,      # Privacy budget
    target_delta=1e-5,      # Failure probability
    max_grad_norm=1.0,      # Gradient clipping threshold
    noise_multiplier=1.1    # Noise scale
)

# Создать privacy-preserving агрегатор
aggregator = SecureFedAvgAggregator(
    dp_config=dp_config,
    enable_dp=True
)

# Создать обновления
updates = [
    ModelUpdate(
        node_id=f"node-{i+1}",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [float(i), float(i+1)]}),
        num_samples=100
    )
    for i in range(5)
]

# Агрегировать с privacy
result = aggregator.aggregate(updates)

if result.success:
    print(f"✅ Privacy-preserving aggregation successful!")
    print(f"   Privacy epsilon spent: {result.privacy_epsilon_spent:.4f}")
    print(f"   Privacy budget remaining: {result.privacy_budget_remaining:.4f}")
    print(f"   Global model version: {result.global_model.version}")
```

---

### 3. Byzantine-Robust Aggregation

```python
from src.federated_learning.byzantine_robust import EnhancedKrumAggregator

# Создать Byzantine-robust агрегатор
aggregator = EnhancedKrumAggregator(
    f=1,                    # Tolerate 1 Byzantine node
    multi_krum=True,        # Use Multi-Krum
    m=2,                    # Average 2 best updates
    adaptive_f=True         # Adaptive f selection
)

# Создать нормальные обновления
updates = [
    ModelUpdate(
        node_id=f"node-{i+1}",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [1.0 + i, 2.0 + i]}),
        num_samples=100
    )
    for i in range(4)
]

# Добавить Byzantine обновление (очень отличается)
byzantine_update = ModelUpdate(
    node_id="byzantine-node",
    round_number=1,
    weights=ModelWeights(layer_weights={"layer1": [1000.0, 2000.0]}),
    num_samples=100
)
updates.append(byzantine_update)

# Агрегировать
result = aggregator.aggregate(updates)

if result.success:
    print(f"✅ Byzantine-robust aggregation successful!")
    print(f"   Updates received: {result.updates_received}")
    print(f"   Updates accepted: {result.updates_accepted}")
    print(f"   Updates rejected: {result.updates_rejected}")
    if result.suspected_byzantine:
        print(f"   Suspected Byzantine: {result.suspected_byzantine}")
```

---

### 4. Model Synchronization

```python
from src.federated_learning.model_sync import ModelSynchronizer
from src.federated_learning.protocol import GlobalModel, ModelWeights

# Создать синхронизатор
synchronizer = ModelSynchronizer(node_id="node-1")

# Получить глобальную модель от координатора
global_model = GlobalModel(
    version=1,
    round_number=1,
    weights=ModelWeights(layer_weights={"layer1": [1.0, 2.0]}),
    num_contributors=3,
    total_samples=450
)

# Получить модель
success = synchronizer.receive_global_model(global_model, "coordinator")

if success:
    print(f"✅ Global model received!")
    print(f"   Version: {synchronizer.get_model_version()}")
    print(f"   Status: {synchronizer.get_sync_status()}")
else:
    print(f"❌ Failed to receive global model")

# Проверить конфликты
local_model = GlobalModel(
    version=0,
    round_number=0,
    weights=ModelWeights(layer_weights={"layer1": [0.5, 1.5]}),
    num_contributors=1
)

conflicts = synchronizer.check_for_conflicts(local_model, global_model)
if conflicts:
    print(f"⚠️ Conflicts detected: {len(conflicts)}")
    for conflict in conflicts:
        print(f"   - {conflict['type']}: {conflict.get('severity', 'unknown')}")
    
    # Разрешить конфликты
    success = synchronizer.resolve_conflicts(conflicts, strategy="prefer_global")
    if success:
        print(f"✅ Conflicts resolved")
```

---

### 5. GraphSAGE Federated Learning

```python
from src.federated_learning.graphsage_integration import (
    GraphSAGEFLCoordinator,
    GraphSAGEDistributedTrainer,
    GraphSAGEFLConfig
)

# Создать конфигурацию
config = GraphSAGEFLConfig(
    enable_privacy=True,
    enable_byzantine_robust=True,
    aggregation_method="graphsage",
    sync_interval=1,
    model_versioning=True
)

# Создать координатор
coordinator = GraphSAGEFLCoordinator(
    node_id="coordinator-1",
    fl_config=config
)

# Начать тренировку
participating_nodes = ["node-1", "node-2", "node-3"]
round_info = coordinator.start_training_round(participating_nodes)

if round_info:
    print(f"✅ Training round started!")
    print(f"   Round number: {round_info['round_number']}")
    print(f"   Selected nodes: {round_info['selected_nodes']}")
    
    # Обучить локально на каждой ноде
    updates = []
    for node_id in participating_nodes:
        update = coordinator.train_local(round_info['round_number'])
        if update:
            updates.append(update)
            print(f"   ✅ Local training completed for {node_id}")
    
    # Агрегировать обновления
    if updates:
        global_model = coordinator.aggregate_updates(updates)
        if global_model:
            print(f"✅ Aggregation successful!")
            print(f"   Global model version: {global_model.version}")
            print(f"   Contributors: {global_model.num_contributors}")
            
            # Распределить глобальную модель
            results = coordinator.distribute_global_model(
                global_model,
                participating_nodes
            )
            print(f"✅ Model distributed to {sum(results.values())}/{len(results)} nodes")
```

---

### 6. Distributed Training

```python
from src.federated_learning.graphsage_integration import (
    GraphSAGEFLCoordinator,
    GraphSAGEDistributedTrainer,
    GraphSAGEFLConfig
)

# Создать координатор
config = GraphSAGEFLConfig(enable_privacy=True)
coordinator = GraphSAGEFLCoordinator(
    node_id="coordinator-1",
    fl_config=config
)

# Создать distributed trainer
trainer = GraphSAGEDistributedTrainer(
    coordinator=coordinator,
    num_rounds=10
)

# Запустить distributed training
participating_nodes = ["node-1", "node-2", "node-3", "node-4", "node-5"]
results = trainer.train(participating_nodes)

print(f"✅ Distributed training completed!")
print(f"   Total rounds: {results['total_rounds']}")
print(f"   Completed rounds: {results['completed_rounds']}")
print(f"   History: {len(results['history'])} rounds recorded")
```

---

### 7. Privacy Budget Tracking

```python
from src.federated_learning.secure_aggregators import SecureFedAvgAggregator
from src.federated_learning.privacy import DPConfig

# Настроить DP с ограниченным budget
dp_config = DPConfig(
    target_epsilon=10.0,    # Total privacy budget
    max_grad_norm=1.0
)

aggregator = SecureFedAvgAggregator(dp_config=dp_config, enable_dp=True)

# Множественные раунды агрегации
for round_num in range(1, 11):
    updates = [
        ModelUpdate(
            node_id=f"node-{i+1}",
            round_number=round_num,
            weights=ModelWeights(layer_weights={"layer1": [float(i)]}),
            num_samples=100
        )
        for i in range(5)
    ]
    
    result = aggregator.aggregate(updates)
    
    if result.success:
        budget_remaining = aggregator.privacy_budget.remaining(10.0)
        epsilon_spent = aggregator.privacy_budget.epsilon
        
        print(f"Round {round_num}:")
        print(f"   Epsilon spent: {epsilon_spent:.4f}")
        print(f"   Budget remaining: {budget_remaining:.4f}")
        
        if budget_remaining < 1.0:
            print(f"⚠️ Privacy budget running low!")
            break
```

---

### 8. Rollback

```python
from src.federated_learning.model_sync import ModelSynchronizer
from src.federated_learning.protocol import GlobalModel, ModelWeights

synchronizer = ModelSynchronizer(node_id="node-1")

# Получить несколько версий моделей
for version in range(1, 6):
    model = GlobalModel(
        version=version,
        round_number=version,
        weights=ModelWeights(layer_weights={"layer1": [float(version)]}),
        num_contributors=3
    )
    synchronizer.receive_global_model(model, "coordinator")
    print(f"✅ Model version {version} received")

# Текущая версия
print(f"Current version: {synchronizer.get_model_version()}")

# Откатить к версии 3
success = synchronizer.rollback(target_version=3)
if success:
    print(f"✅ Rolled back to version 3")
    print(f"Current version: {synchronizer.get_model_version()}")
```

---

### 9. Performance Benchmarking

```python
import time
from src.federated_learning.aggregators import FedAvgAggregator
from src.federated_learning.secure_aggregators import SecureFedAvgAggregator
from src.federated_learning.protocol import ModelUpdate, ModelWeights

# Создать обновления
updates = [
    ModelUpdate(
        node_id=f"node-{i+1}",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [float(j) for j in range(100)]}),
        num_samples=100
    )
    for i in range(10)
]

# Benchmark FedAvg
aggregator1 = FedAvgAggregator()
start = time.time()
result1 = aggregator1.aggregate(updates)
time1 = time.time() - start

# Benchmark SecureFedAvg
aggregator2 = SecureFedAvgAggregator(enable_dp=True)
start = time.time()
result2 = aggregator2.aggregate(updates)
time2 = time.time() - start

# Сравнить
print(f"FedAvg: {time1*1000:.2f}ms")
print(f"SecureFedAvg: {time2*1000:.2f}ms")
print(f"Overhead: {(time2-time1)/time1*100:.1f}%")
```

---

### 10. Полный FL Pipeline

```python
from src.federated_learning.graphsage_integration import (
    GraphSAGEFLCoordinator,
    GraphSAGEFLConfig
)
from src.federated_learning.privacy import DPConfig

# 1. Настроить конфигурацию
dp_config = DPConfig(target_epsilon=10.0, max_grad_norm=1.0)
fl_config = GraphSAGEFLConfig(
    enable_privacy=True,
    enable_byzantine_robust=True,
    aggregation_method="secure_fedavg"
)

# 2. Создать координатор
coordinator = GraphSAGEFLCoordinator(
    node_id="coordinator-1",
    fl_config=fl_config
)

# 3. Зарегистрировать ноды
participating_nodes = ["node-1", "node-2", "node-3", "node-4", "node-5"]

# 4. Запустить несколько раундов
for round_num in range(1, 6):
    print(f"\n=== Round {round_num} ===")
    
    # Начать раунд
    round_info = coordinator.start_training_round(participating_nodes)
    if not round_info:
        print(f"❌ Failed to start round {round_num}")
        continue
    
    # Обучить локально
    updates = []
    for node_id in participating_nodes:
        update = coordinator.train_local(round_num)
        if update:
            updates.append(update)
    
    if not updates:
        print(f"❌ No updates received")
        continue
    
    # Агрегировать
    global_model = coordinator.aggregate_updates(updates)
    if global_model:
        print(f"✅ Round {round_num} completed")
        print(f"   Model version: {global_model.version}")
        print(f"   Contributors: {global_model.num_contributors}")
        
        # Распределить
        results = coordinator.distribute_global_model(global_model, participating_nodes)
        print(f"   Distributed to {sum(results.values())}/{len(results)} nodes")
    else:
        print(f"❌ Aggregation failed")

print(f"\n✅ FL Pipeline completed!")
```

---

## 🎯 Best Practices

1. **Всегда проверяйте результат агрегации:**
   ```python
   result = aggregator.aggregate(updates)
   if not result.success:
       # Handle error
   ```

2. **Мониторьте privacy budget:**
   ```python
   if aggregator.privacy_budget.is_exhausted(max_epsilon=10.0):
       # Stop training or increase budget
   ```

3. **Используйте Byzantine-robust для untrusted environments:**
   ```python
   aggregator = EnhancedKrumAggregator(f=2, adaptive_f=True)
   ```

4. **Проверяйте версии перед применением:**
   ```python
   if global_model.version > local_model.version:
       synchronizer.receive_global_model(global_model, "coordinator")
   ```

---

**Mesh обновлён. Примеры готовы.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

