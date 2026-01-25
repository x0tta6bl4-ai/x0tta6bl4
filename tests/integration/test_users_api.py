"""
Test for user authentication and authorization
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from src.core.app import app

client = TestClient(app)

def test_register_success():
    """Test successful user registration"""
    user_data = {
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "company": "Test Company",
        "plan": "free"
    }
    
    with patch('src.api.users.get_db') as mock_db:
        mock_session = Mock()
        mock_db.return_value = iter([mock_session])
        
        response = client.post("/api/v1/users/register", json=user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "api_key" not in data  # API key should not be in response

def test_register_duplicate_email():
    """Test that duplicate email is rejected"""
    user_data = {
        "email": "existing@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "company": "Test Company",
        "plan": "free"
    }
    
    with patch('src.api.users.get_db') as mock_db:
        mock_session = Mock()
        mock_user = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.return_value = iter([mock_session])
        
        response = client.post("/api/v1/users/register", json=user_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

def test_register_invalid_email():
    """Test that invalid email format is rejected"""
    user_data = {
        "email": "invalid-email",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "plan": "free"
    }
    
    response = client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422  # Validation error

def test_register_weak_password():
    """Test that weak password is rejected"""
    user_data = {
        "email": "test@example.com",
        "password": "weak",
        "full_name": "Test User",
        "plan": "free"
    }
    
    response = client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422  # Validation error

def test_login_success():
    """Test successful user login"""
    credentials = {
        "email": "test@example.com",
        "password": "SecurePassword123!"
    }
    
    with patch('src.api.users.get_db') as mock_db:
        mock_session = Mock()
        mock_user = Mock()
        mock_user.password_hash = b'$2b$12$hash'  # Mock bcrypt hash
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.return_value = iter([mock_session])
        
        with patch('src.api.users.bcrypt.checkpw', return_value=True):
            response = client.post("/api/v1/users/login", json=credentials)
            assert response.status_code == 200
            data = response.json()
            assert "token" in data
            assert "user" in data

def test_login_invalid_credentials():
    """Test that invalid credentials are rejected"""
    credentials = {
        "email": "test@example.com",
        "password": "WrongPassword123!"
    }
    
    with patch('src.api.users.get_db') as mock_db:
        mock_session = Mock()
        mock_user = Mock()
        mock_user.password_hash = b'$2b$12$hash'
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.return_value = iter([mock_session])
        
        with patch('src.api.users.bcrypt.checkpw', return_value=False):
            response = client.post("/api/v1/users/login", json=credentials)
            assert response.status_code == 401

def test_rate_limiting():
    """Test that rate limiting is enforced"""
    credentials = {
        "email": "test@example.com",
        "password": "SecurePassword123!"
    }
    
    # Make 6 login attempts (limit is 5/minute)
    responses = []
    for _ in range(6):
        response = client.post("/api/v1/users/login", json=credentials)
        responses.append(response)
    
    # Last request should be rate limited
    assert responses[-1].status_code == 429

def test_stats_without_admin_token():
    """Test that /stats endpoint requires admin token"""
    response = client.get("/api/v1/users/stats")
    assert response.status_code == 403

def test_stats_with_admin_token():
    """Test that /stats endpoint works with admin token"""
    with patch.dict(os.environ, {'ADMIN_TOKEN': 'test_admin_token'}):
        response = client.get("/api/v1/users/stats", headers={"X-Admin-Token": "test_admin_token"})
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "active_sessions" in data
        assert "plans" in data
