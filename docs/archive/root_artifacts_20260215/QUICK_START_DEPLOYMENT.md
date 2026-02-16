# 🚀 x0tta6bl4: Quick Start Deployment Guide

**Версия:** 1.0  
**Дата:** 31 декабря 2025  
**Время:** ~15 минут до running deployment

---

## 📋 ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

- Kubernetes cluster (minikube, kind, или cloud)
- `kubectl` установлен и настроен
- Доступ к кластеру

---

## ⚡ БЫСТРЫЙ СТАРТ (5 минут)

### 1. Клонировать и перейти в директорию

```bash
git clone https://github.com/x0tta6bl4/x0tta6bl4.git
cd x0tta6bl4
```

### 2. Настроить secrets (опционально)

```bash
cd deployment/kubernetes
cp secrets.yaml.example secrets.yaml
# Отредактировать secrets.yaml с вашими значениями
# Или оставить пустым для тестирования
```

### 3. Deploy все компоненты

```bash
# Применить все manifests одной командой
kubectl apply -f rbac.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml  # если создали
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml
kubectl apply -f network-policy.yaml
```

### 4. Проверить статус

```bash
# Проверить pods
kubectl get pods -l app=x0tta6bl4

# Проверить service
kubectl get svc x0tta6bl4

# Проверить HPA
kubectl get hpa x0tta6bl4-hpa

# Проверить логи
kubectl logs -l app=x0tta6bl4 --tail=50
```

### 5. Доступ к приложению

```bash
# Port-forward для локального доступа
kubectl port-forward svc/x0tta6bl4 8080:80

# В другом терминале
curl http://localhost:8080/health
```

---

## 🌐 CLOUD DEPLOYMENT

### AWS (EKS)

```bash
# 1. Deploy infrastructure
cd infra/terraform/aws
terraform init
terraform plan
terraform apply

# 2. Настроить kubeconfig
aws eks update-kubeconfig --region us-east-1 --name x0tta6bl4

# 3. Deploy application (см. шаги выше)
cd ../../../deployment/kubernetes
kubectl apply -f ...
```

### Azure (AKS)

```bash
# 1. Deploy infrastructure
cd infra/terraform/azure
terraform init
terraform plan
terraform apply

# 2. Настроить kubeconfig
az aks get-credentials --resource-group rg-x0tta6bl4-production --name aks-x0tta6bl4-production

# 3. Deploy application (см. шаги выше)
cd ../../../deployment/kubernetes
kubectl apply -f ...
```

### GCP (GKE)

```bash
# 1. Создать terraform.tfvars
cd infra/terraform/gcp
cat > terraform.tfvars <<EOF
gcp_project_id = "your-project-id"
gcp_region = "us-central1"
environment = "production"
EOF

# 2. Deploy infrastructure
terraform init
terraform plan
terraform apply

# 3. Настроить kubeconfig
gcloud container clusters get-credentials gke-x0tta6bl4-production --region us-central1

# 4. Deploy application (см. шаги выше)
cd ../../../deployment/kubernetes
kubectl apply -f ...
```

---

## 🔧 КОНФИГУРАЦИЯ

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
- name: SPIFFE_ENABLED
  value: "true"
- name: FL_ENABLED
  value: "true"
- name: GRAPHSAGE_ENABLED
  value: "true"
```

### Resource Limits

По умолчанию:
- Requests: 500m CPU, 1Gi Memory
- Limits: 2000m CPU, 2Gi Memory

Изменить в `deployment.yaml`:

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "1Gi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### Autoscaling

HPA настроен на:
- Min replicas: 3
- Max replicas: 10
- CPU target: 70%
- Memory target: 80%

Изменить в `hpa.yaml`:

```yaml
minReplicas: 3
maxReplicas: 10
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70
```

---

## 🔒 БЕЗОПАСНОСТЬ

### Network Policy

Network Policy ограничивает:
- Ingress только от разрешенных источников
- Egress только для необходимых портов
- Mesh node communication разрешен

### RBAC

Service Account с минимальными правами:
- Чтение ConfigMaps и Secrets
- Чтение endpoints для service discovery
- Чтение pods для mesh topology

### Secrets

**ВАЖНО:** Не коммитить `secrets.yaml` в git!

```bash
# Добавить в .gitignore
echo "deployment/kubernetes/secrets.yaml" >> .gitignore
```

---

## 📊 МОНИТОРИНГ

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

### Health Checks

```bash
# Port-forward
kubectl port-forward svc/x0tta6bl4 8080:80

# Проверить health
curl http://localhost:8080/health

# Или напрямую в pod
kubectl exec <pod-name> -- curl http://localhost:8080/health
```

---

## 🔄 ОБНОВЛЕНИЕ

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

### Обновление ConfigMap

```bash
# Изменить configmap.yaml
kubectl apply -f configmap.yaml

# Перезапустить pods для применения изменений
kubectl rollout restart deployment/x0tta6bl4
```

---

## 🐛 TROUBLESHOOTING

### Pod не запускается

```bash
# Описать pod
kubectl describe pod <pod-name>

# Проверить события
kubectl get events --field-selector involvedObject.name=<pod-name>

# Проверить логи
kubectl logs <pod-name>
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

### Resource issues

```bash
# Проверить использование ресурсов
kubectl top pod -l app=x0tta6bl4

# Проверить HPA
kubectl describe hpa x0tta6bl4-hpa
```

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

- **Полная документация:** `deployment/kubernetes/README_DEPLOYMENT.md`
- **Terraform guides:** `infra/terraform/aws/`, `infra/terraform/azure/`, `infra/terraform/gcp/`
- **Benchmark instructions:** `BENCHMARK_INSTRUCTIONS.md`
- **Compliance:** `COMPLIANCE_ALL_TASKS_COMPLETE.md`

---

## ✅ CHECKLIST

- [ ] Kubernetes cluster доступен
- [ ] `kubectl` настроен
- [ ] Secrets созданы (если нужны)
- [ ] Все manifests применены
- [ ] Pods запущены и healthy
- [ ] Service доступен
- [ ] HPA работает
- [ ] Health checks проходят
- [ ] Логи проверены

---

**Готово! x0tta6bl4 развернут и работает! 🎉**

*Время до running deployment: ~15 минут*

