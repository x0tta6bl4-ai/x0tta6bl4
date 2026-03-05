# Runbook: High Latency

**Severity**: Warning / Critical
**Alert**: `MaaSHighLatencyP95`, `MaaSCriticalLatencyP99`, `DatabaseQuerySlowP99`
**MTTR target**: < 30 min
**Owner**: Platform team

---

## 1. Symptoms

| Signal | Value |
|--------|-------|
| `MaaSHighLatencyP95` fires | p95 > 500 ms on any endpoint |
| `MaaSCriticalLatencyP99` fires | p99 > 2 s on any endpoint |
| User-visible slow responses | API timeout errors |
| `DatabaseQuerySlowP99` fires | DB p99 query > 1 s |

---

## 2. Immediate triage (< 5 min)

```bash
# 1. Identify slow endpoints from metrics
curl -s https://api.x0tta6bl4.io/metrics | \
  grep 'http_request_duration_seconds_sum\|_count' | \
  awk '{print $1, $2}' | sort -k2 -rn | head -20

# 2. Check current active requests
curl -s https://api.x0tta6bl4.io/health/detailed | jq .

# 3. Check resource saturation
kubectl top pods -n x0tta6bl4
kubectl top nodes

# 4. Check for slow DB queries
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT pid, now()-query_start AS dur, left(query,80) FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '1s' ORDER BY dur DESC;"
```

---

## 3. Root cause paths

### 3a. CPU saturation (API pods)

```bash
kubectl top pods -n x0tta6bl4 --sort-by=cpu | head -10

# Check HPA status
kubectl get hpa -n x0tta6bl4
kubectl describe hpa -n x0tta6bl4 x0tta6bl4-api-hpa
```

**Fix**: Scale horizontally
```bash
kubectl scale deployment -n x0tta6bl4 x0tta6bl4-api --replicas=5
# Or trigger HPA: ensure CPU metric server is available
```

### 3b. DB connection pool wait

```bash
# Check pool checkout time
curl -s https://api.x0tta6bl4.io/metrics | grep sqlalchemy_pool_checkedout
curl -s https://api.x0tta6bl4.io/metrics | grep sqlalchemy_pool_overflow

# Check DB connection count
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

**Fix**:
```bash
# Increase pool size temporarily
kubectl set env deployment/x0tta6bl4-api DB_POOL_SIZE=20 DB_MAX_OVERFLOW=10

# Kill idle connections older than 5 min
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE state='idle' AND now()-state_change > interval '5 min';"
```

### 3c. Slow / missing DB index

```bash
# Find sequential scans on large tables
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT relname, seq_scan, idx_scan FROM pg_stat_user_tables
   WHERE seq_scan > idx_scan ORDER BY seq_scan DESC LIMIT 10;"

# Find slow queries via pg_stat_statements
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT query, mean_exec_time, calls FROM pg_stat_statements
   ORDER BY mean_exec_time DESC LIMIT 10;"
```

**Fix**: Add missing index (coordinate with migration policy):
```sql
CREATE INDEX CONCURRENTLY idx_mesh_instances_owner_id ON mesh_instances(owner_id);
```

### 3d. Redis latency (cache miss storm)

```bash
# Redis command latency
kubectl exec -n x0tta6bl4 deploy/redis -- redis-cli --latency-history -i 1
kubectl exec -n x0tta6bl4 deploy/redis -- redis-cli INFO stats | grep instantaneous
```

**Fix**: Ensure cache warming is active; increase TTL for hot keys.

### 3e. External API slow (Stripe, RPC)

```bash
# Check Stripe latency in logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api --tail=500 | \
  grep -i "stripe\|duration_ms" | grep -v DEBUG

# Check circuit breaker call duration
curl -s https://api.x0tta6bl4.io/metrics | \
  grep circuit_breaker_call_duration_seconds
```

**Fix**: Lower timeout and let circuit breaker handle; return cached/degraded response.

### 3f. Memory pressure / GC pauses (Python)

```bash
# Check RSS memory of API pods
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  python3 -c "import resource; print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)"

# Check for memory leak: watch RSS over time
kubectl top pods -n x0tta6bl4 --watch
```

**Fix**: Rolling restart to reclaim memory; profile with `memray` in staging.

---

## 4. Short-term mitigations

```bash
# A. Shed load: enable rate limiting on expensive endpoints
kubectl set env deployment/x0tta6bl4-api RATE_LIMIT_MARKETPLACE_PER_MINUTE=100

# B. Increase API replicas
kubectl scale deployment -n x0tta6bl4 x0tta6bl4-api --replicas=8

# C. Return stale cache for non-critical reads (set longer TTL)
kubectl set env deployment/x0tta6bl4-api CACHE_TTL_SECONDS=600

# D. Route traffic to second region (if multi-region deployed)
# Update Caddyfile or Gateway ingress weights
```

---

## 5. Verify resolution

```bash
# Watch p95 latency return below 500 ms
watch -n 10 'curl -s https://api.x0tta6bl4.io/metrics | \
  grep http_request_duration_seconds | grep le=\"0.5\"'

# Confirm health endpoints return 200
curl -si https://api.x0tta6bl4.io/health/live
curl -si https://api.x0tta6bl4.io/health/ready
```

---

## 6. Post-incident

- [ ] Identify root endpoint + query causing slowdown
- [ ] Add missing index / query optimization in next sprint
- [ ] Set HPA min-replicas to prevent recurrence
- [ ] Review SLO targets if consistently tight
- [ ] Update baseline latency benchmark in `plans/` docs

---

## 7. Escalation

| Wait | Action |
|------|--------|
| 5 min | Apply immediate mitigation (scale/rate-limit) |
| 15 min | Page DB/infra team if DB-related |
| 30 min | Incident commander if user-visible SLA breach |
