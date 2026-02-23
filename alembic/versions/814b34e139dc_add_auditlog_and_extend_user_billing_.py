"""Add AuditLog and extend User/Billing models

Revision ID: 814b34e139dc
Revises: v001
Create Date: 2026-02-23 11:28:36.546349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '814b34e139dc'
down_revision: Union[str, Sequence[str], None] = 'v001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table: str, col: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Step 1: Add columns (guarded — marketplace_listings may not exist in SQLite/test envs)
    if _table_exists(inspector, 'marketplace_listings'):
        with op.batch_alter_table('marketplace_listings', schema=None) as batch_op:
            if not _column_exists(inspector, 'marketplace_listings', 'renter_id'):
                batch_op.add_column(sa.Column('renter_id', sa.String(), nullable=True))
            if not _column_exists(inspector, 'marketplace_listings', 'mesh_id'):
                batch_op.add_column(sa.Column('mesh_id', sa.String(), nullable=True))

        # Step 2: Add foreign key (separate block to avoid SQLite circular dep issues)
        with op.batch_alter_table('marketplace_listings', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_listing_renter', 'users', ['renter_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'marketplace_listings'):
        with op.batch_alter_table('marketplace_listings', schema=None) as batch_op:
            batch_op.drop_constraint('fk_listing_renter', type_='foreignkey')
            if _column_exists(inspector, 'marketplace_listings', 'mesh_id'):
                batch_op.drop_column('mesh_id')
            if _column_exists(inspector, 'marketplace_listings', 'renter_id'):
                batch_op.drop_column('renter_id')
