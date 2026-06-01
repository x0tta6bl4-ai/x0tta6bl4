"""Add node runtime credential expiry and rotation metadata.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-01 02:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: str = "e5f6a7b8c9d0"
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

    if not _table_exists(inspector, "mesh_nodes"):
        return

    missing_columns = [
        column_name
        for column_name in (
            "runtime_credential_expires_at",
            "runtime_credential_rotated_at",
        )
        if not _column_exists(inspector, "mesh_nodes", column_name)
    ]
    if missing_columns:
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            if "runtime_credential_expires_at" in missing_columns:
                batch_op.add_column(
                    sa.Column("runtime_credential_expires_at", sa.DateTime(), nullable=True)
                )
            if "runtime_credential_rotated_at" in missing_columns:
                batch_op.add_column(
                    sa.Column("runtime_credential_rotated_at", sa.DateTime(), nullable=True)
                )

    inspector = sa.inspect(bind)
    index_name = op.f("ix_mesh_nodes_runtime_credential_expires_at")
    if _column_exists(
        inspector, "mesh_nodes", "runtime_credential_expires_at"
    ) and not _index_exists(inspector, "mesh_nodes", index_name):
        op.create_index(
            index_name,
            "mesh_nodes",
            ["runtime_credential_expires_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "mesh_nodes"):
        return

    index_name = op.f("ix_mesh_nodes_runtime_credential_expires_at")
    if _index_exists(inspector, "mesh_nodes", index_name):
        op.drop_index(index_name, table_name="mesh_nodes")

    inspector = sa.inspect(bind)
    drop_columns = [
        column_name
        for column_name in (
            "runtime_credential_rotated_at",
            "runtime_credential_expires_at",
        )
        if _column_exists(inspector, "mesh_nodes", column_name)
    ]
    if drop_columns:
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            for column_name in drop_columns:
                batch_op.drop_column(column_name)
