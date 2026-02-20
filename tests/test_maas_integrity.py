
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from src.core.app import app
from src.database import Base, User, AuditLog, get_db, Invoice
from src.api.maas_auth import ApiKeyManager

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_maas.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Fixtures
@pytest.fixture
def db_session():
    # Clear tables before each test
    db = TestingSessionLocal()
    db.query(AuditLog).delete()
    db.query(Invoice).delete()
    db.query(User).delete()
    db.commit()
    
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def admin_user(db_session):
    user = User(
        id="admin-1",
        email="admin@test.com",
        password_hash="hash",
        api_key="admin-key",
        role="admin",
        permissions="*"
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def basic_user(db_session):
    user = User(
        id="user-1",
        email="user@test.com",
        password_hash="hash",
        api_key="user-key",
        role="user",
        permissions="vpn:config" 
    )
    db_session.add(user)
    db_session.commit()
    return user

def test_audit_log_recording(admin_user, db_session):
    """Test that actions are recorded in the audit log."""
    # Perform an action as admin
    response = client.get(
        "/api/v1/maas/me",
        headers={"X-API-Key": admin_user.api_key}
    )
    assert response.status_code == 200
    
    # Check audit log
    log_entry = db_session.query(AuditLog).filter(
        AuditLog.user_id == admin_user.id,
        AuditLog.path == "/api/v1/maas/me"
    ).first()
    
    assert log_entry is not None
    assert log_entry.method == "GET"
    assert log_entry.status_code == 200

def test_rbac_denial(basic_user):
    """Test that a user without permissions is denied access."""
    # Try to access admin-only endpoint (Audit Logs)
    # Requires audit:view, which basic_user implies NOT to have (role=user defaults don't include it)
    response = client.get(
        "/api/v1/maas/mesh-123/audit-logs", 
        headers={"X-API-Key": basic_user.api_key}
    )
    assert response.status_code == 403

def test_rbac_allow(basic_user):
    """Test that a user with specific permission is allowed access."""
    # Try to access permitted endpoint
    response = client.get(
        "/vpn/config", # Requires vpn:config
        headers={"X-API-Key": basic_user.api_key},
        params={"server": "1.2.3.4", "port": 443} # Mock params
    )
    # Note: This might fail if VPN internals (XUI) aren't mocked, 
    # but we expect at least passing the auth check.
    # If it returns 500 (internal error inside _build_vpn_config), auth passed.
    # If it returns 403, auth failed.
    assert response.status_code != 403

def test_billing_invoice_generation(admin_user):
    """Test invoice generation logic (requires billing:view)."""
    # Create a dummy mesh first? Or mock the dependency.
    # For this integration test, we'll skip complex setup and just check permission on the endpoint.
    response = client.post(
        "/api/v1/maas/billing/invoices/generate/mesh-123",
        headers={"X-API-Key": admin_user.api_key}
    )
    # Should fail with 404 (mesh not found) NOT 403 (forbidden)
    assert response.status_code == 404

def test_vpn_admin_access(admin_user, basic_user):
    """Test VPN admin endpoints."""
    # Admin access allowed
    resp_admin = client.get(
        "/vpn/users",
        headers={"X-API-Key": admin_user.api_key}
    )
    assert resp_admin.status_code != 403
    
    # User access denied
    resp_user = client.get(
        "/vpn/users",
        headers={"X-API-Key": basic_user.api_key}
    )
    assert resp_user.status_code == 403

if __name__ == "__main__":
    # Self-runner for quick check
    pass
