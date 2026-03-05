# DB Migration Rollback Runbook

Date: 2026-02-28
Owner: Platform / Backend
Scope: x0tta6bl4 control-plane database migrations (Alembic)

## Purpose

This runbook defines the emergency rollback procedure when a fresh deploy with a new Alembic revision causes production issues.

## Safety Rules

1. Freeze write traffic before rollback.
2. Always take a backup before downgrade.
3. Roll back one revision at a time unless incident response explicitly approves a larger rollback window.
4. After rollback, run schema parity and API smoke checks before re-opening traffic.

## Inputs

- `DATABASE_URL`: target DB DSN.
- `TARGET_REVISION`: Alembic target (recommended: `-1` for single-step rollback).
- Optional: `POSTGRES_BOOTSTRAP_DATABASE_URL` for isolated bootstrap checks.

## Fast Triage (5 minutes)

1. Identify current revision:

```bash
DATABASE_URL='<dsn>' alembic -c alembic.ini current
DATABASE_URL='<dsn>' alembic -c alembic.ini heads
```

2. Inspect latest revision and parent:

```bash
alembic -c alembic.ini history -r -2:current
```

3. Decide if rollback is needed:
- DB-level errors (constraint/index/column mismatch).
- New endpoints failing due to migration side effects.
- Elevated 5xx tied to persistence paths.

## PostgreSQL Rollback Procedure

### 1) Backup

```bash
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
pg_dump "$DATABASE_URL" > /tmp/db_pre_rollback_$(date +%Y%m%d_%H%M%S).sql
```

### 2) Downgrade one revision

```bash
DATABASE_URL="$DATABASE_URL" alembic -c alembic.ini downgrade -1
```

If incident severity requires a specific revision:

```bash
DATABASE_URL="$DATABASE_URL" alembic -c alembic.ini downgrade <revision_id>
```

### 3) Validate schema contract

```bash
DATABASE_URL="$DATABASE_URL" python3 scripts/check_orm_schema_parity.py
```

### 4) Validate app contract

```bash
pytest -q tests/api/test_api_error_contract.py --no-cov
```

### 5) Re-open traffic gradually

- Start with read-only probes.
- Enable partial write traffic.
- Return full traffic after error-rate stabilizes.

## SQLite Rollback Procedure

### 1) File backup

```bash
cp /path/to/x0tta6bl4.db /path/to/x0tta6bl4.db.bak.$(date +%Y%m%d_%H%M%S)
```

### 2) Downgrade

```bash
export DATABASE_URL='sqlite:////path/to/x0tta6bl4.db'
DATABASE_URL="$DATABASE_URL" alembic -c alembic.ini downgrade -1
```

### 3) Validate

```bash
DATABASE_URL="$DATABASE_URL" python3 scripts/check_orm_schema_parity.py
pytest -q tests/api/test_api_error_contract.py --no-cov
```

## Recovery If Downgrade Fails

1. Stop the API service.
2. Restore from backup:
- PostgreSQL: `psql <dbname> < backup.sql` (or restore into a clean DB and switch).
- SQLite: replace DB file with `.bak` copy.
3. Pin app deployment to the last known-good image/commit.
4. Re-run:

```bash
DATABASE_URL='<dsn>' alembic -c alembic.ini current
DATABASE_URL='<dsn>' python3 scripts/check_orm_schema_parity.py
```

## Pre-Merge Guardrails (Already Enabled)

- Bootstrap chain check:

```bash
python3 scripts/check_db_bootstrap_chain.py --validate-downgrade --downgrade-steps 1
```

- Full SQLite+PostgreSQL guard:

```bash
POSTGRES_BOOTSTRAP_DATABASE_URL='<admin_dsn>' \
python3 scripts/check_db_bootstrap_chain.py --require-postgres --validate-downgrade --downgrade-steps 1
```

These commands are also used in CI/golden-smoke to catch rollback regressions before merge.
