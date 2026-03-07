"""add_trace_fields_to_audit_logs

Revision ID: 30552aa07b45
Revises: 3a6f2f0d9e11
Create Date: 2026-02-28 23:32:51.184144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30552aa07b45'
down_revision: Union[str, Sequence[str], None] = '3a6f2f0d9e11'
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


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if inspector is None:
        return False
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _get_inspector(bind) -> "sa.Inspector | None":
    """Return a live Inspector, or None in offline (--sql) mode."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = _get_inspector(bind)
    table_name = "audit_logs"
    index_name = op.f("ix_audit_logs_correlation_id")

    if not _table_exists(inspector, table_name):
        return

    if not _column_exists(inspector, table_name, "user_agent"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("user_agent", sa.String(), nullable=True))

    inspector = _get_inspector(bind)
    if not _column_exists(inspector, table_name, "correlation_id"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("correlation_id", sa.String(), nullable=True))

    inspector = _get_inspector(bind)
    if _column_exists(inspector, table_name, "correlation_id") and not _index_exists(
        inspector, table_name, index_name
    ):
        op.create_index(index_name, table_name, ["correlation_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = _get_inspector(bind)
    table_name = "audit_logs"
    index_name = op.f("ix_audit_logs_correlation_id")

    if not _table_exists(inspector, table_name):
        return

    if _index_exists(inspector, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)

    inspector = _get_inspector(bind)
    if _column_exists(inspector, table_name, "correlation_id"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("correlation_id")

    inspector = _get_inspector(bind)
    if _column_exists(inspector, table_name, "user_agent"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("user_agent")
