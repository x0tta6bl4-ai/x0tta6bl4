"""Add node runtime identity binding metadata.

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-06-01 10:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: str = "f6a7b8c9d0e1"
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
            "runtime_identity_binding_type",
            "runtime_identity_binding_hash",
            "runtime_identity_bound_at",
            "runtime_identity_last_verified_at",
        )
        if not _column_exists(inspector, "mesh_nodes", column_name)
    ]
    if missing_columns:
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            if "runtime_identity_binding_type" in missing_columns:
                batch_op.add_column(
                    sa.Column("runtime_identity_binding_type", sa.String(), nullable=True)
                )
            if "runtime_identity_binding_hash" in missing_columns:
                batch_op.add_column(
                    sa.Column("runtime_identity_binding_hash", sa.String(), nullable=True)
                )
            if "runtime_identity_bound_at" in missing_columns:
                batch_op.add_column(
                    sa.Column("runtime_identity_bound_at", sa.DateTime(), nullable=True)
                )
            if "runtime_identity_last_verified_at" in missing_columns:
                batch_op.add_column(
                    sa.Column(
                        "runtime_identity_last_verified_at",
                        sa.DateTime(),
                        nullable=True,
                    )
                )

    inspector = sa.inspect(bind)
    index_specs = (
        (
            op.f("ix_mesh_nodes_runtime_identity_binding_type"),
            ["runtime_identity_binding_type"],
            False,
        ),
        (
            op.f("ix_mesh_nodes_runtime_identity_binding_hash"),
            ["runtime_identity_binding_hash"],
            True,
        ),
    )
    for index_name, columns, unique in index_specs:
        if all(_column_exists(inspector, "mesh_nodes", column) for column in columns):
            if not _index_exists(inspector, "mesh_nodes", index_name):
                op.create_index(
                    index_name,
                    "mesh_nodes",
                    columns,
                    unique=unique,
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "mesh_nodes"):
        return

    for index_name in (
        op.f("ix_mesh_nodes_runtime_identity_binding_hash"),
        op.f("ix_mesh_nodes_runtime_identity_binding_type"),
    ):
        if _index_exists(inspector, "mesh_nodes", index_name):
            op.drop_index(index_name, table_name="mesh_nodes")

    inspector = sa.inspect(bind)
    drop_columns = [
        column_name
        for column_name in (
            "runtime_identity_last_verified_at",
            "runtime_identity_bound_at",
            "runtime_identity_binding_hash",
            "runtime_identity_binding_type",
        )
        if _column_exists(inspector, "mesh_nodes", column_name)
    ]
    if drop_columns:
        with op.batch_alter_table("mesh_nodes", schema=None) as batch_op:
            for column_name in drop_columns:
                batch_op.drop_column(column_name)
