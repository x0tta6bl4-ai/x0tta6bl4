# Alerting Integration Guide

**Версия:** x0tta6bl4 v3.0  
**Дата:** $(date)

---

## Обзор

Полная интеграция системы алертинга для всех компонентов x0tta6bl4. Все критические события автоматически отправляют алерты через централизованный AlertManager.

---

## Компоненты с Alerting

### 1. PQC Metrics (`src/monitoring/pqc_metrics.py`)

#### Handshake Success SLO Violation
- **Триггер:** Latency > 100ms (p95 target)
- **Severity:** WARNING
- **Alert Name:** `PQC_HANDSHAKE_SLO_VIOLATION`

#### Handshake Failure
- **Триггер:** Любая ошибка handshake
- **Severity:** CRITICAL
- **Alert Name:** `PQC_HANDSHAKE_FAILURE`

#### Fallback Enabled
- **Триггер:** PQC fallback mode активирован
- **Severity:** CRITICAL
- **Alert Name:** `PQC_FALLBACK_ENABLED`
- **TTL:** 1 час (система автоматически отключится)

#### Fallback TTL Expired
- **Триггер:** Fallback mode активен > 1 часа
- **Severity:** CRITICAL
- **Alert Name:** `PQC_FALLBACK_TTL_EXPIRED`
- **Действие:** Система должна быть отключена

#### Key Rotation Failure
- **Триггер:** Ошибка ротации ключей
- **Severity:** HIGH
- **Alert Name:** `PQC_KEY_ROTATION_FAILURE`

---

### 2. Error Handler (`src/core/error_handler.py`)

#### Critical Errors
- **Триггер:** `ErrorSeverity.CRITICAL`
- **Severity:** CRITICAL
- **Alert Name:** `ERROR_{CONTEXT}`

#### High Errors
- **Триггер:** `ErrorSeverity.HIGH`
- **Severity:** ERROR
- **Alert Name:** `ERROR_{CONTEXT}`

**Поддержка:**
- Async версия: `ErrorHandler.handle_error()`
- Sync версия: `ErrorHandler.handle_error_sync()`

---

## Конфигурация

### Environment Variables

```bash
# Prometheus Alertmanager
ALERTMANAGER_URL=http://alertmanager:9093

# Telegram
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# PagerDuty (опционально)
PAGERDUTY_INTEGRATION_KEY=your_key
```

---

## Использование

### PQC Metrics

```python
from src.monitoring.pqc_metrics import (
    record_handshake_success,
    record_handshake_failure,
    enable_fallback
)

# Success with normal latency (no alert)
record_handshake_success(0.05)  # 50ms

# Success with SLO violation (triggers warning)
record_handshake_success(0.15)  # 150ms > 100ms

# Failure (triggers critical alert)
record_handshake_failure("timeout")
```

### Error Handler

```python
from src.core.error_handler import ErrorHandler, ErrorSeverity

# Critical error (triggers alert)
await ErrorHandler.handle_error(
    ValueError("Critical failure"),
    "mesh_router.start",
    ErrorSeverity.CRITICAL
)

# High error (triggers alert)
await ErrorHandler.handle_error(
    RuntimeError("High severity error"),
    "database.connection",
    ErrorSeverity.HIGH
)

# Medium error (no alert, only logging)
await ErrorHandler.handle_error(
    ValueError("Medium error"),
    "cache.get",
    ErrorSeverity.MEDIUM
)
```

---

## Каналы уведомлений

1. **Prometheus Alertmanager** - основной канал
2. **Telegram** - для критических алертов
3. **PagerDuty** - для production инцидентов

---

## Тестирование

```bash
# Запустить тесты alerting
pytest tests/unit/monitoring/test_pqc_metrics_alerting.py
pytest tests/unit/core/test_error_handler_alerting.py
```

---

## Мониторинг

Все алерты доступны через:
- Prometheus: `http://prometheus:9090/alerts`
- Alertmanager: `http://alertmanager:9093`

---

**Последнее обновление:** $(date)


