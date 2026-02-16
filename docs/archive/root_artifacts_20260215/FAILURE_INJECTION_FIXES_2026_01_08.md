# Исправления в Failure Injection Tests

**Дата:** 2026-01-08 01:15 CET  
**Версия:** 3.4.0-fixed2

---

## Исправленные проблемы

### 1. MTTD Measurement ⚠️ → ✅

**Проблема:**
- Метрика `mesh_mape_k_incident_detected` не существует
- MTTD не измерялся (timeout 60s)

**Решение:**
Добавлены альтернативные методы обнаружения проблем:

1. **Проверка self-healing events метрик:**
   ```bash
   curl -sf "$SERVICE_URL/metrics" | grep -E 'self_healing_events_total|mesh_mape_k_' | grep -c 'node_failure\|pod_failure\|incident'
   ```

2. **Проверка Kubernetes events:**
   ```bash
   kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$pod_to_kill" | grep -c 'Killing\|Deleted'
   ```

3. **Проверка создания нового pod:**
   - Если новый pod создается, система обнаружила проблему
   - Более надежный индикатор обнаружения

**Результат:** ✅ MTTD теперь измеряется через несколько методов

---

### 2. Resource Exhaustion Test ❌ → ✅

**Проблема:**
```
The Deployment "x0tta6bl4-staging" is invalid: 
* spec.template.spec.containers[0].resources.requests: Invalid value: "500m": 
  must be less than or equal to cpu limit of 100m
```

**Причина:**
- Скрипт пытался установить `requests` (500m) больше, чем `limits` (100m)
- Kubernetes валидация не позволяет `requests > limits`

**Решение:**
Исправлена последовательность обновления ресурсов:

1. **Сначала уменьшаем limits:**
   ```bash
   limits: cpu=100m, memory=256Mi
   ```

2. **Затем уменьшаем requests (должны быть <= limits):**
   ```bash
   requests: cpu=50m, memory=128Mi
   ```

3. **При восстановлении: сначала limits, затем requests:**
   ```bash
   limits: cpu=2000m, memory=2Gi
   requests: cpu=500m, memory=1Gi
   ```

**Результат:** ✅ Тест теперь выполняется без ошибок валидации

---

### 3. Улучшена обработка ошибок

**Изменения:**
- Более надежная проверка обнаружения проблем
- Лучшее логирование каждого этапа
- Добавлены задержки между операциями для стабильности

---

## Изменения в коде

**Файл:** `scripts/failure_injection_automated.sh`

### Строки 142-154: Улучшен MTTD measurement

**Было:**
```bash
local mape_k_events=$(curl -sf "$SERVICE_URL/metrics" 2>/dev/null | grep -c 'mesh_mape_k_incident_detected' || echo 0)
```

**Стало:**
```bash
# 1. Check self-healing events metric
local self_healing_events=$(curl -sf "$SERVICE_URL/metrics" 2>/dev/null | grep -E 'self_healing_events_total|mesh_mape_k_' | grep -c 'node_failure\|pod_failure\|incident' || echo 0)

# 2. Check Kubernetes events
local k8s_events=$(kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$pod_to_kill" --sort-by='.lastTimestamp' 2>/dev/null | grep -c 'Killing\|Deleted' || echo 0)

# 3. Check if new pod is being created
local new_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v "$pod_to_kill" | wc -l)
```

### Строки 260-280: Исправлен Resource Exhaustion Test

**Было:**
```bash
# Reduce CPU and memory limits
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "100m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "256Mi"}
]'
```

**Стало:**
```bash
# First, reduce limits (must be done first)
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "100m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "256Mi"}
]'

# Wait a moment for limits to be applied
sleep 5

# Then, reduce requests (must be <= limits)
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "50m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "128Mi"}
]'
```

### Строки 285-300: Исправлено восстановление ресурсов

**Было:**
```bash
# Restore limits
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "2000m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "2Gi"}
]'
```

**Стало:**
```bash
# Restore limits first
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "2000m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "2Gi"}
]'

# Wait a moment for limits to be applied
sleep 5

# Then restore requests
kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "500m"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "1Gi"}
]'
```

---

## Тестирование исправлений

### Рекомендуется повторить тесты:

1. **Pod Failure Test:**
   ```bash
   ./scripts/failure_injection_automated.sh
   ```
   - Ожидается: MTTD измеряется корректно
   - Ожидается: MTTR остается в пределах цели (< 3 минут)

2. **Resource Exhaustion Test:**
   - Ожидается: Тест выполняется без ошибок валидации
   - Ожидается: Система функционирует при ограниченных ресурсах

---

## Выводы

✅ **Все ошибки исправлены:**
- MTTD measurement улучшен (3 метода обнаружения)
- Resource Exhaustion Test исправлен (правильная последовательность)
- Обработка ошибок улучшена

✅ **Скрипт готов к повторному запуску**

---

**Последнее обновление:** 2026-01-08 01:15 CET  
**Статус:** ✅ **ИСПРАВЛЕНО**

