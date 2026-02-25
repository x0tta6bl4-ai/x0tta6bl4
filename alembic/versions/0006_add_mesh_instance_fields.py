"""Add region, nodes, pqc_profile columns to mesh_instances.

Revision ID: 0006
Revises: 814b34e139dc
Create Date: 2026-02-25 00:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "814b34e139dc"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table: str, col: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # mesh_instances: add region, nodes, pqc_profile
    if _table_exists(inspector, "mesh_instances"):
        with op.batch_alter_table("mesh_instances") as batch_op:
            if not _column_exists(inspector, "mesh_instances", "region"):
                batch_op.add_column(
                    sa.Column("region", sa.String(), nullable=True, server_default="global")
                )
            if not _column_exists(inspector, "mesh_instances", "nodes"):
                batch_op.add_column(
                    sa.Column("nodes", sa.Integer(), nullable=True)
                )
            if not _column_exists(inspector, "mesh_instances", "pqc_profile"):
                batch_op.add_column(
                    sa.Column("pqc_profile", sa.String(), nullable=True, server_default="edge")
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "mesh_instances"):
        with op.batch_alter_table("mesh_instances") as batch_op:
            if _column_exists(inspector, "mesh_instances", "pqc_profile"):
                batch_op.drop_column("pqc_profile")
            if _column_exists(inspector, "mesh_instances", "nodes"):
                batch_op.drop_column("nodes")
            if _column_exists(inspector, "mesh_instances", "region"):
                batch_op.drop_column("region")
