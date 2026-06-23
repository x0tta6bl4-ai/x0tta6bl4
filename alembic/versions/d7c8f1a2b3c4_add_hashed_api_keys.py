"""Add hashed API key storage.

Revision ID: d7c8f1a2b3c4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 08:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "d7c8f1a2b3c4"
down_revision: str = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("api_key_hash", sa.String(), nullable=True))
    op.create_index("ix_users_api_key_hash", "users", ["api_key_hash"], unique=True)
    op.execute("UPDATE users SET api_key = NULL WHERE api_key IS NOT NULL")


def downgrade() -> None:
    op.drop_index("ix_users_api_key_hash", table_name="users")
    op.drop_column("users", "api_key_hash")
