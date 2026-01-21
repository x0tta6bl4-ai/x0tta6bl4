# x0tta6bl4 Kubernetes Deployment Guide

**Версия:** 2.0  
**Дата:** 31 декабря 2025  
**Статус:** ✅ **PRODUCTION READY**

---

## 📋 Обзор

Полный набор Kubernetes manifests для production deployment x0tta6bl4:

- ✅ Deployment с rolling updates
- ✅ Service (ClusterIP)
- ✅ ConfigMap для конфигурации
- ✅ Secrets (example template)
- ✅ HPA (Horizontal Pod Autoscaler)
- ✅ Network Policy для безопасности
- ✅ RBAC для service accounts
- ✅ Ingress для внешнего доступа

---

## 🚀 Быстрый старт

### 1. Подготовка

```bash
# Создать namespace (опционально)
kubectl create namespace x0tta6bl4

# Создать secrets (из примера)
cp secrets.yaml.example secrets.yaml
# Отредактировать secrets.yaml с реальными значениями
kubectl apply -f secrets.yaml
```

### 2. Deploy

```bash
# Применить все manifests
kubectl apply -f rbac.yaml
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml
kubectl apply -f network-policy.yaml
kubectl apply -f ingress.yaml
```

### 3. Проверка

```bash
# Проверить статус
kubectl get pods -l app=x0tta6bl4
kubectl get svc x0tta6bl4
kubectl get hpa x0tta6bl4-hpa

# Проверить логи
kubectl logs -l app=x0tta6bl4 --tail=100

# Проверить health
kubectl port-forward svc/x0tta6bl4 8080:80
curl http://localhost:8080/health
```

---

## 📁 Структура Manifests

```
deployment/kubernetes/
├── README.md (этот файл)
├── deployment.yaml          # Main deployment
├── service.yaml             # Service (ClusterIP)
├── configmap.yaml           # Configuration
├── secrets.yaml.example     # Secrets template
├── hpa.yaml                 # Horizontal Pod Autoscaler
├── network-policy.yaml       # Network security
├── rbac.yaml                # RBAC for service account
└── ingress.yaml             # Ingress for external access
```

---

## 🔧 Конфигурация

### Environment Variables

Основные переменные в `deployment.yaml`:

```yaml
env:
- name: NODE_ID
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: ENVIRONMENT
  value: "production"
- name: X0TTA6BL4_PRODUCTION
  value: "true"
- name: SPIFFE_ENABLED
  value: "true"
- name: FL_ENABLED
  value: "true"
- name: GRAPHSAGE_ENABLED
  value: "true"
```

### Resource Limits

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "1Gi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### Health Checks

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## 🔒 Безопасность

### Security Context

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
```

### Network Policy

Network Policy ограничивает:
- ✅ Ingress только от разрешенных источников
- ✅ Egress только для необходимых портов
- ✅ Mesh node communication разрешен

### RBAC

Service Account с минимальными правами:
- ✅ Чтение ConfigMaps и Secrets
- ✅ Чтение endpoints для service discovery
- ✅ Чтение pods для mesh topology

---

## 📈 Автомасштабирование

### HPA Configuration

```yaml
minReplicas: 3
maxReplicas: 10
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70
- type: Resource
  resource:
    name: memory
    target:
      averageUtilization: 80
```

HPA автоматически масштабирует на основе:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

---

## 🌐 Ingress

Пример Ingress для внешнего доступа:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: x0tta6bl4-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: x0tta6bl4.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: x0tta6bl4
            port:
              number: 80
  tls:
  - hosts:
    - x0tta6bl4.example.com
    secretName: x0tta6bl4-tls
```

---

## 🔄 Обновление

### Rolling Update

```bash
# Обновить image tag
kubectl set image deployment/x0tta6bl4 \
  app=registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-NEW_SHA

# Проверить rollout
kubectl rollout status deployment/x0tta6bl4

# Откатить при необходимости
kubectl rollout undo deployment/x0tta6bl4
```

### Blue-Green Deployment

Используйте `blue-green-deployment.yaml` для zero-downtime updates.

---

## 📊 Мониторинг

### Проверка статуса

```bash
# Pods
kubectl get pods -l app=x0tta6bl4

# Services
kubectl get svc x0tta6bl4

# HPA
kubectl get hpa x0tta6bl4-hpa

# Events
kubectl get events --sort-by='.lastTimestamp'
```

### Логи

```bash
# Все pods
kubectl logs -l app=x0tta6bl4 --tail=100

# Конкретный pod
kubectl logs <pod-name>

# С follow
kubectl logs -l app=x0tta6bl4 -f
```

---

## 🐛 Troubleshooting

### Pod не запускается

```bash
# Проверить события
kubectl describe pod <pod-name>

# Проверить логи
kubectl logs <pod-name>

# Проверить ресурсы
kubectl top pod <pod-name>
```

### Health check fails

```bash
# Проверить health endpoint
kubectl exec <pod-name> -- curl http://localhost:8080/health

# Проверить конфигурацию
kubectl get configmap x0tta6bl4-config -o yaml
```

### Network issues

```bash
# Проверить network policy
kubectl get networkpolicy x0tta6bl4-network-policy -o yaml

# Проверить service endpoints
kubectl get endpoints x0tta6bl4
```

---

## 🚀 Production Checklist

- [ ] Secrets созданы и применены
- [ ] ConfigMap настроен
- [ ] Image tag обновлен в deployment.yaml
- [ ] Resource limits проверены
- [ ] Health checks работают
- [ ] Network Policy применена
- [ ] RBAC настроен
- [ ] HPA работает
- [ ] Ingress настроен (если нужен)
- [ ] Мониторинг настроен
- [ ] Backup настроен

---

## 📚 Дополнительные ресурсы

- **Terraform:** `infra/terraform/aws/`, `infra/terraform/azure/`, `infra/terraform/gcp/`
- **Helm Charts:** `deployment/kubernetes/helm-charts/`
- **CI/CD:** `.github/workflows/`

---

*Last Updated: December 31, 2025*

