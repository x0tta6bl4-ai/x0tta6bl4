# Kubernetes Deployment Guide

**Версия:** 1.0  
**Дата:** 2025-12-28  
**Статус:** ✅ **READY**

---

## 📋 Обзор

Kubernetes deployment для x0tta6bl4 mesh network с поддержкой:
- Immutable Docker images (content-addressable tags)
- Rolling updates
- Blue-green deployment
- Health checks
- Resource limits
- Security context

---

## 🚀 Быстрый старт

### Validation Scripts

```bash
# Complete production validation suite
bash scripts/run_production_validation.sh

# Individual validations
bash scripts/validate_production_readiness.sh
bash scripts/validate_kubernetes_deployment.sh

# Deploy to test cluster (auto-detects minikube/kind/existing)
bash scripts/deploy_to_test_cluster.sh

# Test deployment strategies
bash scripts/test_rolling_update.sh
bash scripts/test_blue_green_deployment.sh
```

### Manual Deployment

### Deploy with Helm (Recommended)

```bash
# Update image tag in values.yaml
sed -i 's/sha256-REPLACE_WITH_SHA/sha256-abc123def456/' helm-charts/x0tta6bl4/values.yaml

# Deploy
helm install x0tta6bl4 ./helm-charts/x0tta6bl4

# Upgrade
helm upgrade x0tta6bl4 ./helm-charts/x0tta6bl4
```

### Deploy with kubectl

```bash
# Update image tag in deployment.yaml
sed -i 's/sha256-REPLACE_WITH_SHA/sha256-abc123def456/' deployment.yaml

# Apply manifests
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f configmap.yaml
kubectl apply -f ingress.yaml
```

### Blue-Green Deployment

```bash
# Deploy new version to green
kubectl apply -f blue-green-deployment.yaml

# Scale green to 3 replicas
kubectl scale deployment x0tta6bl4-green --replicas=3

# Switch service to green
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'

# Scale down blue
kubectl scale deployment x0tta6bl4-blue --replicas=0
```

---

## 📁 Структура

```
deployment/kubernetes/
├── README.md (этот файл)
├── deployment.yaml          # Main deployment
├── service.yaml             # Service
├── configmap.yaml           # Configuration
├── ingress.yaml             # Ingress with TLS
├── blue-green-deployment.yaml # Blue-green strategy
└── helm-charts/
    └── x0tta6bl4/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
            ├── deployment.yaml
            ├── service.yaml
            ├── ingress.yaml
            └── _helpers.tpl
```

---

## 🔧 Конфигурация

### Environment Variables

- `NODE_ID` - Auto-set from pod name
- `ENVIRONMENT` - "production"
- `X0TTA6BL4_PRODUCTION` - "true"
- `SPIFFE_ENABLED` - "true"
- `FL_ENABLED` - "true"
- `GRAPHSAGE_ENABLED` - "true"

### Resource Limits

- Requests: CPU 500m, Memory 1Gi
- Limits: CPU 2000m, Memory 2Gi

### Health Checks

- Liveness: `/health` endpoint, 30s initial delay
- Readiness: `/health` endpoint, 10s initial delay

---

## 🔐 Security

- Run as non-root (UID 1000)
- No privilege escalation
- Drop all capabilities
- Read-only root filesystem (optional)

---

## 📊 Мониторинг

```bash
# Check deployment status
kubectl get deployment x0tta6bl4

# Check pods
kubectl get pods -l app=x0tta6bl4

# Check logs
kubectl logs -l app=x0tta6bl4 --tail=100

# Check health
kubectl exec -it <pod-name> -- curl http://localhost:8080/health
```

---

## ✅ ГОТОВО

- ✅ Helm charts
- ✅ Blue-green deployment
- ✅ Rolling updates
- ✅ Health checks
- ✅ Resource limits
- ✅ Security context

---

**Mesh обновлён. Kubernetes deployment готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

