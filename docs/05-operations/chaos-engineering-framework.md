# 🔥 Chaos Engineering Framework для x0tta6bl4

**Цель**: Создать framework для chaos testing  
**Статус**: В разработке  
**Приоритет**: Stage 2, недели 19-26

---

## 🎯 Обзор

Chaos Engineering Framework для тестирования resilience x0tta6bl4 mesh network.

**Ключевые возможности**:
- Автоматизированные chaos experiments
- Интеграция с MAPE-K циклом
- Метрики recovery time
- Визуализация результатов

---

## 📋 Компоненты

### 1. Chaos Experiments

#### Node Failure
- **Описание**: Симуляция отказа узла
- **Метрики**: MTTR, recovery success rate
- **Файл**: `tests/chaos/test_node_failure.py`

#### Network Partition
- **Описание**: Симуляция сетевого раздела
- **Метрики**: Resync time, connectivity recovery
- **Файл**: `tests/chaos/test_network_partition.py`

#### High Latency
- **Описание**: Симуляция высокой задержки
- **Метрики**: Path selection, QoS degradation
- **Файл**: `tests/chaos/test_high_latency.py`

#### Packet Loss
- **Описание**: Симуляция потери пакетов
- **Метрики**: Retry rate, delivery success
- **Файл**: `tests/chaos/test_packet_loss.py`

### 2. Chaos Controller

**Файл**: `src/chaos/controller.py`

```python
class ChaosController:
    """
    Управляет chaos experiments и собирает метрики
    """
    def run_experiment(self, experiment_type, duration):
        """Запустить chaos experiment"""
        pass
    
    def collect_metrics(self):
        """Собрать метрики recovery"""
        pass
    
    def generate_report(self):
        """Сгенерировать отчет"""
        pass
```

### 3. Integration с MAPE-K

**Файл**: `src/chaos/mape_k_integration.py`

- Monitor: Отслеживание метрик во время chaos
- Analyze: Анализ recovery patterns
- Plan: Автоматическая адаптация стратегий
- Execute: Восстановление после chaos
- Knowledge: Обучение на chaos results

---

## 🚀 Roadmap

### Phase 1: Basic Chaos (Неделя 19-20)
- [ ] Node failure experiments
- [ ] Network partition experiments
- [ ] Basic metrics collection

### Phase 2: Advanced Chaos (Неделя 21-23)
- [ ] High latency simulation
- [ ] Packet loss simulation
- [ ] Combined failure scenarios

### Phase 3: Automation (Неделя 24-26)
- [ ] Automated chaos scheduling
- [ ] Integration с CI/CD
- [ ] Comprehensive reporting

---

## 📊 Метрики

### Key Metrics:
- **MTTR**: Mean Time To Recovery
- **Recovery Success Rate**: % успешных восстановлений
- **Path Availability**: % доступных путей
- **Service Degradation**: % деградации сервиса

---

## 🔧 Использование

```bash
# Запустить chaos experiment
python -m src.chaos.controller --experiment node_failure --duration 60

# Запустить все experiments
python -m src.chaos.controller --all

# Генерировать отчет
python -m src.chaos.controller --report
```

---

**Framework в разработке. Будет готов к неделе 19-26.** 🔥

