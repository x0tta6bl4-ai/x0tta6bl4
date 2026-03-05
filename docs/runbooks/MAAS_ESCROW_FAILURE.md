# Runbook: MaaS Escrow Failure

**Severity**: Warning
**Alert**: `MaaSEscrowFailureSpike`, `MaaSNodeHeartbeatMissing`
**MTTR target**: < 30 min
**Owner**: MaaS team

---

## 1. Symptoms

| Signal | Value |
|--------|-------|
| `MaaSEscrowFailureSpike` | > 5 escrow failures in 5 min |
| `MaaSNodeHeartbeatMissing` | No heartbeats for 10 min |
| Node status stuck in `rented` | Escrow auto-release failed |
| Customer complaints: payment stuck | Refund not processed |

---

## 2. Immediate triage (< 5 min)

```bash
# 1. Check escrow failure count
curl -s https://api.x0tta6bl4.io/metrics | grep maas_escrow_failures_total

# 2. Find nodes stuck in rented state
curl -s https://api.x0tta6bl4.io/api/v1/maas/nodes?status=rented \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '[.[] | {id, status, rented_until}]'

# 3. Check recent heartbeat activity
curl -s https://api.x0tta6bl4.io/api/v1/maas/telemetry/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# 4. Check API logs for escrow errors
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api --tail=200 | \
  grep -i "escrow\|auto.release\|heartbeat"
```

---

## 3. Root cause paths

### 3a. Stripe payment failure during escrow settlement

```bash
# Check Stripe status
curl -s https://status.stripe.com/api/v2/status.json | jq .status.description

# Find failed payment intents in logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | \
  grep -i "stripe\|payment_intent\|failed"
```

**Fix**: Retry failed escrow settlement via admin endpoint:
```bash
curl -X POST https://api.x0tta6bl4.io/api/v1/maas/admin/retry-escrow \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"node_id": "<node_id>"}'
```

### 3b. Node heartbeat missing — node offline

```bash
# Check node connectivity
curl -s https://api.x0tta6bl4.io/api/v1/maas/nodes/<node_id>/health \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Check if node VPN/mesh tunnel is up
kubectl exec -n x0tta6bl4 deploy/x0tta6bl4-api -- \
  ping -c3 <node_mesh_ip>
```

**Fix**: If node is offline, trigger escrow auto-release manually:
```bash
curl -X POST https://api.x0tta6bl4.io/api/v1/maas/nodes/<node_id>/release \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"reason": "heartbeat_timeout", "refund": true}'
```

### 3c. MAPE-K loop not processing events

```bash
# Check MAPE-K event stream backlog
curl -s https://api.x0tta6bl4.io/api/v1/maas/billing/mapek-status \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Restart MAPE-K background task if stuck
kubectl rollout restart -n x0tta6bl4 deployment/x0tta6bl4-api
```

### 3d. DB write failure (node status not updating)

```bash
# Check for DB errors in logs
kubectl logs -n x0tta6bl4 deploy/x0tta6bl4-api | grep -i "sqlalchemy\|db error\|commit"

# Check table for lock contention
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT * FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid
   WHERE relation = 'mesh_instances'::regclass AND NOT granted;"
```

---

## 4. Manual escrow recovery

```bash
# List all stuck escrow records
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "SELECT id, node_id, tenant_id, amount, status, created_at
   FROM escrow_transactions
   WHERE status = 'pending' AND created_at < NOW() - INTERVAL '2 hours'
   ORDER BY created_at;"

# Force-release stuck escrow (DBA action — coordinate with MaaS lead)
kubectl exec -n x0tta6bl4 deploy/postgres -- psql -U postgres -c \
  "UPDATE escrow_transactions SET status='released', updated_at=NOW()
   WHERE id = '<escrow_id>' AND status='pending';"
```

---

## 5. Verify recovery

```bash
# Confirm escrow failure metric stopped increasing
curl -s https://api.x0tta6bl4.io/metrics | grep maas_escrow_failures_total

# Confirm heartbeats resuming
curl -s https://api.x0tta6bl4.io/api/v1/maas/telemetry/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .last_heartbeat_at

# Confirm no stuck nodes
curl -s https://api.x0tta6bl4.io/api/v1/maas/nodes?status=rented \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq length
```

---

## 6. Customer communication

If escrow failures affect customer billing:
1. Draft incident notice via internal comms tool
2. Trigger refund for affected transactions (via Stripe Dashboard or admin API)
3. Notify affected tenants via email (template: `docs/templates/incident_customer_notice.md`)

---

## 7. Post-incident

- [ ] Confirm no customer funds stuck > 24 h
- [ ] File Stripe support ticket if payment gateway issue
- [ ] Review heartbeat timeout threshold (default: 10 min)
- [ ] Add regression test for newly discovered failure mode
- [ ] Update escrow monitoring dashboards

---

## 8. Escalation

| Wait | Action |
|------|--------|
| 5 min | Check Stripe status and node health |
| 15 min | Page MaaS lead if funds stuck |
| 30 min | Escalate to engineering director if customer funds at risk |
