"""
Schema index coverage tests — P1 Performance

Verifies that critical query-path columns have indexes defined in the ORM models
or are covered by the a1b2c3d4e5f6 migration.

These tests use an in-memory SQLite DB to ensure the full schema is created
and indexes are reflected without needing a running PostgreSQL instance.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect


@pytest.fixture(scope="module")
def inspector():
    """Create all tables in SQLite and return an inspector."""
    from src.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return inspect(engine)


def _indexed_columns(inspector, table_name: str) -> set[str]:
    """Return the set of column names that appear in at least one index."""
    indexes = inspector.get_indexes(table_name)
    cols: set[str] = set()
    for idx in indexes:
        cols.update(idx["column_names"])
    return cols


# ---------------------------------------------------------------------------
# mesh_instances
# ---------------------------------------------------------------------------

class TestMeshInstanceIndexes:
    def test_owner_id_indexed(self, inspector):
        assert "owner_id" in _indexed_columns(inspector, "mesh_instances"), \
            "mesh_instances.owner_id must be indexed (owner dashboard queries)"

    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "mesh_instances"), \
            "mesh_instances.status must be indexed (admin status filters)"


# ---------------------------------------------------------------------------
# marketplace_listings
# ---------------------------------------------------------------------------

class TestMarketplaceListingIndexes:
    def test_owner_id_indexed(self, inspector):
        assert "owner_id" in _indexed_columns(inspector, "marketplace_listings"), \
            "marketplace_listings.owner_id must be indexed"

    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "marketplace_listings"), \
            "marketplace_listings.status must be indexed (browse available)"

    def test_renter_id_indexed(self, inspector):
        assert "renter_id" in _indexed_columns(inspector, "marketplace_listings"), \
            "marketplace_listings.renter_id must be indexed (renter view)"

    def test_region_indexed(self, inspector):
        # region already had index=True in ORM model
        assert "region" in _indexed_columns(inspector, "marketplace_listings"), \
            "marketplace_listings.region must be indexed (geo filter)"


# ---------------------------------------------------------------------------
# marketplace_escrows
# ---------------------------------------------------------------------------

class TestMarketplaceEscrowIndexes:
    def test_listing_id_indexed(self, inspector):
        assert "listing_id" in _indexed_columns(inspector, "marketplace_escrows"), \
            "marketplace_escrows.listing_id must be indexed (FK lookup)"

    def test_renter_id_indexed(self, inspector):
        assert "renter_id" in _indexed_columns(inspector, "marketplace_escrows"), \
            "marketplace_escrows.renter_id must be indexed (renter escrow history)"

    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "marketplace_escrows"), \
            "marketplace_escrows.status must be indexed (expiry scanner)"

    def test_expires_at_indexed(self, inspector):
        assert "expires_at" in _indexed_columns(inspector, "marketplace_escrows"), \
            "marketplace_escrows.expires_at must be indexed (TTL cleanup)"


# ---------------------------------------------------------------------------
# invoices
# ---------------------------------------------------------------------------

class TestInvoiceIndexes:
    def test_user_id_indexed(self, inspector):
        assert "user_id" in _indexed_columns(inspector, "invoices"), \
            "invoices.user_id must be indexed (user billing dashboard)"

    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "invoices"), \
            "invoices.status must be indexed (overdue invoice scan)"

    def test_mesh_id_indexed(self, inspector):
        assert "mesh_id" in _indexed_columns(inspector, "invoices"), \
            "invoices.mesh_id must be indexed (per-mesh billing queries)"


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

class TestSessionIndexes:
    def test_user_id_indexed(self, inspector):
        assert "user_id" in _indexed_columns(inspector, "sessions"), \
            "sessions.user_id must be indexed (session lookup by user)"

    def test_expires_at_indexed(self, inspector):
        assert "expires_at" in _indexed_columns(inspector, "sessions"), \
            "sessions.expires_at must be indexed (expired session cleanup)"

    def test_email_indexed(self, inspector):
        # Already had index=True in ORM
        assert "email" in _indexed_columns(inspector, "sessions"), \
            "sessions.email must be indexed"


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------

class TestPaymentIndexes:
    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "payments"), \
            "payments.status must be indexed (payment reconciliation)"


# ---------------------------------------------------------------------------
# governance_proposals
# ---------------------------------------------------------------------------

class TestGovernanceProposalIndexes:
    def test_state_indexed(self, inspector):
        assert "state" in _indexed_columns(inspector, "governance_proposals"), \
            "governance_proposals.state must be indexed (active proposals query)"

    def test_end_time_indexed(self, inspector):
        assert "end_time" in _indexed_columns(inspector, "governance_proposals"), \
            "governance_proposals.end_time must be indexed (proposal expiry sort)"


# ---------------------------------------------------------------------------
# node_binary_attestations
# ---------------------------------------------------------------------------

class TestNodeBinaryAttestationIndexes:
    def test_node_id_indexed(self, inspector):
        assert "node_id" in _indexed_columns(inspector, "node_binary_attestations"), \
            "node_binary_attestations.node_id must be indexed"

    def test_mesh_id_indexed(self, inspector):
        assert "mesh_id" in _indexed_columns(inspector, "node_binary_attestations"), \
            "node_binary_attestations.mesh_id must be indexed"

    def test_status_indexed(self, inspector):
        assert "status" in _indexed_columns(inspector, "node_binary_attestations"), \
            "node_binary_attestations.status must be indexed (verification scan)"
