# ✅ Staging Deployment Checklist

**Дата создания:** 2026-01-04  
**K8s Platform:** kind (local)  
**Версия:** x0tta6bl4 v3.4.0  
**Статус:** 🟢 READY TO START

---

## 📋 Prerequisites Check

### ✅ Инструменты
- [x] **kind** установлен (версия 0.20.0)
- [x] **kubectl** установлен (версия v1.34.3)
- [x] **helm** установлен (версия v4.0.4)
- [x] **Docker** установлен (версия 29.1.3)
- [x] **Ресурсы:**
  - Память: 6.5Gi доступно ✅
  - Диск: 6.6G свободно ⚠️ (94% занято, но достаточно для staging)

### ⚠️ Предупреждения
- Диск заполнен на 94% - рекомендуется освободить место перед deployment
- Рекомендуется иметь минимум 10GB свободного места для staging

---

## 🚀 Phase 1: Cluster Setup (Jan 8-9)

### Step 1.1: Проверка существующего кластера
- [ ] Проверить существующие кластеры: `kind get clusters`
- [ ] Проверить контекст: `kubectl config current-context`
- [ ] Решить: использовать существующий `x0tta6bl4-staging` или создать новый

### Step 1.2: Создание/Настройка кластера
**Вариант A: Использовать существующий кластер**
```bash
# Переключиться на существующий staging cluster
kubectl config use-context kind-x0tta6bl4-staging

# Проверить статус
kubectl cluster-info
kubectl get nodes
kubectl get pods -A
```

**Вариант B: Создать новый кластер (если нужен чистый)**
```bash
# Создать новый staging cluster
kind create cluster --name x0tta6bl4-staging-deploy --config kind-staging-config.yaml

# Проверить статус
kubectl cluster-info
kubectl get nodes
```

### Step 1.3: Создание namespace
- [ ] Создать namespace для staging:
  ```bash
  kubectl create namespace x0tta6bl4-staging
  kubectl config set-context --current --namespace=x0tta6bl4-staging
  ```

### Step 1.4: Проверка кластера
- [ ] Проверить nodes: `kubectl get nodes`
- [ ] Проверить pods: `kubectl get pods -A`
- [ ] Проверить services: `kubectl get svc -A`
- [ ] Проверить storage: `kubectl get storageclass`

**Критерии успеха:**
- ✅ Cluster доступен и отвечает
- ✅ Nodes в статусе Ready
- ✅ Namespace создан

---

## 🐳 Phase 2: Docker Images (Jan 8-9)

### Step 2.1: Build Docker Image
- [ ] Проверить Dockerfile: `cat Dockerfile | head -20`
- [ ] Build image:
  ```bash
  docker build -t x0tta6bl4:3.4.0 -f Dockerfile .
  docker tag x0tta6bl4:3.4.0 x0tta6bl4:latest
  ```
- [ ] Проверить image: `docker images | grep x0tta6bl4`

### Step 2.2: Load Image в kind
- [ ] Load image в kind cluster:
  ```bash
  kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging
  # или для нового кластера:
  kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging-deploy
  ```
- [ ] Проверить, что image загружен: `docker exec -it <kind-container> crictl images | grep x0tta6bl4`

**Критерии успеха:**
- ✅ Docker image собран успешно
- ✅ Image загружен в kind cluster

---

## 📦 Phase 3: Helm Deployment (Jan 8-9)

### Step 3.1: Проверка Helm Charts
- [ ] Проверить наличие Helm chart: `ls -la helm/x0tta6bl4/`
- [ ] Проверить Chart.yaml: `cat helm/x0tta6bl4/Chart.yaml`
- [ ] Проверить values.yaml: `cat helm/x0tta6bl4/values.yaml | head -30`

### Step 3.2: Создание values-staging.yaml (если нужно)
- [ ] Создать/проверить `helm/x0tta6bl4/values-staging.yaml`:
  ```yaml
  environment: staging
  image:
    repository: x0tta6bl4
    tag: "3.4.0"
  replicaCount: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 2Gi
  ```

### Step 3.3: Deploy через Helm
- [ ] Deploy application:
  ```bash
  helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
    --namespace x0tta6bl4-staging \
    --create-namespace \
    --set image.tag=3.4.0 \
    --set environment=staging \
    -f helm/x0tta6bl4/values-staging.yaml \
    --wait \
    --timeout 10m
  ```

### Step 3.4: Проверка Deployment
- [ ] Проверить pods: `kubectl get pods -n x0tta6bl4-staging`
- [ ] Проверить services: `kubectl get svc -n x0tta6bl4-staging`
- [ ] Проверить deployment: `kubectl get deployment -n x0tta6bl4-staging`
- [ ] Проверить logs: `kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 --tail=50`

**Критерии успеха:**
- ✅ Все pods в статусе Running
- ✅ Services созданы и доступны
- ✅ Нет ошибок в логах

---

## 🏥 Phase 4: Health Checks (Jan 8-9)

### Step 4.1: Проверка Health Endpoints
- [ ] Port-forward к service:
  ```bash
  kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080
  ```
- [ ] Проверить health endpoint:
  ```bash
  curl http://localhost:8080/health
  curl http://localhost:8080/health/dependencies
  ```
- [ ] Проверить metrics endpoint:
  ```bash
  curl http://localhost:8080/metrics | head -20
  ```

### Step 4.2: Проверка компонентов Layer 1-6
- [ ] **Layer 1: Mesh Network**
  - [ ] Проверить beacon signaling
  - [ ] Проверить routing (GraphSAGE)
  - [ ] Проверить anomaly detection

- [ ] **Layer 2: Security**
  - [ ] Проверить PQC handshake
  - [ ] Проверить SPIFFE/SPIRE (если настроено)
  - [ ] Проверить mTLS

- [ ] **Layer 3: Self-Healing**
  - [ ] Проверить MAPE-K циклы
  - [ ] Проверить recovery actions

- [ ] **Layer 4: Distributed Data**
  - [ ] Проверить CRDT sync
  - [ ] Проверить Slot-Sync

- [ ] **Layer 5: AI/ML**
  - [ ] Проверить GraphSAGE inference
  - [ ] Проверить RAG pipeline

- [ ] **Layer 6: Hybrid Search**
  - [ ] Проверить BM25 + Vector search

**Критерии успеха:**
- ✅ Health endpoints отвечают 200 OK
- ✅ Все компоненты Layer 1-6 инициализированы
- ✅ Нет критических ошибок

---

## 📊 Phase 5: Monitoring Setup (Jan 10-11)

### Step 5.1: Prometheus Setup
- [ ] Добавить Prometheus Helm repo:
  ```bash
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  helm repo update
  ```
- [ ] Deploy Prometheus:
  ```bash
  helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    --set prometheus.prometheusSpec.retention=7d
  ```
- [ ] Проверить Prometheus:
  ```bash
  kubectl get pods -n monitoring
  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
  # Открыть http://localhost:9090
  ```

### Step 5.2: ServiceMonitor Configuration
- [ ] Создать ServiceMonitor для x0tta6bl4:
  ```yaml
  apiVersion: monitoring.coreos.com/v1
  kind: ServiceMonitor
  metadata:
    name: x0tta6bl4-staging
    namespace: x0tta6bl4-staging
  spec:
    selector:
      matchLabels:
        app: x0tta6bl4
    endpoints:
    - port: http
      path: /metrics
  ```
- [ ] Применить ServiceMonitor: `kubectl apply -f servicemonitor.yaml`
- [ ] Проверить в Prometheus UI, что targets обнаружены

### Step 5.3: Grafana Setup
- [ ] Port-forward к Grafana:
  ```bash
  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
  # Открыть http://localhost:3000
  # Логин: admin / admin (изменить при первом входе)
  ```
- [ ] Создать dashboards:
  - [ ] System metrics (CPU, Memory, Load)
  - [ ] Application metrics (PQC, Anomaly, GraphSAGE)
  - [ ] Network metrics (Mesh, Latency, Throughput)
  - [ ] Health checks dashboard

**Критерии успеха:**
- ✅ Prometheus собирает метрики
- ✅ Grafana dashboards отображают данные
- ✅ Alerts настроены (если нужно)

---

## 🔧 Phase 6: Troubleshooting

### Common Issues
- [ ] **Pods не запускаются:**
  - Проверить logs: `kubectl logs -n x0tta6bl4-staging <pod-name>`
  - Проверить events: `kubectl describe pod -n x0tta6bl4-staging <pod-name>`
  - Проверить ресурсы: `kubectl top pods -n x0tta6bl4-staging`

- [ ] **Image не найден:**
  - Проверить, что image загружен: `kind load docker-image x0tta6bl4:3.4.0 --name <cluster-name>`
  - Проверить imagePullPolicy в values.yaml

- [ ] **Services не доступны:**
  - Проверить service: `kubectl describe svc -n x0tta6bl4-staging <service-name>`
  - Проверить endpoints: `kubectl get endpoints -n x0tta6bl4-staging`

- [ ] **Health checks fail:**
  - Проверить health endpoint напрямую: `curl http://localhost:8080/health`
  - Проверить зависимости (database, redis, etc.)

---

## ✅ Final Verification

### Pre-Production Checklist
- [ ] Все pods в статусе Running
- [ ] Health endpoints отвечают 200 OK
- [ ] Metrics собираются в Prometheus
- [ ] Grafana dashboards работают
- [ ] Нет критических ошибок в логах
- [ ] Все компоненты Layer 1-6 проверены
- [ ] Smoke tests пройдены

### Documentation
- [ ] Обновить CONTINUITY.md с результатами deployment
- [ ] Создать deployment report
- [ ] Задокументировать известные issues (если есть)

---

**Версия:** 1.0  
**Создано:** Jan 4, 23:50 CET  
**Статус:** 🟢 READY TO USE

