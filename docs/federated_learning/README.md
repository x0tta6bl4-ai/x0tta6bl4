# Federated Learning Documentation

**Версия:** 1.0  
**Дата:** 2025-12-28  
**Статус:** Production-Ready (80%)

---

## 📋 Обзор

Federated Learning (FL) модуль для x0tta6bl4 обеспечивает privacy-preserving distributed training без центрального авторитета. Модуль включает:

- **Privacy-preserving aggregation** с differential privacy
- **Byzantine-robust aggregators** для защиты от атак
- **GraphSAGE integration** для distributed training
- **Model synchronization** с version control

---

## 🏗️ Архитектура

### Компоненты:

1. **Aggregators** (`src/federated_learning/aggregators.py`)
   - `FedAvgAggregator` - Standard weighted averaging
   - `KrumAggregator` - Byzantine-robust selection
   - `TrimmedMeanAggregator` - Outlier removal
   - `MedianAggregator` - Coordinate-wise median

2. **Secure Aggregators** (`src/federated_learning/secure_aggregators.py`)
   - `SecureFedAvgAggregator` - Privacy-preserving FedAvg
   - `SecureKrumAggregator` - Privacy-preserving Krum
   - `GraphSAGEAggregator` - GraphSAGE-specific aggregation

3. **Byzantine-Robust** (`src/federated_learning/byzantine_robust.py`)
   - `EnhancedKrumAggregator` - Enhanced Krum with optimizations
   - `AdaptiveTrimmedMeanAggregator` - Adaptive trimmed mean

4. **Model Synchronization** (`src/federated_learning/model_sync.py`)
   - `ModelSynchronizer` - Version control and conflict resolution

5. **GraphSAGE Integration** (`src/federated_learning/graphsage_integration.py`)
   - `GraphSAGEFLCoordinator` - FL Coordinator with GraphSAGE
   - `GraphSAGEDistributedTrainer` - Distributed training

6. **Privacy** (`src/federated_learning/privacy.py`)
   - `DifferentialPrivacy` - DP engine
   - `GradientClipper` - Gradient clipping
   - `PrivacyBudget` - Budget tracking

---

## 🚀 Быстрый старт

### Базовое использование:

```python
from src.federated_learning.secure_aggregators import SecureFedAvgAggregator
from src.federated_learning.protocol import ModelUpdate, ModelWeights

# Создать агрегатор
aggregator = SecureFedAvgAggregator(enable_dp=True)

# Создать обновления
updates = [
    ModelUpdate(
        node_id="node-1",
        round_number=1,
        weights=ModelWeights(layer_weights={"layer1": [1.0, 2.0]}),
        num_samples=100
    ),
    # ... больше обновлений
]

# Агрегировать
result = aggregator.aggregate(updates)
if result.success:
    global_model = result.global_model
    print(f"Global model version: {global_model.version}")
```

### С GraphSAGE:

```python
from src.federated_learning.graphsage_integration import (
    GraphSAGEFLCoordinator,
    GraphSAGEFLConfig
)

# Создать конфигурацию
config = GraphSAGEFLConfig(
    enable_privacy=True,
    aggregation_method="graphsage"
)

# Создать координатор
coordinator = GraphSAGEFLCoordinator(
    node_id="coordinator-1",
    fl_config=config
)

# Начать тренировку
round_info = coordinator.start_training_round(["node-1", "node-2", "node-3"])

# Обучить локально
update = coordinator.train_local(round_info["round_number"])

# Агрегировать
global_model = coordinator.aggregate_updates([update])
```

---

## 🔒 Privacy-Preserving Aggregation

### Differential Privacy:

```python
from src.federated_learning.secure_aggregators import SecureFedAvgAggregator
from src.federated_learning.privacy import DPConfig

# Настроить DP
dp_config = DPConfig(
    target_epsilon=1.0,      # Privacy budget
    target_delta=1e-5,      # Failure probability
    max_grad_norm=1.0,      # Gradient clipping threshold
    noise_multiplier=1.1    # Noise scale
)

# Создать агрегатор с DP
aggregator = SecureFedAvgAggregator(
    dp_config=dp_config,
    enable_dp=True
)

# Использовать как обычно
result = aggregator.aggregate(updates)

# Проверить privacy budget
if result.success:
    epsilon_spent = result.privacy_epsilon_spent
    budget_remaining = result.privacy_budget_remaining
    print(f"Privacy spent: {epsilon_spent}, Remaining: {budget_remaining}")
```

### Privacy Guarantees:

- **Gradient Clipping:** L2 norm clipping для bounded sensitivity
- **Noise Addition:** Gaussian noise с calibrated scale
- **Privacy Budget:** Tracking (ε, δ) expenditure
- **No Raw Data Sharing:** Только агрегированные градиенты

---

## 🛡️ Byzantine-Robust Aggregation

### Enhanced Krum:

```python
from src.federated_learning.byzantine_robust import EnhancedKrumAggregator

# Создать агрегатор
aggregator = EnhancedKrumAggregator(
    f=1,                    # Byzantine tolerance
    multi_krum=True,        # Multi-Krum mode
    m=2,                    # Number of updates to average
    adaptive_f=True         # Adaptive f selection
)

# Агрегировать
result = aggregator.aggregate(updates)

# Проверить Byzantine detection
if result.success and result.suspected_byzantine:
    print(f"Byzantine nodes detected: {result.suspected_byzantine}")
```

### Adaptive Trimmed Mean:

```python
from src.federated_learning.byzantine_robust import AdaptiveTrimmedMeanAggregator

# Создать агрегатор
aggregator = AdaptiveTrimmedMeanAggregator(
    beta=0.1,               # Trim fraction
    adaptive_beta=True,      # Adaptive beta selection
    outlier_detection="iqr"  # Outlier detection method
)

# Агрегировать
result = aggregator.aggregate(updates)
```

### Byzantine Tolerance:

- **Krum:** Tolerates up to f < (n-2)/2 Byzantine nodes
- **Trimmed Mean:** Removes top/bottom β fraction
- **Adaptive Methods:** Adjust parameters based on network conditions

---

## 🔄 Model Synchronization

### Basic Usage:

```python
from src.federated_learning.model_sync import ModelSynchronizer
from src.federated_learning.protocol import GlobalModel, ModelWeights

# Создать синхронизатор
synchronizer = ModelSynchronizer(node_id="node-1")

# Получить глобальную модель
global_model = GlobalModel(
    version=1,
    round_number=1,
    weights=ModelWeights(layer_weights={"layer1": [1.0, 2.0]}),
    num_contributors=3
)

# Получить модель
success = synchronizer.receive_global_model(global_model, "coordinator")

# Проверить версию
current_version = synchronizer.get_model_version()
print(f"Current model version: {current_version}")
```

### Conflict Resolution:

```python
# Проверить конфликты
conflicts = synchronizer.check_for_conflicts(local_model, global_model)

# Разрешить конфликты
if conflicts:
    success = synchronizer.resolve_conflicts(
        conflicts,
        strategy="prefer_global"  # или "prefer_local", "merge"
    )
```

### Rollback:

```python
# Откатить к предыдущей версии
success = synchronizer.rollback(target_version=2)
```

---

## 📊 Performance Benchmarks

### Aggregation Speed:

| Aggregator | 10 Updates | 50 Updates | 100 Updates |
|------------|------------|------------|-------------|
| FedAvg | <1ms | <5ms | <10ms |
| SecureFedAvg | <2ms | <10ms | <20ms |
| Krum | <10ms | <50ms | <200ms |
| EnhancedKrum | <8ms | <40ms | <150ms |
| TrimmedMean | <2ms | <8ms | <15ms |

### Privacy Overhead:

- **Gradient Clipping:** ~5% overhead
- **Noise Addition:** ~10% overhead
- **Total DP Overhead:** ~15-20%

---

## 🧪 Testing

### Unit Tests:

```bash
# Запустить все тесты
pytest tests/unit/federated_learning/ -v

# Тесты для secure aggregators
pytest tests/unit/federated_learning/test_secure_aggregators.py -v

# Тесты для model sync
pytest tests/unit/federated_learning/test_model_sync.py -v

# Тесты для Byzantine-robust
pytest tests/unit/federated_learning/test_byzantine_robust.py -v
```

### Integration Tests:

```bash
# GraphSAGE FL integration
pytest tests/integration/test_graphsage_fl_integration.py -v
```

### Performance Tests:

```bash
# Benchmarks
pytest tests/performance/test_fl_benchmarks.py -v -s
```

---

## 📚 API Reference

### SecureFedAvgAggregator

```python
class SecureFedAvgAggregator(FedAvgAggregator):
    def __init__(
        self,
        dp_config: Optional[DPConfig] = None,
        enable_dp: bool = True
    ):
        """
        Privacy-preserving FedAvg aggregator.
        
        Args:
            dp_config: Differential privacy configuration
            enable_dp: Enable differential privacy
        """
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """
        Aggregate with privacy-preserving mechanisms.
        
        Returns:
            AggregationResult with privacy metadata
        """
```

### GraphSAGEFLCoordinator

```python
class GraphSAGEFLCoordinator:
    def __init__(
        self,
        node_id: str,
        graphsage_model: Optional[GraphSAGEAnomalyDetector] = None,
        fl_config: Optional[GraphSAGEFLConfig] = None
    ):
        """
        FL Coordinator with GraphSAGE integration.
        
        Args:
            node_id: Coordinator node ID
            graphsage_model: GraphSAGE model instance
            fl_config: FL configuration
        """
    
    def start_training_round(
        self,
        selected_nodes: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Start a new training round."""
    
    def train_local(
        self,
        round_number: int,
        local_data: Optional[Any] = None
    ) -> Optional[ModelUpdate]:
        """Train GraphSAGE model locally."""
    
    def aggregate_updates(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> Optional[GlobalModel]:
        """Aggregate local updates into global model."""
```

---

## 🔧 Configuration

### DPConfig:

```python
@dataclass
class DPConfig:
    target_epsilon: float = 1.0      # Total ε
    target_delta: float = 1e-5      # Fixed δ
    max_grad_norm: float = 1.0       # L2 norm clip threshold
    noise_multiplier: float = 1.1    # Noise scale
    sample_rate: float = 0.01        # Fraction of data per round
    max_rounds: int = 100            # Maximum training rounds
```

### GraphSAGEFLConfig:

```python
@dataclass
class GraphSAGEFLConfig:
    enable_privacy: bool = True
    enable_byzantine_robust: bool = True
    aggregation_method: str = "graphsage"
    sync_interval: int = 1
    model_versioning: bool = True
```

---

## 🎯 Best Practices

1. **Privacy:**
   - Используйте DP для sensitive data
   - Настройте privacy budget согласно требованиям
   - Мониторьте privacy expenditure

2. **Byzantine-Robust:**
   - Используйте Enhanced Krum для adversarial environments
   - Настройте f согласно ожидаемому количеству Byzantine nodes
   - Мониторьте suspected_byzantine в результатах

3. **Performance:**
   - Используйте FedAvg для trusted environments
   - Используйте Enhanced Krum для untrusted environments
   - Оптимизируйте vector size для больших моделей

4. **Model Sync:**
   - Всегда проверяйте версии перед применением
   - Используйте conflict resolution стратегии
   - Храните историю для rollback

---

## 🐛 Troubleshooting

### Privacy Budget Exhausted:

```python
# Проверить budget
if aggregator.privacy_budget.is_exhausted(max_epsilon=10.0):
    # Увеличить epsilon или уменьшить noise
    dp_config.target_epsilon = 20.0
    aggregator = SecureFedAvgAggregator(dp_config=dp_config)
```

### Byzantine Detection Issues:

```python
# Увеличить f для большего tolerance
aggregator = EnhancedKrumAggregator(f=2, adaptive_f=True)
```

### Model Sync Conflicts:

```python
# Использовать prefer_global для автоматического разрешения
synchronizer.resolve_conflicts(conflicts, strategy="prefer_global")
```

---

## 📖 References

- **Differential Privacy:** "Deep Learning with Differential Privacy" (Abadi et al., 2016)
- **Byzantine-Robust:** "Machine Learning with Adversaries" (Blanchard et al., 2017)
- **FedAvg:** "Communication-Efficient Learning" (McMahan et al., 2017)
- **GraphSAGE:** "Inductive Representation Learning" (Hamilton et al., 2017)

---

## ✅ Status

**Current Version:** 1.0  
**Status:** Production-Ready (80%)  
**Last Updated:** 2025-12-28

**Components:**
- ✅ Privacy-preserving aggregation
- ✅ Byzantine-robust aggregators
- ✅ GraphSAGE integration
- ✅ Model synchronization
- ⏳ Documentation (in progress)

---

**Mesh обновлён. Federated Learning готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

