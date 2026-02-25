"""Add marketplace_escrows table, renter/mesh cols to listings, last_seen to nodes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-21 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
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

    # marketplace_listings: add renter_id, mesh_id
    if _table_exists(inspector, "marketplace_listings"):
        with op.batch_alter_table("marketplace_listings") as batch_op:
            if not _column_exists(inspector, "marketplace_listings", "renter_id"):
                batch_op.add_column(sa.Column("renter_id", sa.String(), nullable=True))
            if not _column_exists(inspector, "marketplace_listings", "mesh_id"):
                batch_op.add_column(sa.Column("mesh_id", sa.String(), nullable=True))

    # mesh_nodes: add last_seen
    if _table_exists(inspector, "mesh_nodes"):
        with op.batch_alter_table("mesh_nodes") as batch_op:
            if not _column_exists(inspector, "mesh_nodes", "last_seen"):
                batch_op.add_column(sa.Column("last_seen", sa.DateTime(), nullable=True))

    # marketplace_escrows: create table (only if marketplace_listings exists)
    if not _table_exists(inspector, "marketplace_escrows"):
        # Only create if marketplace_listings exists (has FK dependency)
        if _table_exists(inspector, "marketplace_listings"):
            op.create_table(
                "marketplace_escrows",
                sa.Column("id", sa.String(), primary_key=True),
                sa.Column("listing_id", sa.String(), sa.ForeignKey("marketplace_listings.id"), nullable=False, index=True),
                sa.Column("renter_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
                sa.Column("amount_cents", sa.Integer(), nullable=False),
                sa.Column("status", sa.String(), nullable=False, server_default="held"),
                sa.Column("created_at", sa.DateTime(), nullable=True),
                sa.Column("released_at", sa.DateTime(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "marketplace_escrows"):
        op.drop_table("marketplace_escrows")

    if _table_exists(inspector, "marketplace_listings"):
        with op.batch_alter_table("marketplace_listings") as batch_op:
            if _column_exists(inspector, "marketplace_listings", "renter_id"):
                batch_op.drop_column("renter_id")
            if _column_exists(inspector, "marketplace_listings", "mesh_id"):
                batch_op.drop_column("mesh_id")

    if _table_exists(inspector, "mesh_nodes"):
        with op.batch_alter_table("mesh_nodes") as batch_op:
            if _column_exists(inspector, "mesh_nodes", "last_seen"):
                batch_op.drop_column("last_seen")
