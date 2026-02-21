"""
Unit tests for src/api/maas_analytics.py — Analytics summary and timeseries.
Covers cost calculations, permission enforcement, and edge cases.
"""
import uuid
import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.app import app
from src.database import Base, get_db, User, MeshInstance, MeshNode, Invoice

_TEST_DB_PATH = f"./test_analytics_{uuid.uuid4().hex}.db"
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
    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if original is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def operator_user(client):
    """Register a user and upgrade to operator role (has analytics:view)."""
    email = f"analyst-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    # Upgrade to operator via DB
    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == api_key).first()
    user.role = "operator"
    user_id = user.id
    db.commit()
    db.close()
    return {"email": email, "api_key": api_key, "user_id": user_id,
            "headers": {"X-API-Key": api_key}}


@pytest.fixture(scope="module")
def plain_user(client):
    """Regular user without analytics:view permission."""
    email = f"plain-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == api_key).first()
    user_id = user.id
    db.close()
    return {"api_key": api_key, "user_id": user_id, "headers": {"X-API-Key": api_key}}


@pytest.fixture(scope="module")
def mesh_no_nodes(operator_user):
    """Mesh with zero nodes for edge-case tests."""
    db = TestingSessionLocal()
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    mesh = MeshInstance(
        id=mesh_id,
        name="analytics-mesh-empty",
        owner_id=operator_user["user_id"],
        plan="starter",
        status="active",
        pqc_enabled=True,
    )
    db.add(mesh)
    db.commit()
    db.close()
    return mesh_id


@pytest.fixture(scope="module")
def mesh_with_nodes_and_invoice(operator_user):
    """Mesh with nodes and a billing invoice."""
    db = TestingSessionLocal()
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    mesh = MeshInstance(
        id=mesh_id,
        name="analytics-mesh-full",
        owner_id=operator_user["user_id"],
        plan="pro",
        status="active",
        pqc_enabled=True,
    )
    db.add(mesh)
    # 3 nodes
    for i in range(3):
        db.add(MeshNode(id=f"node-{uuid.uuid4().hex[:8]}", mesh_id=mesh_id,
                        device_class="gateway", status="healthy"))
    # Invoice: $50 (5000 cents) in last 30 days
    invoice = Invoice(
        id=f"inv-{uuid.uuid4().hex[:8]}",
        mesh_id=mesh_id,
        user_id=operator_user["user_id"],
        total_amount=5000,
        status="paid",
        issued_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(invoice)
    db.commit()
    db.close()
    return mesh_id


class TestAnalyticsSummary:
    def test_summary_unauthenticated_returns_401(self, client):
        """Analytics requires authentication."""
        resp = client.get("/api/v1/maas/analytics/some-mesh/summary")
        assert resp.status_code == 401

    def test_summary_unpermitted_user_returns_403(self, client, plain_user, mesh_no_nodes):
        """User without analytics:view cannot access summary."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_no_nodes}/summary",
            headers=plain_user["headers"],
        )
        assert resp.status_code == 403

    def test_summary_wrong_owner_returns_404(self, client, plain_user, mesh_no_nodes):
        """Operator accessing another user's mesh gets 404."""
        # Give plain_user operator role temporarily
        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == plain_user["api_key"]).first()
        old_role = user.role
        user.role = "operator"
        db.commit()
        db.close()
        try:
            resp = client.get(
                f"/api/v1/maas/analytics/{mesh_no_nodes}/summary",
                headers=plain_user["headers"],
            )
            assert resp.status_code == 404
        finally:
            db = TestingSessionLocal()
            user = db.query(User).filter(User.api_key == plain_user["api_key"]).first()
            user.role = old_role
            db.commit()
            db.close()

    def test_summary_zero_nodes_zero_savings(self, client, operator_user, mesh_no_nodes):
        """Mesh with no nodes: AWS estimate=0, savings=0%."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_no_nodes}/summary",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mesh_id"] == mesh_no_nodes
        assert data["cost_aws_estimate"] == 0.0
        assert data["savings_pct"] == 0.0
        assert data["nodes_online"] == 0
        assert data["pqc_status"] is True

    def test_summary_with_nodes_and_invoice(self, client, operator_user, mesh_with_nodes_and_invoice):
        """Mesh with 3 nodes and $50 invoice: AWS=$135, savings calculated."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_with_nodes_and_invoice}/summary",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes_online"] == 3
        assert data["cost_maas_total"] == pytest.approx(50.0, abs=0.01)
        assert data["cost_aws_estimate"] == pytest.approx(135.0, abs=0.01)  # 3 * $45
        # savings = (135 - 50) / 135 * 100 ≈ 63%
        assert data["savings_pct"] == pytest.approx(62.96, abs=1.0)
        assert data["pqc_status"] is True

    def test_summary_nonexistent_mesh_returns_404(self, client, operator_user):
        """Analytics for non-existent mesh returns 404."""
        resp = client.get(
            "/api/v1/maas/analytics/mesh-doesnotexist/summary",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 404


class TestAnalyticsTimeseries:
    def test_timeseries_unauthenticated_returns_401(self, client):
        """Timeseries requires authentication."""
        resp = client.get("/api/v1/maas/analytics/some-mesh/timeseries")
        assert resp.status_code == 401

    def test_timeseries_authenticated_returns_24_points(self, client, operator_user, mesh_no_nodes):
        """Timeseries returns 24 hourly data points."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_no_nodes}/timeseries",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) == 24
        point = data["data"][0]
        assert "timestamp" in point
        assert "health" in point
        assert "traffic_mbps" in point
        assert "latency_ms" in point

    def test_timeseries_data_within_bounds(self, client, operator_user, mesh_no_nodes):
        """Timeseries health values are 0-100, latency >= 5ms."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_no_nodes}/timeseries",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 200
        for point in resp.json()["data"]:
            assert 0.0 <= point["health"] <= 100.0
            assert point["latency_ms"] >= 5.0
            assert point["traffic_mbps"] >= 0.0

    def test_timeseries_nonexistent_mesh_returns_404(self, client, operator_user):
        """Timeseries for non-existent mesh returns 404."""
        resp = client.get(
            "/api/v1/maas/analytics/mesh-doesnotexist/timeseries",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 404

    def test_timeseries_default_range_is_24h(self, client, operator_user, mesh_no_nodes):
        """Response includes range field."""
        resp = client.get(
            f"/api/v1/maas/analytics/{mesh_no_nodes}/timeseries",
            headers=operator_user["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["range"] == "24h"
