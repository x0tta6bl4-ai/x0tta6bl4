# Техническая доказательная база для гранта Старт-ИИ-1

**Проект:** x0tta6bl4 — самовосстанавливающаяся mesh-сеть с постквантовой криптографией
**Дата:** 8 февраля 2026
**Статус:** Все 6 критических НИОКР-пробелов закрыты, метрики измерены

---

## 1. Закрытые критические пробелы

Анализ от 2 февраля 2026 (`АНАЛИЗ_ПРОЕКТА_x0tta6bl4_ОТЧЕТ.md`) выявил 6 критических пробелов. Все закрыты за 4 коммита:

| # | Пробел | Было | Стало | Коммит |
|---|--------|------|-------|--------|
| 1 | ConsciousnessEngineV2 — if/else заглушка | Простые ветвления | Взвешенное мультиобъектное скоринг с sigmoid-активацией по 5 действиям | `0e11a730` |
| 2 | DAO Governance — только логирование | `execute_proposal()` → лог | ActionDispatcher с 5 обработчиками + JSONL-ледер | `0e11a730` |
| 3 | GraphSAGE — обучение на случайных данных | Рандомные фичи | MeshTelemetryGenerator с 6 сценариями, `train_from_telemetry()` | `0e11a730`, `3e327882` |
| 4 | CRDT — только GCounter | 1 тип | GCounter, PNCounter, LWWRegister, ORSet | `524f3d18` |
| 5 | BM25 — полностью отсутствует | Нет | BM25Scorer + HybridSearchPipeline (RRF fusion) | `524f3d18` |
| 6 | eBPF PQC — поддельная верификация (XOR) | XOR-шифр, пустая проверка | SipHash-2-4 аутентификация (64-bit MAC) | `524f3d18` |

---

## 2. Измеренные метрики (бенчмарки)

Все метрики получены воспроизводимым бенчмарком:
```bash
python3 -m benchmarks.benchmark_anomaly_detection
```
Результаты: `benchmarks/anomaly_detection_results.json`

### 2.1 Обнаружение аномалий (GraphSAGE + rule-based fallback)

**Общие метрики (10 000 узлов):**

| Метрика | Значение |
|---------|----------|
| Accuracy | 95.0% |
| Precision | 62.2% |
| Recall | 60.5% |
| F1 Score | 61.4% |
| FPR (ложные срабатывания) | 2.6% |
| Inference throughput | 1.2M узлов/сек |
| Inference latency | 8.02ms на 10K узлов |

**Метрики по типам аномалий:**

| Сценарий | Accuracy | Precision | Recall | F1 |
|----------|----------|-----------|--------|-----|
| Normal (нет аномалий) | 96.7% | — | — | — |
| Partition (разрыв сети) | 98.2% | 90.6% | **100%** | 95.1% |
| Node Overload (перегрузка) | 97.6% | 81.3% | **99.0%** | 89.3% |
| Interference (помехи) | 79.1% | 95.3% | 55.3% | 70.0% |
| Link Degradation (деградация) | 93.0% | 87.2% | 62.9% | 73.1% |
| Cascade Failure (каскад) | 83.2% | 82.6% | 31.7% | 45.8% |

### 2.2 DAO Governance — латентность диспатча

| Метрика | Значение |
|---------|----------|
| Средняя латентность | 64.2 мкс |
| Максимальная латентность | 86.3 мкс |
| Типы действий | 5 (restart_node, rotate_keys, update_threshold, update_config, ban_node) |
| Итерации измерения | 1000 на действие |

### 2.3 Система принятия решений (ConsciousnessV2)

| Метрика | Значение |
|---------|----------|
| Средняя латентность | 16.7 мкс |
| Максимальная латентность | 19.9 мкс |
| Сценарии | 4 (критический, нагрузка, сетевой, нормальный) |
| Итерации измерения | 10 000 на сценарий |

### 2.4 Генерация телеметрии

| Объём | Время | Пропускная способность |
|-------|-------|----------------------|
| 2 000 узлов | 0.039 сек | 51 762 узлов/сек |
| 10 000 узлов | 0.202 сек | 49 526 узлов/сек |
| 20 000 узлов | 0.372 сек | 53 719 узлов/сек |

---

## 3. Тестовое покрытие

| Тестовый файл | Кол-во тестов | Что покрывает |
|--------------|---------------|---------------|
| `tests/unit/core/test_consciousness_v2_unit.py` | 19 | Мультиобъектное скоринг, sigmoid-активация, XAI |
| `tests/unit/core/test_mape_k_loop_unit.py` | 19 | Все 5 фаз MAPE-K, DAO dispatch, Prometheus export |
| `tests/unit/dao/test_governance.py` | 18 | Квадратичное голосование, кворум, состояния предложений |
| `tests/unit/dao/test_governance_dispatch_unit.py` | 23 | ActionDispatcher, 5 обработчиков, ледер |
| `tests/unit/ml/test_graphsage_telemetry_integration.py` | 11 | Telemetry→GraphSAGE, MAPE-K wiring, quality метрики |
| `tests/unit/ml/test_mesh_telemetry_unit.py` | 18 | 6 типов сценариев, генерация данных |
| `tests/unit/ml/test_graphsage_unit.py` | 15 | Детектор инициализация, пороги, фичи |
| `tests/unit/security/test_pqc_liboqs_unit.py` | 34 | ML-KEM-768, ML-DSA-65, AES-256-GCM |
| **Итого новых/расширенных** | **90+** | |

Все тесты проходят:
```bash
python3 -m pytest tests/unit/ -o "addopts=" --no-cov -q
```

---

## 4. Компоненты НИОКР — файловая карта

### 4.1 GraphSAGE обнаружение аномалий
- **Детектор:** `src/ml/graphsage_anomaly_detector.py` (736 строк)
- **Телеметрия:** `src/ml/mesh_telemetry.py` (356 строк) — 6 сценариев с физически корректными корреляциями
- **Бенчмарк:** `benchmarks/benchmark_anomaly_detection.py`
- **Тесты:** 44 тестов (3 файла)

### 4.2 MAPE-K самовосстановление
- **Цикл:** `src/core/mape_k_loop.py` (272 строки) — Monitor→Analyze→Plan→Execute→Knowledge
- **Интеграция с DAO:** `action_dispatcher` в Execute-фазе
- **Тесты:** 19 тестов

### 4.3 Система принятия решений
- **Движок:** `src/core/consciousness_v2.py` (548 строк) — взвешенное мультиобъектное скоринг
- **Алгоритм:** Sigmoid-активация: `1/(1 + e^(-4*(value/threshold - 1)))` по матрице `ACTION_SCORES`
- **5 действий:** restart_service, scale_up, rotate_keys, switch_route, isolate_node
- **Тесты:** 19 тестов

### 4.4 DAO Governance
- **Движок:** `src/dao/governance.py` (402 строки) — квадратичное голосование, ActionDispatcher
- **Формула:** voting_power = sqrt(tokens) — снижает влияние крупных токенхолдеров
- **Ледер:** Append-only JSONL для аудита
- **Тесты:** 41 тест (2 файла)

### 4.5 Постквантовая криптография
- **Библиотека:** `src/security/post_quantum.py` (565 строк) — ML-KEM-768, ML-DSA-65
- **Hybrid TLS:** X25519 + ML-KEM-768
- **eBPF:** `src/network/ebpf/programs/xdp_pqc_verify.c` — SipHash-2-4 MAC
- **Тесты:** 34 теста

### 4.6 Гибридный поиск (RAG)
- **Pipeline:** `src/rag/pipeline.py` — BM25 + Vector Embeddings
- **BM25:** `src/rag/pipeline.py:BM25Scorer` — классический BM25 с IDF
- **Fusion:** Reciprocal Rank Fusion (RRF) для объединения результатов

### 4.7 CRDT для синхронизации
- **Модуль:** `src/data_sync/crdt.py` — GCounter, PNCounter, LWWRegister, ORSet
- **Алгоритм:** Convergent Replicated Data Types для eventual consistency

---

## 5. Воспроизводимость результатов

```bash
# Запуск бенчмарков (генерирует anomaly_detection_results.json)
python3 -m benchmarks.benchmark_anomaly_detection

# Запуск всех unit-тестов
python3 -m pytest tests/unit/ -o "addopts=" --no-cov -v

# Запуск только тестов интеграции GraphSAGE↔Telemetry
python3 -m pytest tests/unit/ml/test_graphsage_telemetry_integration.py -v -o "addopts=" --no-cov
```

---

## 6. Git-история реализации

```
d62d1046 test: add MAPE-K loop unit tests (19) and expand governance tests (12 new)
3e327882 feat: wire GraphSAGE↔telemetry training, MAPE-K↔DAO dispatch, add benchmarks
0e11a730 feat: close 3 more R&D gaps — mesh telemetry, DAO dispatch, consciousness scoring
524f3d18 feat: close 3 critical R&D gaps — CRDT, BM25 hybrid search, eBPF PQC
```

---

**Документ подготовлен:** 8 февраля 2026
**Следующее действие:** Обновить НИОКР описание и подготовить демо-версию
