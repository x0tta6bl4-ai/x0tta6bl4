"""Initial schema creation for x0tta6bl4.

Revision ID: 001
Revises: 
Create Date: 2026-01-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema."""
    
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "hstore"')
    
    # Mesh nodes table
    op.create_table(
        'mesh_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), primary_key=True),
        sa.Column('node_id', sa.String(255), nullable=False, unique=True),
        sa.Column('address', postgresql.INET(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='offline'),
        sa.Column('health_score', sa.Float(), server_default='0.0'),
        sa.Column('last_heartbeat', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_mesh_nodes_status', 'mesh_nodes', ['status'])
    op.create_index('idx_mesh_nodes_heartbeat', 'mesh_nodes', ['last_heartbeat'])
    
    # SPIFFE identities
    op.create_table(
        'spiffe_identities',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), primary_key=True),
        sa.Column('spiffe_id', sa.String(255), nullable=False, unique=True),
        sa.Column('trust_domain', sa.String(255), nullable=False),
        sa.Column('subject_alt_names', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('certificate_pem', sa.Text(), nullable=False),
        sa.Column('key_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_spiffe_id', 'spiffe_identities', ['spiffe_id'])
    op.create_index('idx_spiffe_expires', 'spiffe_identities', ['expires_at'])
    
    # API tokens
    op.create_table(
        'api_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), primary_key=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('last_used', sa.DateTime()),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('revoked_at', sa.DateTime()),
    )
    op.create_index('idx_api_token_hash', 'api_tokens', ['token_hash'])
    op.create_index('idx_api_token_owner', 'api_tokens', ['owner_id'])
    op.create_index('idx_api_token_expires', 'api_tokens', ['expires_at'])
    
    # Audit log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('subject_type', sa.String(100), nullable=False),
        sa.Column('subject_id', postgresql.UUID(as_uuid=True)),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True)),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('changes', postgresql.JSON()),
        sa.Column('result', sa.String(50), server_default='success'),
        sa.Column('error_message', sa.Text()),
        sa.Column('ip_address', postgresql.INET()),
        sa.Column('user_agent', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_audit_event_type', 'audit_log', ['event_type'])
    op.create_index('idx_audit_subject', 'audit_log', ['subject_type', 'subject_id'])
    op.create_index('idx_audit_created', 'audit_log', ['created_at'])
    op.create_index('idx_audit_actor', 'audit_log', ['actor_id'])
    
    # Metrics
    op.create_table(
        'metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('metric_name', sa.String(255), nullable=False),
        sa.Column('labels', postgresql.JSON()),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_metrics_name', 'metrics', ['metric_name'])
    op.create_index('idx_metrics_timestamp', 'metrics', ['timestamp'])
    op.create_index('idx_metrics_name_ts', 'metrics', ['metric_name', 'timestamp'])
    
    # Create views
    op.execute('''
        CREATE OR REPLACE VIEW v_active_nodes AS
        SELECT * FROM mesh_nodes
        WHERE status = 'online'
        AND last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '1 minute'
    ''')
    
    op.execute('''
        CREATE OR REPLACE VIEW v_expiring_certificates AS
        SELECT * FROM spiffe_identities
        WHERE expires_at < CURRENT_TIMESTAMP + INTERVAL '7 days'
    ''')


def downgrade() -> None:
    """Drop all created tables and views."""
    op.execute('DROP VIEW IF EXISTS v_expiring_certificates')
    op.execute('DROP VIEW IF EXISTS v_active_nodes')
    op.drop_table('metrics')
    op.drop_table('audit_log')
    op.drop_table('api_tokens')
    op.drop_table('spiffe_identities')
    op.drop_table('mesh_nodes')
