# Migration Policy (Fail-Closed)

Date: 2026-02-28
Owner: Platform / Backend

## Goal

Keep Alembic migrations safe for repeated deploys and for upgrades from older DB snapshots.

## Required Rules for New Revisions

1. Idempotent DDL style:
- `create_table` / `drop_table` must be guarded by table existence checks.
- `add_column` / `drop_column` must be guarded by column existence checks.
- `create_index` / `drop_index` must be guarded by index existence checks.

2. Nullable hardening (`nullable=False`) is controlled:
- direct `alter_column(..., nullable=False)` requires either
  - explicit `server_default` / `existing_server_default`, or
  - explicit marker in migration file: `MIGRATION_ALLOW_NULLABLE_TO_NON_NULLABLE = True`
    only after validated data backfill.

3. Downgrade path:
- every revision must keep a working downgrade path,
- destructive downgrade is forbidden for shared production tables unless explicitly justified in migration doc.

## Automated Gates

- Policy audit (latest 3 revisions from head):

```bash
python3 scripts/check_migration_policy.py --depth 3
```

- Bootstrap + historical snapshot roundtrip (`-1/-2/-3`):

```bash
python3 scripts/check_db_bootstrap_chain.py --validate-downgrade --downgrade-steps 3
```

- Full SQLite + PostgreSQL chain:

```bash
POSTGRES_BOOTSTRAP_DATABASE_URL='<admin_dsn>' \
python3 scripts/check_db_bootstrap_chain.py --require-postgres --validate-downgrade --downgrade-steps 3
```

These checks are included in pre-merge gate and CI.
