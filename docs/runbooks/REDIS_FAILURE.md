# Runbook: Redis Failure / Unavailability

**Severity**: Critical
**Alert**: `RedisUnavailable`, `RedisHighMemoryUsage`, `RedisConnectionPoolExhausted`
**MTTR target**: < 30 min
**Owner**: Platform team

---

## 1. Symptoms

| Signal | Value |
|--------|-------|
| Alert `RedisUnavailable` fires | `redis_up == 0` for > 1 min |
| API responses have `X-Degraded-Dependencies: redis` header | Cache bypass active |
| Elevated latency on Marketplace / Telemetry endpoints | In-memory fallback slower |
| 500 errors on endpoints requiring idempotency-key dedup | Redis-backed dedup down |

---

## 2. Immediate triage (< 5 min)

```bash
# 1. Check pod/container status
kubectl get pods -n x0tta6bl4 | grep redis

# 2. Check logs for the Redis pod
kubectl logs -n x0tta6bl4 -l app=redis --tail=100

# 3. Verify connectivity from API pod
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  redis-cli -u "$REDIS_URL" ping

# 4. Check Sentinel (if configured)
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  redis-cli -h "$REDIS_SENTINEL_HOST" -p 26379 sentinel masters
```

---

## 3. Root cause paths

### 3a. Pod OOMKilled / crash

```bash
kubectl describe pod -n x0tta6bl4 <redis-pod> | grep -A5 OOM
# If OOM: check maxmemory config and current usage
redis-cli -u "$REDIS_URL" INFO memory | grep used_memory_human
```

**Fix**: Increase `maxmemory` limit in Helm values or reduce TTLs.
`helm upgrade x0tta6bl4-redis bitnami/redis --set master.resources.limits.memory=2Gi`

### 3b. Network partition / DNS failure

```bash
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  nslookup redis-service.x0tta6bl4.svc.cluster.local
kubectl get svc -n x0tta6bl4 redis-service
kubectl get endpoints -n x0tta6bl4 redis-service
```

**Fix**: Check NetworkPolicy, Service selectors, and pod labels.

### 3c. TLS certificate expired (if TLS enabled)

```bash
redis-cli -u "rediss://$REDIS_HOST:6380" --tls ping
openssl s_client -connect $REDIS_HOST:6380 2>&1 | grep -E "NotBefore|NotAfter"
```

**Fix**: Rotate certificate via cert-manager or manual renewal.

### 3d. Persistence / AOF corruption

```bash
kubectl logs -n x0tta6bl4 <redis-pod> | grep -i "corrupt\|error\|aof"
# If corrupt AOF: rename and restart
kubectl exec -n x0tta6bl4 <redis-pod> -- \
  redis-cli BGREWRITEAOF
```

---

## 4. Recovery steps

```bash
# Option A: Rolling restart (if pod is stuck)
kubectl rollout restart -n x0tta6bl4 deployment/redis

# Option B: Scale up replicas temporarily
kubectl scale -n x0tta6bl4 deployment/redis --replicas=2

# Option C: Failover to Sentinel replica
redis-cli -h $SENTINEL_HOST -p 26379 SENTINEL failover x0tta6bl4-redis
```

---

## 5. Verify recovery

```bash
# API health should no longer show redis as degraded
curl -s https://api.x0tta6bl4.io/health/detailed | jq .checks

# Confirm no X-Degraded-Dependencies header
curl -si https://api.x0tta6bl4.io/api/v1/maas/status | grep Degraded

# Confirm Redis roundtrip in health endpoint
curl -s https://api.x0tta6bl4.io/health/ready | jq .
```

---

## 6. Post-incident

- [ ] Update `docs/operations/DISASTER_RECOVERY_PLAN.md` with new failure mode if novel
- [ ] File capacity ticket if OOM was root cause
- [ ] Check if idempotency-key cache needs backfill (unlikely — short TTL)
- [ ] Review alert threshold if false positive

---

## 7. Escalation

| Wait | Action |
|------|--------|
| 5 min | Page on-call platform lead |
| 15 min | Engage DB/infra team |
| 30 min | Incident commander escalation — SLA breach risk |
