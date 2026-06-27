# Спецификация SLA для x0tta6bl4

## Production Service Level Agreement (SLA)

**Статус**: 📋 **СПЕЦИФИКАЦИЯ**  
**Дата**: 2026-01-13  
**Целевая версия**: v1.0 production  
**Масштаб**: 1000+ узлов в mesh

---

## Исполнительное резюме

Данный документ определяет Service Level Agreements (SLA) для production-развёртывания x0tta6bl4. SLA охватывают критические метрики производительности, доступности и надёжности во всех слоях системы.

### Ключевые SLA Метрики
✅ **Доступность**: 99.99% uptime  
✅ **Задержка (p99)**: < 100ms для beacon processing  
✅ **Throughput**: 100k+ beacons/sec  
✅ **Data Loss**: 0 потерь при контролируемых сбоях  
✅ **Recovery Time**: < 5 секунд после failure

---

## Слой 1: Mesh Network SLA

### 1.1 Обработка Beacon

**Метрика**: Latency для обработки beacon сообщения

```yaml
SLA Targets:
  p50:  5ms     (медиана)
  p95:  25ms    (95-й перцентиль)
  p99:  100ms   (99-й перцентиль)
  p100: 500ms   (максимум)

Failure Threshold: p99 > 150ms (3 consecutive measurements)

Measurement:
  - Начало: Получение beacon сообщения
  - Конец: Завершение валидации и синхронизации
  - Фреквенция: Каждое beacon (100% sampling)
```

**Согласованность**: 
- ✅ 100 узлов: p99 < 10ms
- ✅ 500 узлов: p99 < 50ms  
- ✅ 1000 узлов: p99 < 100ms
- ✅ 2000 узлов: p99 < 200ms

**Нарушение SLA**: Если p99 latency превышает 150ms в течение 5 минут.

### 1.2 Пропускная способность Beacon

**Метрика**: Throughput beacon сообщений в секунду

```yaml
SLA Targets:
  Minimum:   100,000 beacons/sec (100 узлов)
  Sustained: 50,000 beacons/sec (1000 узлов)
  Burst:     500,000 beacons/sec (spike tolerance)

Measurement:
  - Период: 60 секунд
  - Фреквенция: Каждую минуту
  - Метод: Счёт успешно обработанных beacon сообщений
```

**Нарушение SLA**: Если throughput < minimum на протяжении 10 минут.

### 1.3 Доступность Mesh Сети

**Метрика**: Процент времени, когда mesh сеть полностью функциональна

```yaml
Target Availability: 99.99%
  - Допустимое простое время: 43.2 секунды в день
  - Допустимое простое время: 5.26 минут в неделю
  - Допустимое простое время: 21.6 минут в месяц

Definition of Downtime:
  - Полная потеря связи между зонами (partition)
  - 50%+ узлов не могут обмениваться сообщениями
  - Beacon latency p99 > 500ms (> 5 минут)

Exclusions (не считаются downtime):
  - Плановое обслуживание (с предварительным уведомлением 24 часа)
  - Сбои, вызванные внешними сервисами
  - DDoS атаки (вне scope security SLA)
```

### 1.4 Synchronization Accuracy

**Метрика**: Точность синхронизации slot между узлами

```yaml
SLA Target: ≤ 1% узлов с drift > 100ms
  - Измеряется каждые 10 секунд
  - Допустимое отклонение: 100ms от leader узла

Definition:
  - Leader: Узел с наиболее актуальным beacon
  - Drift: |узел_timestamp - leader_timestamp|

Measurement Window: 5 минут для определения нарушения
```

---

## Слой 2: PQC (Post-Quantum Cryptography) SLA

### 2.1 Производительность PQC Операций

**Метрика**: Latency для криптографических операций

```yaml
ML-KEM-768 (Encapsulation):
  p50:  0.5ms
  p95:  1.0ms
  p99:  2.0ms
  Target: 100% операций < 5ms

ML-DSA-65 (Signature):
  p50:  1.0ms
  p95:  2.0ms
  p99:  5.0ms
  Target: 100% операций < 10ms

Verification:
  p50:  0.5ms
  p95:  1.0ms
  p99:  2.0ms
  Target: 100% операций < 5ms

Measurement:
  - Период: Каждая операция
  - Фреквенция: 100% sampling
  - Инструмент: Performance timer (microsecond precision)
```

### 2.2 Пропускная способность PQC

**Метрика**: Количество операций в секунду

```yaml
Target Throughput:
  Signatures:   1,000+ ops/sec
  Verifications: 1,000+ ops/sec
  KEM Operations: 1,000+ ops/sec

Sustained Load:
  - Minimum sustained: 500 ops/sec per operation type
  - Burst capacity: 5,000+ ops/sec
  
Measurement:
  - Фреквенция: Каждую минуту
  - Период: 60-секундное окно
```

### 2.3 Надёжность Crypto Operations

**Метрика**: Success rate криптографических операций

```yaml
Target Success Rate: 99.99% (< 1 failure на 10,000 операций)

Failure Categories:
  - Key generation failures
  - Encapsulation failures  
  - Decapsulation failures
  - Signature generation failures
  - Signature verification failures

Measurement:
  - Период: 10,000 операций
  - Метод: Счёт успешных операций / всех операций
```

---

## Слой 3: SPIFFE Identity SLA

### 3.1 SVID Issuance Latency

**Метрика**: Время выдачи новой SVID identity

```yaml
SLA Target:
  p50:  100ms
  p95:  500ms
  p99:  1000ms (1 second)
  p100: < 5000ms (5 seconds)

Definition:
  - Начало: Запрос SVID от узла
  - Конец: Получение и валидация signed SVID

Measurement:
  - Фреквенция: 100% из новых identities
  - Инструмент: Agent timestamp + controller timestamp
```

**Нарушение SLA**: p99 > 2000ms в течение 5 минут.

### 3.2 SVID Rotation Success

**Метрика**: Успешное обновление identity

```yaml
Target Success Rate: 99.99%
  - < 1 failure на 10,000 rotations

Rotation Schedule:
  - Базовый интервал: 24 часа
  - Под нагрузкой: 1 час (ускоренная ротация)
  - Emergency rotation: < 1 minute

Measurement:
  - Период: 1000 rotations
  - Метод: Счёт успешных / всех rotations
```

### 3.3 Identity Availability

**Метрика**: Доступность identity service для всех узлов

```yaml
Target Availability: 99.99%
  - Допустимое простое: 43.2 сек/день

Definition of Unavailability:
  - Identity service не доступен (connection timeout)
  - > 5% узлов не могут получить новую SVID
  - SVID validation failures > 1% от попыток

Measurement:
  - Фреквенция: Каждую минуту
  - Метод: Health check к identity service
```

### 3.4 Attestation Success Rate

**Метрика**: Success rate для attestation процесса

```yaml
Target Success Rate: 99.95%
  - Допустимые failures: < 50 на 100,000 attestations

Types of Attestation:
  - Initial attestation (новый узел)
  - Re-attestation (периодическая проверка)
  - Emergency attestation (при изменении состояния)

Measurement:
  - Фреквенция: Каждый attestation
  - Период: 10,000 попыток для определения тренда
```

---

## Слой 4: Federated Learning SLA

### 4.1 Aggregation Latency

**Метрика**: Время агрегации model updates

```yaml
Batch Async Aggregation (1000 nodes):
  p50:  50ms
  p95:  150ms
  p99:  300ms
  Max:  < 5000ms (5 seconds)

Hierarchical Aggregation (10 zones):
  Level 1 (per zone): < 100ms
  Level 2 (central):  < 200ms
  Total round time:   < 6 seconds

Streaming Aggregation:
  Per-update latency: < 100ms
  Continuous (no rounds)

Measurement:
  - Период: Каждый training round
  - Метод: Timestamp from model distribution to aggregation completion
```

### 4.2 Convergence SLA

**Метрика**: Количество rounds для convergence

```yaml
Target Convergence:
  - Типичная сходимость: 100-200 rounds
  - Максимальная сходимость: 500 rounds
  - Failure detection: Если loss не улучшается за 50 rounds

Definition of Convergence:
  - Validation loss улучшается < 0.1% за 10 rounds
  - Gradient norm < threshold (0.01)
  - Accuracy plateau (improvement < 0.1%)

Measurement:
  - Фреквенция: Каждый round
  - Окно: 10-round sliding window
```

### 4.3 Byzantine Tolerance

**Метрика**: Максимальный процент malicious узлов

```yaml
Target Tolerance: ≥ 30% Byzantine nodes
  - System достигает convergence даже с 30% attacks
  - Detection accuracy: > 95%

Attack Types Handled:
  - Corrupted gradients (targeted poisoning)
  - Invalid updates (random noise)
  - Coordinated attacks (multi-node collusion)

Measurement:
  - Test: Inject N% Byzantine nodes
  - Verify: Convergence still achieved
  - Verify: Malicious nodes detected and isolated
```

### 4.4 Update Loss

**Метрика**: Процент потерь model updates

```yaml
Target Data Loss: 0% under normal conditions
  - Все updates должны быть обработаны или явно rejected
  - No silent data loss

Under Network Failures:
  - Straggler handling: Updates may timeout (acceptable)
  - Timeout threshold: 60 seconds
  - Measurement: Updates received / updates sent

Measurement:
  - Фреквенция: Каждый training round
  - Метод: Счёт received updates vs sent updates
```

---

## Слой 5: System Resource SLA

### 5.1 CPU Utilization

**Метрика**: CPU usage под production load

```yaml
Per-Node Target (1000-node cluster):
  Normal state:     10-30% CPU
  Peak load:        40-60% CPU
  Maximum allowed:  80% CPU (threshold for alert)

Sustained Load Window: 5 minutes
  - Если CPU > 80% > 5 min → WARNING alert
  - Если CPU > 95% > 2 min → CRITICAL alert

Measurement:
  - Фреквенция: Каждую секунду
  - Инструмент: cgroup metrics + Prometheus
```

### 5.2 Memory Utilization

**Метрика**: Memory usage per node

```yaml
Per-Node Target:
  Minimum free:  20% (warning if < 25%)
  Critical:      < 10% free (trigger OOM prevention)

Memory Breakdown (1000-node, per node):
  Base system:   500 MB
  Mesh network:  200 MB (scales with node count)
  PQC keys:      100 MB
  FL training:   200-500 MB (depends on model size)
  Cache/buffers: 200 MB
  Total:         ~1.2 GB typical

Measurement:
  - Фреквенция: Каждую минуту
  - Инструмент: /proc/meminfo + Docker stats
```

### 5.3 Network Bandwidth

**Метрика**: Сетевая пропускная способность

```yaml
Per-Node Targets (1000-node cluster):
  Beacons:        5-10 Mbps (100 beacons/sec * ~10KB each)
  FL updates:     20-50 Mbps (depends on model size)
  Identity ops:   1-2 Mbps (SVID rotations, attestation)
  Control plane:  1-5 Mbps (management traffic)
  Total:          ~30-70 Mbps per node (sustained)

Burst tolerance:  500+ Mbps (temporary spikes)
Network timeout:  > 10 seconds packet loss = failure

Measurement:
  - Фреквенция: Каждую минуту
  - Инструмент: tc (traffic control) + iptables
  - Direction: Inbound + outbound (separate)
```

### 5.4 Disk I/O (if applicable)

**Метрика**: Disk операции для persistence

```yaml
Per-Node Targets:
  Beacon log writes:  1000+ ops/sec
  State snapshots:    10-100 MB/sec (during snapshot)
  Cache flush:        100-500 MB/sec (periodic)

Latency:
  Write latency p99:  < 10ms
  Read latency p99:   < 5ms

Measurement:
  - Фреквенция: Каждую минуту
  - Инструмент: iostat + block device metrics
```

---

## Нарушения SLA и Компенсации

### Уровни Нарушений

```yaml
Severity 1 - CRITICAL (≤ 99.9% uptime):
  - Compensation: 5% credit за месяц
  - Action: Immediate incident response
  - Target resolution: < 1 hour

Severity 2 - HIGH (99.9% - 99.95% uptime):
  - Compensation: 2% credit за месяц
  - Action: Urgent escalation
  - Target resolution: < 4 hours

Severity 3 - MEDIUM (99.95% - 99.99% uptime):
  - Compensation: 1% credit за месяц
  - Action: Standard incident process
  - Target resolution: < 24 hours

Severity 4 - LOW (> 99.99%):
  - Compensation: None
  - Action: Monitoring and logging
  - Target resolution: < 7 days
```

### Исключения из SLA

Следующие события **не** являются нарушениями SLA:

1. **Плановое обслуживание**
   - ≤ 2 часа в месяц
   - Требуется предварительное уведомление 24 часа
   - Можно на выходных

2. **Внешние сбои**
   - Сбой интернет-провайдера
   - Проблемы с DNS
   - Проблемы с облачной инфраструктурой

3. **Пользовательские ошибки**
   - Неправильная конфигурация
   - Превышение лимитов ресурсов
   - Неправильное использование API

4. **DDoS/Security атаки**
   - Покрывается отдельным Security SLA
   - Best-effort mitigation

5. **Force Majeure**
   - Стихийные бедствия
   - Политические события
   - Чрезвычайные ситуации

---

## Мониторинг и Отчётность

### Инструменты Мониторинга

**Prometheus**: Сбор метрик
- Фреквенция scrape: 15 секунд
- Retention: 90 дней

**AlertManager**: Управление алертами
- Deduplicate: 5 минут
- Group wait: 10 секунд
- Repeat: 4 часа

**Grafana**: Визуализация и dashboards
- Auto-refresh: 30 секунд
- Time range: 24 часа (по умолчанию)

**ELK Stack**: Логирование
- Сбор: Real-time
- Retention: 30 дней
- Indexing: 1 индекс в день

### Отчётность

**Ежедневно**:
- SLA status dashboard
- Alert summary
- Top performance issues

**Еженедельно**:
- SLA compliance report
- Trend analysis
- Recommendations

**Ежемесячно**:
- Полный SLA report
- Compensation calculation (если нужно)
- Planning для next month

---

## Пересмотр и Обновление SLA

**Пересмотр**: Квартально
- Анализ фактических метрик
- Обновление целевых показателей
- Обновление thresholds на основе опыта

**Версионирование**:
- v1.0: Initial SLA (January 2026)
- v1.1: Updates based on 1-month production data (February 2026)
- v2.0: Major revision after 6 months (July 2026)

---

## Приложение A: Формулы Расчёта

### Uptime Percentage
```
Uptime % = ((Total Minutes - Downtime Minutes) / Total Minutes) × 100
```

### Percentile Calculation
```
P99 = Sort all values, take value at 99th percentile position
Index = ceil(n × 0.99) where n = total count
```

### Request Success Rate
```
Success % = (Successful Requests / Total Requests) × 100
```

### Availability
```
Availability = Uptime % (if > 99.99%)
```

---

## Статус Документа

**Версия**: v1.0  
**Статус**: ACTIVE  
**Последнее обновление**: 2026-01-13  
**Следующий пересмотр**: 2026-04-13
