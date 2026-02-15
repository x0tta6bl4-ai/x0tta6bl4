from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from src.api.maas import router
from src.database import get_db, User

# Create a clean app for testing router integration
app = FastAPI()
app.include_router(router)

client = TestClient(app)

def test_deploy_mesh_success():
    """Test successful deployment within quota."""
    # Mock DB Session
    mock_db = MagicMock()
    
    # Mock User object
    mock_user = User(id="u1", api_key="valid-key", plan="pro")
    
    # Setup query chain: db.query(User).filter(...).first()
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = mock_user
    
    # Override dependency
    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "name": "test-mesh",
        "nodes": 5,
        "api_key": "valid-key",
        "billing_plan": "pro"
    }
    
    # Note: prefix is included in router, so path is /api/v1/mesh/deploy
    response = client.post("/api/v1/mesh/deploy", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "provisioning"
    assert "mesh_id" in data

def test_deploy_mesh_quota_exceeded():
    """Test 402 Payment Required when quota exceeded."""
    mock_db = MagicMock()
    # Pro limit is 50
    mock_user = User(id="u1", api_key="valid-key", plan="pro")
    
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = mock_user
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "name": "huge-mesh",
        "nodes": 100, 
        "api_key": "valid-key",
        "billing_plan": "pro"
    }
    
    response = client.post("/api/v1/mesh/deploy", json=payload)
    
    assert response.status_code == 402
    assert "Quota exceeded" in response.json()["detail"]

def test_deploy_mesh_invalid_key():
    """Test 401 Unauthorized for invalid key."""
    mock_db = MagicMock()
    
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = None # User not found
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "name": "test-mesh",
        "nodes": 5,
        "api_key": "invalid",
        "billing_plan": "pro"
    }
    
    response = client.post("/api/v1/mesh/deploy", json=payload)
    
    assert response.status_code == 401
