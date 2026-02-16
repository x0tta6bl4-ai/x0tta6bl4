"""Integration smoke tests for billing API."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import pytest_asyncio

try:
    from fastapi import FastAPI

    from src.api.billing import router as billing_router

    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False


@pytest.mark.skipif(not API_AVAILABLE, reason="billing API not available")
@pytest.mark.asyncio
class TestBillingAPI:
    @pytest_asyncio.fixture
    async def client(self):
        app = FastAPI()
        app.include_router(billing_router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as tc:
            yield tc

    async def test_get_config_success(self, client):
        with patch.dict(
            "os.environ",
            {
                "STRIPE_PUBLISHABLE_KEY": "pk_test_key",
                "STRIPE_PRICE_ID": "price_test_id",
                "STRIPE_SECRET_KEY": "sk_test_secret",
            },
            clear=False,
        ):
            response = await client.get("/api/v1/billing/config")

        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["publishable_key"] == "pk_test_key"
        assert data["price_id"] == "price_test_id"

    @patch("src.api.billing.httpx.AsyncClient")
    async def test_create_checkout_session_stripe_error(
        self, mock_httpx_client, client
    ):
        session_data = {
            "email": "test@example.com",
            "plan": "pro",
            "quantity": 1,
        }

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Invalid request"}}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value = mock_client

        with patch.dict(
            "os.environ",
            {
                "STRIPE_PUBLISHABLE_KEY": "pk_test_key",
                "STRIPE_PRICE_ID": "price_test_id",
                "STRIPE_SECRET_KEY": "sk_test_secret",
                "STRIPE_SUCCESS_URL": "http://localhost:8080/success",
                "STRIPE_CANCEL_URL": "http://localhost:8080/cancel",
            },
            clear=False,
        ):
            response = await client.post(
                "/api/v1/billing/checkout-session", json=session_data
            )

        assert response.status_code == 502
        assert "detail" in response.json()
