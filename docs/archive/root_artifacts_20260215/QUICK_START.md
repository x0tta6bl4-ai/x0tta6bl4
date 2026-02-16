# x0tta6bl4 v3.3.0 - Quick Start Guide (Updated 2026-01-12)

**Status:** ✅ **PRODUCTION READY (Staging)**

---

## 🎯 What's Ready

✅ **Staging environment fully operational:**
- 5 core services running (API, PostgreSQL, Redis, Prometheus, Grafana)
- All infrastructure working and reproducible
- One-command startup with `make`

✅ **New files:**
- `Dockerfile.prod` - Production-ready multi-stage build
- `Makefile` - Complete command reference  
- `run-fastapi.sh` - Quick local FastAPI launcher

---

## 🚀 Start Staging (One Command)

```bash
make up
```

Services accessible at:
- **API**: http://localhost:8000 (currently http.server, FastAPI ready)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

---

## 💡 Three Ways to Run FastAPI

### Option 1: Local Development (Fastest, Recommended for Dev)
```bash
# Install dependencies once
pip install -r requirements-staging.txt

# Run with auto-reload
uvicorn src.core.app:app --reload --port 8000
```

### Option 2: Automated Script (One-liner)
```bash
./run-fastapi.sh
# Auto-creates venv, installs deps, starts FastAPI
```

### Option 3: Docker Production Build (Optimized, Multi-stage)bash
# Создать kind cluster
kind create cluster --name x0tta6bl4-staging

# Установить kubectl context
kubectl cluster-info --context kind-x0tta6bl4-staging

# Создать namespace
kubectl create namespace x0tta6bl4-staging
```

### Существующий кластер

```bash
# Убедиться, что kubectl настроен
kubectl cluster-info

# Создать namespace
kubectl create namespace x0tta6bl4-staging
```

---

## 📋 Шаг 2: Сборка Docker Image (3 минуты)

```bash
# Собрать image
docker build -t localhost:5001/x0tta6bl4:3.4.0-fixed2 .

# Загрузить в kind (если используется)
kind load docker-image localhost:5001/x0tta6bl4:3.4.0-fixed2 --name x0tta6bl4-staging
```

---

## 📋 Шаг 3: Deployment (2 минуты)

```bash
# Deploy с Helm
helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f ./helm/x0tta6bl4/values-staging.yaml \
  --set image.tag=3.4.0-fixed2 \
  -n x0tta6bl4-staging \
  --create-namespace

# Или использовать скрипт
./scripts/deploy_staging.sh
```

---

## 📋 Шаг 4: Проверка (1 минута)

```bash
# Проверить pods
kubectl get pods -n x0tta6bl4-staging

# Проверить health
curl http://localhost:8080/health

# Проверить metrics
curl http://localhost:8080/metrics | head -20
```

---

## ✅ Ожидаемый Результат

**Pods:**
```
NAME                              READY   STATUS    RESTARTS
x0tta6bl4-staging-xxx-yyy         1/1     Running   0
```

**Health Check:**
```json
{
  "status": "ok",
  "version": "3.4.0-fixed2",
  "components": {
    "mesh": "active",
    "monitoring": "active"
  }
}
```

---

## 🐛 Troubleshooting

### Pod не запускается

```bash
# Проверить логи
kubectl logs -n x0tta6bl4-staging <pod-name>

# Проверить события
kubectl describe pod <pod-name> -n x0tta6bl4-staging
```

**Common issues:**
- liboqs проблема → Проверить `OQS_DISABLE_AUTO_INSTALL=1`
- Memory limit → Увеличить в values.yaml
- Port conflict → Проверить port 8080

### Health check failing

```bash
# Проверить application logs
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging --tail=50

# Проверить readiness probe
kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep -A 5 "Readiness"
```

---

## 📚 Дополнительные Ресурсы

- **Полная документация:** `README.md`
- **Troubleshooting:** `TROUBLESHOOTING_QUICK_REFERENCE_2026_01_07.md`
- **Production Runbooks:** `PRODUCTION_RUNBOOKS_2026_01_07.md`
- **Deployment Status:** `DEPLOYMENT_STATUS_2026_01_06.md`

---

## 🎯 Следующие Шаги

После успешного deployment:

1. **Multi-node testing:** Масштабировать до 5 pods
2. **Load testing:** Запустить load test
3. **Stability test:** 24+ часовой тест
4. **Failure injection:** Chaos engineering tests

---

**Последнее обновление:** 2026-01-07  
**Статус:** ✅ Quick Start Guide  
**Время:** 5-10 минут
