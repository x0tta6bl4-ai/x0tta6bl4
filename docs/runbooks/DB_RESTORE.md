# Runbook: DB Restore from Backup (DR Scenario)

**Severity:** P0 — Data loss / service-down
**Owner:** Platform / Database SRE
**Last updated:** 2026-03-04

---

## Overview

This runbook covers the full disaster-recovery (DR) restore procedure for the
x0tta6bl4 PostgreSQL database from a `pg_dump` backup file.

---

## Symptoms

- Primary DB is unrecoverable (disk corruption, accidental drop, provider incident)
- Migration rollback is not sufficient — data must be restored from a point-in-time backup
- RTO target: **< 30 min** for a 1 GB backup on a standard cloud instance

---

## Prerequisites

| Tool | How to get |
|------|-----------|
| `pg_restore` / `psql` / `pg_isready` | `apt install postgresql-client-15` |
| `alembic` | `pip install alembic` |
| Backup file path | S3 / GCS / NFS backup bucket |
| Target DB DSN | Vault secret `db/x0tta6bl4/restore_url` |

---

## Triage checklist before restore

```bash
# 1. Confirm primary DB is actually down
pg_isready -h <PRIMARY_HOST> -p 5432

# 2. List available backups (example: S3)
aws s3 ls s3://x0tta6bl4-backups/db/ --recursive | sort | tail -20

# 3. Choose latest backup
BACKUP_KEY="db/x0tta6bl4_2026-03-04T03:00Z.dump"
aws s3 cp "s3://x0tta6bl4-backups/${BACKUP_KEY}" /tmp/restore.dump

# 4. Confirm backup integrity
md5sum /tmp/restore.dump
# Compare with the .md5 sidecar file on S3
```

---

## Restore procedure

### Step 0 — Declare incident

- Open incident in PagerDuty / Slack #incidents
- Notify team: estimated RTO, backup timestamp being restored

### Step 1 — Dry run (optional but recommended)

```bash
RESTORE_SKIP_CONFIRM=true \
./scripts/ops/db_restore_from_backup.sh \
  --backup /tmp/restore.dump \
  --target-url "postgresql://user:pass@restore-host:5432/x0tta6bl4_dr" \
  --dry-run
```

### Step 2 — Full restore

```bash
./scripts/ops/db_restore_from_backup.sh \
  --backup /tmp/restore.dump \
  --target-url "postgresql://user:pass@restore-host:5432/x0tta6bl4" \
  --skip-confirm
```

The script will:
1. Check target DB connectivity
2. Write a pre-restore checkpoint file
3. Drop and recreate `public` schema
4. Run `pg_restore --no-owner --no-acl --exit-on-error`
5. Run `alembic upgrade head` (catches any schema delta since backup)
6. Smoke-check: count public tables
7. Log alembic head revision

All output is also written to `logs/dr_restore_<timestamp>.log`.

### Step 3 — Smoke test

```bash
# Verify row counts in critical tables
psql "$TARGET_URL" -c "
SELECT
  (SELECT count(*) FROM users)        AS users,
  (SELECT count(*) FROM mesh_nodes)   AS nodes,
  (SELECT count(*) FROM billing_records) AS billing;
"

# Run the quick smoke suite against the restored DB
DATABASE_URL="$TARGET_URL" bash scripts/golden_smoke_premerge.sh quick
```

### Step 4 — Cut traffic over

Only after smoke passes:

```bash
# Update the active connection secret in Vault
vault kv put secret/x0tta6bl4/db url="postgresql://..."

# Restart app pods to pick up new URL
kubectl rollout restart deployment/x0tta6bl4-api -n production
kubectl rollout status  deployment/x0tta6bl4-api -n production
```

---

## Verify recovery

```bash
# API health
curl -sf https://api.x0tta6bl4.io/health/ready | jq .

# DB circuit breaker should be CLOSED
curl -sf https://api.x0tta6bl4.io/health/detailed | jq '.checks[] | select(.name=="database")'

# Check recent error rate
# In Grafana: "x0tta6bl4 On-Call" → "Error Rate 5xx" panel
```

---

## Rollback

If restore makes things worse:

1. Restore traffic back to read-only standby (if available)
2. Escalate to DB admin — manual point-in-time recovery may be needed
3. Do **not** run migrations again until root cause is understood

---

## Post-incident

- [ ] Fill in incident postmortem template
- [ ] Update backup schedule if RPO was exceeded
- [ ] Verify next scheduled backup completed successfully
- [ ] Check `logs/dr_restore_<timestamp>.log` for any warnings

---

## Escalation

| Threshold | Contact |
|-----------|---------|
| Restore script fails | @db-sre Slack channel |
| `pg_restore` errors | On-call DBA |
| Data inconsistency found | Engineering lead + CTO |
