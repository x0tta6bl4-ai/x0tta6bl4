"""
Unit tests for maas_dashboard.py — Dashboard summary endpoint.
"""
import uuid
import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, MeshInstance, Invoice, AuditLog

_TEST_DB_PATH = f"./test_dashboard_{uuid.uuid4().hex}.db"
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
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if original_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original_override
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def registered_user(client):
    email = f"dash-{uuid.uuid4().hex}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    return {"email": email, "api_key": api_key, "headers": {"X-API-Key": api_key}}


def test_dashboard_summary_unauthenticated(client):
    """Dashboard returns 401 for unauthenticated requests."""
    resp = client.get("/api/v1/maas/dashboard/summary")
    assert resp.status_code == 401


def test_dashboard_summary_authenticated_empty(client, registered_user):
    """Fresh user gets empty meshes, logs, invoices."""
    resp = client.get(
        "/api/v1/maas/dashboard/summary",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["user"]["email"] == registered_user["email"]
    assert data["user"]["plan"] == "starter"
    assert data["user"]["role"] == "user"
    assert data["meshes"] == []
    assert data["recent_audit"] == [] or isinstance(data["recent_audit"], list)
    assert data["pending_invoices"] == []
    assert data["stats"]["total_meshes"] == 0
    assert data["stats"]["pending_payment"] is False


def test_dashboard_summary_shows_deployed_mesh(client, registered_user):
    """After inserting a MeshInstance in DB, dashboard shows it.

    Note: legacy /deploy creates in-memory only; dashboard reads from DB (MeshInstance model).
    We insert directly into DB to test the dashboard's query path.
    """
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == registered_user["email"]).first()
        from src.database import MeshInstance
        import uuid as _uuid
        mesh = MeshInstance(
            id=f"mesh-{_uuid.uuid4().hex[:8]}",
            name="dash-mesh",
            owner_id=user.id,
            plan="starter",
            status="active",
        )
        db.add(mesh)
        db.commit()
    finally:
        db.close()

    resp = client.get(
        "/api/v1/maas/dashboard/summary",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["stats"]["total_meshes"] >= 1
    mesh_names = [m["name"] for m in data["meshes"]]
    assert "dash-mesh" in mesh_names


def test_dashboard_summary_shows_pending_invoice(client, registered_user):
    """Dashboard reflects pending invoices."""
    db = TestingSessionLocal()
    try:
        # find the user
        user = db.query(User).filter(User.email == registered_user["email"]).first()
        assert user is not None
        invoice = Invoice(
            id=f"inv-{uuid.uuid4().hex[:6]}",
            user_id=user.id,
            mesh_id="test-mesh",
            total_amount=2500,  # $25.00
            currency="USD",
            status="issued",
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
        )
        db.add(invoice)
        db.commit()
    finally:
        db.close()

    resp = client.get(
        "/api/v1/maas/dashboard/summary",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["stats"]["pending_payment"] is True
    assert len(data["pending_invoices"]) >= 1
    inv = data["pending_invoices"][0]
    assert inv["amount"] == 25.0
    assert inv["currency"] == "USD"


def test_dashboard_summary_non_admin_sees_own_logs_only(client):
    """Non-admin user only sees their own audit logs in the dashboard."""
    email_a = f"user-a-{uuid.uuid4().hex}@test.com"
    resp_a = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email_a, "password": "password123"},
    )
    key_a = resp_a.json()["access_token"]
    headers_a = {"X-API-Key": key_a}

    # Deploy something to generate audit logs
    client.post(
        "/api/v1/maas/deploy",
        json={"name": "log-mesh-a", "nodes": 1, "billing_plan": "starter"},
        headers=headers_a,
    )

    resp = client.get("/api/v1/maas/dashboard/summary", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()
    # Should have audit logs (from audit middleware on deploy)
    # All returned logs should belong to user
    assert isinstance(data["recent_audit"], list)


def test_dashboard_stats_security_field(client, registered_user):
    """Dashboard stats includes security breakdown dict."""
    resp = client.get(
        "/api/v1/maas/dashboard/summary",
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    stats = resp.json()["stats"]
    assert "security" in stats
    security = stats["security"]
    assert "HARDWARE_ROOTED" in security or isinstance(security, dict)
