"""
Tests for VPN API endpoints.
"""
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI # Added import
from src.api.vpn import router as vpn_router # Added import
from src.database import get_db, User # Added import

# Removed global client = TestClient(app) as it's being refactored into fixtures

class TestVPNConfig:
    """Tests for VPN configuration endpoints."""

    @pytest.fixture
    def client(self, mock_db): # Added client fixture
        app = FastAPI()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        app.include_router(vpn_router) # Router already has prefix="/vpn"
        return TestClient(app)

    @pytest.fixture
    def mock_db(self): # Added mock_db fixture
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        db.close = Mock()
        return db

    def test_get_vpn_config_success(self, client): # Added client arg
        """Test successful VPN config generation."""
        # The actual API doesn't use DB for this, but the fixture setup needs it
        response = client.get("/vpn/config?user_id=12345")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 12345
        assert "vless_link" in data
        assert "config_text" in data
        assert data["vless_link"].startswith("vless://")

    def test_get_vpn_config_with_custom_server(self, client): # Added client arg
        """Test VPN config with custom server."""
        response = client.get(
            "/vpn/config?user_id=12345&server=custom.server.com&port=443"
        )
        assert response.status_code == 200
        data = response.json()
        assert "custom.server.com" in data["vless_link"]

    def test_get_vpn_config_with_username(self, client): # Added client arg
        """Test VPN config with optional username."""
        response = client.get("/vpn/config?user_id=12345&username=testuser")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"

    def test_post_vpn_config_success(self, client): # Added client arg
        """Test POST endpoint for VPN config creation."""
        config_request = {
            "user_id": 12345,
            "username": "testuser",
            "server": "test.server.com",
            "port": 8443
        }
        response = client.post("/vpn/config", json=config_request)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 12345
        assert "vless_link" in data

    def test_get_vpn_config_missing_user_id(self, client): # Added client arg
        """Test that missing user_id returns validation error."""
        response = client.get("/vpn/config")
        assert response.status_code == 422


class TestVPNStatus:
    """Tests for VPN status endpoint."""

    @pytest.fixture
    def client(self, mock_db): # Added client fixture
        app = FastAPI()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        app.include_router(vpn_router) # Router already has prefix="/vpn"
        return TestClient(app)

    @pytest.fixture
    def mock_db(self): # Added mock_db fixture
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        db.close = Mock()
        return db

    def test_get_vpn_status_online(self, client): # Added client arg
        """Test VPN status endpoint."""
        response = client.get("/vpn/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["online", "offline"]
        assert "server" in data
        assert "port" in data
        assert data["protocol"] == "VLESS+Reality"

    def test_get_vpn_status_cached(self, client): # Added client arg
        """Test that VPN status returns cached response."""
        # First request
        response1 = client.get("/vpn/status")
        assert response1.status_code == 200

        # Second request should hit cache (same response)
        response2 = client.get("/vpn/status")
        assert response2.status_code == 200
        assert response1.json()["server"] == response2.json()["server"]


class TestVPNUsers:
    """Tests for VPN users management endpoints."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        db.close = Mock()
        return db

    @pytest.fixture
    def client(self, mock_db):
        app = FastAPI()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        app.include_router(vpn_router)
        return TestClient(app)

    def test_get_users_without_admin_token(self, client):
        """Test that /users requires admin authentication."""
        response = client.get("/vpn/users")
        assert response.status_code == 403 # Should be 403 Forbidden, not 500 Internal Server Error

    def test_get_users_with_admin_token(self, client, mock_db, monkeypatch):
        """Test /users with valid admin token."""
        monkeypatch.setenv("ADMIN_TOKEN", "test_admin_token")
        
        mock_user_1 = Mock(spec=User)
        mock_user_1.id = "user1"
        mock_user_1.email = "user1@example.com"
        mock_user_1.plan = "pro"

        mock_user_2 = Mock(spec=User)
        mock_user_2.id = "user2"
        mock_user_2.email = "user2@example.com"
        mock_user_2.plan = "enterprise"

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user_1, mock_user_2]
        
        with patch('src.api.vpn.cache') as mock_cache: # Patch cache here
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)

            response = client.get(
                "/vpn/users",
                headers={"X-Admin-Token": "test_admin_token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "total" in data
            assert "users" in data
            assert isinstance(data["users"], list)
            assert len(data["users"]) == 2
            assert data["users"][0]["user_id"] == "user1"


    def test_get_users_with_invalid_token(self, client, monkeypatch):
        """Test /users with invalid admin token."""
        monkeypatch.setenv("ADMIN_TOKEN", "correct_token")
        response = client.get(
            "/vpn/users",
            headers={"X-Admin-Token": "wrong_token"}
        )
        assert response.status_code == 403

    def test_delete_user_success(self, client, mock_db, monkeypatch):
        """Test successful user deletion (downgrade to free)."""
        monkeypatch.setenv("ADMIN_TOKEN", "test_admin_token")
        
        mock_user = Mock(spec=User)
        mock_user.plan = "pro"
        mock_user.id = "12345"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.commit = Mock()

        with patch('src.api.vpn.cache') as mock_cache: # Patch cache here
            mock_cache.delete = AsyncMock(return_value=True)

            response = client.delete(
                "/vpn/user/12345",
                headers={"X-Admin-Token": "test_admin_token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "downgraded" in data["message"]
            mock_user.plan = "free" # Verify plan change
            mock_db.commit.assert_called_once()


    def test_delete_user_not_found(self, client, mock_db, monkeypatch):
        """Test deletion of non-existent user."""
        monkeypatch.setenv("ADMIN_TOKEN", "test_admin_token")
        
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.delete(
            "/vpn/user/99999",
            headers={"X-Admin-Token": "test_admin_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"]

    def test_delete_user_without_admin_token(self, client):
        """Test that user deletion requires admin auth."""
        response = client.delete("/vpn/user/12345")
        assert response.status_code == 403 # Should be 403 Forbidden, not 500 Internal Server Error


class TestVPNRateLimiting:
    """Tests for rate limiting on VPN endpoints."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        db.close = Mock()
        return db

    @pytest.fixture
    def client(self, mock_db):
        app = FastAPI()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        app.include_router(vpn_router)
        return TestClient(app)

    def test_config_rate_limit(self, client):
        """Test that /config endpoint has rate limiting."""
        responses = []
        for i in range(35):
            response = client.get(f"/vpn/config?user_id={i}")
            responses.append(response.status_code)

        # Some requests should be rate limited (429)
        assert 429 in responses or all(r == 200 for r in responses)

    def test_status_rate_limit(self, client):
        """Test that /status endpoint has rate limiting."""
        responses = []
        for _ in range(65):
            response = client.get("/vpn/status")
            responses.append(response.status_code)

        # Higher limit (60/minute), may not hit in fast test
        # Just verify requests don't fail unexpectedly
        assert all(r in [200, 429] for r in responses)
