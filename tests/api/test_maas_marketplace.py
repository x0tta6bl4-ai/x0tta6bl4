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

import json
import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, GlobalConfig, MarketplaceEscrow, MarketplaceListing, User, get_db

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


def _set_global_multiplier(value: float) -> None:
    db = TestingSessionLocal()
    try:
        row = db.query(GlobalConfig).filter(GlobalConfig.key == "global_price_multiplier").first()
        if row is None:
            row = GlobalConfig(key="global_price_multiplier", value_json=json.dumps(value))
            db.add(row)
        else:
            row.value_json = json.dumps(value)
        db.commit()
    finally:
        db.close()


def _clear_global_multiplier() -> None:
    db = TestingSessionLocal()
    try:
        db.query(GlobalConfig).filter(GlobalConfig.key == "global_price_multiplier").delete()
        db.commit()
    finally:
        db.close()


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
        assert "trust_score" in data
        assert 0.0 <= data["trust_score"] <= 1.0

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
# Idempotency (create/rent/release/refund)
# ---------------------------------------------------------------------------

class TestMarketplaceIdempotency:
    def _create_listing(self, client, seller_token):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 1.0, "bandwidth_mbps": 100},
            headers={"X-API-Key": seller_token},
        )
        return node_id, r.json()["listing_id"]

    def _create_rented_listing(self, client, seller_token, buyer_token):
        _, listing_id = self._create_listing(client, seller_token)
        rent = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-idem",
            headers={"X-API-Key": buyer_token},
        )
        assert rent.status_code == 200
        return listing_id

    def test_create_listing_idempotent_replay(self, client, market_data):
        node_id = _unique_node()
        idem_key = f"idem-create-{uuid.uuid4().hex[:10]}"
        headers = {
            "X-API-Key": market_data["seller_token"],
            "Idempotency-Key": idem_key,
        }
        payload = {
            "node_id": node_id,
            "region": "us-east",
            "price_per_hour": 0.9,
            "bandwidth_mbps": 100,
        }

        first = client.post("/api/v1/maas/marketplace/list", json=payload, headers=headers)
        second = client.post("/api/v1/maas/marketplace/list", json=payload, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["listing_id"] == second.json()["listing_id"]

        db = TestingSessionLocal()
        count = db.query(MarketplaceListing).filter(MarketplaceListing.node_id == node_id).count()
        db.close()
        assert count == 1

    def test_rent_idempotent_replay(self, client, market_data):
        _, listing_id = self._create_listing(client, market_data["seller_token"])
        idem_key = f"idem-rent-{uuid.uuid4().hex[:10]}"
        headers = {
            "X-API-Key": market_data["buyer_token"],
            "Idempotency-Key": idem_key,
        }

        first = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-idem-rent",
            headers=headers,
        )
        second = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-idem-rent",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["escrow_id"] == second.json()["escrow_id"]
        assert first.json()["status"] == "escrow"
        assert second.json()["status"] == "escrow"

        db = TestingSessionLocal()
        held_count = (
            db.query(MarketplaceEscrow)
            .filter(
                MarketplaceEscrow.listing_id == listing_id,
                MarketplaceEscrow.status == "held",
            )
            .count()
        )
        db.close()
        assert held_count == 1

    def test_release_idempotent_replay(self, client, market_data):
        listing_id = self._create_rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"]
        )
        idem_key = f"idem-release-{uuid.uuid4().hex[:10]}"
        headers = {
            "X-API-Key": market_data["buyer_token"],
            "Idempotency-Key": idem_key,
        }

        first = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers=headers,
        )
        second = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["status"] == "released"
        assert second.json()["status"] == "released"
        assert first.json()["listing_id"] == second.json()["listing_id"] == listing_id
        assert first.json()["released_at"] == second.json()["released_at"]

    def test_refund_idempotent_replay(self, client, market_data):
        listing_id = self._create_rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"]
        )
        idem_key = f"idem-refund-{uuid.uuid4().hex[:10]}"
        headers = {
            "X-API-Key": market_data["buyer_token"],
            "Idempotency-Key": idem_key,
        }

        first = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers=headers,
        )
        second = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["status"] == "refunded"
        assert second.json()["status"] == "refunded"
        assert first.json()["listing_id"] == second.json()["listing_id"] == listing_id

        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row is not None
        assert row.status == "available"
        db.close()

    def test_create_rejects_invalid_idempotency_key_chars(self, client, market_data):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={
                "node_id": node_id,
                "region": "us-east",
                "price_per_hour": 1.0,
                "bandwidth_mbps": 100,
            },
            headers={
                "X-API-Key": market_data["seller_token"],
                "Idempotency-Key": "bad key with spaces",
            },
        )
        assert r.status_code == 400
        assert "Idempotency-Key" in r.json()["detail"]

    def test_create_rejects_too_long_idempotency_key(self, client, market_data):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={
                "node_id": node_id,
                "region": "us-east",
                "price_per_hour": 1.0,
                "bandwidth_mbps": 100,
            },
            headers={
                "X-API-Key": market_data["seller_token"],
                "Idempotency-Key": "x" * 1024,
            },
        )
        assert r.status_code == 400
        assert "Idempotency-Key" in r.json()["detail"]

    def test_rent_rechecks_db_status_when_cache_is_stale(self, client, market_data):
        import src.api.maas_marketplace as marketplace_mod

        _, listing_id = self._create_listing(client, market_data["seller_token"])
        first = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-stale-1",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert first.status_code == 200, first.text

        # Simulate stale cache that still marks listing as available.
        with marketplace_mod._listings_lock:
            marketplace_mod._listings[listing_id]["status"] = "available"
            marketplace_mod._listings[listing_id]["renter_id"] = None
            marketplace_mod._listings[listing_id]["mesh_id"] = None

        second = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-stale-2",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert second.status_code == 400
        assert "not available" in second.json()["detail"].lower()

        db = TestingSessionLocal()
        held_count = (
            db.query(MarketplaceEscrow)
            .filter(
                MarketplaceEscrow.listing_id == listing_id,
                MarketplaceEscrow.status == "held",
            )
            .count()
        )
        db.close()
        assert held_count == 1

    def test_release_rechecks_db_renter_when_cache_is_tampered(self, client, market_data):
        import src.api.maas_marketplace as marketplace_mod

        listing_id = self._create_rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"]
        )

        db = TestingSessionLocal()
        seller = db.query(User).filter(User.api_key == market_data["seller_token"]).first()
        seller_id = seller.id
        db.close()

        # Tamper cache to impersonate seller as renter.
        with marketplace_mod._listings_lock:
            marketplace_mod._listings[listing_id]["renter_id"] = seller_id

        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/release",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 403

    def test_refund_rechecks_db_renter_when_cache_is_tampered(self, client, market_data):
        import src.api.maas_marketplace as marketplace_mod

        listing_id = self._create_rented_listing(
            client, market_data["seller_token"], market_data["buyer_token"]
        )

        db = TestingSessionLocal()
        seller = db.query(User).filter(User.api_key == market_data["seller_token"]).first()
        seller_id = seller.id
        db.close()

        with marketplace_mod._listings_lock:
            marketplace_mod._listings[listing_id]["renter_id"] = seller_id

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

    def test_cancel_rechecks_db_state_when_cache_is_stale(self, client, market_data):
        import src.api.maas_marketplace as marketplace_mod

        listing_id = self._create(client, market_data["seller_token"])
        # Move real DB state to rented while keeping cache stale/available.
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        row.status = "rented"
        db.commit()
        db.close()

        with marketplace_mod._listings_lock:
            marketplace_mod._listings[listing_id]["status"] = "available"

        r = client.delete(
            f"/api/v1/maas/marketplace/list/{listing_id}",
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 400
        assert "active rental state" in r.json()["detail"]


class TestX0TTokenMarketplace:
    def test_create_listing_x0t(self, client, market_data):
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "eu-central",
                  "price_token_per_hour": 10.5, "currency": "X0T", "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["currency"] == "X0T"
        assert data["price_token_per_hour"] == 10.5
        assert data["price_per_hour"] is None

    def test_search_filter_by_currency(self, client, market_data):
        # Create one USD and one X0T listing
        node_usd = _unique_node()
        node_x0t = _unique_node()
        client.post("/api/v1/maas/marketplace/list",
                    json={"node_id": node_usd, "region": "global", "price_per_hour": 1.0, "currency": "USD", "bandwidth_mbps": 100},
                    headers={"X-API-Key": market_data["seller_token"]})
        client.post("/api/v1/maas/marketplace/list",
                    json={"node_id": node_x0t, "region": "global", "price_token_per_hour": 50.0, "currency": "X0T", "bandwidth_mbps": 100},
                    headers={"X-API-Key": market_data["seller_token"]})

        # Search for X0T only
        r = client.get("/api/v1/maas/marketplace/search?currency=X0T")
        results = r.json()
        assert all(x["currency"] == "X0T" for x in results)
        assert any(x["node_id"] == node_x0t for x in results)
        assert not any(x["node_id"] == node_usd for x in results)

    def test_rent_success_x0t(self, client, market_data):
        node_id = _unique_node()
        r_list = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-west",
                  "price_token_per_hour": 5.0, "currency": "X0T", "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        listing_id = r_list.json()["listing_id"]

        r_rent = client.post(
            f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-token-1&hours=2",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r_rent.status_code == 200, r_rent.text
        data = r_rent.json()
        assert data["status"] == "escrow"
        assert data["currency"] == "X0T"
        assert data["amount_held_token"] == 10.0  # 5.0 * 2 hours
        assert data["amount_held_cents"] is None

    def test_search_x0t_applies_global_multiplier(self, client, market_data):
        node_id = _unique_node()
        _set_global_multiplier(1.5)
        try:
            r_list = client.post(
                "/api/v1/maas/marketplace/list",
                json={
                    "node_id": node_id,
                    "region": "global",
                    "price_token_per_hour": 10.0,
                    "currency": "X0T",
                    "bandwidth_mbps": 100,
                },
                headers={"X-API-Key": market_data["seller_token"]},
            )
            assert r_list.status_code == 200, r_list.text

            r_search = client.get("/api/v1/maas/marketplace/search?currency=X0T&region=global")
            assert r_search.status_code == 200, r_search.text
            matched = [x for x in r_search.json() if x["node_id"] == node_id]
            assert matched, r_search.json()
            assert matched[0]["price_token_per_hour"] == 15.0
        finally:
            _clear_global_multiplier()

    def test_search_x0t_max_price_uses_global_multiplier(self, client, market_data):
        node_id = _unique_node()
        _set_global_multiplier(1.5)
        try:
            r_list = client.post(
                "/api/v1/maas/marketplace/list",
                json={
                    "node_id": node_id,
                    "region": "us-east",
                    "price_token_per_hour": 10.0,
                    "currency": "X0T",
                    "bandwidth_mbps": 100,
                },
                headers={"X-API-Key": market_data["seller_token"]},
            )
            assert r_list.status_code == 200, r_list.text

            r_search = client.get(
                "/api/v1/maas/marketplace/search?currency=X0T&max_price=12&region=us-east"
            )
            assert r_search.status_code == 200, r_search.text
            assert all(item["node_id"] != node_id for item in r_search.json())
        finally:
            _clear_global_multiplier()

    def test_rent_x0t_amount_uses_global_multiplier(self, client, market_data):
        node_id = _unique_node()
        _set_global_multiplier(1.5)
        try:
            r_list = client.post(
                "/api/v1/maas/marketplace/list",
                json={
                    "node_id": node_id,
                    "region": "us-west",
                    "price_token_per_hour": 5.0,
                    "currency": "X0T",
                    "bandwidth_mbps": 100,
                },
                headers={"X-API-Key": market_data["seller_token"]},
            )
            assert r_list.status_code == 200, r_list.text
            listing_id = r_list.json()["listing_id"]

            r_rent = client.post(
                f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id=mesh-token-global&hours=2",
                headers={"X-API-Key": market_data["buyer_token"]},
            )
            assert r_rent.status_code == 200, r_rent.text
            data = r_rent.json()
            assert data["currency"] == "X0T"
            assert data["amount_held_token"] == pytest.approx(15.0)
        finally:
            _clear_global_multiplier()


# ---------------------------------------------------------------------------
# Edge cases: 404 and 400 for release/refund on nonexistent/wrong-state listings
# ---------------------------------------------------------------------------

class TestEscrowEdgeCases:
    def test_release_nonexistent_listing_404(self, client, market_data):
        """release_escrow on a listing that doesn't exist → 404."""
        r = client.post(
            "/api/v1/maas/marketplace/escrow/lst-does-not-exist/release",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 404

    def test_refund_nonexistent_listing_404(self, client, market_data):
        """refund_escrow on a listing that doesn't exist → 404."""
        r = client.post(
            "/api/v1/maas/marketplace/escrow/lst-does-not-exist-x/refund",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 404

    def test_refund_listing_not_in_escrow_400(self, client, market_data):
        """refund_escrow on an available (not-in-escrow) listing → 400."""
        node_id = _unique_node()
        r = client.post(
            "/api/v1/maas/marketplace/list",
            json={"node_id": node_id, "region": "us-east",
                  "price_per_hour": 0.5, "bandwidth_mbps": 100},
            headers={"X-API-Key": market_data["seller_token"]},
        )
        listing_id = r.json()["listing_id"]
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{listing_id}/refund",
            headers={"X-API-Key": market_data["buyer_token"]},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Unit-style tests for _db_session_available and _as_listing_response
# ---------------------------------------------------------------------------

class TestMarketplaceUtilityFunctions:
    """Direct tests for marketplace utility helpers (no TestClient needed)."""

    def test_db_session_available_with_session_like_object(self):
        """Object with 'query' and 'commit' → True."""
        from unittest.mock import MagicMock
        from src.api.maas_marketplace import _db_session_available
        mock_db = MagicMock(spec=["query", "commit"])
        assert _db_session_available(mock_db) is True

    def test_db_session_available_with_dict_returns_false(self):
        """Plain dict has no 'query' attr → False."""
        from src.api.maas_marketplace import _db_session_available
        assert _db_session_available({}) is False

    def test_db_session_available_with_none_returns_false(self):
        """None → False."""
        from src.api.maas_marketplace import _db_session_available
        assert _db_session_available(None) is False

    def test_db_session_available_has_query_but_no_commit_returns_false(self):
        """Object with 'query' only (no 'commit') → False."""
        from unittest.mock import MagicMock
        from src.api.maas_marketplace import _db_session_available
        mock_db = MagicMock(spec=["query"])  # has query but not commit
        assert _db_session_available(mock_db) is False

    def test_as_listing_response_maps_all_fields(self):
        """_as_listing_response maps all expected keys from the data dict."""
        from src.api.maas_marketplace import _as_listing_response
        import datetime
        data = {
            "listing_id": "lst-abc123",
            "owner_id": "owner-1",
            "node_id": "node-xyz",
            "region": "us-east",
            "price_per_hour": 0.75,
            "currency": "USD",
            "bandwidth_mbps": 100,
            "status": "available",
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        result = _as_listing_response(data)
        assert result["listing_id"] == "lst-abc123"
        assert result["owner_id"] == "owner-1"
        assert result["node_id"] == "node-xyz"
        assert result["region"] == "us-east"
        assert result["price_per_hour"] == 0.75
        assert result["currency"] == "USD"
        assert result["bandwidth_mbps"] == 100
        assert result["status"] == "available"
        assert result["trust_score"] == 0.5
        assert "created_at" in result

    def test_as_listing_response_preserves_status(self):
        """_as_listing_response preserves status field as-is."""
        from src.api.maas_marketplace import _as_listing_response
        import datetime
        data = {
            "listing_id": "lst-xyz", "owner_id": "o1", "node_id": "n1",
            "region": "eu-central", "price_per_hour": 1.0, "bandwidth_mbps": 50,
            "status": "in_escrow", "created_at": datetime.datetime.utcnow().isoformat(),
        }
        result = _as_listing_response(data)
        assert result["status"] == "in_escrow"

    def test_as_listing_response_applies_global_multiplier_for_x0t(self):
        """X0T listing response must apply the passed global multiplier."""
        from src.api.maas_marketplace import _as_listing_response
        data = {
            "listing_id": "lst-token-1",
            "owner_id": "owner-1",
            "node_id": "node-token-1",
            "region": "global",
            "price_token_per_hour": 8.0,
            "currency": "X0T",
            "bandwidth_mbps": 100,
            "status": "available",
            "created_at": datetime.utcnow().isoformat(),
        }
        result = _as_listing_response(data, multiplier=1.25)
        assert result["price_per_hour"] is None
        assert result["price_token_per_hour"] == 10.0
