"""
Tests for Subscription Health Visibility.
"""

from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.maas.endpoints.vpn import router as vpn_router, SubscriptionStatusResponse
from src.database import User, get_db

class TestSubscriptionVisibility:
    @pytest.fixture
    def mock_db(self):
        db = Mock()
        return db

    @pytest.fixture
    def client(self, mock_db):
        app = FastAPI()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        app.include_router(vpn_router, prefix="/vpn")
        return TestClient(app)

    def test_get_subscription_status_success(self, client, mock_db):
        """Test successful retrieval of subscription status."""
        future_date = datetime.now() + timedelta(days=10)
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.email = "test@x0t.net"
        mock_user.plan = "pro"
        mock_user.expires_at = future_date
        mock_user.requests_count = 100
        mock_user.requests_limit = 1000
        mock_user.vpn_uuid = "some-uuid"

        with patch("src.api.maas.endpoints.vpn.get_current_user_from_maas", new=AsyncMock(return_value=mock_user)):
            response = client.get("/vpn/subscription/status")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert data["status"] == "active"
        assert data["days_left"] == 9  # (future - now).days
        assert data["vpn_uuid_present"] is True

    def test_get_subscription_status_expired(self, client, mock_db):
        """Test status when subscription is expired."""
        past_date = datetime.now() - timedelta(days=1)
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.email = "test@x0t.net"
        mock_user.plan = "pro"
        mock_user.expires_at = past_date
        mock_user.requests_count = 500
        mock_user.requests_limit = 500
        mock_user.vpn_uuid = "some-uuid"

        with patch("src.api.maas.endpoints.vpn.get_current_user_from_maas", new=AsyncMock(return_value=mock_user)):
            response = client.get("/vpn/subscription/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "expired"
        assert data["days_left"] == 0

    def test_get_subscription_status_unauthorized(self, client, mock_db):
        """Test that authentication is required."""
        with patch("src.api.maas.endpoints.vpn.get_current_user_from_maas", new=AsyncMock(return_value=None)):
            response = client.get("/vpn/subscription/status")

        assert response.status_code == 401
