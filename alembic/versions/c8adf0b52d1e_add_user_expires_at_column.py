"""Add expires_at column to users table.

Revision ID: c8adf0b52d1e
Revises: b49070d1c83b
Create Date: 2026-03-04 17:59:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8adf0b52d1e"
down_revision: Union[str, Sequence[str], None] = "b49070d1c83b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "users"

    if not _table_exists(inspector, table_name):
        return

    if not _column_exists(inspector, table_name, "expires_at"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "users"

    if not _table_exists(inspector, table_name):
        return

    if _column_exists(inspector, table_name, "expires_at"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("expires_at")
