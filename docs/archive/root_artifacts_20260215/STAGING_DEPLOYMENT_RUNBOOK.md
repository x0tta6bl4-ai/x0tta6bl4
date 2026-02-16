# 🚀 Staging Deployment Runbook

**Проект:** x0tta6bl4 v3.4  
**Окружение:** Staging (kind)  
**Дата:** Jan 5-8, 2026  
**Статус:** 🟢 READY FOR DEPLOYMENT

---

## 📋 Prerequisites

### ✅ Проверка перед началом

```bash
# 1. Проверить Docker image
docker images x0tta6bl4:3.4.0

# 2. Проверить kind cluster
kind get clusters
kubectl cluster-info

# 3. Проверить Helm
helm version

# 4. Проверить контекст Kubernetes
kubectl config current-context
```

**Ожидаемый результат:**
- ✅ Image `x0tta6bl4:3.4.0` существует
- ✅ Cluster `x0tta6bl4-staging` доступен
- ✅ Helm 3.10+ установлен
- ✅ Контекст указывает на staging cluster

---

## 🐳 Step 1: Docker Image Preparation

### 1.1 Проверка Build

```bash
# Проверить, что image создан
docker images x0tta6bl4:3.4.0

# Если image не существует, запустить build
cd /mnt/AC74CC2974CBF3DC
./scripts/build_docker_image.sh 3.4.0
```

**Критерии успеха:**
- ✅ Image `x0tta6bl4:3.4.0` существует
- ✅ Image имеет правильный tag (3.4.0)
- ✅ Image имеет метаданные (version: 3.4.0)

### 1.2 Load Image в kind

```bash
# Load image в staging cluster
kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging

# Verify image loaded
docker exec -it x0tta6bl4-staging-control-plane crictl images | grep x0tta6bl4
```

**Критерии успеха:**
- ✅ Image загружен в kind cluster
- ✅ Image виден в `crictl images`

---

## ☸️ Step 2: Kubernetes Cluster Setup

### 2.1 Проверка Cluster

```bash
# Проверить существующий cluster
kind get clusters

# Если cluster не существует, создать новый
kind create cluster --name x0tta6bl4-staging --config kind-staging-config.yaml

# Проверить статус
kubectl cluster-info
kubectl get nodes
```

**Критерии успеха:**
- ✅ Cluster доступен
- ✅ Nodes в статусе Ready
- ✅ kubectl может подключиться

### 2.2 Создание Namespace

```bash
# Создать namespace для staging
kubectl create namespace x0tta6bl4-staging

# Установить namespace как default для контекста
kubectl config set-context --current --namespace=x0tta6bl4-staging

# Verify
kubectl get namespace x0tta6bl4-staging
```

**Критерии успеха:**
- ✅ Namespace создан
- ✅ Контекст обновлён
- ✅ Namespace активен

---

## 📦 Step 3: Helm Deployment

### 3.1 Подготовка Values

```bash
# Проверить values-staging.yaml
cd /mnt/AC74CC2974CBF3DC
cat helm/x0tta6bl4/values-staging.yaml

# Verify Chart.yaml
cat helm/x0tta6bl4/Chart.yaml
```

**Проверка конфигурации:**
- ✅ `image.tag: "3.4.0"` соответствует Docker image
- ✅ `replicaCount: 2` для staging
- ✅ `environment: staging` установлен
- ✅ Feature flags настроены правильно

### 3.2 Dry-Run Deployment

```bash
# Dry-run для проверки манифестов
helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f helm/x0tta6bl4/values-staging.yaml \
  -n x0tta6bl4-staging \
  --dry-run \
  --debug
```

**Критерии успеха:**
- ✅ Helm может рендерить templates
- ✅ Нет ошибок валидации
- ✅ Image tag правильный (3.4.0)
- ✅ Resources настроены правильно

### 3.3 Actual Deployment

```bash
# Deploy application
helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f helm/x0tta6bl4/values-staging.yaml \
  -n x0tta6bl4-staging \
  --wait \
  --timeout 10m

# Verify deployment
helm list -n x0tta6bl4-staging
```

**Критерии успеха:**
- ✅ Helm release создан
- ✅ Deployment запущен
- ✅ Pods в статусе Running

---

## ✅ Step 4: Verification

### 4.1 Pod Status

```bash
# Проверить pods
kubectl get pods -n x0tta6bl4-staging

# Проверить детали pod
kubectl describe pod -n x0tta6bl4-staging -l app=x0tta6bl4

# Проверить логи
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 --tail=50
```

**Ожидаемый результат:**
- ✅ 2 pods в статусе Running
- ✅ Pods готовы (READY 1/1)
- ✅ Нет ошибок в логах

### 4.2 Service Status

```bash
# Проверить services
kubectl get svc -n x0tta6bl4-staging

# Проверить endpoints
kubectl get endpoints -n x0tta6bl4-staging

# Port-forward для тестирования
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080
```

**Тест health endpoint:**
```bash
# В другом терминале
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/health
```

**Ожидаемый результат:**
- ✅ Service создан
- ✅ Endpoints указывают на pods
- ✅ Health endpoint отвечает 200 OK

### 4.3 Resource Usage

```bash
# Проверить использование ресурсов
kubectl top pods -n x0tta6bl4-staging

# Проверить events
kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp'
```

**Ожидаемый результат:**
- ✅ CPU/Memory в пределах limits
- ✅ Нет предупреждений о ресурсах
- ✅ Нет ошибок в events

---

## 🔍 Step 5: Health Checks

### 5.1 Application Health

```bash
# Health check через port-forward
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080 &

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/health
curl http://localhost:8080/api/v1/metrics
```

**Ожидаемый результат:**
- ✅ `/health` возвращает 200 OK
- ✅ `/api/v1/health` возвращает JSON с статусом
- ✅ `/api/v1/metrics` возвращает метрики

### 5.2 Component Verification

```bash
# Проверить компоненты через API
curl http://localhost:8080/api/v1/mesh/status
curl http://localhost:8080/api/v1/security/status
curl http://localhost:8080/api/v1/ai/status
```

**Ожидаемый результат:**
- ✅ Mesh network работает
- ✅ Security компоненты активны
- ✅ AI компоненты инициализированы

---

## 📊 Step 6: Monitoring Setup

### 6.1 Prometheus (если включён)

```bash
# Проверить ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4-staging

# Проверить метрики
curl http://localhost:8080/metrics
```

**Ожидаемый результат:**
- ✅ ServiceMonitor создан (если monitoring.enabled=true)
- ✅ Метрики доступны на `/metrics`

### 6.2 Logs

```bash
# Собрать логи всех pods
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 --tail=100

# Следить за логами в реальном времени
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 -f
```

**Ожидаемый результат:**
- ✅ Логи в формате JSON (если logging.format=json)
- ✅ Уровень логов INFO (если logging.level=INFO)
- ✅ Нет критических ошибок

---

## 🚨 Troubleshooting

### Проблема: Pods не запускаются

**Диагностика:**
```bash
# Проверить статус pods
kubectl get pods -n x0tta6bl4-staging

# Проверить события
kubectl describe pod -n x0tta6bl4-staging <pod-name>

# Проверить логи
kubectl logs -n x0tta6bl4-staging <pod-name>
```

**Возможные причины:**
- Image не загружен в kind → `kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging`
- Недостаточно ресурсов → проверить `kubectl top nodes`
- Ошибки в конфигурации → проверить values-staging.yaml

### Проблема: ImagePullBackOff

**Решение:**
```bash
# Убедиться, что image загружен
kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging

# Проверить pullPolicy в values-staging.yaml (должен быть IfNotPresent)
```

### Проблема: Health endpoint не отвечает

**Диагностика:**
```bash
# Проверить, что pod запущен
kubectl get pods -n x0tta6bl4-staging

# Проверить логи на ошибки
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4

# Проверить, что порт правильный (8080)
kubectl get svc -n x0tta6bl4-staging
```

---

## 📝 Post-Deployment Checklist

После успешного deployment:

- [ ] Все pods в статусе Running
- [ ] Health endpoint отвечает
- [ ] Логи не содержат критических ошибок
- [ ] Метрики собираются (если monitoring включён)
- [ ] Service доступен через port-forward
- [ ] Ресурсы в пределах limits
- [ ] Helm release создан успешно
- [ ] Namespace настроен правильно

---

## 🔄 Rollback Procedure

Если deployment не удался:

```bash
# Откатить Helm release
helm rollback x0tta6bl4-staging -n x0tta6bl4-staging

# Или удалить release
helm uninstall x0tta6bl4-staging -n x0tta6bl4-staging

# Очистить namespace (опционально)
kubectl delete namespace x0tta6bl4-staging
```

---

## 📚 Quick Reference

### Основные команды

```bash
# Deploy
helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f helm/x0tta6bl4/values-staging.yaml \
  -n x0tta6bl4-staging

# Status
helm status x0tta6bl4-staging -n x0tta6bl4-staging
kubectl get pods -n x0tta6bl4-staging

# Logs
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4 -f

# Port-forward
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080

# Delete
helm uninstall x0tta6bl4-staging -n x0tta6bl4-staging
```

---

**Версия:** 1.0  
**Создано:** Jan 5, 00:50 CET  
**Статус:** 🟢 READY FOR DEPLOYMENT  
**Следующий шаг:** Дождаться завершения Docker build, затем выполнить Step 1

