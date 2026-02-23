"""
Integration tests for MaaS Marketplace Escrow and Node Heartbeat.

Tests the full rental lifecycle:
  available → escrow (on rent) → rented (on heartbeat/release) or
  available → escrow → available (on refund)
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, MeshNode, MeshInstance, MarketplaceListing

_TEST_DB_PATH = f"./test_escrow_{uuid.uuid4().hex}.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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
def seller_token(client):
    email = f"seller-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def buyer_token(client):
    email = f"buyer-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["access_token"]


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def create_listing(client, seller_token) -> dict:
    """Create a fresh listing and return its JSON payload."""
    node_id = f"nd-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/maas/marketplace/list",
        headers={"X-API-Key": seller_token},
        json={"node_id": node_id, "region": "eu-central", "price_per_hour": 0.50, "bandwidth_mbps": 500},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────
# Escrow creation
# ─────────────────────────────────────────────

class TestEscrowCreation:
    def test_rent_creates_escrow(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        r = client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "test-mesh-1"},
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "escrow"
        assert "escrow_id" in data
        assert data["amount_held_cents"] == 50  # 0.50 * 100

    def test_rent_sets_listing_to_escrow(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        r = client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 200

        # Listing should no longer appear in search
        search = client.get("/api/v1/maas/marketplace/search")
        found_ids = [x["listing_id"] for x in search.json()]
        assert lid not in found_ids

    def test_cannot_rent_own_listing(self, client, seller_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        r = client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": seller_token},
        )
        assert r.status_code == 400
        assert "own" in r.json()["detail"].lower()

    def test_cannot_double_rent(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        r1 = client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )
        assert r1.status_code == 200

        r2 = client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m2"},
            headers={"X-API-Key": buyer_token},
        )
        assert r2.status_code == 400
        assert "not available" in r2.json()["detail"].lower()


# ─────────────────────────────────────────────
# Manual escrow release
# ─────────────────────────────────────────────

class TestEscrowRelease:
    def test_buyer_can_release_escrow(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )

        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/release",
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "released"
        assert data["listing_id"] == lid
        assert "released_at" in data

    def test_release_changes_listing_to_rented(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )
        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/release",
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 200

        # DB check
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == lid).first()
        db.close()
        assert row is not None
        assert row.status == "rented"

    def test_cannot_release_non_escrow_listing(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/release",
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 400

    def test_seller_cannot_release_own_escrow(self, client, seller_token, buyer_token):
        """Seller has no renter permissions and must not release escrow."""
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )

        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/release",
            headers={"X-API-Key": seller_token},
        )
        # Seller has marketplace:list but not marketplace:rent → 403
        assert r.status_code == 403


# ─────────────────────────────────────────────
# Escrow refund
# ─────────────────────────────────────────────

class TestEscrowRefund:
    def test_buyer_can_refund_escrow(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )

        r = client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/refund",
            headers={"X-API-Key": buyer_token},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "refunded"

    def test_refund_returns_listing_to_available(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )
        client.post(
            f"/api/v1/maas/marketplace/escrow/{lid}/refund",
            headers={"X-API-Key": buyer_token},
        )

        search = client.get("/api/v1/maas/marketplace/search")
        found_ids = [x["listing_id"] for x in search.json()]
        assert lid in found_ids

    def test_cannot_cancel_listing_with_active_escrow(self, client, seller_token, buyer_token):
        listing = create_listing(client, seller_token)
        lid = listing["listing_id"]

        client.post(
            f"/api/v1/maas/marketplace/rent/{lid}",
            params={"mesh_id": "m1"},
            headers={"X-API-Key": buyer_token},
        )

        r = client.delete(
            f"/api/v1/maas/marketplace/list/{lid}",
            headers={"X-API-Key": seller_token},
        )
        assert r.status_code == 400
        assert "escrow" in r.json()["detail"].lower()


# ─────────────────────────────────────────────
# Heartbeat auto-release
# ─────────────────────────────────────────────

class TestHeartbeatAutoRelease:
    def _setup_mesh_and_node(self, client, seller_token) -> tuple[str, str, str]:
        """Create mesh + node, return (mesh_id, node_id, listing_id)."""
        r = client.post(
            "/api/v1/maas/deploy",
            json={"name": "hb-mesh", "nodes": 1, "billing_plan": "starter"},
            headers={"X-API-Key": seller_token},
        )
        assert r.status_code == 200, r.text
        mesh_id = r.json()["mesh_id"]

        # Insert an approved node directly into DB for heartbeat + escrow flows.
        db = TestingSessionLocal()
        node_id = f"nd-{uuid.uuid4().hex[:6]}"
        db_node = MeshNode(
            id=node_id, mesh_id=mesh_id, device_class="edge", status="approved"
        )
        db.add(db_node)
        db.commit()
        db.close()

        return mesh_id, node_id

    def test_heartbeat_updates_last_seen(self, client, seller_token, buyer_token):
        mesh_id, node_id = self._setup_mesh_and_node(client, seller_token)

        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["node_status"] == "approved"
        assert "last_seen" in data

    def test_heartbeat_releases_escrow_automatically(self, client, seller_token, buyer_token):
        mesh_id, node_id = self._setup_mesh_and_node(client, seller_token)

        # Create listing for that node_id directly in DB
        db = TestingSessionLocal()
        listing_id = f"lst-{uuid.uuid4().hex[:8]}"
        buyer_id = db.query(User).filter(User.email.like("buyer-%")).first().id
        from src.database import MarketplaceEscrow
        db_listing = MarketplaceListing(
            id=listing_id, owner_id=db.query(User).filter(User.email.like("seller-%")).first().id,
            node_id=node_id, region="eu-central", price_per_hour=50,
            bandwidth_mbps=100, status="escrow", renter_id=buyer_id, mesh_id=mesh_id,
        )
        db.add(db_listing)
        db_escrow = MarketplaceEscrow(
            id=f"esc-{uuid.uuid4().hex[:8]}", listing_id=listing_id,
            renter_id=buyer_id, amount_cents=50, status="held",
        )
        db.add(db_escrow)
        db.commit()
        db.close()

        # Send healthy heartbeat
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["escrow_released"] is not None  # escrow was released

        # Verify DB state
        db = TestingSessionLocal()
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        assert row.status == "rented"
        db.close()

    def test_heartbeat_404_unknown_node(self, client, seller_token):
        r = client.post(
            "/api/v1/maas/mesh-x/nodes/nd-unknown/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 404


# ─────────────────────────────────────────────
# Server-side ACL check
# ─────────────────────────────────────────────

class TestAccessCheck:
    @staticmethod
    def _ensure_operator(api_key: str):
        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == api_key).first()
        user.role = "operator"
        db.commit()
        db.close()

    @staticmethod
    def _headers(api_key: str) -> dict:
        return {"X-API-Key": api_key}

    def _make_mesh_with_nodes(self, client, seller_token) -> tuple:
        """Returns (mesh_id, node_a_id, node_b_id)."""
        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == seller_token).first()
        assert user is not None

        mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
        db.add(MeshInstance(
            id=mesh_id,
            name="acl-mesh",
            owner_id=user.id,
            plan="starter",
            status="active",
            join_token=f"join-{uuid.uuid4().hex[:8]}",
        ))

        na = f"na-{uuid.uuid4().hex[:6]}"
        nb = f"nb-{uuid.uuid4().hex[:6]}"
        db.add(MeshNode(id=na, mesh_id=mesh_id, device_class="edge",
                        status="approved", acl_profile="frontend"))
        db.add(MeshNode(id=nb, mesh_id=mesh_id, device_class="edge",
                        status="approved", acl_profile="backend"))
        db.commit()
        db.close()
        return mesh_id, na, nb

    def test_deny_by_default_no_policies(self, client, seller_token):
        mesh_id, na, nb = self._make_mesh_with_nodes(client, seller_token)
        self._ensure_operator(seller_token)

        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/check-access",
            json={"source_node_id": na, "target_node_id": nb},
            headers=self._headers(seller_token),
        )
        assert r.status_code == 200
        assert r.json()["verdict"] == "deny"

    def test_allow_when_policy_matches(self, client, seller_token):
        from src.database import ACLPolicy
        mesh_id, na, nb = self._make_mesh_with_nodes(client, seller_token)
        self._ensure_operator(seller_token)

        # Insert allow policy directly into DB (clean, no auth dependency)
        pol_id = f"pol-{uuid.uuid4().hex[:6]}"
        db = TestingSessionLocal()
        db.add(ACLPolicy(
            id=pol_id, mesh_id=mesh_id,
            source_tag="frontend", target_tag="backend", action="allow",
        ))
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/check-access",
            json={"source_node_id": na, "target_node_id": nb},
            headers=self._headers(seller_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["verdict"] == "allow"
        assert data["policy_id"] == pol_id

    def test_deny_explicitly_by_policy(self, client, seller_token):
        from src.database import ACLPolicy
        mesh_id, na, nb = self._make_mesh_with_nodes(client, seller_token)
        self._ensure_operator(seller_token)

        pol_id = f"pol-{uuid.uuid4().hex[:6]}"
        db = TestingSessionLocal()
        db.add(ACLPolicy(
            id=pol_id, mesh_id=mesh_id,
            source_tag="frontend", target_tag="backend", action="deny",
        ))
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/check-access",
            json={"source_node_id": na, "target_node_id": nb},
            headers=self._headers(seller_token),
        )
        assert r.status_code == 200
        assert r.json()["verdict"] == "deny"
        assert r.json()["policy_id"] == pol_id

    def test_check_access_unknown_node(self, client, seller_token):
        self._ensure_operator(seller_token)
        r = client.post(
            "/api/v1/maas/mesh-x/nodes/check-access",
            json={"source_node_id": "unknown-1", "target_node_id": "unknown-2"},
            headers=self._headers(seller_token),
        )
        assert r.status_code == 404
