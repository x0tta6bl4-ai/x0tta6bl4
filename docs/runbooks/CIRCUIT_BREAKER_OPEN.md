# Runbook: Circuit Breaker Open

**Severity**: Warning → Critical (if prolonged)
**Alert**: `CircuitBreakerOpen`, `CircuitBreakerFlapping`, `HighCircuitBreakerFailureRate`, `MaaSBillingFailure`
**MTTR target**: < 30 min
**Owner**: Platform / MaaS team

---

## 1. Symptoms

| Signal | Value |
|--------|-------|
| Alert `CircuitBreakerOpen` | `circuit_breaker_state == 1` for > 1 min |
| API returns 503 with `"Circuit breaker open"` body | Downstream rejection |
| `circuit_breaker_failures_total` rate increasing | Dependency degrading |
| Billing/escrow/marketplace operations failing | stripe/db circuit tripped |

---

## 2. Immediate triage (< 5 min)

```bash
# 1. Identify which circuit(s) are open via metrics
curl -s https://api.x0tta6bl4.io/metrics | grep circuit_breaker_state

# 2. Check API health detail for degraded deps
curl -s https://api.x0tta6bl4.io/health/detailed | jq '.checks[] | select(.status != "healthy")'

# 3. Check recent logs for the failing dependency
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api --tail=200 | \
  grep -i "circuit\|breaker\|open\|failure"
```

**Common circuits and their dependencies:**

| Circuit Name | Dependency | Typical failure cause |
|-------------|-----------|----------------------|
| `stripe_dependency` | Stripe API | Rate limit, outage, bad key |
| `db_dependency` | PostgreSQL | Connection pool exhausted, migration issue |
| `redis_dependency` | Redis | See REDIS_FAILURE.md |
| `governance_dependency` | On-chain RPC | Node down, chain congestion |
| `maas_billing` | Billing pipeline | Webhook timeout, Stripe unavailable |

---

## 3. Root cause by circuit

### 3a. Stripe circuit (`stripe_dependency`)

```bash
# Check Stripe status
curl -s https://status.stripe.com/api/v2/status.json | jq .status

# Check our Stripe API key is valid
kubectl get secret -n x0tta6bl4 stripe-secret -o jsonpath='{.data.api_key}' | \
  base64 -d | xargs -I{} curl -su {}:"" https://api.stripe.com/v1/account | jq .id

# Check rate limit headers in logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | grep "stripe\|Rate-Limit"
```

**Fixes**:
- Stripe outage: wait; circuit auto-recovers after `recovery_timeout`
- Rate limit: reduce request rate or request limit increase from Stripe
- Bad API key: rotate `STRIPE_SECRET_KEY` in Kubernetes secret + rolling restart

### 3b. DB circuit (`db_dependency`)

```bash
# Check DB connection pool
curl -s https://api.x0tta6bl4.io/metrics | grep sqlalchemy_pool

# Check DB status
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  python3 -c "from src.database import engine; print(engine.pool.status())"

# Check for long-running queries (PostgreSQL)
kubectl exec -n x0tta6bl4 deploy/postgres -- \
  psql -U postgres -c "SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity WHERE state='active' ORDER BY duration DESC LIMIT 10;"
```

**Fixes**:
- Connection pool exhausted: increase `DB_POOL_SIZE` env var or kill idle connections
- Long-running query: `SELECT pg_terminate_backend(<pid>);`
- DB disk full: expand PV or purge old data

### 3c. Governance/RPC circuit

```bash
# Check RPC endpoint reachability
curl -X POST https://$POLYGON_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Check chain sync status
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | grep -i "governance\|rpc\|chain"
```

**Fixes**:
- RPC endpoint down: switch to backup RPC in env var `POLYGON_RPC_URL`
- Chain congestion: increase `governance_dependency` timeout via env:
  `RELIABILITY_GOVERNANCE_TIMEOUT_SECONDS=30`

---

## 4. Force circuit reset (use with caution)

The circuit auto-recovers after `recovery_timeout` seconds (default 30 s).
**Do not force-reset unless the underlying issue is confirmed resolved.**

```bash
# Via API (if admin endpoint available)
curl -X POST https://api.x0tta6bl4.io/api/v1/admin/circuit-breakers/reset \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"circuit": "stripe_dependency"}'

# Or restart the API pod to reset in-memory state
kubectl rollout restart -n x0tta6bl4 deployment/x0tta6bl4-api
```

---

## 5. Verify recovery

```bash
# Watch circuit state return to 0 (closed)
watch -n 5 'curl -s https://api.x0tta6bl4.io/metrics | grep circuit_breaker_state'

# Confirm business operations succeed
curl -X POST https://api.x0tta6bl4.io/api/v1/maas/billing/test-ping \
  -H "Authorization: Bearer $API_TOKEN"
```

---

## 6. Adjust circuit breaker policy (if flapping)

For circuit-level tuning, set env vars on the deployment:

```yaml
# Example: increase failure threshold and recovery timeout for stripe
- name: RELIABILITY_STRIPE_FAILURE_THRESHOLD
  value: "10"
- name: RELIABILITY_STRIPE_RECOVERY_TIMEOUT_SECONDS
  value: "60"
- name: RELIABILITY_STRIPE_TIMEOUT_SECONDS
  value: "15"
```

Apply: `kubectl set env deployment/x0tta6bl4-api RELIABILITY_STRIPE_FAILURE_THRESHOLD=10`

---

## 7. Post-incident

- [ ] Identify root cause of dependency failure
- [ ] Update baseline policy if default thresholds proved too aggressive
- [ ] File ticket with third-party provider if applicable
- [ ] Add regression test if new failure mode discovered

---

## 8. Escalation

| Wait | Action |
|------|--------|
| 5 min | Identify circuit and start root cause analysis |
| 15 min | Page dependency owner (Stripe: provider; DB: infra team) |
| 30 min | Incident commander — SLA breach imminent |
