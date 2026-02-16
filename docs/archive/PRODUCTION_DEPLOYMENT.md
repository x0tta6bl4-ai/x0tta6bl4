# Production Deployment Guide

**Версия:** 1.0  
**Дата:** 2025-12-28  
**Статус:** ✅ **READY**

---

## 📋 Обзор

Полное руководство по развертыванию x0tta6bl4 в production.

---

## 🚀 Быстрый старт

### 1. Подготовка

```bash
# Клонировать репозиторий
git clone https://gitlab.com/x0tta6bl4/x0tta6bl4.git
cd x0tta6bl4

# Установить зависимости
pip install -r requirements.txt
```

### 2. Сборка Docker образа

```bash
# Собрать immutable image
./scripts/build_immutable_image.sh

# Или через CI/CD
git push origin main
```

### 3. Развертывание в Kubernetes

```bash
# Обновить image tag в values.yaml
sed -i 's/sha256-REPLACE_WITH_SHA/sha256-<COMMIT_SHA>/' \
  deployment/kubernetes/helm-charts/x0tta6bl4/values.yaml

# Развернуть с Helm
helm install x0tta6bl4 ./deployment/kubernetes/helm-charts/x0tta6bl4

# Проверить статус
kubectl get pods -l app=x0tta6bl4
```

---

## 🔧 Конфигурация

### Environment Variables

```yaml
ENVIRONMENT: "production"
X0TTA6BL4_PRODUCTION: "true"
SPIFFE_ENABLED: "true"
FL_ENABLED: "true"
GRAPHSAGE_ENABLED: "true"
NODE_ID: "<auto-set>"
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

---

## 🔐 Безопасность

### Post-Quantum Cryptography

- **Обязательно:** LibOQS должен быть установлен
- **Алгоритмы:** ML-KEM-768 (KEM), ML-DSA-65 (Signatures)
- **Проверка:** `python -c "from oqs import KeyEncapsulation"`

### SPIFFE/SPIRE

- **Обязательно в production:** SPIFFE/SPIRE для Zero Trust
- **Socket:** `/run/spire/sockets/agent.sock`
- **Проверка:** SPIRE Agent должен быть запущен

### Security Context

- Run as non-root (UID 1000)
- No privilege escalation
- Drop all capabilities

---

## 📊 Мониторинг

### Health Checks

```bash
# Проверить health endpoint
curl http://localhost:8080/health

# Проверить metrics
curl http://localhost:8080/metrics
```

### Логи

```bash
# Kubernetes logs
kubectl logs -l app=x0tta6bl4 --tail=100

# Follow logs
kubectl logs -f -l app=x0tta6bl4
```

---

## 🔄 Обновление

### Rolling Update

```bash
# Обновить image tag
kubectl set image deployment/x0tta6bl4 \
  app=registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-<NEW_SHA>

# Проверить rollout
kubectl rollout status deployment/x0tta6bl4
```

### Blue-Green Deployment

```bash
# Развернуть новую версию в green
kubectl apply -f deployment/kubernetes/blue-green-deployment.yaml

# Переключить трафик
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'
```

---

## 🐛 Troubleshooting

### Проблема: Pod не запускается

```bash
# Проверить события
kubectl describe pod <pod-name>

# Проверить логи
kubectl logs <pod-name>
```

### Проблема: Health check fails

```bash
# Проверить endpoint напрямую
kubectl exec -it <pod-name> -- curl http://localhost:8080/health
```

### Проблема: LibOQS не найден

```bash
# Проверить установку
kubectl exec -it <pod-name> -- python -c "from oqs import KeyEncapsulation"
```

---

## ✅ Чеклист перед Production

- [ ] LibOQS установлен и работает
- [ ] SPIFFE/SPIRE настроен
- [ ] Health checks проходят
- [ ] Resource limits установлены
- [ ] Security context настроен
- [ ] Monitoring настроен
- [ ] Logging настроен
- [ ] Backup настроен

---

**Mesh обновлён. Production deployment готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

