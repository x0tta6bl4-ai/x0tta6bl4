# 📞 On-Call Runbook для x0tta6bl4

**Версия:** 3.0.0  
**Дата:** 30 ноября 2025  
**Статус:** Production Ready

---

## 🚨 КРИТИЧЕСКИЕ АЛЕРТЫ

### PQC Handshake Failure
**Severity:** CRITICAL  
**Alert:** `PQC_HANDSHAKE_FAILURE`

**Симптомы:**
- PQC handshake failures > 0
- Security alerts в логах
- Connections rejected

**Действия:**
1. Проверить логи: `docker logs x0tta6bl4-staging | grep PQC`
2. Проверить liboqs availability: `ldconfig -p | grep liboqs`
3. Проверить fallback mode: `curl http://localhost:8080/security/pqc/status`
4. Если fallback enabled → **IMMEDIATE ESCALATION** (security issue)
5. Проверить certificate validity
6. Restart service если необходимо

**Escalation:** CTO (if fallback enabled)

---

### High Error Rate
**Severity:** CRITICAL  
**Alert:** `HIGH_ERROR_RATE`

**Симптомы:**
- Error rate > 5%
- Failed requests increasing
- Service degradation

**Действия:**
1. Проверить error logs: `docker logs x0tta6bl4-staging | grep ERROR`
2. Проверить metrics: `curl http://localhost:8080/metrics | grep error`
3. Проверить resource usage: CPU, memory, disk
4. Проверить network connectivity
5. Если error rate > 10% → **ROLLBACK**
6. Если error rate 5-10% → Monitor closely, prepare rollback

**Rollback Trigger:** Error rate > 10% for 5 minutes

---

### High Latency
**Severity:** WARNING → CRITICAL  
**Alert:** `HIGH_LATENCY`

**Симптомы:**
- Latency P95 > 200ms
- Slow response times
- Timeout errors

**Действия:**
1. Проверить latency metrics: `curl http://localhost:8080/metrics | grep latency`
2. Проверить CPU usage: `docker stats x0tta6bl4-staging`
3. Проверить network latency: `ping mesh-peers`
4. Проверить database/backend services
5. Если latency > 500ms → **ROLLBACK**
6. Если latency 200-500ms → Scale up resources

**Rollback Trigger:** Latency P95 > 500ms for 10 minutes

---

### Memory Exhaustion
**Severity:** CRITICAL  
**Alert:** `MEMORY_EXHAUSTION`

**Симптомы:**
- Memory usage > 2.4GB
- OOM (Out of Memory) errors
- Service crashes

**Действия:**
1. Проверить memory: `docker stats x0tta6bl4-staging`
2. Проверить LRU maps: `bpftool map show`
3. Проверить connection count
4. Restart service if necessary
5. Scale down connections if needed
6. If OOM → **IMMEDIATE RESTART**

**Escalation:** Team Lead (if OOM)

---

### Service Down
**Severity:** CRITICAL  
**Alert:** `SERVICE_DOWN`

**Симптомы:**
- Health endpoint returns 503/500
- Service not responding
- All requests failing

**Действия:**
1. Проверить service status: `docker ps | grep x0tta6bl4`
2. Проверить health: `curl http://localhost:8080/health`
3. Проверить logs: `docker logs x0tta6bl4-staging --tail 100`
4. Restart service: `docker restart x0tta6bl4-staging`
5. Если не восстанавливается → **ROLLBACK**
6. Если восстанавливается → Monitor closely

**Rollback Trigger:** Service down for > 5 minutes

---

## 🔄 ROLLBACK PROCEDURE

### Автоматический Rollback
**Триггеры:**
- Error rate > 10% for 5 minutes
- Latency P95 > 500ms for 10 minutes
- Service down for > 5 minutes

**Процесс:**
1. Canary deployment автоматически откатывается
2. Traffic возвращается к предыдущей версии
3. Alert отправляется команде
4. Мониторинг продолжается

### Manual Rollback
**Команда:**
```bash
# Stop current deployment
docker-compose -f staging/docker-compose.staging.yml down

# Deploy previous version
docker-compose -f staging/docker-compose.staging.yml up -d --scale control-plane=1

# Verify
curl http://localhost:8080/health
```

**Проверка:**
1. Health endpoint: `curl http://localhost:8080/health`
2. Metrics: `curl http://localhost:8080/metrics`
3. Smoke tests: `bash staging/smoke_tests.sh`

---

## 📊 МОНИТОРИНГ

### Ключевые Метрики
- **Throughput:** > 6,000 req/sec (target: 6,800)
- **Latency P95:** < 100ms (warning: > 150ms, critical: > 200ms)
- **Error Rate:** < 0.1% (warning: > 1%, critical: > 5%)
- **Memory:** < 2.4GB (warning: > 2GB, critical: > 2.4GB)
- **CPU:** < 80% (warning: > 80%, critical: > 95%)

### Dashboards
- **Grafana:** http://localhost:3000
- **Prometheus:** http://localhost:9091
- **Health:** http://localhost:8080/health
- **Metrics:** http://localhost:8080/metrics

---

## 🔧 COMMON ISSUES

### Issue: High CPU Usage
**Причина:** High traffic, inefficient code
**Решение:**
1. Check hot paths: `python3 -m src.performance.optimizer`
2. Scale up resources
3. Optimize code if needed

### Issue: Network Partition
**Причина:** Network issues, mesh connectivity
**Решение:**
1. Check mesh peers: `curl http://localhost:8080/mesh/peers`
2. Check network connectivity
3. Restart mesh router if needed

### Issue: PQC Handshake Slow
**Причина:** liboqs performance, high load
**Решение:**
1. Check PQC metrics: `curl http://localhost:8080/metrics | grep pqc`
2. Check liboqs version
3. Consider caching if appropriate

---

## 📞 ESCALATION PATH

### Level 1: On-Call Engineer
- Monitor metrics
- Respond to alerts
- Execute runbook procedures
- Execute rollback if needed

### Level 2: Team Lead
- Coordinate response
- Make rollback decision
- Communicate with stakeholders
- Escalate to Level 3 if needed

### Level 3: CTO
- Executive decisions
- External communication
- Final go/no-go decisions

---

## 📝 LOGGING

### Логи для проверки
```bash
# Application logs
docker logs x0tta6bl4-staging --tail 100

# Error logs
docker logs x0tta6bl4-staging | grep ERROR

# PQC logs
docker logs x0tta6bl4-staging | grep PQC

# Security logs
docker logs x0tta6bl4-staging | grep SECURITY
```

### Логи для сохранения
- All critical alerts
- All rollbacks
- All security incidents
- Performance degradation events

---

## ✅ POST-INCIDENT

### После инцидента:
1. Document incident in incident log
2. Root cause analysis
3. Update runbook if needed
4. Team retrospective
5. Prevent recurrence

---

**Last Updated:** 30 ноября 2025  
**Next Review:** After first production incident

