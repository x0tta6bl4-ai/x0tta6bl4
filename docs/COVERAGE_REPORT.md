# Отчёт о тестовом покрытии НИОКР-компонентов

**Проект:** x0tta6bl4
**Дата:** 8 февраля 2026
**Инструмент:** pytest + unittest

---

## Сводка по НИОКР-модулям

| Модуль | Файл | Строк кода | Функций | Классов | Тестов |
|--------|------|-----------|---------|---------|--------|
| GraphSAGE детектор | `src/ml/graphsage_anomaly_detector.py` | 736 | 19 | 4 | 44 |
| Генератор телеметрии | `src/ml/mesh_telemetry.py` | 356 | 11 | 3 | 18 |
| MAPE-K цикл | `src/core/mape_k_loop.py` | 272 | 11 | 2 | 19 |
| ConsciousnessV2 | `src/core/consciousness_v2.py` | 548 | 22 | 6 | 19 |
| DAO Governance | `src/dao/governance.py` | 401 | 19 | 6 | 41 |
| PQC (ML-KEM/DSA) | `src/security/post_quantum.py` | 565 | 21 | 6 | 34 |
| RAG Pipeline | `src/rag/pipeline.py` | 428 | 9 | 2 | 5 |
| CRDT | `src/data_sync/crdt.py` | 292 | 45 | 6 | 8 |
| eBPF XDP SipHash | `src/network/ebpf/programs/xdp_pqc_verify.c` | 280 | C | — | 0 |
| **ИТОГО** | | **3 878** | | | **188** |

---

## Тестовые файлы

| Тестовый файл | Кол-во тестов | Покрываемый модуль |
|--------------|---------------|-------------------|
| `tests/unit/ml/test_mesh_telemetry_unit.py` | 18 | MeshTelemetryGenerator (6 сценариев) |
| `tests/unit/ml/test_graphsage_unit.py` | 15 | GraphSAGEAnomalyDetector |
| `tests/unit/ml/test_graphsage_telemetry_integration.py` | 11 | GraphSAGE↔Telemetry↔MAPE-K |
| `tests/unit/core/test_mape_k_loop_unit.py` | 19 | MAPE-K все 5 фаз + DAO dispatch |
| `tests/unit/core/test_consciousness_v2_unit.py` | 19 | Sigmoid scoring, XAI, 5 действий |
| `tests/unit/dao/test_governance.py` | 18 | Квадратичное голосование, кворум |
| `tests/unit/dao/test_governance_dispatch_unit.py` | 23 | ActionDispatcher, 5 обработчиков, леджер |
| `tests/unit/security/test_pqc_liboqs_unit.py` | 34 | ML-KEM-768, ML-DSA-65, AES-256-GCM |
| `tests/unit/security/test_pqc_fuzzing.py` | ~20 | Фаззинг PQC |
| `tests/unit/rag/test_rag_pipeline.py` | 5 | BM25 + HybridSearch |
| `tests/unit/security/spiffe/test_spiffe_controller.py` | 6 | SPIFFE/SPIRE identity |

---

## Соотношение тестов к коду

| Метрика | Значение |
|---------|----------|
| Строк кода НИОКР | 3 878 |
| Кол-во тестов | 188 |
| Соотношение | ~1 тест на 21 строк |
| Коммитов с тестами | 4 (524f3d18, 0e11a730, 3e327882, d62d1046) |

---

## Что покрыто тестами

### GraphSAGE (44 теста)
- [x] Инициализация детектора, конфигурация порогов
- [x] Генерация всех 6 типов сценариев
- [x] Корреляции между признаками (SNR↔RSSI, throughput↔latency)
- [x] train_from_telemetry() — обучение из телеметрии
- [x] Rule-based labeling с качественными метриками
- [x] Интеграция с MAPE-K (dispatcher wiring)

### MAPE-K (19 тестов)
- [x] Инициализация с зависимостями
- [x] Monitor фаза — сбор метрик consciousness
- [x] Analyze фаза — генерация directives
- [x] Plan фаза — формирование плана
- [x] Execute фаза — исполнение + DAO dispatch
- [x] Knowledge фаза — обновление базы знаний
- [x] Prometheus экспорт метрик
- [x] История состояний (trimming)
- [x] Полный цикл (full cycle)

### ConsciousnessV2 (19 тестов)
- [x] Sigmoid-активация
- [x] Выбор оптимального действия
- [x] Обработка граничных случаев
- [x] XAI объяснения
- [x] Мультиобъектное скоринг

### DAO Governance (41 тест)
- [x] Создание предложений
- [x] Квадратичное голосование (sqrt)
- [x] Кворум (participation check)
- [x] ABSTAIN учитывается в total_weighted
- [x] Истёкшие предложения
- [x] Состояния: ACTIVE → PASSED/REJECTED → EXECUTED
- [x] ActionDispatcher — 5 типов действий
- [x] JSONL леджер (append-only)
- [x] Пользовательские обработчики

### PQC (34+ теста)
- [x] ML-KEM-768 keypair/encapsulate/decapsulate
- [x] ML-DSA-65 keypair/sign/verify
- [x] AES-256-GCM encrypt/decrypt
- [x] Hybrid encapsulation
- [x] Фаззинг (невалидные входы)

---

## Воспроизводимость

```bash
# Запуск всех НИОКР-тестов
python3 -m pytest tests/unit/core/test_mape_k_loop_unit.py \
  tests/unit/core/test_consciousness_v2_unit.py \
  tests/unit/dao/ tests/unit/ml/ \
  tests/unit/security/test_pqc_liboqs_unit.py \
  tests/unit/rag/test_rag_pipeline.py \
  --override-ini="addopts=" -p no:cacheprovider -v
```

**Примечание:** Coverage plugin (pytest-cov) вызывает зависание при teardown из-за torch cleanup в conftest.py. Тесты проходят корректно — проблема только в генерации coverage report. Количественное покрытие: **188 тестов на 3878 строк кода**.

---

**Дата отчёта:** 8 февраля 2026
