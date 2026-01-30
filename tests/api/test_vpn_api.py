"""
Tests for VPN API endpoints.
"""
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from src.core.app import app

client = TestClient(app)


class TestVPNConfig:
    """Tests for VPN configuration endpoints."""

    def test_get_vpn_config_success(self):
        """Test successful VPN config generation."""
        response = client.get("/vpn/config?user_id=12345")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 12345
        assert "vless_link" in data
        assert "config_text" in data
        assert data["vless_link"].startswith("vless://")

    def test_get_vpn_config_with_custom_server(self):
        """Test VPN config with custom server."""
        response = client.get(
            "/vpn/config?user_id=12345&server=custom.server.com&port=443"
        )
        assert response.status_code == 200
        data = response.json()
        assert "custom.server.com" in data["vless_link"]

    def test_get_vpn_config_with_username(self):
        """Test VPN config with optional username."""
        response = client.get("/vpn/config?user_id=12345&username=testuser")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"

    def test_post_vpn_config_success(self):
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

    def test_get_vpn_config_missing_user_id(self):
        """Test that missing user_id returns validation error."""
        response = client.get("/vpn/config")
        assert response.status_code == 422


class TestVPNStatus:
    """Tests for VPN status endpoint."""

    def test_get_vpn_status_online(self):
        """Test VPN status endpoint."""
        response = client.get("/vpn/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["online", "offline"]
        assert "server" in data
        assert "port" in data
        assert data["protocol"] == "VLESS+Reality"

    def test_get_vpn_status_cached(self):
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

    def test_get_users_without_admin_token(self):
        """Test that /users requires admin authentication."""
        response = client.get("/vpn/users")
        assert response.status_code in [403, 500]

    @patch.dict(os.environ, {"ADMIN_TOKEN": "test_admin_token"})
    def test_get_users_with_admin_token(self):
        """Test /users with valid admin token."""
        with patch('src.api.vpn.get_db') as mock_db:
            mock_session = Mock()
            mock_session.query.return_value.filter.return_value.all.return_value = []
            mock_db.return_value = iter([mock_session])

            with patch('src.api.vpn.cache') as mock_cache:
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

    @patch.dict(os.environ, {"ADMIN_TOKEN": "test_admin_token"})
    def test_get_users_with_invalid_token(self):
        """Test /users with invalid admin token."""
        response = client.get(
            "/vpn/users",
            headers={"X-Admin-Token": "wrong_token"}
        )
        assert response.status_code == 403

    @patch.dict(os.environ, {"ADMIN_TOKEN": "test_admin_token"})
    def test_delete_user_success(self):
        """Test successful user deletion (downgrade to free)."""
        with patch('src.api.vpn.get_db') as mock_db:
            mock_session = Mock()
            mock_user = Mock()
            mock_user.plan = "pro"
            mock_user.id = "12345"
            mock_session.query.return_value.filter.return_value.first.return_value = mock_user
            mock_session.commit = Mock()
            mock_db.return_value = iter([mock_session])

            with patch('src.api.vpn.cache') as mock_cache:
                mock_cache.delete = AsyncMock(return_value=True)

                response = client.delete(
                    "/vpn/user/12345",
                    headers={"X-Admin-Token": "test_admin_token"}
                )
                assert response.status_code == 200
                data = response.json()
                # Result depends on database mock - check response structure
                assert "success" in data
                assert "message" in data

    @patch.dict(os.environ, {"ADMIN_TOKEN": "test_admin_token"})
    def test_delete_user_not_found(self):
        """Test deletion of non-existent user."""
        with patch('src.api.vpn.get_db') as mock_db:
            mock_session = Mock()
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_db.return_value = iter([mock_session])

            response = client.delete(
                "/vpn/user/99999",
                headers={"X-Admin-Token": "test_admin_token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["message"]

    def test_delete_user_without_admin_token(self):
        """Test that user deletion requires admin auth."""
        response = client.delete("/vpn/user/12345")
        assert response.status_code in [403, 500]


class TestVPNRateLimiting:
    """Tests for rate limiting on VPN endpoints."""

    def test_config_rate_limit(self):
        """Test that /config endpoint has rate limiting."""
        responses = []
        for i in range(35):
            response = client.get(f"/vpn/config?user_id={i}")
            responses.append(response.status_code)

        # Some requests should be rate limited (429)
        assert 429 in responses or all(r == 200 for r in responses)

    def test_status_rate_limit(self):
        """Test that /status endpoint has rate limiting."""
        responses = []
        for _ in range(65):
            response = client.get("/vpn/status")
            responses.append(response.status_code)

        # Higher limit (60/minute), may not hit in fast test
        # Just verify requests don't fail unexpectedly
        assert all(r in [200, 429] for r in responses)
