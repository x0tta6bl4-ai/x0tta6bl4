# 🚨 Emergency Procedures

**Версия:** 3.0.0  
**Дата:** 30 ноября 2025

---

## 🚨 CRITICAL INCIDENTS

### Service Down
**Severity:** SEV-1  
**Response Time:** 15 minutes

**Actions:**
1. Check service status: `docker ps | grep x0tta6bl4`
2. Check health: `curl http://localhost:8080/health`
3. Check logs: `docker logs x0tta6bl4-staging --tail 100`
4. Restart service: `docker restart x0tta6bl4-staging`
5. If not recovered in 5 minutes → **ROLLBACK**

**Rollback:**
```bash
docker-compose -f staging/docker-compose.staging.yml down
docker-compose -f staging/docker-compose.staging.yml up -d --scale control-plane=1
```

---

### High Error Rate (>10%)
**Severity:** SEV-1  
**Response Time:** 15 minutes

**Actions:**
1. Check error logs: `docker logs x0tta6bl4-staging | grep ERROR`
2. Check metrics: `curl http://localhost:8080/metrics | grep error`
3. Identify root cause
4. If error rate > 10% for 5 minutes → **AUTO-ROLLBACK**
5. If error rate 5-10% → Monitor closely, prepare rollback

**Auto-Rollback:**
```bash
bash scripts/production_toolkit.sh rollback
```

---

### PQC Fallback Enabled
**Severity:** SEV-1 (Security)  
**Response Time:** IMMEDIATE

**Actions:**
1. Check PQC status: `curl http://localhost:8080/security/pqc/status`
2. Check logs: `docker logs x0tta6bl4-staging | grep PQC`
3. **IMMEDIATE ROLLBACK** (security issue)
4. Escalate to CTO
5. Investigate root cause

**Rollback:**
```bash
# Immediate rollback
bash scripts/production_toolkit.sh rollback
```

---

### High Latency (>500ms)
**Severity:** SEV-2  
**Response Time:** 1 hour

**Actions:**
1. Check latency metrics: `curl http://localhost:8080/metrics | grep latency`
2. Check CPU usage: `docker stats x0tta6bl4-staging`
3. Check network: `ping mesh-peers`
4. If latency > 500ms for 10 minutes → **ROLLBACK**
5. If latency 200-500ms → Scale up resources

**Rollback:**
```bash
bash scripts/production_toolkit.sh rollback
```

---

### Memory Exhaustion
**Severity:** SEV-1  
**Response Time:** 15 minutes

**Actions:**
1. Check memory: `docker stats x0tta6bl4-staging`
2. Check LRU maps: `bpftool map show`
3. Restart service if necessary
4. If OOM → **IMMEDIATE RESTART**
5. Escalate to Team Lead

**Restart:**
```bash
docker restart x0tta6bl4-staging
```

---

## 🔄 ROLLBACK PROCEDURES

### Automatic Rollback
**Triggers:**
- Error rate > 10% for 5 minutes
- Latency P95 > 500ms for 10 minutes
- Service down for > 5 minutes

**Process:**
1. System automatically triggers rollback
2. Traffic returns to previous version
3. Alert sent to team
4. Monitoring continues

### Manual Rollback
**Command:**
```bash
# Stop current
docker-compose -f staging/docker-compose.staging.yml down

# Deploy previous
docker-compose -f staging/docker-compose.staging.yml up -d --scale control-plane=1

# Verify
curl http://localhost:8080/health
```

**Verification:**
1. Health endpoint: `curl http://localhost:8080/health`
2. Metrics: `curl http://localhost:8080/metrics`
3. Smoke tests: `bash staging/smoke_tests.sh`

---

## 📞 ESCALATION

### When to Escalate

**To Team Lead:**
- SEV-1 incidents not resolved in 30 minutes
- Multiple services affected
- Security incidents (PQC fallback)

**To CTO:**
- SEV-1 incidents not resolved in 1 hour
- Data loss or corruption
- Security breach
- External communication needed

---

## 📝 POST-INCIDENT

### After Resolution
1. Document incident in incident log
2. Root cause analysis
3. Update runbook if needed
4. Team retrospective
5. Prevent recurrence

---

**Last Updated:** 30 ноября 2025

