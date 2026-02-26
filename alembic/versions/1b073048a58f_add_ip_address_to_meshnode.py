"""Add ip_address to MeshNode

Revision ID: 1b073048a58f
Revises: 55ceb1fa2a27
Create Date: 2026-02-26 22:46:50.802557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b073048a58f'
down_revision: Union[str, Sequence[str], None] = '55ceb1fa2a27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    index_name = op.f("ix_mesh_nodes_ip_address")

    if not _table_exists(inspector, "mesh_nodes"):
        return

    if not _column_exists(inspector, "mesh_nodes", "ip_address"):
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            batch_op.add_column(sa.Column("ip_address", sa.String(), nullable=True))

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "mesh_nodes", "ip_address") and not _index_exists(
        inspector, "mesh_nodes", index_name
    ):
        op.create_index(index_name, "mesh_nodes", ["ip_address"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    index_name = op.f("ix_mesh_nodes_ip_address")

    if not _table_exists(inspector, "mesh_nodes"):
        return

    if _index_exists(inspector, "mesh_nodes", index_name):
        op.drop_index(index_name, table_name="mesh_nodes")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "mesh_nodes", "ip_address"):
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            batch_op.drop_column("ip_address")
