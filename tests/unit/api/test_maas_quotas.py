import pytest
from fastapi.testclient import TestClient
from src.core.app import app
from src.database import SessionLocal, User, MeshNode
import uuid

client = TestClient(app)

def test_tenant_node_quota_enforcement_on_approval():
    """
    Verify that a tenant cannot approve more nodes than their plan allows.
    The 'free' plan limit is 1 node.
    """
    # 1. Setup free user
    email = f"quota-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/maas/register", json={"email": email, "password": "password123"})
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    # 2. Deploy mesh
    mesh_resp = client.post("/api/v1/maas/deploy", json={"name": "QuotaTest"}, headers=headers)
    assert mesh_resp.status_code == 200
    mesh_id = mesh_resp.json()["mesh_id"]

    # 3. Register and Approve first node (Limit is 1)
    node1_id = "node-1"
    client.post(f"/api/v1/maas/{mesh_id}/register-node", 
                json={"node_id": node1_id, "enrollment_token": "dummy"}, 
                headers=headers)
    
    appr1 = client.post(f"/api/v1/maas/{mesh_id}/approve-node/{node1_id}", json={}, headers=headers)
    assert appr1.status_code == 200

    # 4. Try to Approve second node (Should Fail)
    node2_id = "node-2"
    client.post(f"/api/v1/maas/{mesh_id}/register-node", 
                json={"node_id": node2_id, "enrollment_token": "dummy"}, 
                headers=headers)
    
    appr2 = client.post(f"/api/v1/maas/{mesh_id}/approve-node/{node2_id}", json={}, headers=headers)
    
    assert appr2.status_code == 403
    assert "Node quota exceeded" in appr2.json()["detail"]
