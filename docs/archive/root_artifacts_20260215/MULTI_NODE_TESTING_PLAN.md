# Multi-Node Testing Plan

**Дата:** 2026-01-07  
**Цель:** Проверить connectivity и communication между mesh nodes

---

## Текущий статус

**Pods:**
- Pod 1: `x0tta6bl4-staging-764d4d4968-25q6m` (IP: TBD)
- Pod 2: `x0tta6bl4-staging-764d4d4968-7xpr9` (IP: TBD)

**Service:**
- ClusterIP: `10.96.1.88:8080`

---

## Тесты

### 1. Pod-to-Pod Communication

**Цель:** Проверить, что pods могут общаться друг с другом

**Команды:**
```bash
# Получить IP адреса pods
POD1_IP=$(kubectl get pod -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -o jsonpath='{.status.podIP}')
POD2_IP=$(kubectl get pod -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -o jsonpath='{.status.podIP}')

# Проверить connectivity из pod1 к pod2
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -- \
  curl -s http://${POD2_IP}:8080/health

# Проверить connectivity из pod2 к pod1
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -- \
  curl -s http://${POD1_IP}:8080/health
```

**Ожидаемый результат:** Оба запроса возвращают `200 OK`

---

### 2. Mesh Peers Discovery

**Цель:** Проверить, что nodes видят друг друга через mesh API

**Команды:**
```bash
# Проверить peers из pod1
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -- \
  curl -s http://localhost:8080/mesh/peers | python3 -m json.tool

# Проверить peers из pod2
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -- \
  curl -s http://localhost:8080/mesh/peers | python3 -m json.tool
```

**Ожидаемый результат:** Оба pods видят друг друга в списке peers

---

### 3. Mesh Status Check

**Цель:** Проверить статус mesh сети на каждом node

**Команды:**
```bash
# Статус из pod1
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -- \
  curl -s http://localhost:8080/mesh/status | python3 -m json.tool

# Статус из pod2
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -- \
  curl -s http://localhost:8080/mesh/status | python3 -m json.tool
```

**Ожидаемый результат:** Оба pods показывают активный mesh статус

---

### 4. Beacon Exchange Test

**Цель:** Проверить обмен beacon сообщениями между nodes

**Команды:**
```bash
# Отправить beacon от pod1 к pod2
POD2_IP=$(kubectl get pod -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -o jsonpath='{.status.podIP}')

kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -- \
  curl -s -X POST http://${POD2_IP}:8080/mesh/beacon \
    -H "Content-Type: application/json" \
    -d '{"node_id": "pod1", "timestamp": '$(date +%s)', "neighbors": []}'
```

**Ожидаемый результат:** Beacon успешно отправлен и получен

---

### 5. Metrics Collection

**Цель:** Проверить, что метрики собираются корректно на обоих nodes

**Команды:**
```bash
# Метрики с pod1
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-25q6m -- \
  curl -s http://localhost:8080/metrics | grep -E "(mesh|mapek|pqc)" | head -20

# Метрики с pod2
kubectl exec -n x0tta6bl4-staging x0tta6bl4-staging-764d4d4968-7xpr9 -- \
  curl -s http://localhost:8080/metrics | grep -E "(mesh|mapek|pqc)" | head -20
```

**Ожидаемый результат:** Метрики собираются на обоих pods

---

## Масштабирование до 3 nodes

**Цель:** Добавить третий pod и проверить connectivity

**Команды:**
```bash
# Увеличить replicas до 3
helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f helm/x0tta6bl4/values-staging.yaml \
  -n x0tta6bl4-staging \
  --set replicaCount=3

# Проверить, что все pods запустились
kubectl get pods -n x0tta6bl4-staging -w

# Повторить все тесты выше для 3 pods
```

---

## Ожидаемые результаты

- ✅ Pod-to-pod communication работает
- ✅ Mesh peers discovery работает
- ✅ Mesh status корректный на всех nodes
- ✅ Beacon exchange работает
- ✅ Metrics собираются на всех nodes
- ✅ 3+ nodes могут общаться друг с другом

---

## Если что-то не работает

**Проблема:** Pods не видят друг друга
- Проверить network policies
- Проверить service mesh configuration
- Проверить логи pods

**Проблема:** Mesh API не отвечает
- Проверить, что mesh компонент инициализирован
- Проверить логи приложения
- Проверить health endpoint

**Проблема:** Метрики не собираются
- Проверить Prometheus configuration
- Проверить, что metrics endpoint доступен
- Проверить service monitor (если включен)

---

**Время выполнения:** ~30-60 минут  
**Статус:** ⏳ Ready to start

