"""Bootstrap missing core MaaS tables for clean Alembic installs.

Revision ID: 2f9da6377b73
Revises: 1c0c8d128426
Create Date: 2026-02-25 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.database import Base


# revision identifiers, used by Alembic.
revision: str = "2f9da6377b73"
down_revision: Union[str, Sequence[str], None] = "1c0c8d128426"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BOOTSTRAP_TABLES = (
    "mesh_instances",
    "acl_policies",
    "mesh_nodes",
    "marketplace_listings",
    "marketplace_escrows",
    "invoices",
    "signed_playbooks",
    "playbook_acks",
    "audit_logs",
)


def _table_exists(inspector, name: str) -> bool:
    if inspector is None:
        return True
    return name in inspector.get_table_names()


def _get_inspector(bind) -> "sa.Inspector | None":
    """Return a live Inspector, or None in offline (--sql) mode."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    """Create core MaaS tables that may be missing on a clean migration path."""
    bind = op.get_bind()
    inspector = _get_inspector(bind)

    missing_table_names = [
        table_name
        for table_name in _BOOTSTRAP_TABLES
        if not _table_exists(inspector, table_name)
    ]
    if not missing_table_names:
        return

    missing_tables = [
        Base.metadata.tables[name]
        for name in missing_table_names
        if name in Base.metadata.tables
    ]
    if missing_tables:
        Base.metadata.create_all(bind=bind, tables=missing_tables, checkfirst=True)


def downgrade() -> None:
    """No-op to avoid destructive drops of potentially pre-existing production tables."""
    return

