"""Add GlobalConfig table

Revision ID: 1c0c8d128426
Revises: 0006
Create Date: 2026-02-25 23:28:52.298421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c0c8d128426'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'global_config',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value_json', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_global_config_key'), 'global_config', ['key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_global_config_key'), table_name='global_config')
    op.drop_table('global_config')
