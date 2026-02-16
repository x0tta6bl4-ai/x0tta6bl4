# 🧠 GNN Detector Observe Mode Plan

**Цель**: Активировать GNN detector в observe mode  
**Статус**: Планирование  
**Приоритет**: Stage 2, недели 24-28

---

## 🎯 Обзор

Активировать GraphSAGE v2 detector в "observe mode" - детектирование без автоматических действий.

**Преимущества observe mode**:
- Сбор данных для обучения
- Валидация accuracy
- Низкий риск (нет автоматических действий)
- Постепенная миграция к "block mode"

---

## 📋 Implementation Plan

### Phase 1: Observe Mode Setup (Неделя 24-25)

#### 1.1 Configuration
**Файл**: `src/ml/graphsage_anomaly_detector.py`

```python
class GraphSAGEAnomalyDetector:
    def __init__(self, mode='observe'):
        """
        mode: 'observe' | 'block' | 'warn'
        """
        self.mode = mode
        self.anomalies_detected = []
    
    def detect(self, graph_data):
        """Detect anomalies"""
        anomaly_score = self.model.predict(graph_data)
        
        if anomaly_score > self.threshold:
            if self.mode == 'observe':
                self._log_anomaly(anomaly_score)
            elif self.mode == 'warn':
                self._log_anomaly(anomaly_score)
                self._send_alert(anomaly_score)
            elif self.mode == 'block':
                self._block_action(anomaly_score)
        
        return anomaly_score
```

#### 1.2 Logging
- [ ] Логировать все detected anomalies
- [ ] Сохранять context (graph state, metrics)
- [ ] Timestamp и confidence score

#### 1.3 Metrics
- [ ] Anomaly detection rate
- [ ] False positive rate
- [ ] Confidence distribution

### Phase 2: Validation (Неделя 26-27)

#### 2.1 Manual Review
- [ ] Review detected anomalies
- [ ] Validate true/false positives
- [ ] Adjust thresholds

#### 2.2 Performance Metrics
- [ ] Accuracy tracking
- [ ] Precision/Recall
- [ ] F1 score

### Phase 3: Migration to Block Mode (Неделя 28)

#### 3.1 Gradual Rollout
- [ ] Start with low-risk actions
- [ ] Monitor impact
- [ ] Gradually increase scope

#### 3.2 Safety Mechanisms
- [ ] Circuit breaker
- [ ] Manual override
- [ ] Rollback capability

---

## 📊 Success Metrics

### Observe Mode:
- **Accuracy**: >95% (target)
- **False Positive Rate**: <5%
- **Coverage**: 100% of nodes

### Block Mode (после observe):
- **Action Success Rate**: >98%
- **False Block Rate**: <1%
- **MTTR Impact**: <10% increase

---

## 🔧 Configuration

```yaml
# config/gnn_detector.yaml
mode: observe  # observe | warn | block
threshold: 0.95
confidence_required: 0.90
logging:
  enabled: true
  level: INFO
metrics:
  enabled: true
  export_to_prometheus: true
```

---

## 🚀 Roadmap

- [ ] Week 24-25: Observe mode setup
- [ ] Week 26-27: Validation и tuning
- [ ] Week 28: Migration to block mode (опционально)

---

**Plan готов. Реализация начнется в неделе 24-28.** 🧠

