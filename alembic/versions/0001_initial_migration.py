"""Initial migration - create tables

Revision ID: 0001
Revises: 
Create Date: 2026-01-28 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('company', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('requests_count', sa.Integer(), nullable=True),
        sa.Column('requests_limit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_api_key'), 'users', ['api_key'], unique=True)
    op.create_index(op.f('ix_users_stripe_customer_id'), 'users', ['stripe_customer_id'], unique=True)
    op.create_index(op.f('ix_users_stripe_subscription_id'), 'users', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    
    # Create sessions table
    op.create_table('sessions',
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_sessions_email'), 'sessions', ['email'], unique=False)
    op.create_index(op.f('ix_sessions_token'), 'sessions', ['token'], unique=False)
    
    # Create payments table
    op.create_table('payments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('transaction_hash', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=True)
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    
    # Create licenses table
    op.create_table('licenses',
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('order_id', sa.String(), nullable=True),
        sa.Column('tier', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_licenses_order_id'), 'licenses', ['order_id'], unique=False)
    op.create_index(op.f('ix_licenses_token'), 'licenses', ['token'], unique=False)


def downgrade() -> None:
    # Drop all tables
    op.drop_table('licenses')
    op.drop_table('payments')
    op.drop_table('sessions')
    op.drop_table('users')
