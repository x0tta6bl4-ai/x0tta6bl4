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


def _table_exists(inspector, name: str) -> bool:
    if inspector is None:
        return True
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, col: str) -> bool:
    if inspector is None:
        return False
    if not _table_exists(inspector, table):
        return False
    return col in {c["name"] for c in inspector.get_columns(table)}


def _get_inspector(bind) -> "sa.Inspector | None":
    """Return a live Inspector, or None in offline (--sql) mode."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = _get_inspector(bind)

    # Step 1: Add columns (guarded — marketplace_listings may not exist in SQLite/test envs)
    if _table_exists(inspector, 'marketplace_listings'):
        # Step 2: Add foreign key
        with op.batch_alter_table('marketplace_listings', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_listing_renter', 'users', ['renter_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = _get_inspector(bind)

    if _table_exists(inspector, 'marketplace_listings'):
        with op.batch_alter_table('marketplace_listings', schema=None) as batch_op:
            batch_op.drop_constraint('fk_listing_renter', type_='foreignkey')
            if _column_exists(inspector, 'marketplace_listings', 'mesh_id'):
                batch_op.drop_column('mesh_id')
            if _column_exists(inspector, 'marketplace_listings', 'renter_id'):
                batch_op.drop_column('renter_id')
