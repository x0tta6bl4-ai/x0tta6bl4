"""Add X0T token support to marketplace.

Revision ID: 55ceb1fa2a27
Revises: 2f9da6377b73
Create Date: 2026-02-26 00:22:22.443564
"""
from typing import Any, Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55ceb1fa2a27'
down_revision: Union[str, Sequence[str], None] = '2f9da6377b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_info(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
) -> Optional[dict[str, Any]]:
    if not _table_exists(inspector, table_name):
        return None
    for col in inspector.get_columns(table_name):
        if col.get("name") == column_name:
            return col
    return None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # marketplace_listings: add token pricing columns if they are still missing.
    listing_price_token_col = _column_info(inspector, "marketplace_listings", "price_token_per_hour")
    listing_currency_col = _column_info(inspector, "marketplace_listings", "currency")
    if _table_exists(inspector, "marketplace_listings") and (
        listing_price_token_col is None or listing_currency_col is None
    ):
        with op.batch_alter_table("marketplace_listings", schema=None) as batch_op:
            if listing_price_token_col is None:
                batch_op.add_column(sa.Column("price_token_per_hour", sa.Float(), nullable=True))
            if listing_currency_col is None:
                batch_op.add_column(
                    sa.Column("currency", sa.String(), nullable=True, server_default="USD")
                )

    # marketplace_escrows: add token amount/currency columns and allow non-USD escrows.
    escrow_amount_token_col = _column_info(inspector, "marketplace_escrows", "amount_token")
    escrow_currency_col = _column_info(inspector, "marketplace_escrows", "currency")
    escrow_amount_cents_col = _column_info(inspector, "marketplace_escrows", "amount_cents")
    needs_amount_cents_nullable = (
        escrow_amount_cents_col is not None and escrow_amount_cents_col.get("nullable") is False
    )
    if _table_exists(inspector, "marketplace_escrows") and (
        escrow_amount_token_col is None
        or escrow_currency_col is None
        or needs_amount_cents_nullable
    ):
        with op.batch_alter_table("marketplace_escrows", schema=None) as batch_op:
            if escrow_amount_token_col is None:
                batch_op.add_column(sa.Column("amount_token", sa.Float(), nullable=True))
            if escrow_currency_col is None:
                batch_op.add_column(
                    sa.Column("currency", sa.String(), nullable=True, server_default="USD")
                )
            if needs_amount_cents_nullable:
                batch_op.alter_column("amount_cents", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Keep amount_cents nullable on downgrade to avoid destructive failures if X0T rows exist.
    if _table_exists(inspector, "marketplace_escrows"):
        with op.batch_alter_table("marketplace_escrows", schema=None) as batch_op:
            if _column_info(inspector, "marketplace_escrows", "currency") is not None:
                batch_op.drop_column("currency")
            if _column_info(inspector, "marketplace_escrows", "amount_token") is not None:
                batch_op.drop_column("amount_token")

    if _table_exists(inspector, "marketplace_listings"):
        with op.batch_alter_table("marketplace_listings", schema=None) as batch_op:
            if _column_info(inspector, "marketplace_listings", "currency") is not None:
                batch_op.drop_column("currency")
            if _column_info(inspector, "marketplace_listings", "price_token_per_hour") is not None:
                batch_op.drop_column("price_token_per_hour")
