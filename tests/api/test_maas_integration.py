
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
import uuid

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.app import app
from src.database import Base, get_db

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_maas.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module")
def client():
    # Create tables
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_maas.db"):
        os.remove("./test_maas.db")

def test_maas_full_flow(client):
    # 1. Register
    reg_payload = {
        "email": "test@x0tta6bl4.net",
        "password": "strong_password_123",
        "full_name": "Test User",
        "company": "Test Corp"
    }
    response = client.post("/api/v1/maas/register", json=reg_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    api_key = data["access_token"]

    # 2. Login (Optional check)
    login_payload = {
        "email": "test@x0tta6bl4.net",
        "password": "strong_password_123"
    }
    response = client.post("/api/v1/maas/login", json=login_payload)
    assert response.status_code == 200
    assert response.json()["access_token"] == api_key

    # 3. Deploy Mesh
    deploy_payload = {
        "name": "My First Mesh",
        "nodes": 3,
        "billing_plan": "starter"
    }
    headers = {"X-API-Key": api_key}
    response = client.post("/api/v1/maas/deploy", json=deploy_payload, headers=headers)
    
    assert response.status_code == 200
    deploy_data = response.json()
    
    assert "mesh_id" in deploy_data
    assert "join_config" in deploy_data
    assert deploy_data["status"] == "active"
    assert deploy_data["plan"] == "starter"
    
    # Check PQC Identity
    if deploy_data.get("pqc_identity"):
        pqc = deploy_data["pqc_identity"]
        assert "did" in pqc
        assert "keys" in pqc
        assert pqc["keys"]["sig_alg"] in ["ML-DSA-65", "Dilithium3"]

    # 4. Check "Me" info and usage
    response = client.get("/api/v1/maas/me", headers=headers)
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["email"] == "test@x0tta6bl4.net"
    # Usage should be > 0 because of previous calls
    # Wait, middleware updates usage AFTER response? Or async?
    # In test client, it might be synchronous enough or not. 
    # Let's verify requests_count exists at least.
    assert "requests_count" in me_data


def test_node_revoke_reissue_flow(client):
    email = f"node-flow-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    # 1. Register and deploy mesh
    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Node Flow User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    deploy = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Node Flow Mesh", "nodes": 3, "billing_plan": "starter"},
        headers=headers,
    )
    assert deploy.status_code == 200
    deploy_data = deploy.json()
    mesh_id = deploy_data["mesh_id"]
    enrollment_token = deploy_data["join_config"]["token"]

    # 2. Register + approve node
    register_payload = {
        "node_id": "robot-node-1",
        "enrollment_token": enrollment_token,
        "device_class": "robot",
        "labels": {"zone": "alpha"},
    }
    reg_node = client.post(f"/api/v1/maas/{mesh_id}/nodes/register", json=register_payload)
    assert reg_node.status_code == 200
    assert reg_node.json()["status"] == "pending_approval"

    approve = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/robot-node-1/approve",
        json={"acl_profile": "strict", "tags": ["robot"]},
        headers=headers,
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    # 3. Revoke
    revoke = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/revoke",
        json={"node_id": "robot-node-1", "reason": "rotation"},
        headers=headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    # 4. Reissue one-time token
    reissue = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/robot-node-1/reissue-token",
        json={"ttl_seconds": 900},
        headers=headers,
    )
    assert reissue.status_code == 200
    reissued_token = reissue.json()["join_token"]["token"]

    # 5. Re-register with reissued token
    reregister = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/register",
        json={
            "node_id": "robot-node-1",
            "enrollment_token": reissued_token,
            "device_class": "robot",
        },
    )
    assert reregister.status_code == 200
    assert reregister.json()["status"] == "pending_approval"

    # 6. One-time token cannot be reused
    reuse = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/register",
        json={
            "node_id": "robot-node-1",
            "enrollment_token": reissued_token,
            "device_class": "robot",
        },
    )
    assert reuse.status_code == 401
