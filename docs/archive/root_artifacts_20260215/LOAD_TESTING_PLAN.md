# Load Testing Plan

**Дата:** 2026-01-07  
**Цель:** Проверить производительность системы под нагрузкой

---

## Текущий статус

**Pods:** 5/5 (scaling in progress)

---

## Тесты

### 1. Health Check Load Test

**Цель:** Проверить, что health endpoint выдерживает нагрузку

**Команды:**
```bash
# Используем curl в цикле для простого load test
for i in {1..100}; do
  curl -s http://localhost:8080/health > /dev/null &
done
wait

# Или используем Apache Bench (если установлен)
ab -n 1000 -c 10 http://localhost:8080/health
```

**Ожидаемый результат:** Все запросы возвращают 200 OK, latency < 100ms p95

---

### 2. Mesh API Load Test

**Цель:** Проверить mesh endpoints под нагрузкой

**Endpoints для тестирования:**
- `/mesh/status`
- `/mesh/peers`
- `/mesh/routes`

**Команды:**
```bash
# Параллельные запросы к mesh endpoints
for i in {1..50}; do
  curl -s http://localhost:8080/mesh/status > /dev/null &
  curl -s http://localhost:8080/mesh/peers > /dev/null &
done
wait
```

**Ожидаемый результат:** Все запросы успешны, нет ошибок

---

### 3. Metrics Collection Under Load

**Цель:** Проверить, что метрики собираются корректно под нагрузкой

**Команды:**
```bash
# Запустить load test и одновременно собирать метрики
curl -s http://localhost:8080/metrics | grep -E "(mesh_|mape_k_|pqc_)" > metrics_before.txt

# Запустить load
# ... load test commands ...

# Собрать метрики после
curl -s http://localhost:8080/metrics | grep -E "(mesh_|mape_k_|pqc_)" > metrics_after.txt

# Сравнить
diff metrics_before.txt metrics_after.txt
```

**Ожидаемый результат:** Метрики обновляются корректно, нет аномалий

---

### 4. Multi-Pod Load Test

**Цель:** Проверить распределение нагрузки между pods

**Команды:**
```bash
# Получить все pod IPs
POD_IPS=$(kubectl get pods -n x0tta6bl4-staging -o jsonpath='{.items[*].status.podIP}')

# Отправить запросы к каждому pod
for POD_IP in $POD_IPS; do
  for i in {1..20}; do
    kubectl exec -n x0tta6bl4-staging <pod-name> -- \
      curl -s http://${POD_IP}:8080/health > /dev/null &
  done
done
wait
```

**Ожидаемый результат:** Нагрузка распределяется равномерно между pods

---

### 5. Resource Usage Monitoring

**Цель:** Проверить использование ресурсов под нагрузкой

**Команды:**
```bash
# Мониторинг CPU и памяти
watch -n 2 'kubectl top pods -n x0tta6bl4-staging'

# Или сохранить в файл
kubectl top pods -n x0tta6bl4-staging --containers > resource_usage.txt
```

**Ожидаемый результат:** CPU < 80%, Memory < 75% на каждом pod

---

## K6 Load Test (если доступен)

**Цель:** Использовать k6 для более продвинутого load testing

**Скрипт:**
```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 10 },    // Stay at 10 users
    { duration: '30s', target: 50 },   // Ramp up to 50 users
    { duration: '1m', target: 50 },    // Stay at 50 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  const res = http.get('http://localhost:8080/health');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
```

**Запуск:**
```bash
k6 run load_test.js
```

---

## Ожидаемые результаты

- ✅ Health endpoint: 100% success rate, < 100ms p95
- ✅ Mesh API: 100% success rate, < 200ms p95
- ✅ Metrics: собираются корректно
- ✅ Resource usage: CPU < 80%, Memory < 75%
- ✅ No errors, no restarts

---

## Если что-то не работает

**Проблема:** High latency
- Проверить network policies
- Проверить resource limits
- Проверить количество pods

**Проблема:** High error rate
- Проверить логи pods
- Проверить health endpoints
- Проверить resource exhaustion

**Проблема:** Pods restarting
- Проверить resource limits
- Проверить health checks
- Проверить logs на OOM errors

---

**Время выполнения:** ~1-2 часа  
**Статус:** ⏳ Ready to start

