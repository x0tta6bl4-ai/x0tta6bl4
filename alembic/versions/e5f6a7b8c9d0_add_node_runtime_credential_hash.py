"""Add node runtime credential hash storage.

Revision ID: e5f6a7b8c9d0
Revises: d7c8f1a2b3c4
Create Date: 2026-06-01 02:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: str = "d7c8f1a2b3c4"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    index_name = op.f("ix_mesh_nodes_runtime_credential_hash")

    if not _table_exists(inspector, "mesh_nodes"):
        return

    if not _column_exists(inspector, "mesh_nodes", "runtime_credential_hash"):
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("runtime_credential_hash", sa.String(), nullable=True)
            )

    inspector = sa.inspect(bind)
    if _column_exists(
        inspector, "mesh_nodes", "runtime_credential_hash"
    ) and not _index_exists(inspector, "mesh_nodes", index_name):
        op.create_index(
            index_name,
            "mesh_nodes",
            ["runtime_credential_hash"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    index_name = op.f("ix_mesh_nodes_runtime_credential_hash")

    if not _table_exists(inspector, "mesh_nodes"):
        return

    if _index_exists(inspector, "mesh_nodes", index_name):
        op.drop_index(index_name, table_name="mesh_nodes")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "mesh_nodes", "runtime_credential_hash"):
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            batch_op.drop_column("runtime_credential_hash")
