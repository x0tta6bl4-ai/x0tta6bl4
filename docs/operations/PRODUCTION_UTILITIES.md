# 🛠️ Production Utilities Guide

**Версия:** 1.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Обзор

Production utilities для проверки и управления новыми компонентами, добавленными в Q1 2026.

---

## 🔒 Zero Trust Enforcement

### `check_zero_trust_status.py`

Проверка статуса Zero Trust enforcement.

**Использование:**
```bash
# Общий статус
python3 scripts/check_zero_trust_status.py

# Детальная информация
python3 scripts/check_zero_trust_status.py --detailed

# Проверка конкретного peer
python3 scripts/check_zero_trust_status.py --peer spiffe://x0tta6bl4.mesh/workload/api

# JSON вывод
python3 scripts/check_zero_trust_status.py --json
```

**Пример вывода:**
```
============================================================
Zero Trust Enforcement Status
============================================================
Total Requests: 1000
Allowed: 950 (95.0%)
Denied: 50 (5.0%)
Isolated: 10 (1.0%)
Tracked Peers: 25
```

---

## 🗳️ Raft Consensus

### `check_raft_status.py`

Проверка статуса Raft consensus.

**Использование:**
```bash
# Статус узла
python3 scripts/check_raft_status.py --node-id node-1

# С указанием peers
python3 scripts/check_raft_status.py --node-id node-1 --peers node-2 node-3

# С custom storage path
python3 scripts/check_raft_status.py --node-id node-1 --storage-path /custom/path

# JSON вывод
python3 scripts/check_raft_status.py --json
```

**Пример вывода:**
```
============================================================
Raft Consensus Status
============================================================
Node ID: node-1
State: 👑 LEADER
Term: 5
Commit Index: 100
Last Applied: 100
Log Length: 101
Peers: node-2, node-3

============================================================
Persistent Storage
============================================================
State File: /var/lib/x0tta6bl4/raft/node-1/raft_state.json (✅ EXISTS)
Log File: /var/lib/x0tta6bl4/raft/node-1/raft_log.json (✅ EXISTS)
Saved Term: 5
Voted For: node-1
```

---

## 🔄 CRDT Sync

### `check_crdt_sync_status.py`

Проверка статуса CRDT синхронизации.

**Использование:**
```bash
# Статус синхронизации
python3 scripts/check_crdt_sync_status.py --node-id node-1

# JSON вывод
python3 scripts/check_crdt_sync_status.py --json
```

**Пример вывода:**
```
============================================================
CRDT Sync Status
============================================================
Node ID: node-1
Total Syncs: 500
Successful Syncs: 495
Failed Syncs: 5
Success Rate: 99.0%
Avg Sync Duration: 12.34ms
Bytes Sent: 1,234,567
Bytes Received: 987,654
Conflicts Resolved: 3

============================================================
CRDT State
============================================================
shared-key: value-1
counter: 42
```

---

## 🔧 Recovery Actions

### `test_recovery_actions.py`

Тестирование recovery actions.

**Использование:**
```bash
# Список доступных действий
python3 scripts/test_recovery_actions.py --list-actions

# Перезапуск сервиса
python3 scripts/test_recovery_actions.py \
  --action "Restart service" \
  --service test-service \
  --namespace default

# Масштабирование
python3 scripts/test_recovery_actions.py \
  --action "Scale up" \
  --deployment test-deployment \
  --replicas 5 \
  --namespace default

# Переключение маршрута
python3 scripts/test_recovery_actions.py \
  --action "Switch route" \
  --old-route route-1 \
  --new-route route-2

# Очистка кэша
python3 scripts/test_recovery_actions.py \
  --action "Clear cache" \
  --service test-service \
  --cache-type all

# Failover
python3 scripts/test_recovery_actions.py \
  --action "Failover" \
  --service test-service \
  --primary-region us-east-1 \
  --fallback-region eu-west-1

# Карантин узла
python3 scripts/test_recovery_actions.py \
  --action "Quarantine node" \
  --node-id problematic-node
```

**Доступные действия:**
1. **Restart service** - Перезапуск Kubernetes сервиса
2. **Switch route** - Переключение сетевого маршрута
3. **Clear cache** - Очистка кэша сервиса
4. **Scale up** - Масштабирование deployment
5. **Failover** - Failover между регионами
6. **Quarantine node** - Изоляция проблемного узла

---

## 🔄 Интеграция с Production Toolkit

Все утилиты можно интегрировать в `production_toolkit.sh`:

```bash
# Добавить в production_toolkit.sh
case "$TOOL" in
    zero-trust)
        echo "🔒 Zero Trust Status"
        python3 scripts/check_zero_trust_status.py "${@:2}"
        ;;
    
    raft)
        echo "🗳️ Raft Status"
        python3 scripts/check_raft_status.py "${@:2}"
        ;;
    
    crdt)
        echo "🔄 CRDT Sync Status"
        python3 scripts/check_crdt_sync_status.py "${@:2}"
        ;;
    
    recovery)
        echo "🔧 Recovery Actions"
        python3 scripts/test_recovery_actions.py "${@:2}"
        ;;
esac
```

**Использование:**
```bash
bash scripts/production_toolkit.sh zero-trust
bash scripts/production_toolkit.sh raft --node-id node-1
bash scripts/production_toolkit.sh crdt --node-id node-1
bash scripts/production_toolkit.sh recovery --list-actions
```

---

## 📊 Мониторинг

Все утилиты поддерживают JSON вывод для интеграции с мониторингом:

```bash
# Сбор метрик для Prometheus
python3 scripts/check_zero_trust_status.py --json | \
  jq -r '.allow_rate * 100' | \
  promtool textfile-exporter zero_trust_allow_rate.prom

# Сбор метрик Raft
python3 scripts/check_raft_status.py --json | \
  jq -r '.term' | \
  promtool textfile-exporter raft_term.prom
```

---

## ✅ Проверка работоспособности

```bash
# Проверить все компоненты
python3 scripts/check_zero_trust_status.py && \
python3 scripts/check_raft_status.py --node-id node-1 && \
python3 scripts/check_crdt_sync_status.py --node-id node-1 && \
python3 scripts/test_recovery_actions.py --list-actions

echo "✅ Все production utilities работают"
```

---

**Последнее обновление:** 2026-01-XX  
**Версия:** 1.0  
**Статус:** ✅ Production-ready

