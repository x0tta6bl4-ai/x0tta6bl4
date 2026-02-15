# Failure Injection (Chaos Engineering) Plan

**Дата:** 2026-01-07  
**Цель:** Проверить self-healing механизмы (MAPE-K, GraphSAGE) в условиях реальных отказов

---

## Текущий статус

**Pods:** 5/5  
**Версия:** 3.4.0-fixed2  
**Self-healing:** MAPE-K loop, GraphSAGE anomaly detection

---

## Тестовые сценарии

### 1. Pod Failure (Kill Pod)

**Цель:** Проверить автоматическое восстановление после падения pod

**Сценарий:**
1. Убить один pod: `kubectl delete pod <pod-name> -n x0tta6bl4-staging`
2. Наблюдать восстановление
3. Проверить, что mesh network восстановился
4. Проверить, что MAPE-K обнаружил проблему

**Ожидаемое поведение:**
- Pod автоматически пересоздается (< 1 минута)
- Mesh network восстанавливается (< 3 минуты)
- MAPE-K обнаруживает проблему (< 20 секунд)
- GraphSAGE идентифицирует root cause

**Метрики:**
- MTTR (Mean Time To Recover): < 3 minutes
- MTTD (Mean Time To Detect): < 20 seconds
- Mesh convergence time: < 2.3 seconds

**Проверка:**
```bash
# Kill pod
kubectl delete pod x0tta6bl4-staging-764d4d4968-25q6m -n x0tta6bl4-staging

# Monitor recovery
watch -n 2 'kubectl get pods -n x0tta6bl4-staging'

# Check mesh status
curl -s http://localhost:8080/mesh/status | jq .

# Check MAPE-K metrics
curl -s http://localhost:8080/metrics | grep mape_k
```

---

### 2. Network Delay Injection

**Цель:** Проверить поведение при задержках сети

**Сценарий:**
1. Добавить network delay через eBPF или tc
2. Наблюдать влияние на mesh networking
3. Проверить, что система адаптируется

**Ожидаемое поведение:**
- Система обнаруживает задержки
- MAPE-K адаптирует routing
- GraphSAGE идентифицирует проблему
- Система продолжает работать (degraded mode)

**Метод:**
```bash
# Add network delay (requires privileged pod or node access)
# Using tc (traffic control)
tc qdisc add dev eth0 root netem delay 100ms

# Or using eBPF (if available)
# ... eBPF program to inject delay
```

---

### 3. Network Partition

**Цель:** Проверить поведение при разделении сети

**Сценарий:**
1. Разделить сеть на 2 части (например, 2 pods в одной части, 3 в другой)
2. Наблюдать поведение mesh network
3. Проверить восстановление после восстановления связи

**Ожидаемое поведение:**
- Каждая часть работает независимо
- Mesh network адаптируется к разделению
- После восстановления связи - автоматическая реконвергенция

**Метод:**
```bash
# Using network policies or iptables to partition network
# This is complex in kind, might need to simulate differently
```

---

### 4. Resource Exhaustion

**Цель:** Проверить поведение при нехватке ресурсов

**Сценарий:**
1. Ограничить CPU/Memory для pods
2. Наблюдать поведение системы
3. Проверить graceful degradation

**Ожидаемое поведение:**
- Система обнаруживает нехватку ресурсов
- MAPE-K принимает меры (например, снижение нагрузки)
- GraphSAGE идентифицирует проблему
- Система работает в degraded mode

**Метод:**
```bash
# Reduce resource limits
kubectl patch deployment x0tta6bl4-staging -n x0tta6bl4-staging \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"x0tta6bl4","resources":{"limits":{"cpu":"100m","memory":"256Mi"}}}]}}}}'
```

---

### 5. Storage Failure Simulation

**Цель:** Проверить поведение при проблемах с хранилищем

**Сценарий:**
1. Симулировать проблемы с persistent storage
2. Наблюдать поведение системы
3. Проверить восстановление

**Ожидаемое поведение:**
- Система обнаруживает проблемы с storage
- MAPE-K принимает меры
- GraphSAGE идентифицирует root cause
- Система восстанавливается после исправления

---

### 6. High Load Injection

**Цель:** Проверить поведение при высокой нагрузке

**Сценарий:**
1. Создать высокую нагрузку (1000+ req/s)
2. Наблюдать поведение системы
3. Проверить, что система справляется или gracefully degrades

**Ожидаемое поведение:**
- Система обнаруживает высокую нагрузку
- MAPE-K принимает меры (например, rate limiting)
- GraphSAGE идентифицирует проблему
- Система стабилизируется

**Метод:**
```bash
# High load using Apache Bench or k6
ab -n 10000 -c 100 http://localhost:8080/health

# Or using k6
k6 run --vus 100 --duration 5m load_test.js
```

---

## Метрики для мониторинга

### MAPE-K Metrics

- `mesh_mape_k_packet_drop_rate` - должен оставаться низким
- `mesh_mape_k_route_discovery_success_rate` - должен восстановиться
- `mesh_mape_k_total_routes_known` - должен восстановиться

### GraphSAGE Metrics

- `gnn_recall_score` - должен оставаться стабильным
- Anomaly detection accuracy - должна оставаться высокой

### Recovery Metrics

- MTTR (Mean Time To Recover): < 3 minutes
- MTTD (Mean Time To Detect): < 20 seconds
- Mesh convergence time: < 2.3 seconds

---

## Критерии успеха

**После каждого теста:**
- ✅ Система обнаруживает проблему (< 20 секунд)
- ✅ MAPE-K принимает меры
- ✅ GraphSAGE идентифицирует root cause
- ✅ Система восстанавливается (< 3 минуты)
- ✅ Mesh network реконвергирует (< 2.3 секунды)
- ✅ Нет data loss
- ✅ Нет permanent failures

---

## Порядок выполнения

1. **Pod Failure** (самый простой, начинаем с него)
2. **High Load Injection** (проверяем под нагрузкой)
3. **Resource Exhaustion** (проверяем graceful degradation)
4. **Network Delay** (если доступно)
5. **Network Partition** (если доступно)
6. **Storage Failure** (если доступно)

---

## Документация результатов

Для каждого теста записывать:
- Время обнаружения проблемы (MTTD)
- Время восстановления (MTTR)
- Действия MAPE-K
- Root cause от GraphSAGE
- Финальное состояние системы

---

**Время выполнения:** ~2-4 часа (в зависимости от количества тестов)  
**Статус:** ⏳ Ready after stability test

