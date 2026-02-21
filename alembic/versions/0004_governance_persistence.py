"""Add governance_proposals and governance_votes tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-21 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _table_exists(inspector, name):
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "governance_proposals"):
        op.create_table(
            "governance_proposals",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("state", sa.String(), nullable=False, server_default="active"),
            sa.Column("actions_json", sa.Text(), nullable=True),
            sa.Column("end_time", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("execution_hash", sa.String(), nullable=True),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists(inspector, "governance_votes"):
        op.create_table(
            "governance_votes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("proposal_id", sa.String(), sa.ForeignKey("governance_proposals.id"),
                      nullable=False, index=True),
            sa.Column("voter_id", sa.String(), nullable=False, index=True),
            sa.Column("vote", sa.String(), nullable=False),
            sa.Column("tokens", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "governance_votes"):
        op.drop_table("governance_votes")
    if _table_exists(inspector, "governance_proposals"):
        op.drop_table("governance_proposals")
