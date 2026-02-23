# Migration Safety Checklist

## Pre-Migration

- [ ] `alembic current` shows expected base revision
- [ ] `git status` is clean (no uncommitted model changes that aren't in migration)
- [ ] Migration SQL reviewed with `alembic upgrade head --sql`
- [ ] No unintended DROP statements
- [ ] Nullable constraints correct for existing data
- [ ] Backup exists for production databases
- [ ] Migration tested on dev environment first

## Key Files

| File | Purpose |
|------|---------|
| `alembic.ini` | DB URL and migration settings |
| `alembic/env.py` | Migration environment, model import |
| `alembic/versions/` | All migration files |
| `src/database/__init__.py` | SQLAlchemy models (source of truth) |
| `check_actual_schema.py` | Schema drift detector |
| `migrate_db.py` | Custom migration runner |
| `migrate_enterprise_db.py` | Enterprise schema migration |

## Naming Convention

Migration files follow: `NNNN_short_description.py`
Example: `0005_supply_chain_and_playbook_acks.py`

## Common MaaS Schema Operations

```python
# Add nullable column (safe for existing rows)
op.add_column('mesh_instances',
    sa.Column('batman_interface', sa.String(50), nullable=True))

# Add index
op.create_index('ix_mesh_instances_owner_id',
    'mesh_instances', ['owner_id'], unique=False)

# Add foreign key
op.create_foreign_key('fk_node_mesh',
    'nodes', 'mesh_instances', ['mesh_id'], ['id'])
```

## Alembic Quick Reference

| Command | Effect |
|---------|--------|
| `alembic current` | Show current revision |
| `alembic history` | Show all revisions |
| `alembic upgrade head` | Apply all pending |
| `alembic upgrade +1` | Apply one step |
| `alembic downgrade -1` | Rollback one step |
| `alembic downgrade base` | Full rollback |
| `alembic revision -m "msg"` | Manual revision |
| `alembic revision --autogenerate -m "msg"` | Auto-detect changes |
| `alembic stamp head` | Mark DB as up-to-date without running |
