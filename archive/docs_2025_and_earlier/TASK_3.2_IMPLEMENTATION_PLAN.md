# 🚀 Задача 3.2: Federated Learning агрегатор - План реализации

**Дата:** 2025-01-27  
**Задача:** 3.2 - Federated Learning агрегатор  
**Статус:** ⏳ **ГОТОВ К СТАРТУ**  
**Дедлайн:** 19 февраля 2026

---

## 📋 Анализ существующего кода

### Существующие компоненты:

#### 1. Aggregators (`src/federated_learning/aggregators.py`):
- ✅ `FedAvgAggregator` - базовый weighted averaging
- ✅ `KrumAggregator` - Byzantine-robust selection
- ✅ `TrimmedMeanAggregator` - outlier removal
- ✅ `MedianAggregator` - coordinate-wise median

**Статус:** 60% готовности  
**Требуется:**
- Privacy-preserving методы
- GraphSAGE-specific aggregation
- Performance optimization

#### 2. Privacy (`src/federated_learning/privacy.py`):
- ✅ `DifferentialPrivacy` - базовый DP
- ✅ `DPConfig` - конфигурация
- ✅ `PrivacyBudget` - отслеживание бюджета

**Статус:** 65% готовности  
**Требуется:**
- Интеграция с агрегаторами
- Secure aggregation
- Privacy guarantees

#### 3. GraphSAGE (`src/ml/graphsage_anomaly_detector.py`):
- ✅ `GraphSAGEAnomalyDetector` - базовый детектор
- ✅ Model training
- ✅ Inference

**Статус:** 80% готовности  
**Требуется:**
- Federated training support
- Model synchronization
- Gradient aggregation

---

## 🎯 План реализации

### Этап 1: Privacy-Preserving Aggregation (1 неделя)

#### 1.1. Secure Aggregation для FedAvg

**Файл:** `src/federated_learning/aggregators.py`

**Изменения:**
```python
class SecureFedAvgAggregator(FedAvgAggregator):
    """
    Privacy-preserving FedAvg with differential privacy.
    
    Features:
    - Gradient clipping
    - Noise addition
    - Privacy budget tracking
    """
    
    def __init__(self, dp_config: Optional[DPConfig] = None):
        super().__init__()
        self.dp_config = dp_config or DPConfig()
        self.privacy_budget = PrivacyBudget()
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        # 1. Clip gradients
        clipped_updates = self._clip_gradients(updates)
        
        # 2. Add noise (if DP enabled)
        if self.dp_config.enabled:
            noisy_updates = self._add_noise(clipped_updates)
        else:
            noisy_updates = clipped_updates
        
        # 3. Aggregate (use parent method)
        result = super().aggregate(noisy_updates, previous_model)
        
        # 4. Update privacy budget
        if self.dp_config.enabled:
            self.privacy_budget.consume(self.dp_config.epsilon)
        
        return result
```

#### 1.2. Интеграция DP с существующими агрегаторами

**Изменения:**
- Добавить DP support в `KrumAggregator`
- Добавить DP support в `TrimmedMeanAggregator`
- Добавить DP support в `MedianAggregator`

#### 1.3. Тесты для Privacy-Preserving

**Файл:** `tests/unit/federated_learning/test_privacy_aggregation.py`

**Тесты:**
- Gradient clipping
- Noise addition
- Privacy budget tracking
- No raw data sharing

---

### Этап 2: GraphSAGE Integration (1 неделя)

#### 2.1. GraphSAGE-Specific Aggregation

**Файл:** `src/federated_learning/graphsage_aggregator.py` (новый)

**Реализация:**
```python
class GraphSAGEAggregator(Aggregator):
    """
    GraphSAGE-specific aggregator for federated learning.
    
    Handles:
    - Node embedding aggregation
    - Graph structure aggregation
    - Edge weight aggregation
    """
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        # 1. Aggregate node embeddings
        node_embeddings = self._aggregate_embeddings(updates)
        
        # 2. Aggregate graph structure
        graph_structure = self._aggregate_structure(updates)
        
        # 3. Aggregate edge weights
        edge_weights = self._aggregate_edge_weights(updates)
        
        # 4. Create global model
        global_model = self._create_global_model(
            node_embeddings,
            graph_structure,
            edge_weights,
            previous_model
        )
        
        return AggregationResult(
            success=True,
            global_model=global_model
        )
```

#### 2.2. Model Synchronization

**Файл:** `src/federated_learning/model_sync.py` (новый)

**Реализация:**
- Global model distribution
- Local model updates
- Version control
- Conflict resolution

#### 2.3. Integration с Coordinator

**Файл:** `src/federated_learning/coordinator.py`

**Изменения:**
- Добавить GraphSAGE support
- Интегрировать GraphSAGE aggregator
- Добавить model synchronization

---

### Этап 3: Byzantine-Robust Improvements (1 неделя)

#### 3.1. Улучшение Krum Aggregator

**Изменения:**
- Performance optimization
- Better Byzantine detection
- Multi-Krum improvements

#### 3.2. Улучшение Trimmed Mean

**Изменения:**
- Adaptive beta selection
- Better outlier detection
- Performance optimization

#### 3.3. Тесты для Byzantine-Robust

**Файл:** `tests/unit/federated_learning/test_byzantine_robust.py`

**Тесты:**
- Byzantine node detection
- Robust aggregation
- Performance under attack

---

### Этап 4: Testing & Documentation (1 неделя)

#### 4.1. Unit Tests

- Aggregator tests
- Privacy tests
- GraphSAGE integration tests
- Byzantine-robust tests

#### 4.2. Integration Tests

- Multi-node FL scenarios
- GraphSAGE distributed training
- Privacy-preserving scenarios
- Byzantine attack scenarios

#### 4.3. Documentation

- API documentation
- Usage examples
- Privacy guarantees
- Performance benchmarks

---

## 📊 Критерии готовности

- [ ] Privacy-preserving aggregation работает
- [ ] GraphSAGE integration завершена
- [ ] Model synchronization работает
- [ ] Byzantine-robust aggregation улучшен
- [ ] Тесты проходят (≥80% coverage)
- [ ] Документация полная

---

## 🎯 Ожидаемый результат

**После завершения:**
- ✅ Federated Learning агрегатор работает
- ✅ Privacy-preserving подтверждено
- ✅ GraphSAGE интегрирован
- ✅ Byzantine-robust aggregation работает
- ✅ Тесты проходят
- ✅ Готовность: +10% (77% → 87%)

---

## 📅 Timeline

| Неделя | Этап | Результат |
|--------|------|-----------|
| **1** | Privacy-Preserving Aggregation | Secure aggregation работает |
| **2** | GraphSAGE Integration | GraphSAGE интегрирован |
| **3** | Byzantine-Robust Improvements | Улучшенные агрегаторы |
| **4** | Testing & Documentation | Тесты и документация готовы |

**Дедлайн:** 19 февраля 2026

---

## 🚀 Следующие шаги

### Немедленно (после завершения 3.1):
1. Начать Этап 1 (Privacy-Preserving Aggregation)
2. Создать `SecureFedAvgAggregator`
3. Интегрировать DP с агрегаторами

### Эта неделя:
1. Реализовать GraphSAGE aggregator
2. Начать model synchronization
3. Создать тесты

### До 19 февраля:
1. Завершить все этапы
2. Протестировать
3. Документировать

---

**Mesh готов к задаче 3.2. План реализации готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

---

**Создано:** 2025-01-27  
**Версия:** 1.0  
**Статус:** ⏳ ГОТОВ К СТАРТУ

