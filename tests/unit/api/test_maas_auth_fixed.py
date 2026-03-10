import pytest
from fastapi.testclient import TestClient
from src.core.app import app
from src.database import SessionLocal, User
import uuid

client = TestClient(app)

def test_maas_auth_registration_flow():
    """Verify that user registration works and returns a token."""
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    
    # 1. Register
    response = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "company": "Test Corp"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "api_key"

def test_maas_auth_login_flow():
    """Verify that login works for an existing user."""
    email = f"login-{uuid.uuid4().hex[:8]}@example.com"
    password = "loginpassword123"
    
    # Pre-register
    client.post(
        "/api/v1/maas/register",
        json={"email": email, "password": password}
    )
    
    # 2. Login
    response = client.post(
        "/api/v1/maas/login",
        json={"email": email, "password": password}
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_maas_auth_invalid_credentials():
    """Verify that login fails with wrong password."""
    response = client.post(
        "/api/v1/maas/login",
        json={"email": "nonexistent@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
