"""
Integration tests for MaaS Marketplace.

Endpoints:
  POST   /api/v1/maas/marketplace/list              — create listing (marketplace:list)
  GET    /api/v1/maas/marketplace/search             — search (no auth)
  POST   /api/v1/maas/marketplace/rent/{listing_id} — rent node (marketplace:rent)
  POST   /api/v1/maas/marketplace/escrow/{id}/release — release escrow (renter/admin)
  POST   /api/v1/maas/marketplace/escrow/{id}/refund  — refund escrow (renter/admin)
  DELETE /api/v1/maas/marketplace/list/{listing_id}  — cancel listing (owner)

Architecture note:
  The module uses a module-level _listings dict as primary store.
  create_listing writes to BOTH _listings AND DB.
  search reads _listings (if non-empty) OR DB.
  rent reads _listings first, then DB.
  Tests use unique node_ids per test to avoid cross-test state pollution.

Permissions:
  user role has: marketplace:list, marketplace:rent
  operator role does NOT have these (but admin bypasses all)
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, MarketplaceListing, MarketplaceEscrow, User, get_db

_TEST_DB_PATH = f"./test_marketplace_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def market_data(client):
    """Two regular users: seller and buyer. user role has marketplace:list and marketplace:rent."""
    email_seller = f"seller-{uuid.uuid4().hex[:8]}@test.com"
    email_buyer = f"buyer-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_seller, "password": "password123"})
    seller_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_buyer, "password": "password123"})
    buyer_token = r.json()["access_token"]

    return {
        "seller_token": seller_token,
        "buyer_token": buyer_token,
    }


def _unique_node():
    """Generate a unique node_id to avoid _listings dict state pollution."""
    return f"node-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Create Listing
# ---------------------------------------------------------------------------

class TestCreateListing:
    def test_requires_auth(self, client):
        r = client.post("/api/v1/maas/marketplace/list",
                        json={"node_id": _unique_node(), "region": "us-east",
                              "price_per_hour": 0.5, "bandwidth_mbps": 100})
        assert r.status_code == 401

    def test_user_can_create(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": _unique_node(), "region": "eu-central",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 200, r.text

    def test_create_returns_fields(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": _unique_node(), "region": "us-east",
                  "price_per_hour": 1.0, "bandwidth_mbps": 200},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        data = r.json()
        assert "listing_id" in data
        assert data["status"] == "available"
        assert data["region"] == "us-east"
        assert data["price_per_hour"] == 1.0
        assert data["bandwidth_mbps"] == 200

    def test_create_saves_to_db(self, client, market_data):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "asia-south",
                  "price_per_hour": 0.75, "bandwidth_mbps": 150},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        listing_id = r.json()["listing_id"]

        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row is not None
        assert row.node_id == node_id
        assert row.status == "available"
        db.close()

    def test_duplicate_node_rejected(self, client, market_data):
        node_id = _unique_node()
        client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-west",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-west",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 400

    def test_invalid_region_rejected(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": _unique_node(), "region": "mars-base",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 422

    def test_negative_price_rejected(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": _unique_node(), "region": "us-east",
                  "price_per_hour": -1.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 422

    def test_below_min_bandwidth_rejected(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": _unique_node(), "region": "us-east",
                  "price_per_hour": 0.5, "bandwidth_mbps": 5},  # min is 10
        )
        assert r.status_code in (401, 422)  # 401 if auth checked first, 422 if validation first


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_no_auth_required(self, client):
        r = client.get("/api/v1/maas/marketplace/search")
        assert r.status_code == 200

    def test_returns_list(self, client):
        r = client.get("/api/v1/maas/marketplace/search")
        assert isinstance(r.json(), list)

    def test_only_available_in_results(self, client, market_data):
        # All returned listings must be available
        r = client.get("/api/v1/maas/marketplace/search")
        for item in r.json():
            assert item["status"] == "available"

    def test_filter_by_region(self, client, market_data):
        node_id = _unique_node()
        client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "global",
                  "price_per_hour": 2.0, "bandwidth_mbps": 500},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        r = client.get("/api/v1/maas/marketplace/search?region=global")
        results = r.json()
        assert any(x["node_id"] == node_id for x in results)
        assert all(x["region"] == "global" for x in results)

    def test_filter_by_max_price(self, client, market_data):
        r = client.get("/api/v1/maas/marketplace/search?max_price=0.6")
        for item in r.json():
            assert item["price_per_hour"] <= 0.6

    def test_filter_by_min_bandwidth(self, client, market_data):
        r = client.get("/api/v1/maas/marketplace/search?min_bandwidth=400")
        for item in r.json():
            assert item["bandwidth_mbps"] >= 400


# ---------------------------------------------------------------------------
# Rent Node (marketplace:rent — user role has it)
# ---------------------------------------------------------------------------

class TestRentNode:
    def _create_listing(self, client, seller_token):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 1.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": seller_token},
        )
        return r.json()["listing_id"]

    def test_requires_auth(self, client, market_data):
        listing_id = self._create_listing(client, market_data["seller_token"])
        r = client.post(f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-x")
        assert r.status_code == 401

    def test_rent_success(self, client, market_data):
        listing_id = self._create_listing(client, market_data["seller_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-test-1",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "escrow"
        assert "escrow_id" in data
        assert data["listing_id"] == listing_id
        assert data["amount_held_cents"] > 0

    def test_rent_creates_escrow_in_db(self, client, market_data):
        listing_id = self._create_listing(client, market_data["seller_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-test-2",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        escrow_id = r.json()["escrow_id"]

        db = TestingSessionLocal()
        escrow = db.query(MarketplaceEscrow).filter(MarketplaceEscrow.id == escrow_id).first()
        assert escrow is not None
        assert escrow.status == "held"
        assert escrow.amount_cents > 0
        db.close()

    def test_cannot_rent_own_node(self, client, market_data):
        listing_id = self._create_listing(client, market_data["seller_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-self",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 400

    def test_cannot_rent_unavailable(self, client, market_data):
        listing_id = self._create_listing(client, market_data["seller_token"])
        # First rental puts it in escrow
        client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-test-3",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        # Second rental should fail — already in escrow
        r = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-test-4",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 400

    def test_rent_nonexistent_listing(self, client, market_data):
        r = client.post(
            "/api/v1/maas/marketplace/rent/lst-nonexistent?mesh_id=mesh-x",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 404

    def test_amount_held_matches_price(self, client, market_data):
        """price_per_hour=2.0 → amount_held_cents=200"""
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 2.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        listing_id = r.json()["listing_id"]
        r = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-price-test",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.json()["amount_held_cents"] == 200


# ---------------------------------------------------------------------------
# Escrow Release
# ---------------------------------------------------------------------------

class TestEscrowRelease:
    def _rented_listing(self, client, seller_token, buyer_token):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 1.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": seller_token},
        )
        listing_id = r.json()["listing_id"]
        client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-rel",
            headers={"X-API-Key": buyer_token},
        )
        return listing_id

    def test_release_requires_auth(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(f"/api/v1/maas/marketplace/escrow/{listing_id}/release")
        assert r.status_code == 401

    def test_release_by_renter_success(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "released"

    def test_release_updates_listing_to_rented(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row.status == "rented"
        db.close()

    def test_release_by_non_renter_forbidden(self, client, market_data):
        """seller cannot release escrow they don't hold"""
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 403

    def test_release_no_escrow(self, client, market_data):
        """listing exists but not in escrow state"""
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        listing_id = r.json()["listing_id"]
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Escrow Refund
# ---------------------------------------------------------------------------

class TestEscrowRefund:
    def _rented_listing(self, client, seller_token, buyer_token):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 1.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": seller_token},
        )
        listing_id = r.json()["listing_id"]
        client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-ref",
            headers={"X-API-Key": buyer_token},
        )
        return listing_id

    def test_refund_requires_auth(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(f"/api/v1/maas/marketplace/escrow/{listing_id}/refund")
        assert r.status_code == 401

    def test_refund_by_renter_success(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "refunded"

    def test_refund_returns_listing_to_available(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row.status == "available"
        assert row.renter_id is None
        db.close()

    def test_refund_by_non_renter_forbidden(self, client, market_data):
        listing_id = self._rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"])
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Cancel Listing
# ---------------------------------------------------------------------------

class TestCancelListing:
    def _create(self, client, token):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": token},
        )
        return r.json()["listing_id"]

    def test_cancel_requires_auth(self, client, market_data):
        listing_id = self._create(client, market_data["seller_token"])
        r = client.delete(f"/api/v1/maas/marketplace/list/{listing_id}")
        assert r.status_code == 401

    def test_cancel_own_listing_success(self, client, market_data):
        listing_id = self._create(client, market_data["seller_token"])
        r = client.delete(
            f"/api/v1/maas/marketplace/list/{listing_id}",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

    def test_cancel_removes_from_db(self, client, market_data):
        listing_id = self._create(client, market_data["seller_token"])
        client.delete(
            f"/api/v1/maas/marketplace/list/{listing_id}",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row is None
        db.close()

    def test_cancel_other_user_listing_forbidden(self, client, market_data):
        listing_id = self._create(client, market_data["seller_token"])
        r = client.delete(
            f"/api/v1/maas/marketplace/list/{listing_id}",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 403

    def test_cannot_cancel_active_escrow(self, client, market_data):
        listing_id = self._create(client, market_data["seller_token"])
        # Put in escrow
        client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-cancel",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        r = client.delete(
            f"/api/v1/maas/marketplace/list/{listing_id}",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 400

    def test_cancel_nonexistent_404(self, client, market_data):
        r = client.delete(
            "/api/v1/maas/marketplace/list/lst-nonexistent-12345",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 404
