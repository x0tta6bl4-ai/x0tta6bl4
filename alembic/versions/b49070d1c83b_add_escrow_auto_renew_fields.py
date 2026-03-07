
"""add_escrow_auto_renew_fields

Revision ID: b49070d1c83b
Revises: 30552aa07b45
Create Date: 2026-03-01 10:35:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b49070d1c83b'
down_revision: Union[str, None] = '30552aa07b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, table_name: str) -> bool:
    if inspector is None:
        return True
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if inspector is None:
        return False
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _get_inspector(bind) -> "sa.Inspector | None":
    """Return a live Inspector, or None in offline (--sql) mode."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = _get_inspector(bind)
    table_name = "marketplace_escrows"

    if not _table_exists(inspector, table_name):
        return

    if not _column_exists(inspector, table_name, "auto_renew"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("auto_renew", sa.Boolean(), nullable=True))

    inspector = _get_inspector(bind)
    if not _column_exists(inspector, table_name, "expires_at"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))

def downgrade() -> None:
    bind = op.get_bind()
    inspector = _get_inspector(bind)
    table_name = "marketplace_escrows"

    if not _table_exists(inspector, table_name):
        return

    if _column_exists(inspector, table_name, "expires_at"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("expires_at")

    inspector = _get_inspector(bind)
    if _column_exists(inspector, table_name, "auto_renew"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("auto_renew")
