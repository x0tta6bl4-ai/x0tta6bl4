# 📘 Complete Runbooks for x0tta6bl4

**Версия:** 2.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Содержание

1. [Общие операции](#общие-операции)
2. [Troubleshooting](#troubleshooting)
3. [Мониторинг и метрики](#мониторинг-и-метрики)
4. [Безопасность](#безопасность)
5. [Масштабирование](#масштабирование)
6. [Восстановление после сбоев](#восстановление-после-сбоев)
7. [Обновление и развертывание](#обновление-и-развертывание)
8. [MAPE-K цикл](#mape-k-цикл)
9. [Mesh Network](#mesh-network)
10. [SPIFFE/SPIRE](#spiffespire)

---

## 🔧 Общие операции

### Проверка статуса системы

```bash
# Health check
curl http://localhost:8080/health
# Ожидаемый ответ: {"status": "healthy", "version": "3.0"}

# Детальный health check
curl http://localhost:8080/health/detailed
# Показывает статус всех компонентов

# Kubernetes status
kubectl get pods -l app=x0tta6bl4
kubectl get services -l app=x0tta6bl4
kubectl get deployments -l app=x0tta6bl4

# Проверка метрик
curl http://localhost:8080/metrics
```

### Перезапуск сервиса

```bash
# Kubernetes (рекомендуется)
kubectl rollout restart deployment/x0tta6bl4
kubectl rollout status deployment/x0tta6bl4

# Docker
docker restart x0tta6bl4
docker ps | grep x0tta6bl4

# Systemd
sudo systemctl restart x0tta6bl4
sudo systemctl status x0tta6bl4
```

### Просмотр логов

```bash
# Kubernetes
kubectl logs -l app=x0tta6bl4 --tail=100 -f

# По pod
kubectl logs <pod-name> --tail=100

# Docker
docker logs x0tta6bl4 --tail=100 -f

# Systemd
sudo journalctl -u x0tta6bl4 -f --tail=100
```

---

## 🐛 Troubleshooting

### Проблема: Высокая загрузка CPU (>90%)

**Симптомы:**
- CPU usage > 90%
- Медленный отклик системы
- Timeout ошибки

**Диагностика:**
```bash
# Проверить метрики
kubectl top pods -l app=x0tta6bl4

# Проверить логи на ошибки
kubectl logs -l app=x0tta6bl4 --tail=100 | grep ERROR

# Проверить процессы
kubectl exec -it <pod-name> -- top

# Проверить MAPE-K цикл
curl http://localhost:8080/api/v1/mapek/status
```

**Решение:**
```bash
# 1. Увеличить ресурсы
kubectl edit deployment/x0tta6bl4
# Изменить resources.limits.cpu и resources.requests.cpu

# 2. Масштабировать горизонтально
kubectl scale deployment/x0tta6bl4 --replicas=5

# 3. Проверить MAPE-K автоматическое восстановление
# Система должна автоматически перезапустить сервис при высокой загрузке
```

### Проблема: Высокое использование памяти (>85%)

**Симптомы:**
- Memory usage > 85%
- OOM (Out of Memory) ошибки
- Pod перезапуски

**Диагностика:**
```bash
# Проверить использование памяти
kubectl top pods -l app=x0tta6bl4

# Проверить утечки памяти
kubectl logs -l app=x0tta6bl4 | grep -i memory

# Проверить OOM events
kubectl get events --field-selector reason=OOMKilled
```

**Решение:**
```bash
# 1. Увеличить лимиты памяти
kubectl edit deployment/x0tta6bl4
# Изменить resources.limits.memory

# 2. Очистить кеш (MAPE-K должен сделать это автоматически)
curl -X POST http://localhost:8080/api/v1/recovery/clear-cache

# 3. Перезапустить pod
kubectl delete pod <pod-name>
```

### Проблема: Сеть недоступна / Mesh connectivity issues

**Симптомы:**
- Нет связи между узлами
- Высокий packet loss
- Timeout при mesh операциях

**Диагностика:**
```bash
# Проверить connectivity
kubectl exec -it <pod-name> -- ping 8.8.8.8

# Проверить DNS
kubectl exec -it <pod-name> -- nslookup google.com

# Проверить mesh connectivity
curl http://localhost:8080/api/v1/mesh/peers
curl http://localhost:8080/api/v1/mesh/topology

# Проверить Batman-adv статус
kubectl exec -it <pod-name> -- batctl o
```

**Решение:**
```bash
# 1. Переключить маршрут (MAPE-K автоматически)
curl -X POST http://localhost:8080/api/v1/recovery/switch-route \
  -d '{"target_node": "node-id", "alternative_route": "backup-route"}'

# 2. Проверить сетевые политики
kubectl get networkpolicies

# 3. Перезапустить mesh компоненты
kubectl rollout restart daemonset/batman-adv
```

### Проблема: SPIFFE/SPIRE ошибки

**Симптомы:**
- SVID не выдается
- mTLS handshake failures
- Certificate errors

**Диагностика:**
```bash
# Проверить SPIRE Agent статус
kubectl exec -it <pod-name> -- spire-agent healthcheck

# Проверить SVID
kubectl exec -it <pod-name> -- spire-agent api fetch x509

# Проверить логи SPIRE
kubectl logs -l app=spire-agent --tail=100

# Проверить SPIFFE метрики
curl http://localhost:8080/metrics | grep spire
```

**Решение:**
```bash
# 1. Перезапустить SPIRE Agent
kubectl rollout restart daemonset/spire-agent

# 2. Проверить SPIRE Server
kubectl get pods -l app=spire-server
kubectl logs -l app=spire-server --tail=100

# 3. Проверить trust bundle
kubectl exec -it <pod-name> -- spire-agent api fetch jwt -audience x0tta6bl4.mesh
```

---

## 📊 Мониторинг и метрики

### Prometheus метрики

```bash
# Основные метрики
curl http://localhost:8080/metrics | grep x0tta6bl4

# MAPE-K метрики
curl http://localhost:8080/metrics | grep mape_k

# Mesh метрики
curl http://localhost:8080/metrics | grep mesh

# Security метрики
curl http://localhost:8080/metrics | grep pqc
curl http://localhost:8080/metrics | grep spire
```

### OpenTelemetry Tracing

```bash
# Проверить Jaeger
# Открыть http://jaeger:16686 в браузере

# Проверить traces
curl http://jaeger:16686/api/traces?service=x0tta6bl4

# Проверить Zipkin
curl http://zipkin:9411/api/v2/traces?serviceName=x0tta6bl4
```

### Grafana Dashboards

```bash
# Доступ к Grafana
# Открыть http://grafana:3000 в браузере

# Основные дашборды:
# - Mesh Topology
# - MAPE-K Cycles
# - Security Events
# - Resource Utilization
# - Error Rates
```

---

## 🔒 Безопасность

### Проверка PQC статуса

```bash
# Проверить PQC метрики
curl http://localhost:8080/metrics | grep pqc

# Проверить handshake failures
curl http://localhost:8080/api/v1/security/pqc/status

# Проверить fallback mode
curl http://localhost:8080/api/v1/security/pqc/fallback-status
```

### Проверка SPIFFE/SPIRE

```bash
# Проверить SVID expiry
kubectl exec -it <pod-name> -- spire-agent api fetch x509 | grep expires

# Проверить trust bundle
kubectl exec -it <pod-name> -- spire-agent api fetch jwt -audience x0tta6bl4.mesh

# Проверить workload entries
kubectl exec -it <pod-name> -- spire-server entry show
```

### Аудит безопасности

```bash
# Запустить security audit
python scripts/security_audit_checklist.py

# Проверить CVE
pip-audit

# Проверить зависимости
safety check
```

---

## 📈 Масштабирование

### Горизонтальное масштабирование

```bash
# Увеличить количество реплик
kubectl scale deployment/x0tta6bl4 --replicas=5

# Автомасштабирование
kubectl autoscale deployment/x0tta6bl4 \
  --min=3 \
  --max=10 \
  --cpu-percent=80

# Проверить статус
kubectl get hpa x0tta6bl4
```

### Вертикальное масштабирование

```bash
# Изменить ресурсы
kubectl edit deployment/x0tta6bl4

# Пример ресурсов:
# resources:
#   requests:
#     cpu: "500m"
#     memory: "512Mi"
#   limits:
#     cpu: "2000m"
#     memory: "2Gi"
```

---

## 🔄 Восстановление после сбоев

### Автоматическое восстановление (MAPE-K)

Система автоматически восстанавливается через MAPE-K цикл:

1. **Monitor**: Обнаружение аномалий
2. **Analyze**: Анализ root cause
3. **Plan**: Выбор стратегии восстановления
4. **Execute**: Выполнение действий
5. **Knowledge**: Обучение на опыте

**Проверить статус:**
```bash
curl http://localhost:8080/api/v1/mapek/status
curl http://localhost:8080/api/v1/mapek/history
```

### Ручное восстановление

```bash
# Restart service
curl -X POST http://localhost:8080/api/v1/recovery/restart-service \
  -d '{"service_name": "x0tta6bl4"}'

# Switch route
curl -X POST http://localhost:8080/api/v1/recovery/switch-route \
  -d '{"target_node": "node-id", "alternative_route": "backup"}'

# Clear cache
curl -X POST http://localhost:8080/api/v1/recovery/clear-cache

# Failover
curl -X POST http://localhost:8080/api/v1/recovery/failover \
  -d '{"primary_node": "node-1", "backup_node": "node-2"}'
```

---

## 🚀 Обновление и развертывание

### Canary Deployment

```bash
# Запустить canary deployment
python scripts/canary_deployment.py \
  --image=registry.gitlab.com/x0tta6bl4/x0tta6bl4:v3.1 \
  --canary-percent=10

# Мониторинг canary
kubectl get pods -l version=canary

# Продвинуть canary
python scripts/canary_deployment.py --promote

# Откатить canary
python scripts/canary_deployment.py --rollback
```

### Blue-Green Deployment

```bash
# Развернуть green версию
kubectl apply -f k8s/green/

# Переключить трафик
kubectl patch service/x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'

# Проверить green
kubectl get pods -l version=green

# Откатить к blue
kubectl patch service/x0tta6bl4 -p '{"spec":{"selector":{"version":"blue"}}}'
```

---

## 🔄 MAPE-K цикл

### Проверка MAPE-K статуса

```bash
# Статус цикла
curl http://localhost:8080/api/v1/mapek/status

# История инцидентов
curl http://localhost:8080/api/v1/mapek/history

# Метрики цикла
curl http://localhost:8080/metrics | grep mape_k_cycle
```

### Ручной запуск цикла

```bash
# Запустить цикл вручную
curl -X POST http://localhost:8080/api/v1/mapek/run-cycle
```

### Настройка thresholds

```bash
# Получить текущие thresholds
curl http://localhost:8080/api/v1/mapek/thresholds

# Обновить threshold (через DAO)
curl -X POST http://localhost:8080/api/v1/dao/proposals \
  -d '{
    "title": "Update CPU threshold",
    "description": "Increase CPU threshold to 95%",
    "actions": [{
      "type": "update_threshold",
      "metric": "cpu_percent",
      "value": 95.0
    }]
  }'
```

---

## 🌐 Mesh Network

### Проверка mesh топологии

```bash
# Список пиров
curl http://localhost:8080/api/v1/mesh/peers

# Топология
curl http://localhost:8080/api/v1/mesh/topology

# Статус узла
curl http://localhost:8080/api/v1/mesh/node/status
```

### Batman-adv операции

```bash
# Проверить originators
kubectl exec -it <pod-name> -- batctl o

# Проверить gateways
kubectl exec -it <pod-name> -- batctl g

# Проверить neighbors
kubectl exec -it <pod-name> -- batctl n

# Проверить трансил
kubectl exec -it <pod-name> -- batctl tr
```

---

## 🔐 SPIFFE/SPIRE

### Проверка SVID

```bash
# Fetch X.509 SVID
kubectl exec -it <pod-name> -- spire-agent api fetch x509

# Fetch JWT SVID
kubectl exec -it <pod-name> -- spire-agent api fetch jwt -audience x0tta6bl4.mesh

# Проверить expiry
kubectl exec -it <pod-name> -- spire-agent api fetch x509 | grep expires
```

### Управление workload entries

```bash
# Список entries
kubectl exec -it <pod-name> -- spire-server entry show

# Создать entry
kubectl exec -it <pod-name> -- spire-server entry create \
  -spiffeID spiffe://x0tta6bl4.mesh/workload/test \
  -parentID spiffe://x0tta6bl4.mesh/node/node-1 \
  -selector unix:uid:1000

# Удалить entry
kubectl exec -it <pod-name> -- spire-server entry delete -entryID <entry-id>
```

---

## 📞 Экстренные процедуры

### Полный откат

```bash
# Откатить deployment
kubectl rollout undo deployment/x0tta6bl4

# Откатить к конкретной версии
kubectl rollout undo deployment/x0tta6bl4 --to-revision=2

# Проверить историю
kubectl rollout history deployment/x0tta6bl4
```

### Остановка системы

```bash
# Graceful shutdown
kubectl scale deployment/x0tta6bl4 --replicas=0

# Принудительная остановка
kubectl delete deployment/x0tta6bl4
```

### Восстановление из backup

```bash
# Восстановить из backup
python scripts/backup_restore.py --restore --backup-id=<backup-id>

# Проверить backup статус
python scripts/backup_restore.py --list-backups
```

---

## 📚 Дополнительные ресурсы

- **Quick Reference**: `docs/QUICK_REFERENCE.md`
- **Emergency Procedures**: `docs/EMERGENCY_PROCEDURES.md`
- **On-Call Runbook**: `docs/team/ON_CALL_RUNBOOK.md`
- **Incident Response Plan**: `docs/team/INCIDENT_RESPONSE_PLAN.md`

---

**Последнее обновление:** 2026-01-XX  
**Версия:** 2.0  
**Статус:** ✅ Production-ready

