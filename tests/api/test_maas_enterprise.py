import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
import os
import time

from src.core.app import app
from src.database import Base, get_db, User

# Fresh Test DB
_TEST_DB_PATH = f"./test_maas_final_{uuid.uuid4().hex}.db"
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
    # Restore previous state
    if original_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original_override
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)

def test_enterprise_core_flow(client):
    # 1. Register & Get Token
    email = f"ent-{uuid.uuid4().hex}@test.com"
    resp = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200
    token_payload = resp.json()
    assert token_payload["token_type"] == "api_key"
    assert token_payload["expires_in"] == 31536000
    api_key = token_payload["access_token"]
    headers = {"X-API-Key": api_key}

    # 2. Deploy Mesh (uses maas_legacy.py which returns mesh_id)
    mesh = client.post(
        "/api/v1/maas/deploy",
        json={"name": "ent-mesh", "nodes": 2, "billing_plan": "starter"},
        headers=headers,
    )
    assert mesh.status_code == 200
    mesh_data = mesh.json()
    assert "mesh_id" in mesh_data
    mesh_id = mesh_data["mesh_id"]

    # 3. Try to approve a non-existent node — expect 404 (node not in pending queue)
    approve = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/n1/approve",
        json={"acl_profile": "default", "tags": []},
        headers=headers,
    )
    assert approve.status_code in [403, 404]

def test_marketplace_persistence(client):
    email = f"mkt-{uuid.uuid4().hex}@test.com"
    u1 = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"}).json()["access_token"]
    headers = {"X-API-Key": u1}

    # List node
    node_id = f"node-{uuid.uuid4().hex[:6]}"
    client.post("/api/v1/maas/marketplace/list", headers=headers, json={
        "node_id": node_id, "region": "us-east", "price_per_hour": 0.1, "bandwidth_mbps": 100
    })
    
    # Search
    search = client.get("/api/v1/maas/marketplace/search")
    assert search.status_code == 200
    listings = search.json()
    assert any(l["node_id"] == node_id for l in listings)


def test_auth_register_persists_profile_fields(client):
    email = f"profile-{uuid.uuid4().hex}@test.com"
    full_name = "Alice Operator"
    company = "MeshOps Inc"

    resp = client.post(
        "/api/v1/maas/auth/register",
        json={
            "email": email,
            "password": "password123",
            "full_name": full_name,
            "company": company,
        },
    )
    assert resp.status_code == 200

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.full_name == full_name
        assert user.company == company
    finally:
        db.close()


def test_auth_rotate_api_key_endpoint(client):
    email = f"rotate-{uuid.uuid4().hex}@test.com"
    register = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert register.status_code == 200
    old_key = register.json()["access_token"]

    rotate = client.post(
        "/api/v1/maas/auth/api-key",
        headers={"X-API-Key": old_key},
    )
    assert rotate.status_code == 200
    new_key = rotate.json()["api_key"]
    assert new_key != old_key

    old_me = client.get("/api/v1/maas/auth/me", headers={"X-API-Key": old_key})
    assert old_me.status_code == 401

    new_me = client.get("/api/v1/maas/auth/me", headers={"X-API-Key": new_key})
    assert new_me.status_code == 200
    assert new_me.json()["email"] == email

def test_telemetry_isolation(client):
    email = f"tel-{uuid.uuid4().hex}@test.com"
    u1 = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"}).json()["access_token"]
    
    # Non-existent node heartbeat
    hb = client.post("/api/v1/maas/heartbeat", json={
        "node_id": "non-existent-at-all", "cpu_usage": 50, "memory_usage": 50, 
        "neighbors_count": 0, "routing_table_size": 0, "uptime": 10
    })
    # If this fails, it means 401 (Auth required) or 404 (Not found)
    assert hb.status_code in [401, 404]


def test_legacy_plaintext_password_migrates_on_login(client):
    email = f"legacy-{uuid.uuid4().hex}@test.com"
    legacy_password = "legacy_password_123"
    api_key = f"x0t_{uuid.uuid4().hex}"

    db = TestingSessionLocal()
    try:
        db.add(
            User(
                id=f"user-{uuid.uuid4().hex}",
                email=email,
                password_hash=legacy_password,
                api_key=api_key,
                role="user",
            )
        )
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/maas/auth/login",
        json={"email": email, "password": legacy_password},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["access_token"] == api_key
    assert payload["token_type"] == "api_key"
    assert payload["expires_in"] == 31536000

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.password_hash != legacy_password
        assert user.password_hash.startswith("$2")
    finally:
        db.close()


def test_auth_email_normalization_and_case_insensitive_login(client):
    raw_email = f"  User-{uuid.uuid4().hex}@Test.COM  "
    password = "password123"

    register = client.post(
        "/api/v1/maas/auth/register",
        json={"email": raw_email, "password": password},
    )
    assert register.status_code == 200
    api_key = register.json()["access_token"]

    login = client.post(
        "/api/v1/maas/auth/login",
        json={"email": raw_email.strip().upper(), "password": password},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] == api_key

    me = client.get("/api/v1/maas/auth/me", headers={"X-API-Key": api_key})
    assert me.status_code == 200
    assert me.json()["email"] == raw_email.strip().lower()


def test_auth_register_rejects_case_insensitive_duplicate_email(client):
    base_email = f"dup-auth-{uuid.uuid4().hex}@test.com"
    first = client.post(
        "/api/v1/maas/auth/register",
        json={"email": base_email.upper(), "password": "password123"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/maas/auth/register",
        json={"email": base_email.lower(), "password": "password123"},
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Email already registered"
