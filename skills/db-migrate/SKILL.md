---
name: db-migrate
description: "Manages Alembic database migrations for x0tta6bl4. Detects schema drift, generates migrations, runs them safely with rollback support. Use when user asks to: run migration, create migration, upgrade database, check schema drift, apply alembic, migrate database, добавь колонку в БД, создай миграцию, запусти alembic, обнови схему базы данных, откат миграции, rollback migration."
---

# DB Migrate

Safe Alembic migration workflow for x0tta6bl4 (PostgreSQL via SQLAlchemy).

## Step 1: Check Current Schema State

```bash
# Check what migrations have been applied
alembic current

# Check what's pending
alembic history --verbose | head -20

# Check schema vs models drift (custom script)
python3 check_actual_schema.py
```

Expected output: list of tables and columns. Compare with `src/database/__init__.py` models.

## Step 2: Detect What Changed

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "describe_the_change"
```

The generated file appears in `alembic/versions/`. Review it carefully:
- Confirm `upgrade()` adds exactly the expected columns/tables
- Confirm `downgrade()` correctly reverses the change
- Remove any auto-generated changes you did NOT intend

Common autogenerate issues to fix:
- Server defaults that differ between SQLAlchemy and Postgres representation
- Index names that don't match

## Step 3: Validate Migration Before Applying

```bash
# Check SQL without applying
alembic upgrade head --sql > /tmp/migration_preview.sql
cat /tmp/migration_preview.sql
```

Checklist before applying:
- [ ] No `DROP TABLE` or `DROP COLUMN` without explicit intent
- [ ] No data loss operations on columns with existing data
- [ ] Nullable columns added to existing tables (non-nullable requires default)
- [ ] Foreign key constraints have correct ON DELETE behavior

## Step 4: Apply Migration

```bash
# Apply all pending migrations
alembic upgrade head

# Apply one step at a time
alembic upgrade +1

# Apply to specific revision
alembic upgrade <revision_id>
```

Verify after applying:
```bash
alembic current
python3 check_actual_schema.py
```

## Step 5: Run Affected Tests

```bash
python3 -m pytest tests/unit/api/ tests/api/ --no-cov -q -x
```

## Rollback

```bash
# Rollback one step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Full rollback (DANGEROUS — drops all data)
alembic downgrade base
```

## Troubleshooting

**Error: target database is not up to date**
```bash
alembic stamp head  # mark current state as up-to-date (use only if DB matches models)
```

**Error: Can't locate revision**
Check `alembic/versions/` for the file, ensure it's committed and `alembic_version` table is correct.

**Error: column already exists**
Migration was partially applied. Check `alembic_version` table and manually fix state:
```sql
UPDATE alembic_version SET version_num = '<previous_revision>';
```

## References

- `references/migration-checklist.md` — full safety checklist
