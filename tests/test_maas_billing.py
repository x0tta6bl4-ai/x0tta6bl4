from fastapi.testclient import TestClient
from src.api.maas import router, app
import pytest

# Create a test app instance if not imported
# Assuming valid implementation of app that includes the router
client = TestClient(router)

def test_deploy_mesh_success():
    """Test successful deployment within quota."""
    payload = {
        "name": "test-mesh",
        "nodes": 5,
        "api_key": "valid-key-123456789",
        "billing_plan": "pro"
    }
    response = client.post("/deploy", json=payload)
    if response.status_code == 404: # Router mounted on prefix
         response = client.post("/api/v1/mesh/deploy", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "provisioning"
    assert "mesh_id" in data

def test_deploy_mesh_quota_exceeded():
    """Test 402 Payment Required when quota exceeded."""
    payload = {
        "name": "huge-mesh",
        "nodes": 100, # Exceeds 50 limit
        "api_key": "valid-key-123456789",
        "billing_plan": "pro"
    }
    response = client.post("/deploy", json=payload)
    if response.status_code == 404:
         response = client.post("/api/v1/mesh/deploy", json=payload)

    assert response.status_code == 402
    assert "Quota exceeded" in response.json()["detail"]

def test_deploy_mesh_invalid_key():
    """Test 401 Unauthorized for invalid key."""
    payload = {
        "name": "test-mesh",
        "nodes": 5,
        "api_key": "invalid",
        "billing_plan": "pro"
    }
    response = client.post("/deploy", json=payload)
    if response.status_code == 404:
         response = client.post("/api/v1/mesh/deploy", json=payload)

    assert response.status_code == 401
