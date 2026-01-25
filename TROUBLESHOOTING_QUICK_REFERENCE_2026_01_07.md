# Troubleshooting Quick Reference
**Дата:** 2026-01-07  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ✅ **QUICK REFERENCE**

---

## 🎯 Quick Reference

**Быстрые решения для common issues.**

---

## 🔴 Критические Проблемы

### Pod в CrashLoopBackOff

**Симптомы:**
```bash
kubectl get pods -n x0tta6bl4-staging
# STATUS: CrashLoopBackOff
```

**Быстрая диагностика:**
```bash
# 1. Проверить логи
kubectl logs -n x0tta6bl4-staging <pod-name> --previous

# 2. Проверить события
kubectl describe pod <pod-name> -n x0tta6bl4-staging

# 3. Проверить ресурсы
kubectl top pod <pod-name> -n x0tta6bl4-staging
```

**Common причины:**
- ❌ liboqs не установлен → Проверить `OQS_DISABLE_AUTO_INSTALL=1`
- ❌ Memory limit exceeded → Увеличить limits
- ❌ Health check failing → Проверить `/health` endpoint
- ❌ ConfigMap/Secret missing → Проверить `kubectl get configmap,secret`

**Решение:**
```bash
# Если liboqs проблема:
# Убедиться, что OQS_DISABLE_AUTO_INSTALL=1 установлен
kubectl get deployment -n x0tta6bl4-staging -o yaml | grep OQS

# Если memory проблема:
# Увеличить limits в values.yaml
```

---

### Health Check Failing

**Симптомы:**
```bash
curl http://localhost:8080/health
# 500 Internal Server Error или timeout
```

**Быстрая диагностика:**
```bash
# 1. Проверить pod status
kubectl get pods -n x0tta6bl4-staging

# 2. Проверить логи
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging --tail=50

# 3. Проверить readiness probe
kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep -A 5 "Readiness"
```

**Common причины:**
- ❌ Application не запустилось → Проверить startup logs
- ❌ Dependency недоступна → Проверить connectivity
- ❌ Port conflict → Проверить port 8080

**Решение:**
```bash
# Проверить application logs
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i error

# Проверить dependencies
curl http://localhost:8080/health | jq .dependencies
```

---

### Memory Leak (подозрение)

**Симптомы:**
- Memory usage растет линейно
- Pods перезапускаются из-за OOMKilled

**Быстрая диагностика:**
```bash
# 1. Проверить memory usage за время
kubectl top pods -n x0tta6bl4-staging --containers

# 2. Проверить в Prometheus
# rate(container_memory_usage_bytes[1h])

# 3. Проверить логи на memory warnings
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i memory
```

**Решение:**
- Увеличить memory limits (временное)
- Найти и исправить leak (постоянное)
- Проверить PyTorch tensor cleanup
- Проверить connection pooling

---

## 🟡 Предупреждения

### High CPU Usage

**Симптомы:**
- CPU usage > 80%
- Slow response times

**Быстрая диагностика:**
```bash
# Проверить CPU
kubectl top pods -n x0tta6bl4-staging

# Проверить процессы
kubectl exec -n x0tta6bl4-staging <pod-name> -- top -n 1
```

**Решение:**
- Scale horizontally: `kubectl scale deployment --replicas=7`
- Увеличить CPU limits
- Проверить на infinite loops

---

### High Error Rate

**Симптомы:**
- Error rate > 1%
- Errors в логах

**Быстрая диагностика:**
```bash
# Проверить error rate
curl -s http://localhost:8080/metrics | grep errors_total

# Проверить логи
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i error | tail -20
```

**Решение:**
- Проверить error patterns
- Исправить root cause
- Rollback если недавний deployment

---

### Network Issues

**Симптомы:**
- Pods не могут общаться
- Timeouts

**Быстрая диагностика:**
```bash
# Проверить connectivity
kubectl exec -n x0tta6bl4-staging <pod-1> -- ping <pod-2-ip>

# Проверить network policies
kubectl get networkpolicies -n x0tta6bl4-staging
```

**Решение:**
- Проверить network policies
- Проверить service endpoints
- Проверить DNS

---

## 🟢 Информация

### Как получить help

**Логи:**
```bash
# Все pods
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4-staging --tail=100

# Specific pod
kubectl logs -n x0tta6bl4-staging <pod-name> --tail=100 -f

# Previous container (if crashed)
kubectl logs -n x0tta6bl4-staging <pod-name> --previous
```

**Метрики:**
```bash
# Prometheus metrics
curl -s http://localhost:8080/metrics

# Health check
curl http://localhost:8080/health | jq .

# Mesh status
curl http://localhost:8080/mesh/status | jq .
```

**События:**
```bash
# Recent events
kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp' | tail -20

# Pod events
kubectl describe pod <pod-name> -n x0tta6bl4-staging
```

---

## 📝 Common Commands

### Debugging

```bash
# Exec into pod
kubectl exec -it -n x0tta6bl4-staging <pod-name> -- /bin/bash

# Check environment
kubectl exec -n x0tta6bl4-staging <pod-name> -- env | grep X0TTA6BL4

# Check network
kubectl exec -n x0tta6bl4-staging <pod-name> -- netstat -tulpn
```

### Restart

```bash
# Restart deployment
kubectl rollout restart deployment/x0tta6bl4-staging -n x0tta6bl4-staging

# Rollback
kubectl rollout undo deployment/x0tta6bl4-staging -n x0tta6bl4-staging
```

### Scale

```bash
# Scale up
kubectl scale deployment/x0tta6bl4-staging --replicas=7 -n x0tta6bl4-staging

# Scale down
kubectl scale deployment/x0tta6bl4-staging --replicas=3 -n x0tta6bl4-staging
```

---

## 🔗 Ссылки

- **Production Runbooks:** `PRODUCTION_RUNBOOKS_2026_01_07.md`
- **Disaster Recovery:** `DISASTER_RECOVERY_PLAN_2026_01_07.md`
- **Security Hardening:** `SECURITY_HARDENING_GUIDE_2026_01_07.md`

---

**Последнее обновление:** 2026-01-07  
**Статус:** ✅ Quick Reference  
**Следующий шаг:** Использовать при проблемах

