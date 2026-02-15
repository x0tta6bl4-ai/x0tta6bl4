# Troubleshooting Guide

**Версия:** 1.0  
**Дата:** 2025-12-28  
**Статус:** ✅ **READY**

---

## 📋 Обзор

Руководство по устранению неполадок для x0tta6bl4.

---

## 🔍 Диагностика

### Проверка статуса системы

```bash
# Health check
curl http://localhost:8080/health

# Проверить компоненты
curl http://localhost:8080/health | jq .components

# Проверить статистику
curl http://localhost:8080/health | jq .component_stats
```

### Проверка логов

```bash
# Kubernetes
kubectl logs -l app=x0tta6bl4 --tail=100

# Docker
docker logs x0tta6bl4 --tail=100

# Follow logs
kubectl logs -f -l app=x0tta6bl4
```

### Проверка метрик

```bash
# Prometheus metrics
curl http://localhost:8080/metrics

# Проверить память
curl http://localhost:8080/metrics | grep process_resident_memory_bytes
```

---

## 🐛 Частые проблемы

### Проблема: Pod не запускается

**Симптомы:**
- Pod в статусе `CrashLoopBackOff`
- Pod в статусе `Pending`

**Диагностика:**
```bash
# Проверить события
kubectl describe pod <pod-name>

# Проверить логи
kubectl logs <pod-name>

# Проверить ресурсы
kubectl top pod <pod-name>
```

**Решения:**
1. **Недостаточно ресурсов:**
   ```bash
   # Проверить ресурсы узла
   kubectl describe node
   
   # Уменьшить requests/limits
   kubectl edit deployment/x0tta6bl4
   ```

2. **Ошибка инициализации:**
   ```bash
   # Проверить LibOQS
   kubectl exec -it <pod-name> -- python -c "from oqs import KeyEncapsulation"
   
   # Проверить SPIFFE
   kubectl exec -it <pod-name> -- ls -la /run/spire/sockets/agent.sock
   ```

3. **Image pull error:**
   ```bash
   # Проверить image
   kubectl describe pod <pod-name> | grep Image
   
   # Проверить registry access
   kubectl get secrets
   ```

---

### Проблема: Health check fails

**Симптомы:**
- `/health` возвращает 503
- Pod в статусе `NotReady`

**Диагностика:**
```bash
# Проверить health endpoint напрямую
kubectl exec -it <pod-name> -- curl http://localhost:8080/health

# Проверить readiness probe
kubectl describe pod <pod-name> | grep Readiness
```

**Решения:**
1. **Компоненты не инициализированы:**
   ```bash
   # Проверить логи инициализации
   kubectl logs <pod-name> | grep "initialized"
   
   # Проверить зависимости
   kubectl exec -it <pod-name> -- python -c "import oqs"
   ```

2. **Порт недоступен:**
   ```bash
   # Проверить порт
   kubectl exec -it <pod-name> -- netstat -tlnp | grep 8080
   
   # Проверить service
   kubectl get svc x0tta6bl4
   ```

---

### Проблема: LibOQS не найден

**Симптомы:**
- Ошибка: `ModuleNotFoundError: No module named 'oqs'`
- Build fails с ошибкой LibOQS

**Диагностика:**
```bash
# Проверить установку
kubectl exec -it <pod-name> -- python -c "from oqs import KeyEncapsulation"

# Проверить Dockerfile
cat Dockerfile.app | grep liboqs
```

**Решения:**
1. **Пересобрать image:**
   ```bash
   # Собрать с LibOQS
   docker build -f Dockerfile.app -t x0tta6bl4:test .
   
   # Проверить в контейнере
   docker run --rm x0tta6bl4:test python -c "from oqs import KeyEncapsulation"
   ```

2. **Проверить зависимости:**
   ```bash
   # Проверить requirements.txt
   cat requirements.txt | grep liboqs
   ```

---

### Проблема: SPIFFE/SPIRE не работает

**Симптомы:**
- Ошибка: `SPIFFE/SPIRE REQUIRED but not available`
- mTLS handshake fails

**Диагностика:**
```bash
# Проверить SPIRE Agent
kubectl exec -it <pod-name> -- ls -la /run/spire/sockets/agent.sock

# Проверить SPIFFE SDK
kubectl exec -it <pod-name> -- python -c "import spiffe"
```

**Решения:**
1. **SPIRE Agent не запущен:**
   ```bash
   # Проверить SPIRE Agent pod
   kubectl get pods -l app=spire-agent
   
   # Запустить SPIRE Agent
   kubectl apply -f spire-agent.yaml
   ```

2. **Socket недоступен:**
   ```bash
   # Проверить volume mount
   kubectl describe pod <pod-name> | grep spire
   
   # Добавить volume mount в deployment
   kubectl edit deployment/x0tta6bl4
   ```

---

### Проблема: Высокая загрузка CPU

**Симптомы:**
- CPU usage > 80%
- Медленные ответы API

**Диагностика:**
```bash
# Проверить CPU usage
kubectl top pods -l app=x0tta6bl4

# Проверить процессы
kubectl exec -it <pod-name> -- top
```

**Решения:**
1. **Увеличить ресурсы:**
   ```bash
   # Увеличить CPU limit
   kubectl edit deployment/x0tta6bl4
   # Изменить: resources.limits.cpu: "4000m"
   ```

2. **Масштабировать:**
   ```bash
   # Увеличить количество реплик
   kubectl scale deployment/x0tta6bl4 --replicas=5
   ```

3. **Оптимизировать код:**
   ```bash
   # Проверить профилирование
   kubectl logs <pod-name> | grep "performance"
   ```

---

### Проблема: Высокое использование памяти

**Симптомы:**
- Memory usage > 80%
- OOMKilled pods

**Диагностика:**
```bash
# Проверить memory usage
kubectl top pods -l app=x0tta6bl4

# Проверить memory в контейнере
kubectl exec -it <pod-name> -- free -h
```

**Решения:**
1. **Увеличить memory limit:**
   ```bash
   # Увеличить memory limit
   kubectl edit deployment/x0tta6bl4
   # Изменить: resources.limits.memory: "4Gi"
   ```

2. **Проверить утечки памяти:**
   ```bash
   # Проверить логи
   kubectl logs <pod-name> | grep "memory"
   
   # Перезапустить pod
   kubectl delete pod <pod-name>
   ```

---

### Проблема: Mesh network недоступен

**Симптомы:**
- `/mesh/status` возвращает 503
- Нет peers в mesh

**Диагностика:**
```bash
# Проверить mesh status
curl http://localhost:8080/mesh/status

# Проверить peers
curl http://localhost:8080/mesh/peers
```

**Решения:**
1. **Yggdrasil не запущен:**
   ```bash
   # Проверить Yggdrasil service
   kubectl get pods -l app=yggdrasil
   
   # Запустить Yggdrasil
   kubectl apply -f yggdrasil.yaml
   ```

2. **Network connectivity:**
   ```bash
   # Проверить connectivity
   kubectl exec -it <pod-name> -- ping 8.8.8.8
   
   # Проверить DNS
   kubectl exec -it <pod-name> -- nslookup google.com
   ```

---

### Проблема: API медленно отвечает

**Симптомы:**
- Response time > 1s
- Timeout errors

**Диагностика:**
```bash
# Проверить response time
time curl http://localhost:8080/health

# Проверить метрики
curl http://localhost:8080/metrics | grep latency
```

**Решения:**
1. **Проверить нагрузку:**
   ```bash
   # Проверить CPU/Memory
   kubectl top pods -l app=x0tta6bl4
   
   # Масштабировать
   kubectl scale deployment/x0tta6bl4 --replicas=5
   ```

2. **Оптимизировать запросы:**
   ```bash
   # Проверить медленные запросы
   kubectl logs <pod-name> | grep "slow"
   ```

---

## 🔧 Полезные команды

### Kubernetes

```bash
# Получить все ресурсы
kubectl get all -l app=x0tta6bl4

# Описать ресурс
kubectl describe deployment/x0tta6bl4

# Редактировать ресурс
kubectl edit deployment/x0tta6bl4

# Удалить и пересоздать
kubectl delete deployment/x0tta6bl4
kubectl apply -f deployment.yaml
```

### Docker

```bash
# Проверить контейнеры
docker ps -a | grep x0tta6bl4

# Проверить логи
docker logs x0tta6bl4

# Войти в контейнер
docker exec -it x0tta6bl4 bash
```

---

## 📞 Поддержка

Если проблема не решена:

1. Собрать диагностическую информацию:
   ```bash
   # Health check
   curl http://localhost:8080/health > health.json
   
   # Logs
   kubectl logs -l app=x0tta6bl4 > logs.txt
   
   # Events
   kubectl get events > events.txt
   ```

2. Проверить документацию:
   - `docs/deployment/PRODUCTION_DEPLOYMENT.md`
   - `docs/deployment/RUNBOOKS.md`
   - `docs/api/API_REFERENCE.md`

3. Создать issue в GitLab с диагностической информацией.

---

**Mesh обновлён. Troubleshooting guide готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

