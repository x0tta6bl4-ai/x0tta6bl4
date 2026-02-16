# Metrics API Setup Guide

**Дата:** 2026-01-07  
**Проблема:** Metrics API not available в kind cluster  
**Влияние:** Низкое (не критично для staging, но полезно для мониторинга)

---

## Проблема

**Ошибка:** `error: Metrics API not available`

**Причина:** `metrics-server` не установлен в kind cluster

**Где используется:**
- `stability_test_monitor.sh` - строка 45: `kubectl top pods`
- `scripts/monitor_deployment.sh` - строка 87: `kubectl top pods`
- `scripts/validate_cluster.sh` - строка 76: проверка наличия metrics-server

**Влияние:**
- ⚠️ Нельзя получить CPU/Memory usage через `kubectl top pods`
- ✅ Не критично для staging тестирования
- ✅ Приложение метрики доступны через `/metrics` endpoint
- ✅ Prometheus метрики работают нормально

---

## Решение: Установка metrics-server

### Для kind cluster

```bash
# 1. Применить metrics-server manifest для kind
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 2. Для kind нужно добавить флаги (из-за self-signed certificates)
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

# 3. Подождать готовности
kubectl wait --for=condition=available --timeout=300s deployment/metrics-server -n kube-system

# 4. Проверить
kubectl top nodes
kubectl top pods -n x0tta6bl4-staging
```

### Альтернатива: Локальный manifest

Создайте файл `k8s/metrics-server-kind.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: metrics-server
  namespace: kube-system
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-server
  namespace: kube-system
  labels:
    k8s-app: metrics-server
spec:
  selector:
    matchLabels:
      k8s-app: metrics-server
  template:
    metadata:
      name: metrics-server
      labels:
        k8s-app: metrics-server
    spec:
      serviceAccountName: metrics-server
      containers:
      - name: metrics-server
        image: registry.k8s.io/metrics-server/metrics-server:v0.6.4
        args:
          - --cert-dir=/tmp
          - --secure-port=4443
          - --kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname
          - --kubelet-use-node-status-port
          - --kubelet-insecure-tls  # Для kind
        ports:
        - name: https
          containerPort: 4443
          protocol: TCP
        resources:
          requests:
            cpu: 100m
            memory: 200Mi
        volumeMounts:
        - name: tmp-dir
          mountPath: /tmp
      volumes:
      - name: tmp-dir
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: metrics-server
  namespace: kube-system
  labels:
    k8s-app: metrics-server
spec:
  selector:
    k8s-app: metrics-server
  ports:
  - port: 443
    protocol: TCP
    targetPort: https
```

Применить:
```bash
kubectl apply -f k8s/metrics-server-kind.yaml
kubectl wait --for=condition=available --timeout=300s deployment/metrics-server -n kube-system
```

---

## Проверка установки

```bash
# 1. Проверить deployment
kubectl get deployment metrics-server -n kube-system

# 2. Проверить pods
kubectl get pods -n kube-system | grep metrics-server

# 3. Проверить API
kubectl top nodes
kubectl top pods -n x0tta6bl4-staging

# 4. Проверить в скрипте
./scripts/validate_cluster.sh
```

---

## Обновление скриптов

После установки metrics-server, скрипты автоматически начнут работать:

1. **stability_test_monitor.sh** - будет показывать CPU/Memory usage
2. **monitor_deployment.sh** - будет показывать resource usage
3. **validate_cluster.sh** - будет проверять наличие metrics-server

---

## Для production

В production (EKS/GKE/AKS) metrics-server обычно установлен по умолчанию.

**EKS:**
```bash
# Проверить
kubectl get deployment metrics-server -n kube-system

# Если нет, установить через eksctl или вручную
```

**GKE:**
- Metrics server включен по умолчанию

**AKS:**
- Metrics server включен по умолчанию

---

## Альтернативные способы мониторинга

Если metrics-server недоступен, можно использовать:

### 1. Prometheus метрики (уже работает)

```bash
# CPU/Memory из приложения
curl http://localhost:8080/metrics | grep process_resident_memory_bytes

# Mesh метрики
curl http://localhost:8080/metrics | grep mesh_
```

### 2. kubectl describe

```bash
# Resource requests/limits
kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep -A 5 "Limits\|Requests"
```

### 3. cAdvisor (если доступен)

```bash
# Через node metrics
kubectl proxy --port=8001
curl http://localhost:8001/api/v1/nodes/<node-name>/proxy/metrics/cadvisor
```

---

## Рекомендации

### Для staging (текущее состояние)

**Статус:** ⚠️ **Optional** - не критично

- ✅ Приложение метрики работают через `/metrics`
- ✅ Prometheus может собирать метрики
- ⚠️ `kubectl top` не работает (но это не критично)

**Решение:** Можно оставить как есть, или установить для удобства

### Для production

**Статус:** ✅ **Рекомендуется** - установить

- ✅ Нужен для HPA (Horizontal Pod Autoscaler)
- ✅ Нужен для мониторинга resource usage
- ✅ Нужен для alerting на основе CPU/Memory

**Решение:** Установить metrics-server

---

## Быстрая установка (для kind)

```bash
# Одной командой
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml && \
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]' && \
kubectl wait --for=condition=available --timeout=300s deployment/metrics-server -n kube-system && \
echo "✅ Metrics server установлен!" && \
kubectl top nodes
```

---

## Troubleshooting

### Проблема: metrics-server не запускается

```bash
# Проверить логи
kubectl logs -n kube-system deployment/metrics-server

# Проверить события
kubectl get events -n kube-system --sort-by='.lastTimestamp' | grep metrics-server
```

### Проблема: "unable to fetch metrics"

```bash
# Проверить, что kubelet доступен
kubectl get nodes -o wide

# Проверить, что metrics-server может подключиться к kubelet
kubectl logs -n kube-system deployment/metrics-server | grep -i error
```

### Проблема: "x509: certificate signed by unknown authority" (kind)

**Решение:** Добавить флаг `--kubelet-insecure-tls` (см. инструкцию выше)

---

## Ссылки

- [Kubernetes Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
- [Kind Metrics Server Setup](https://kind.sigs.k8s.io/docs/user/quick-start/#metrics-server)
- [Kubernetes Resource Metrics](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)

---

**Последнее обновление:** 2026-01-07  
**Статус:** ⚠️ Optional для staging, ✅ Recommended для production

