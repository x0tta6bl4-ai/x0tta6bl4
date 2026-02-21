# Resilience Module Documentation

## Обзор

Модуль Resilience предоставляет комплексные паттерны отказоустойчивости для распределённых систем. Реализует проверенные практики построения надёжных микросервисных архитектур.

**Версия:** 2.0.0  
**Последнее обновление:** 2026-02-20  
**Статус:** Production Ready (75%)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Resilience Module Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ResilientExecutor                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │   Circuit    │  │    Retry     │  │   Timeout Pattern        │  │   │
│  │  │   Breaker    │  │   Policy     │  │   (Cascade Protection)   │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────────┐   │
│  │                         Bulkhead Layer                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │  Semaphore   │  │   Queue      │  │   Isolation Pools        │  │   │
│  │  │  Isolation   │  │   Throttle   │  │   (Per-Component)        │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └───────────────────────────────┬─────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────────────────────────▼─────────────────────────────────────┐   │
│  │                       Health Check Layer                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │    HTTP      │  │     TCP      │  │   Graceful Degradation   │  │   │
│  │  │  HealthCheck │  │  HealthCheck │  │   Manager                │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Компоненты

### 1. Circuit Breaker (Автоматический выключатель)

Защищает систему от каскадных отказов, временно блокируя запросы к нестабильному сервису.

**Состояния:**
- **CLOSED** - Нормальная работа, запросы проходят
- **OPEN** - Запросы блокируются, сервис считается недоступным
- **HALF_OPEN** - Пробные запросы для проверки восстановления

```python
from src.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState

# Создание Circuit Breaker с настройками
config = CircuitBreakerConfig(
    failure_threshold=5,      # Порог отказов для открытия
    recovery_timeout_seconds=60,  # Время до попытки восстановления
    success_threshold=2,      # Успешных запросов для закрытия
)

circuit_breaker = CircuitBreaker(config, name="api-service")

# Использование
def call_external_api():
    return circuit_breaker.call(
        lambda: requests.get("https://api.example.com/data").json()
    )

# Проверка состояния
if circuit_breaker.is_open():
    print("Сервис временно недоступен")
elif circuit_breaker.is_half_open():
    print("Сервис восстанавливается...")
```

**Конфигурация:**

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `failure_threshold` | 5 | Количество отказов для перехода в OPEN |
| `recovery_timeout_seconds` | 60 | Секунды до перехода в HALF_OPEN |
| `success_threshold` | 2 | Успешных запросов для перехода в CLOSED |

---

### 2. Retry Policy (Политика повторов)

Автоматический повтор запросов с настраиваемой стратегией backoff и jitter.

**Типы Jitter:**
- **NONE** - Без jitter
- **FULL** - Случайная задержка от 0 до delay
- **EQUAL** - Случайная задержка от delay/2 до delay
- **DECORRELATED** - AWS-style decorrelated jitter

```python
from src.resilience import RetryPolicy, RetryConfig, JitterType

# Создание политики повторов
config = RetryConfig(
    max_retries=3,
    base_delay_ms=100,
    max_delay_ms=60000,
    exponential_base=2.0,
    jitter_type=JitterType.FULL,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

retry_policy = RetryPolicy(config)

# Использование
def fetch_with_retry():
    return retry_policy.execute(
        lambda: requests.get("https://api.example.com/data").json()
    )

# Асинхронное использование
async def fetch_async():
    return await retry_policy.execute_async(
        lambda: aiohttp_get("https://api.example.com/data")
    )

# Декоратор для автоматического повтора
from src.resilience import retry

@retry(max_retries=3, base_delay_ms=100, jitter_type=JitterType.DECORRELATED)
def unreliable_operation():
    return external_service.call()
```

**Стратегии Backoff:**

```
Exponential Backoff с Full Jitter:

Attempt 1: delay = 100ms  → actual = random(0, 100)
Attempt 2: delay = 200ms  → actual = random(0, 200)
Attempt 3: delay = 400ms  → actual = random(0, 400)
Attempt 4: delay = 800ms  → actual = random(0, 800)
```

---

### 3. Timeout Pattern (Паттерн таймаута)

Защита от зависания запросов с каскадной защитой для вложенных вызовов.

```python
from src.resilience import TimeoutPattern, TimeoutConfig, TimeoutContext

# Создание timeout pattern
config = TimeoutConfig(
    default_timeout=30.0,
    connection_timeout=10.0,
    read_timeout=30.0,
    max_cascade_depth=5,
    cascade_timeout_multiplier=0.8,
    fallback_on_timeout=True,
    fallback_value=None,
)

timeout_pattern = TimeoutPattern(config)

# Использование
def call_with_timeout():
    return timeout_pattern.execute(
        lambda: slow_external_call(),
        timeout=10.0,
        operation="external_api_call",
    )

# Асинхронное использование
async def call_async():
    return await timeout_pattern.execute_async(
        lambda: async_external_call(),
        timeout=15.0,
    )

# Контекстный менеджер
with TimeoutContext(timeout=5.0, operation="database_query") as ctx:
    result = database.query("SELECT * FROM users")
    if ctx.is_expired:
        raise TimeoutError("Query took too long")
    remaining = ctx.remaining  # Оставшееся время
```

**Каскадная защита:**

```
Level 0: timeout = 30s (100%)
Level 1: timeout = 24s (80%)
Level 2: timeout = 19.2s (64%)
Level 3: timeout = 15.4s (51%)
Level 4: timeout = 12.3s (41%)
Level 5: CascadeTimeout exception
```

---

### 4. Bulkhead (Изоляция)

Ограничение параллельных запросов для предотвращения перегрузки.

```python
from src.resilience import Bulkhead, BulkheadIsolation

# Bulkhead с семафором
bulkhead = Bulkhead(max_concurrent=10, name="database_pool")

def query_database():
    with bulkhead:
        return database.execute("SELECT ...")

# Bulkhead с изоляцией и burst control
isolation = BulkheadIsolation(
    max_concurrent=20,
    burst_window_ms=50,
)

def process_request():
    return isolation.execute(
        lambda: handle_request(),
    )

# Проверка статистики
stats = isolation.get_stats()
print(f"Active: {stats['active']}/{stats['max_concurrent']}")
```

---

### 5. Health Check (Проверка здоровья)

Мониторинг здоровья сервисов с graceful degradation.

```python
from src.resilience import (
    HealthCheckEndpoint,
    HTTPHealthCheck,
    TCPHealthCheck,
    HealthStatus,
    HealthCheckConfig,
    GracefulDegradation,
)

# Создание endpoint для проверок
endpoint = HealthCheckEndpoint()

# Регистрация HTTP проверки
http_check = HTTPHealthCheck(
    name="api-service",
    url="https://api.example.com/health",
    expected_status=200,
    expected_content="OK",
)
endpoint.register_check(http_check)

# Регистрация TCP проверки
tcp_check = TCPHealthCheck(
    name="database",
    host="db.example.com",
    port=5432,
)
endpoint.register_check(tcp_check)

# Запуск проверок
results = await endpoint.run_checks()

# Получение общего статуса
status = endpoint.get_overall_status()
if status == HealthStatus.UNHEALTHY:
    alert_team()

# Получение отчёта
report = endpoint.get_health_report()
```

**Graceful Degradation:**

```python
degradation = GracefulDegradation()

# Регистрация feature с проверкой здоровья
degradation.register_feature(
    name="recommendations",
    health_check=lambda: recommendation_service.is_healthy(),
    fallback=lambda: get_popular_items(),  # Fallback функция
)

# Использование
def get_recommendations(user_id):
    if degradation.is_available("recommendations"):
        return recommendation_service.get(user_id)
    else:
        return degradation.execute(
            "recommendations",
            lambda: recommendation_service.get(user_id),
        )
```

---

### 6. ResilientExecutor (Комбинированный исполнитель)

Объединяет все паттерны в едином интерфейсе.

```python
from src.resilience import ResilientExecutor, get_resilient_executor

# Получение глобального экземпляра
executor = get_resilient_executor()

# Выполнение с защитой
def protected_call():
    return executor.execute(
        lambda: external_api.call(),
    )

# Статистика
stats = executor.get_stats()
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Circuit breaker: {stats['circuit_breaker_state']}")
```

---

## Интеграция

### С FastAPI

```python
from fastapi import FastAPI, HTTPException
from src.resilience import CircuitBreaker, RetryPolicy, TimeoutPattern

app = FastAPI()

# Инициализация
circuit_breaker = CircuitBreaker(name="external_api")
retry_policy = RetryPolicy()
timeout_pattern = TimeoutPattern()

@app.get("/api/data")
async def get_data():
    try:
        return await timeout_pattern.execute_async(
            lambda: circuit_breaker.call(
                lambda: retry_policy.execute_async(
                    lambda: fetch_external_data()
                )
            ),
            timeout=10.0,
            operation="get_data",
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

### С MAPE-K Loop

```python
from src.core.mape_k import MAPEKLoop
from src.resilience import HealthCheckEndpoint, HealthStatus

class ResilientMAPEK(MAPEKLoop):
    def __init__(self):
        super().__init__()
        self.health_endpoint = HealthCheckEndpoint()
        self._setup_health_checks()
    
    def _setup_health_checks(self):
        # Регистрация проверок для компонентов MAPE-K
        self.health_endpoint.register_check(
            HTTPHealthCheck("monitor", "http://localhost:8080/health")
        )
        self.health_endpoint.register_check(
            HTTPHealthCheck("analyzer", "http://localhost:8081/health")
        )
    
    async def execute_cycle(self):
        # Проверка здоровья перед выполнением
        status = self.health_endpoint.get_overall_status()
        
        if status == HealthStatus.UNHEALTHY:
            await self.handle_degraded_mode()
            return
        
        await super().execute_cycle()
```

---

## Конфигурация

### YAML конфигурация

```yaml
resilience:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 60
    success_threshold: 2
  
  retry:
    max_retries: 3
    base_delay_ms: 100
    max_delay_ms: 60000
    jitter_type: full
  
  timeout:
    default_timeout: 30.0
    connection_timeout: 10.0
    max_cascade_depth: 5
  
  bulkhead:
    max_concurrent: 20
    burst_window_ms: 50
  
  health_check:
    check_interval_seconds: 30
    timeout_seconds: 5
    failure_threshold: 3
```

### Переменные окружения

```bash
# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Retry
RETRY_MAX_RETRIES=3
RETRY_BASE_DELAY_MS=100
RETRY_JITTER_TYPE=full

# Timeout
TIMEOUT_DEFAULT=30
TIMEOUT_CONNECTION=10

# Bulkhead
BULKHEAD_MAX_CONCURRENT=20

# Health Check
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=5
```

---

## Метрики Prometheus

```
# Circuit Breaker
resilience_circuit_breaker_state{name="api"} 1
resilience_circuit_breaker_failures_total{name="api"} 12
resilience_circuit_breaker_successes_total{name="api"} 1234

# Retry
resilience_retry_attempts_total{operation="fetch"} 56
resilience_retry_successes_total{operation="fetch"} 45
resilience_retry_failures_total{operation="fetch"} 11

# Timeout
resilience_timeout_timeouts_total{operation="api_call"} 3
resilience_timeout_avg_latency_ms{operation="api_call"} 245

# Bulkhead
resilience_bulkhead_active{name="database"} 8
resilience_bulkhead_max_concurrent{name="database"} 20
resilience_bulkhead_rejected_total{name="database"} 5

# Health Check
resilience_health_check_status{name="api", status="healthy"} 1
resilience_health_check_latency_ms{name="api"} 45
```

---

## Best Practices

### 1. Настройка Circuit Breaker

```python
# Для быстрых операций
fast_config = CircuitBreakerConfig(
    failure_threshold=10,
    recovery_timeout_seconds=30,
)

# Для медленных операций
slow_config = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout_seconds=120,
)
```

### 2. Настройка Retry

```python
# Для идемпотентных операций
idempotent_config = RetryConfig(
    max_retries=5,
    jitter_type=JitterType.DECORRELATED,
)

# Для неидемпотентных операций
non_idempotent_config = RetryConfig(
    max_retries=0,  # Без повторов
)
```

### 3. Каскадные таймауты

```python
# Внешний вызов должен иметь больший таймаут
outer_timeout = TimeoutConfig(default_timeout=60.0)

# Внутренние вызовы - меньший
inner_timeout = TimeoutConfig(
    default_timeout=30.0,
    cascade_timeout_multiplier=0.7,
)
```

---

## Troubleshooting

### Circuit Breaker постоянно открыт

**Причина:** Высокий уровень отказов внешнего сервиса  
**Решение:** Увеличьте `failure_threshold` или проверьте здоровье сервиса

### Retry не помогает

**Причина:** Ошибки не попадают в `retryable_exceptions`  
**Решение:** Добавьте нужные типы исключений в конфигурацию

### Timeout срабатывает слишком часто

**Причина:** Недостаточный timeout для медленных операций  
**Решение:** Увеличьте `default_timeout` или используйте fallback

---

## Тестирование

```bash
# Unit тесты
pytest tests/test_resilience.py -v

# Integration тесты
pytest tests/test_resilience_integration.py -v

# Coverage
pytest tests/test_resilience.py --cov=src/resilience --cov-report=html
```

---

## Changelog

### v2.0.0 (2026-02-20)
- Добавлен Timeout Pattern с cascade protection
- Добавлен Retry с exponential backoff и jitter
- Добавлен Health Check с graceful degradation
- Улучшена интеграция с MAPE-K
- Полное покрытие тестами

### v1.0.0 (2025-12-01)
- Базовая реализация Circuit Breaker
- Простой Retry механизм
- Bulkhead изоляция
