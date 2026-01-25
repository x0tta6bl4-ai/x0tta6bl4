# Production Runbooks
**Дата:** 2026-01-07  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ⏳ В процессе подготовки

---

## 📋 Overview

**Цель:** Операционные runbooks для production incidents

**Структура:**
- Alert-based runbooks
- Common procedures
- Troubleshooting guides
- Escalation procedures

---

## 🚨 Alert Runbooks

### Alert: X0TTA6BL4HealthCheckFailed

**Severity:** Critical  
**Description:** Service is down for more than 2 minutes

**Steps:**
1. **Verify the issue:**
   ```bash
   kubectl get pods -n x0tta6bl4-staging
   kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging --tail=50
   curl -v http://localhost:8080/health
   ```

2. **Check pod status:**
   ```bash
   kubectl describe pod <pod-name> -n x0tta6bl4-staging
   kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp'
   ```

3. **Check resource constraints:**
   ```bash
   kubectl top pods -n x0tta6bl4-staging
   kubectl describe node <node-name>
   ```

4. **Restart if needed:**
   ```bash
   kubectl rollout restart deployment/x0tta6bl4-staging -n x0tta6bl4-staging
   ```

5. **Verify recovery:**
   ```bash
   kubectl rollout status deployment/x0tta6bl4-staging -n x0tta6bl4-staging
   curl http://localhost:8080/health
   ```

**Escalation:** If not resolved in 15 minutes, escalate to on-call engineer

---

### Alert: X0TTA6BL4PQCHandshakeFailure

**Severity:** Critical  
**Description:** High PQC handshake failure rate

**Steps:**
1. **Check PQC metrics:**
   ```bash
   curl -s http://localhost:8080/metrics | grep pqc_handshake
   ```

2. **Check liboqs availability:**
   ```bash
   kubectl exec -n x0tta6bl4-staging <pod-name> -- python3 -c "import liboqs; print('OK')"
   ```

3. **Check certificates:**
   ```bash
   kubectl exec -n x0tta6bl4-staging <pod-name> -- ls -la /etc/x0tta6bl4/certs/
   ```

4. **Check logs:**
   ```bash
   kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i "pqc\|handshake\|liboqs"
   ```

5. **Restart if needed:**
   ```bash
   kubectl rollout restart deployment/x0tta6bl4-staging -n x0tta6bl4-staging
   ```

**Escalation:** If security-related, escalate to security team immediately

---

### Alert: X0TTA6BL4HighErrorRate

**Severity:** Warning  
**Description:** Error rate above threshold

**Steps:**
1. **Check error rate:**
   ```bash
   curl -s http://localhost:8080/metrics | grep errors_total
   ```

2. **Check error logs:**
   ```bash
   kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i error | tail -50
   ```

3. **Check recent changes:**
   ```bash
   kubectl rollout history deployment/x0tta6bl4-staging -n x0tta6bl4-staging
   ```

4. **Check dependencies:**
   ```bash
   curl -s http://localhost:8080/health | jq .dependencies
   ```

5. **Rollback if needed:**
   ```bash
   kubectl rollout undo deployment/x0tta6bl4-staging -n x0tta6bl4-staging
   ```

**Escalation:** If error rate > 5%, escalate to critical

---

### Alert: X0TTA6BL4HighLatency

**Severity:** Warning  
**Description:** P95 latency above threshold

**Steps:**
1. **Check latency metrics:**
   ```bash
   curl -s http://localhost:8080/metrics | grep request_duration
   ```

2. **Check resource usage:**
   ```bash
   kubectl top pods -n x0tta6bl4-staging
   ```

3. **Check network:**
   ```bash
   kubectl exec -n x0tta6bl4-staging <pod-name> -- ping -c 5 <other-pod-ip>
   ```

4. **Check mesh status:**
   ```bash
   curl -s http://localhost:8080/mesh/status | jq .
   ```

5. **Scale if needed:**
   ```bash
   kubectl scale deployment/x0tta6bl4-staging --replicas=7 -n x0tta6bl4-staging
   ```

**Escalation:** If latency > 1s for >10 minutes, escalate

---

### Alert: X0TTA6BL4HighCPUUsage

**Severity:** Warning  
**Description:** CPU usage above 80%

**Steps:**
1. **Check CPU usage:**
   ```bash
   kubectl top pods -n x0tta6bl4-staging
   ```

2. **Check processes:**
   ```bash
   kubectl exec -n x0tta6bl4-staging <pod-name> -- top -n 1
   ```

3. **Check for runaway processes:**
   ```bash
   kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-staging | grep -i "loop\|infinite"
   ```

4. **Scale horizontally:**
   ```bash
   kubectl scale deployment/x0tta6bl4-staging --replicas=7 -n x0tta6bl4-staging
   ```

5. **Increase resources if needed:**
   ```bash
   kubectl patch deployment x0tta6bl4-staging -n x0tta6bl4-staging \
     -p '{"spec":{"template":{"spec":{"containers":[{"name":"x0tta6bl4","resources":{"limits":{"cpu":"3000m"}}}]}}}}'
   ```

**Escalation:** If CPU > 95% for >15 minutes, escalate

---

### Alert: X0TTA6BL4FrequentRestarts

**Severity:** Warning  
**Description:** Pod restarting frequently

**Steps:**
1. **Check restart count:**
   ```bash
   kubectl get pods -n x0tta6bl4-staging
   kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep Restart
   ```

2. **Check crash logs:**
   ```bash
   kubectl logs -n x0tta6bl4-staging <pod-name> --previous
   ```

3. **Check events:**
   ```bash
   kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp' | grep <pod-name>
   ```

4. **Check resource limits:**
   ```bash
   kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep -A 5 "Limits"
   ```

5. **Check OOMKilled:**
   ```bash
   kubectl describe pod <pod-name> -n x0tta6bl4-staging | grep -i "oom\|killed"
   ```

**Escalation:** If >3 restarts in 15 minutes, escalate

---

## 🔧 Common Procedures

### Deployment

**Rollout:**
```bash
# Deploy new version
helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f values-staging.yaml \
  --set image.tag="3.4.0" \
  -n x0tta6bl4-staging

# Monitor rollout
kubectl rollout status deployment/x0tta6bl4-staging -n x0tta6bl4-staging

# Verify health
curl http://localhost:8080/health
```

**Rollback:**
```bash
# Rollback to previous version
helm rollback x0tta6bl4-staging -n x0tta6bl4-staging

# Or kubectl
kubectl rollout undo deployment/x0tta6bl4-staging -n x0tta6bl4-staging
```

### Scaling

**Scale Up:**
```bash
kubectl scale deployment/x0tta6bl4-staging --replicas=10 -n x0tta6bl4-staging
```

**Scale Down:**
```bash
kubectl scale deployment/x0tta6bl4-staging --replicas=3 -n x0tta6bl4-staging
```

### Logs

**View logs:**
```bash
# All pods
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4-staging --tail=100

# Specific pod
kubectl logs -n x0tta6bl4-staging <pod-name> --tail=100 -f

# Previous container (if crashed)
kubectl logs -n x0tta6bl4-staging <pod-name> --previous
```

### Debugging

**Exec into pod:**
```bash
kubectl exec -it -n x0tta6bl4-staging <pod-name> -- /bin/bash
```

**Check environment:**
```bash
kubectl exec -n x0tta6bl4-staging <pod-name> -- env | grep X0TTA6BL4
```

**Check network:**
```bash
kubectl exec -n x0tta6bl4-staging <pod-name> -- netstat -tulpn
```

---

## 📞 Escalation Procedures

### Level 1: On-Call Engineer
- **Response Time:** <15 minutes
- **Responsibilities:**
  - Initial triage
  - Run runbooks
  - Basic troubleshooting
  - Escalate if needed

### Level 2: Senior Engineer
- **Response Time:** <30 minutes
- **Triggers:**
  - Critical alerts not resolved in 15 minutes
  - Security incidents
  - Data loss incidents
  - Multiple service failures

### Level 3: Engineering Lead
- **Response Time:** <1 hour
- **Triggers:**
  - Production outage >30 minutes
  - Security breach
  - Customer impact >10%
  - Infrastructure failure

---

## 📝 Incident Response Template

**File:** `INCIDENT_REPORT_TEMPLATE.md`

**Fields:**
- Incident ID
- Severity (Critical/Warning/Info)
- Start Time
- Detection Method (Alert/Manual/Monitoring)
- Affected Services
- Impact (Users/Revenue/Reputation)
- Root Cause
- Resolution
- Resolution Time
- Lessons Learned
- Action Items

---

**Статус:** ⏳ В процессе подготовки  
**Следующий шаг:** Create incident response template and test runbooks

