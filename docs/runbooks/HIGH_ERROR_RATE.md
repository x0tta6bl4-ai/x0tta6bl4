# Runbook: High Error Rate (5xx)

**Severity**: Warning → Critical
**Alert**: `MaaSHighErrorRate`, `MaaSCriticalErrorRate`
**MTTR target**: < 30 min
**Owner**: Platform team

---

## 1. Symptoms

| Signal | Value |
|--------|-------|
| `MaaSHighErrorRate` fires | 5xx rate > 1% on any endpoint for 5 min |
| `MaaSCriticalErrorRate` fires | Global 5xx rate > 5% for 2 min |
| Users reporting failed API calls | Client-visible errors |
| Alert trace IDs in `X-Trace-ID` header | Correlated errors |

---

## 2. Immediate triage (< 5 min)

```bash
# 1. Identify affected endpoints
curl -s https://api.x0tta6bl4.io/metrics | \
  grep 'http_requests_total{.*status="5' | sort -t= -k2 -rn | head -10

# 2. Sample recent errors from logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api --tail=500 | \
  grep -E '"level":"ERROR"|"status_code":5[0-9][0-9]' | tail -30

# 3. Check health endpoints
curl -si https://api.x0tta6bl4.io/health/live
curl -si https://api.x0tta6bl4.io/health/ready
curl -s https://api.x0tta6bl4.io/health/detailed | jq .

# 4. Check if circuit breakers are open
curl -s https://api.x0tta6bl4.io/metrics | grep 'circuit_breaker_state.*1'
```

---

## 3. Error taxonomy

| HTTP Status | Likely cause | Action |
|-------------|-------------|--------|
| 500 Internal Server Error | Bug, unhandled exception | Check logs for traceback |
| 502 Bad Gateway | Upstream/proxy issue | Check Caddy/ingress logs |
| 503 Service Unavailable | Circuit open, shutdown in progress | See CIRCUIT_BREAKER_OPEN.md |
| 504 Gateway Timeout | Slow upstream, timeout too short | See HIGH_LATENCY.md |

---

## 4. Root cause paths

### 4a. Deployment regression

```bash
# Check recent deployment
kubectl rollout history deployment/x0tta6bl4-api -n x0tta6bl4

# If recent bad deploy, rollback
kubectl rollout undo deployment/x0tta6bl4-api -n x0tta6bl4
kubectl rollout status deployment/x0tta6bl4-api -n x0tta6bl4
```

### 4b. DB migration failure at startup

```bash
# Check for migration errors in pod startup logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | grep -i "alembic\|migration\|upgrade"

# If migration failed: check DB schema manually
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT version_num FROM alembic_version;"
```

### 4c. Configuration / secret mismatch

```bash
# Check env vars (non-sensitive)
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- env | grep -v SECRET | grep -v KEY

# Verify Vault connectivity if secrets are Vault-sourced
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  curl -s "$VAULT_ADDR/v1/sys/health" | jq .sealed
```

### 4d. Unhandled exception in specific endpoint

```bash
# Get trace ID from failing request
curl -si https://api.x0tta6bl4.io/api/v1/maas/marketplace/listings | grep X-Trace-ID

# Search logs by trace ID
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | grep "<trace_id>"
```

### 4e. Memory pressure / OOMKill

```bash
kubectl describe pods -n x0tta6bl4 | grep -A5 OOM
kubectl get events -n x0tta6bl4 --sort-by='.lastTimestamp' | tail -20
```

---

## 5. Immediate mitigations

```bash
# A. Rollback if caused by bad deploy (safest)
kubectl rollout undo deployment/x0tta6bl4-api -n x0tta6bl4

# B. Scale up to reduce per-pod load
kubectl scale deployment/x0tta6bl4-api -n x0tta6bl4 --replicas=6

# C. Enable maintenance mode (return 503 for non-health endpoints)
kubectl set env deployment/x0tta6bl4-api MAINTENANCE_MODE=true
# Then update Caddy to return friendly maintenance page

# D. Shed traffic to specific broken endpoint
# Add to Caddyfile: respond /api/v1/broken-endpoint 503
kubectl exec -n x0tta6bl4 deploy/caddy -- caddy reload
```

---

## 6. Verify resolution

```bash
# Watch error rate drop
watch -n 10 'curl -s https://api.x0tta6bl4.io/metrics | \
  grep http_requests_total | grep "5[0-9][0-9]"'

# Confirm API contract test passes
python3 scripts/check_api_model_compat.py --smoke-only

# Run golden smoke quick
bash scripts/golden_smoke_premerge.sh quick
```

---

## 7. Post-incident

- [ ] Root cause documented in incident ticket
- [ ] Fix deployed and smoke tested
- [ ] Regression test added for the specific error path
- [ ] Alert threshold tuned if false positive
- [ ] Stakeholders notified if SLA was breached

---

## 8. Escalation

| Wait | Action |
|------|--------|
| 5 min | Assess if rollback needed |
| 10 min | Page on-call lead |
| 20 min | Global error > 5% — incident commander |
| 30 min | Customer-facing SLA breach — VP Engineering |
