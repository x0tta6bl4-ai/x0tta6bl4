# 🏗️ РАСШИФРОВКА АРХИТЕКТУРНОЙ ДИАГРАММЫ (5 СЛОЁВ)

> Статус доказательств на 2026-05-30: это расшифровка диаграммы и инвентарь
> claims, а не текущее production proof. Числа вроде `<100ms`, `94-98%`,
> `99.2%`, `<1ms failover` и `20s MTTD` ниже не являются доказанными
> runtime-фактами без current verification artifact. Актуальные границы
> доказательств: `docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md` и
> `docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json`.

**Дата:** 28 декабря 2025  
**Источник:** Детальная архитектурная диаграмма системы x0tta6bl4

---

## 📊 ОБЩАЯ СТРУКТУРА

Диаграмма показывает **5-слойную архитектуру** автономной AI-системы для mesh-сети с полным циклом от сбора данных до обратной связи.

```
┌─────────────────────────────────────────────────────────────┐
│  1. MESH NETWORK (фиолетовый)                                │
│     ↓                                                        │
│  2. DATA COLLECTION LAYER (синий)                           │
│     ↓                                                        │
│  3. AI/ML PROCESSING (зелёный)                              │
│     ↓                                                        │
│  4. ACTION LAYER (оранжевый)                                │
│     ↓                                                        │
│  5. FEEDBACK LOOP (фиолетовый)                              │
│     ↑                                                        │
│     └───────────────────────────────────────────────────────┘
```

---

## 1️⃣ MESH NETWORK (Фиолетовый блок)

### Узлы сети:

- **Node1 (Edge)** — Edge узел
- **Node2 (Edge)** — Edge узел
- **Node3 (Core)** — Центральный узел
- **Node4 (Edge)** — Edge узел
- **Node5 (Edge)** — Edge узел

### Топология соединений:

```
Node1 ──→ Node3
Node2 ──→ Node3
Node3 ──→ Node4
Node3 ──→ Node5
Node4 ──→ Node5
```

**Интерпретация:**
- **Star topology** с Node3 в центре
- Node3 (Core) — центральный хаб
- Остальные узлы — Edge устройства (Raspberry Pi, etc.)

### Исходящие соединения:

Все узлы отправляют данные в **Data Collection Layer**:
- Node1, Node3, Node4, Node5 → Prometheus
- Node1, Node3, Node4, Node5 → Log Collector

### Обратная связь:

**Feedback Loop** отправляет команды обратно:
- Feedback → Node2
- Feedback → Node3

**Контекст:** Система может управлять узлами напрямую (изоляция, маршрутизация, масштабирование).

---

## 2️⃣ DATA COLLECTION LAYER (Синий блок)

### Компоненты:

1. **Prometheus (metrics) <100ms**
   - Сбор метрик в реальном времени
   - Источники: Node1, Node3, Node4, Node5
   - Задержка: <100ms

2. **Log Collector (events) <100ms**
   - Сбор событий и логов
   - Источники: Node1, Node3, Node4, Node5
   - Задержка: <100ms

3. **eBPF (kernel-level) <100ms**
   - Сбор данных на уровне ядра
   - Источник: Log Collector
   - Задержка: <100ms

### Потоки данных:

```
Mesh Network
    │
    ├─→ Prometheus ──→ AI/ML Processing
    │
    └─→ Log Collector ──→ eBPF ──→ AI/ML Processing
```

**Интерпретация:**
- **Prometheus:** Метрики (CPU, память, сеть, latency)
- **Log Collector:** События (соединения, ошибки, инциденты)
- **eBPF:** Kernel-level данные (пакеты, системные вызовы)

**Все компоненты:** <100ms задержка (real-time сбор)

---

## 3️⃣ AI/ML PROCESSING (Зелёный блок)

### 3.1 Anomaly Detection (Обнаружение аномалий)

**Компоненты:**

1. **Isolation Forest**
   - Источник: Prometheus
   - Unsupervised детектор (не требует меток)

2. **GraphSAGE v2 (diagram claim: 94-98% accuracy)**
   - Источники: Prometheus + Log Collector
   - Graph Neural Network для топологии сети
   - Точность: 94-98% как claim, needs current artifact

3. **Ensemble Detector**
   - Источник: GraphSAGE v2
   - Multi-model консенсус
   - Повышает точность до 99.2% как claim, needs current artifact

4. **Causal Analysis (diagram claim: >90% accuracy)**
   - Источник: eBPF
   - Определение root cause
   - Точность: >90% как claim, needs current artifact

**Поток данных:**
```
Prometheus ──→ Isolation Forest ──→ FL Coordinator
Prometheus ──→ GraphSAGE v2 ──→ Ensemble ──→ Byzantine Agg
Log Collector ──→ GraphSAGE v2
eBPF ──→ Causal Analysis ──→ Diff Privacy
```

---

### 3.2 Federated Learning (Федеративное обучение)

**Компоненты:**

1. **FL Coordinator**
   - Источник: Isolation Forest
   - Оркестрация раундов обучения

2. **PPO Agent**
   - Источник: GraphSAGE v2
   - Reinforcement Learning для маршрутизации

3. **Byzantine Agg**
   - Источник: Ensemble Detector
   - Защита от злых узлов (Krum, TrimmedMean, Median)

4. **Diff Privacy**
   - Источник: Causal Analysis
   - Дифференциальная приватность (ε=1.0, δ=1e-5)

5. **Model Chain**
   - Источник: Diff Privacy
   - Blockchain для audit trail (PBFT consensus)

**Поток данных:**
```
Anomaly Detection
    │
    ├─→ FL Coordinator ──→ Mesh AI Router
    ├─→ PPO Agent ──→ MAPE-K Loop
    ├─→ Byzantine Agg ──→ eBPF-GraphSAGE
    └─→ Diff Privacy ──→ Model Chain
```

---

### 3.3 Self-Healing (Самолечение)

**Компоненты:**

1. **Mesh AI Router (diagram claim: <1ms failover)**
   - Источник: FL Coordinator
   - Multi-LLM routing (Local/P2P/Cloud)
   - Failover: <1ms как claim, needs current artifact

2. **MAPE-K Loop (diagram claim: MTTD 20s)**
   - Источник: PPO Agent
   - Monitor → Analyze → Plan → Execute → Knowledge
   - MTTD: 20 секунд как claim, needs current artifact

3. **eBPF-GraphSAGE (<100ms stream)**
   - Источники: Byzantine Agg + Diff Privacy
   - Real-time kernel→ML streaming
   - Задержка: <100ms

**Поток данных:**
```
Federated Learning
    │
    ├─→ Mesh AI Router ──→ Consciousness Eng
    ├─→ MAPE-K Loop ──→ QAOA Optimizer
    └─→ eBPF-GraphSAGE ──→ Sandbox Manager
```

---

### 3.4 Optimization (Оптимизация)

**Компоненты:**

1. **Consciousness Eng**
   - Источник: Mesh AI Router
   - Harmony metrics (φ-ratio)

2. **QAOA Optimizer**
   - Источник: MAPE-K Loop
   - Quantum-inspired оптимизация топологии

3. **Sandbox Manager**
   - Источник: eBPF-GraphSAGE
   - Безопасное тестирование экспериментов

4. **Digital Twin**
   - Источники: QAOA Optimizer + Sandbox Manager
   - Chaos-tested симуляция сети

5. **Twin FL Integr**
   - Источник: Consciousness Eng
   - Валидированное обучение на симуляции

**Поток данных:**
```
Self-Healing
    │
    ├─→ Consciousness Eng ──→ Twin FL Integr ──→ Routing Update
    ├─→ QAOA Optimizer ──→ Digital Twin ──→ Scaling Actions
    └─→ Sandbox Manager ──→ Digital Twin ──→ Isolation Actions
```

---

## 4️⃣ ACTION LAYER (Оранжевый блок)

**Компоненты:**

1. **Routing Update (topology changes)**
   - Источники: Consciousness Eng + Twin FL Integr
   - Изменение топологии маршрутизации
   - Действие: Обновление таблиц маршрутизации

2. **Isolation Actions (quarantine nodes)**
   - Источник: QAOA Optimizer
   - Изоляция скомпрометированных узлов
   - Действие: Quarantine Node2, Node4, etc.

3. **Scaling Actions (auto-scale)**
   - Источник: Digital Twin
   - Автоматическое масштабирование
   - Действие: Добавление/удаление узлов

**Поток данных:**
```
Optimization
    │
    ├─→ Routing Update ──→ Knowledge Base
    ├─→ Isolation Actions ──→ Model Improvement
    └─→ Scaling Actions ──→ Learning from Incidents
```

**Контекст:** Все действия применяются к Mesh Network через Feedback Loop.

---

## 5️⃣ FEEDBACK LOOP (Фиолетовый блок)

**Компоненты:**

1. **Knowledge Base (historical data)**
   - Источник: Routing Update
   - Хранение исторических данных
   - Использование: RAG для инцидент-респонса

2. **Model Improvement (continuous learning)**
   - Источник: Isolation Actions
   - Непрерывное улучшение моделей
   - Использование: Обновление GraphSAGE, PPO, etc.

3. **Learning from Incidents (post-mortem)**
   - Источник: Scaling Actions
   - Обучение на инцидентах
   - Использование: Улучшение MAPE-K, Causal Analysis

**Обратная связь:**

```
Feedback Loop
    │
    ├─→ Feedback ──→ Node2 (Mesh Network)
    └─→ Feedback ──→ Node3 (Mesh Network)
```

**Контекст:**
- Система учится на каждом инциденте
- Знания накапливаются в Knowledge Base
- Модели улучшаются через FL
- Обратная связь применяется к узлам сети

---

## 🔄 ПОЛНЫЙ ЦИКЛ РАБОТЫ

### Пример: Обнаружение аномалии на Node4

```
1. MESH NETWORK
   Node4 отправляет метрики → Prometheus
   Node4 отправляет события → Log Collector

2. DATA COLLECTION
   Prometheus (<100ms) → GraphSAGE v2
   Log Collector (<100ms) → GraphSAGE v2
   eBPF (<100ms) → Causal Analysis

3. AI/ML PROCESSING
   GraphSAGE v2 (diagram claim: 94-98%) → Обнаружена аномалия
   Causal Analysis (>90%) → Root cause: высокая latency
   Ensemble Detector → Подтверждение (99.2%)
   
   FL Coordinator → Оркестрация обучения
   PPO Agent → Оптимизация маршрута
   Byzantine Agg → Защита от злых узлов
   
   MAPE-K Loop (diagram claim: 20s MTTD) → План действий
   Mesh AI Router (diagram claim: <1ms) → Выбор LLM провайдера
   eBPF-GraphSAGE (<100ms) → Real-time streaming
   
   QAOA Optimizer → Оптимизация топологии
   Digital Twin → Симуляция решения

4. ACTION LAYER
   Routing Update → Изменение маршрута (Node4 → Node5 обход)
   Isolation Actions → Временная изоляция Node4 (если нужно)
   Scaling Actions → Добавление резервного узла (если нужно)

5. FEEDBACK LOOP
   Knowledge Base → Сохранение инцидента
   Model Improvement → Обновление GraphSAGE
   Learning from Incidents → Улучшение MAPE-K
   
   Feedback → Node2, Node3 (применение изменений)
```

**Результат:**
- Диаграмма заявляет обнаружение аномалии за 20 секунд (MTTD); current proof не приложен
- Диаграмма заявляет root cause с >90% точностью; current proof не приложен
- Диаграмма заявляет автоматическое изменение маршрута; current dataplane proof не приложен
- Диаграмма заявляет обучение на инциденте; current runtime proof не приложен

---

## 📊 КЛЮЧЕВЫЕ CLAIM-МЕТРИКИ ИЗ ДИАГРАММЫ

| Метрика | Значение из диаграммы | Компонент | Evidence status |
|---------|----------|-----------|---|
| **Data Collection Latency** | <100ms | Prometheus, Log Collector, eBPF | claim, needs current artifact |
| **Anomaly Accuracy** | 94-98% | GraphSAGE v2 | claim, needs current artifact |
| **Root Cause Accuracy** | >90% | Causal Analysis | claim, needs current artifact |
| **Ensemble Precision** | 99.2% | Ensemble Detector | claim, needs current artifact |
| **MTTD** | 20s | MAPE-K Loop | claim, needs current artifact |
| **Failover Time** | <1ms | Mesh AI Router | claim, needs current artifact |
| **Streaming Latency** | <100ms | eBPF-GraphSAGE | claim, needs current artifact |

---

## 🎯 СВЯЗЬ С 17 КОМПОНЕНТАМИ

| Слой диаграммы | Компоненты x0tta6bl4 |
|----------------|---------------------|
| **3.1 Anomaly Detection** | #1 GraphSAGE v2<br>#2 Isolation Forest<br>#3 Ensemble Detector<br>#4 Causal Analysis |
| **3.2 Federated Learning** | #6 FL Coordinator<br>#7 PPO Agent<br>#8 Byzantine Aggregators<br>#9 Differential Privacy<br>#10 Model Blockchain |
| **3.3 Self-Healing** | #5 MAPE-K Loop<br>#11 Mesh AI Router<br>#12 eBPF→GraphSAGE Streaming |
| **3.4 Optimization** | #13 QAOA Optimizer<br>#14 Consciousness Engine<br>#15 Sandbox Manager<br>#16 Digital Twin<br>#17 Twin FL Integration |

**Все 17 компонентов присутствуют в диаграмме! ✅**

---

## 💡 КЛЮЧЕВЫЕ ВЫВОДЫ

1. **Полный цикл:** От сбора данных до обратной связи
2. **Real-time:** Все компоненты работают с задержкой <100ms
3. **Автономность:** Система сама обнаруживает, понимает, чинит и улучшается
4. **5 слоёв:** Чёткое разделение ответственности
5. **Feedback Loop:** Непрерывное обучение и улучшение

---

**Документ:** ARCHITECTURE_DIAGRAM_DECODED.md  
**Версия:** 1.0  
**Дата:** 28 декабря 2025
