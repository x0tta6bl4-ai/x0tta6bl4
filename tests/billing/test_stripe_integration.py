"""
Unit and integration tests for Stripe billing integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.billing.stripe_client import (
    StripeClient, 
    StripeConfig, 
    StripeSubscriptionStatus,
    StripeSubscription
)

@pytest.fixture
def stripe_config():
    return StripeConfig(
        api_key="sk_test_123",
        webhook_secret="whsec_abc",
        publishable_key="pk_test_456",
        price_free="p_free",
        price_pro="p_pro",
        price_enterprise="p_ent"
    )

@pytest.fixture
def stripe_client(stripe_config):
    return StripeClient(config=stripe_config)

@pytest.mark.asyncio
async def test_create_customer(stripe_client):
    with patch.object(stripe_client, "stripe") as mock_stripe:
        mock_stripe.Customer.create.return_value = MagicMock(
            id="cus_123",
            email="test@example.com",
            name="Test User",
            created=1700000000,
            metadata={}
        )
        
        customer = await stripe_client.create_customer("test@example.com", name="Test User")
        
        assert customer.customer_id == "cus_123"
        assert customer.email == "test@example.com"
        assert customer.name == "Test User"
        mock_stripe.Customer.create.assert_called_once_with(
            email="test@example.com",
            name="Test User",
            metadata={}
        )

@pytest.mark.asyncio
async def test_create_subscription(stripe_client):
    with patch.object(stripe_client, "stripe") as mock_stripe:
        mock_sub = MagicMock(
            id="sub_123",
            customer="cus_123",
            status="active",
            current_period_start=1700000000,
            current_period_end=1702678400,
            cancel_at_period_end=False,
            metadata={"plan": "pro"}
        )
        mock_stripe.Subscription.create.return_value = mock_sub
        
        subscription = await stripe_client.create_subscription("cus_123", "pro")
        
        assert subscription.subscription_id == "sub_123"
        assert subscription.status == StripeSubscriptionStatus.ACTIVE
        assert subscription.plan == "pro"
        mock_stripe.Subscription.create.assert_called_once()

@pytest.mark.asyncio
async def test_handle_webhook_subscription_updated(stripe_client):
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "active",
                "metadata": {"plan": "enterprise"},
                "current_period_start": 1700000000,
                "current_period_end": 1702678400,
                "cancel_at_period_end": False
            }
        }
    }
    
    result = await stripe_client.handle_webhook_event(event)
    assert result["status"] == "processed"
    assert result["action"] == "subscription_updated"

def test_verify_webhook_signature(stripe_client):
    with patch.object(stripe_client, "stripe") as mock_stripe:
        payload = b'{"id": "evt_123"}'
        sig = "sig_abc"
        
        stripe_client.verify_webhook_signature(payload, sig)
        
        mock_stripe.Webhook.construct_event.assert_called_once_with(
            payload, sig, stripe_client._config.webhook_secret
        )
