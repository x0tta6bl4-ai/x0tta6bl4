"""Add missing performance indexes for hot query paths

Revision ID: a1b2c3d4e5f6
Revises: c8adf0b52d1e
Create Date: 2026-03-04 00:00:00.000000

Hot spots identified during P1 performance review:
- mesh_instances: owner_id, status — owner dashboard & admin status filters
- marketplace_listings: owner_id, status, renter_id — marketplace browse & renter views
- marketplace_escrows: renter_id, status, expires_at — expiry scanner & renter history
- invoices: user_id, status, mesh_id — billing dashboard queries
- sessions: user_id, expires_at — session lookup and TTL cleanup
- payments: status — payment reconciliation queries
- governance_proposals: state, end_time — DAO active proposal queries
- node_binary_attestations: status — attestation verification queries
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c8adf0b52d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Index definitions: (table, column(s), index_name)
_INDEXES = [
    # mesh_instances
    ("mesh_instances", ["owner_id"], "ix_mesh_instances_owner_id"),
    ("mesh_instances", ["status"],   "ix_mesh_instances_status"),
    # marketplace_listings
    ("marketplace_listings", ["owner_id"],   "ix_marketplace_listings_owner_id"),
    ("marketplace_listings", ["status"],     "ix_marketplace_listings_status"),
    ("marketplace_listings", ["renter_id"],  "ix_marketplace_listings_renter_id"),
    # marketplace_escrows
    ("marketplace_escrows", ["renter_id"],  "ix_marketplace_escrows_renter_id"),
    ("marketplace_escrows", ["status"],     "ix_marketplace_escrows_status"),
    ("marketplace_escrows", ["expires_at"], "ix_marketplace_escrows_expires_at"),
    # invoices
    ("invoices", ["user_id"],  "ix_invoices_user_id"),
    ("invoices", ["status"],   "ix_invoices_status"),
    ("invoices", ["mesh_id"],  "ix_invoices_mesh_id"),
    # sessions
    ("sessions", ["user_id"],    "ix_sessions_user_id"),
    ("sessions", ["expires_at"], "ix_sessions_expires_at"),
    # payments
    ("payments", ["status"], "ix_payments_status"),
    # governance_proposals
    ("governance_proposals", ["state"],    "ix_governance_proposals_state"),
    ("governance_proposals", ["end_time"], "ix_governance_proposals_end_time"),
    # node_binary_attestations
    ("node_binary_attestations", ["status"], "ix_node_binary_attestations_status"),
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    for table, columns, index_name in _INDEXES:
        col_list = ", ".join(columns)
        if dialect == "postgresql":
            # IF NOT EXISTS avoids aborting the PostgreSQL transaction on duplicate index.
            # try/except alone is insufficient: PG marks the whole transaction as aborted
            # after any DDL error, making subsequent statements fail.
            bind.execute(sa.text(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col_list})"
            ))
        else:
            # SQLite also supports IF NOT EXISTS since 3.3.7.
            bind.execute(sa.text(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col_list})"
            ))


def downgrade() -> None:
    bind = op.get_bind()
    for _table, _columns, index_name in reversed(_INDEXES):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
