"""Add permissions column to users.

Revision ID: 3a6f2f0d9e11
Revises: 1b073048a58f
Create Date: 2026-02-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a6f2f0d9e11"
down_revision: Union[str, Sequence[str], None] = "1b073048a58f"
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

    if not _table_exists(inspector, "users"):
        return

    if not _column_exists(inspector, "users", "permissions"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("permissions", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = _get_inspector(bind)

    if not _table_exists(inspector, "users"):
        return

    if _column_exists(inspector, "users", "permissions"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("permissions")
