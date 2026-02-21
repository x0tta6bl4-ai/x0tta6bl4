"""
Integration tests for MaaS Analytics:
- GET /{mesh_id}/summary — AnalyticsSummary fields, RBAC, ownership isolation
- GET /{mesh_id}/timeseries — time_range param, data structure, data point count
- GET /{mesh_id}/marketplace-roi — ROI breakdown, listing status aggregation

Permissions:
  - user role: NO analytics:view → 403
  - operator role: has analytics:view → 200
  - admin: bypass → 200
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, MeshInstance, MeshNode, MarketplaceListing

_TEST_DB_PATH = f"./test_analytics_{uuid.uuid4().hex}.db"
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
def analytics_data(client):
    """Register a regular user, an operator, and set up a mesh with nodes and listings."""
    email_user = f"ana-user-{uuid.uuid4().hex[:8]}@test.com"
    email_op = f"ana-op-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email_user, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    user_token = r.json()["access_token"]

    r = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email_op, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    op_token = r.json()["access_token"]

    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == user_token).first()
    operator = db.query(User).filter(User.api_key == op_token).first()
    user_id = user.id
    op_id = operator.id

    # Elevate operator
    operator.role = "operator"
    db.commit()

    mesh_id = f"mesh-ana-{uuid.uuid4().hex[:6]}"
    mesh = MeshInstance(
        id=mesh_id,
        name="Analytics Test Mesh",
        owner_id=op_id,
        status="active",
        pqc_enabled=True,
    )
    db.add(mesh)

    # 2 healthy nodes (recently seen)
    for _ in range(2):
        db.add(MeshNode(
            id=f"nd-{uuid.uuid4().hex[:8]}",
            mesh_id=mesh_id,
            status="approved",
            device_class="gateway",
            hardware_id=f"tpm-{uuid.uuid4().hex[:6]}",
            enclave_enabled=True,
            last_seen=datetime.utcnow() - timedelta(minutes=1),
        ))

    # 1 stale node
    db.add(MeshNode(
        id=f"nd-{uuid.uuid4().hex[:8]}",
        mesh_id=mesh_id,
        status="approved",
        device_class="edge",
        hardware_id=None,
        enclave_enabled=False,
        last_seen=datetime.utcnow() - timedelta(minutes=20),
    ))

    # Marketplace listings
    db.add(MarketplaceListing(
        id=f"lst-{uuid.uuid4().hex[:8]}",
        owner_id=op_id,
        node_id=None,
        price_per_hour=50,   # $0.50/hr
        status="rented",
        bandwidth_mbps=100.0,
    ))
    db.add(MarketplaceListing(
        id=f"lst-{uuid.uuid4().hex[:8]}",
        owner_id=op_id,
        node_id=None,
        price_per_hour=75,   # $0.75/hr
        status="available",
        bandwidth_mbps=200.0,
    ))
    db.add(MarketplaceListing(
        id=f"lst-{uuid.uuid4().hex[:8]}",
        owner_id=op_id,
        node_id=None,
        price_per_hour=100,  # $1.00/hr
        status="escrow",
        bandwidth_mbps=150.0,
    ))
    db.commit()
    db.close()

    return {
        "user_token": user_token,
        "op_token": op_token,
        "user_id": user_id,
        "op_id": op_id,
        "mesh_id": mesh_id,
    }


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

class TestAnalyticsSummary:
    def test_summary_requires_auth(self, client, analytics_data):
        r = client.get(f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary")
        assert r.status_code == 401

    def test_summary_user_role_forbidden(self, client, analytics_data):
        """user role lacks analytics:view"""
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["user_token"]},
        )
        assert r.status_code == 403

    def test_summary_operator_allowed(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.status_code == 200, r.text

    def test_summary_fields_present(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        expected_fields = {
            "mesh_id", "cost_maas_total", "cost_aws_estimate",
            "savings_pct", "pqc_status", "nodes_total",
            "nodes_online", "health_score",
        }
        assert expected_fields.issubset(data.keys())

    def test_summary_mesh_id_matches(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["mesh_id"] == analytics_data["mesh_id"]

    def test_summary_pqc_status_true(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["pqc_status"] is True

    def test_summary_nodes_total(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["nodes_total"] == 3

    def test_summary_nodes_online(self, client, analytics_data):
        """2 healthy nodes seen within 5 min → nodes_online == 2"""
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["nodes_online"] == 2

    def test_summary_health_score_range(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        score = r.json()["health_score"]
        assert 0.0 <= score <= 1.0

    def test_summary_cost_aws_estimate(self, client, analytics_data):
        """cost_aws_estimate = nodes * $45"""
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        assert data["cost_aws_estimate"] == 3 * 45.0

    def test_summary_unknown_mesh_404(self, client, analytics_data):
        r = client.get(
            "/api/v1/maas/analytics/mesh-nonexistent/summary",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.status_code == 404

    def test_summary_other_user_mesh_404(self, client, analytics_data):
        """Operator cannot see another user's mesh"""
        r2 = client.post(
            "/api/v1/maas/auth/register",
            json={"email": f"other-{uuid.uuid4().hex[:8]}@test.com", "password": "pw123456"},
        )
        other_token = r2.json()["access_token"]
        # elevate to operator so RBAC passes
        db = TestingSessionLocal()
        other = db.query(User).filter(User.api_key == other_token).first()
        other.role = "operator"
        db.commit()
        db.close()

        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/summary",
            headers={"X-API-Key": other_token},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Timeseries endpoint
# ---------------------------------------------------------------------------

class TestAnalyticsTimeseries:
    def test_timeseries_requires_auth(self, client, analytics_data):
        r = client.get(f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries")
        assert r.status_code == 401

    def test_timeseries_user_role_forbidden(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries",
            headers={"X-API-Key": analytics_data["user_token"]},
        )
        assert r.status_code == 403

    def test_timeseries_operator_allowed(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.status_code == 200, r.text

    def test_timeseries_default_24h(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        assert data["range"] == "24h"
        assert len(data["data"]) == 24

    def test_timeseries_7d_168_points(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries?time_range=7d",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        assert data["range"] == "7d"
        assert len(data["data"]) == 168

    def test_timeseries_6h_6_points(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries?time_range=6h",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        assert data["range"] == "6h"
        assert len(data["data"]) == 6

    def test_timeseries_data_point_structure(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries?time_range=1h",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        point = r.json()["data"][0]
        assert "timestamp" in point
        assert "health" in point
        assert "traffic_mbps" in point
        assert "latency_ms" in point

    def test_timeseries_mesh_id_in_response(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["mesh_id"] == analytics_data["mesh_id"]

    def test_timeseries_nodes_total(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/timeseries",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["nodes_total"] == 3

    def test_timeseries_unknown_mesh_404(self, client, analytics_data):
        r = client.get(
            "/api/v1/maas/analytics/mesh-nonexistent/timeseries",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Marketplace ROI endpoint
# ---------------------------------------------------------------------------

class TestAnalyticsROI:
    def test_roi_requires_auth(self, client, analytics_data):
        r = client.get(f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi")
        assert r.status_code == 401

    def test_roi_user_role_forbidden(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["user_token"]},
        )
        assert r.status_code == 403

    def test_roi_operator_allowed(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.status_code == 200, r.text

    def test_roi_structure(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        data = r.json()
        assert "listings" in data
        assert "revenue" in data

    def test_roi_listings_total(self, client, analytics_data):
        """3 listings created in fixture"""
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        listings = r.json()["listings"]
        assert listings["total"] == 3

    def test_roi_listing_status_breakdown(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        listings = r.json()["listings"]
        assert listings["available"] == 1
        assert listings["rented"] == 1
        assert listings["in_escrow"] == 1

    def test_roi_revenue_calculation(self, client, analytics_data):
        """rented(50) + escrow(100) = 150 cents/hr = $1.50/hr"""
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        revenue = r.json()["revenue"]
        assert revenue["hourly_cents"] == 150
        assert revenue["hourly_usd"] == 1.50
        assert revenue["monthly_estimate_usd"] == round(1.50 * 24 * 30, 2)

    def test_roi_mesh_id_in_response(self, client, analytics_data):
        r = client.get(
            f"/api/v1/maas/analytics/{analytics_data['mesh_id']}/marketplace-roi",
            headers={"X-API-Key": analytics_data["op_token"]},
        )
        assert r.json()["mesh_id"] == analytics_data["mesh_id"]
