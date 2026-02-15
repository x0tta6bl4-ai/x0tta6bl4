# Runbooks для x0tta6bl4

**Версия:** 1.0  
**Дата:** 2025-12-28  
**Статус:** ✅ **READY**

---

## 📋 Обзор

Runbooks для операционных задач x0tta6bl4.

---

## 🔧 Общие операции

### Проверка статуса системы

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Kubernetes status
kubectl get pods -l app=x0tta6bl4
```

### Перезапуск сервиса

```bash
# Kubernetes
kubectl rollout restart deployment/x0tta6bl4

# Docker
docker restart x0tta6bl4
```

### Масштабирование

```bash
# Увеличить количество реплик
kubectl scale deployment/x0tta6bl4 --replicas=5

# Автомасштабирование
kubectl autoscale deployment/x0tta6bl4 --min=3 --max=10 --cpu-percent=80
```

---

## 🐛 Troubleshooting

### Проблема: Высокая загрузка CPU

```bash
# Проверить метрики
kubectl top pods -l app=x0tta6bl4

# Проверить логи
kubectl logs -l app=x0tta6bl4 --tail=100 | grep ERROR

# Увеличить ресурсы
kubectl edit deployment/x0tta6bl4
```

### Проблема: Высокое использование памяти

```bash
# Проверить использование памяти
kubectl top pods -l app=x0tta6bl4

# Проверить утечки памяти
kubectl logs -l app=x0tta6bl4 | grep memory

# Перезапустить pod
kubectl delete pod <pod-name>
```

### Проблема: Сеть недоступна

```bash
# Проверить connectivity
kubectl exec -it <pod-name> -- ping 8.8.8.8

# Проверить DNS
kubectl exec -it <pod-name> -- nslookup google.com

# Проверить mesh connectivity
curl http://localhost:8080/mesh/peers
```

---

## 🔄 Обновление

### Обновление до новой версии

```bash
# 1. Получить новый image
docker pull registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-<NEW_SHA>

# 2. Обновить deployment
kubectl set image deployment/x0tta6bl4 \
  app=registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-<NEW_SHA>

# 3. Проверить rollout
kubectl rollout status deployment/x0tta6bl4

# 4. Откатить при необходимости
kubectl rollout undo deployment/x0tta6bl4
```

### Blue-Green Deployment

```bash
# 1. Развернуть green
kubectl apply -f deployment/kubernetes/blue-green-deployment.yaml

# 2. Масштабировать green
kubectl scale deployment/x0tta6bl4-green --replicas=3

# 3. Переключить трафик
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'

# 4. Проверить green
kubectl get pods -l version=green

# 5. Масштабировать blue вниз
kubectl scale deployment/x0tta6bl4-blue --replicas=0
```

---

## 🔐 Безопасность

### Проверка PQC

```bash
# Проверить LibOQS
kubectl exec -it <pod-name> -- python -c "from oqs import KeyEncapsulation; print('OK')"

# Проверить SPIFFE
kubectl exec -it <pod-name> -- ls -la /run/spire/sockets/agent.sock
```

### Обновление сертификатов

```bash
# SPIFFE сертификаты обновляются автоматически
# Проверить статус
kubectl exec -it <pod-name> -- curl http://localhost:8080/health | jq .components.spiffe
```

---

## 📊 Мониторинг

### Проверка метрик

```bash
# Prometheus metrics
curl http://localhost:8080/metrics

# Health metrics
curl http://localhost:8080/health | jq .component_stats
```

### Алерты

```bash
# Проверить статус алертов
# (зависит от системы мониторинга)
```

---

## 🚨 Инциденты

### Критический инцидент

1. **Оценить ситуацию**
   ```bash
   kubectl get pods -l app=x0tta6bl4
   kubectl logs -l app=x0tta6bl4 --tail=100
   ```

2. **Изолировать проблему**
   ```bash
   # Отключить проблемный pod
   kubectl delete pod <problematic-pod>
   ```

3. **Восстановить сервис**
   ```bash
   # Масштабировать
   kubectl scale deployment/x0tta6bl4 --replicas=5
   ```

4. **Откатить при необходимости**
   ```bash
   kubectl rollout undo deployment/x0tta6bl4
   ```

---

**Mesh обновлён. Runbooks готовы.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

