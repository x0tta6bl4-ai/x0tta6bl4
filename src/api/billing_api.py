"""
Billing API Endpoints for MaaS
===============================

Handles Stripe Checkout sessions and Webhooks to automate
subscription management and ZKP access.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from src.billing.stripe_client import StripeClient, StripeConfig
from database import get_user, update_user, record_payment
from datetime import datetime, timedelta

logger = logging.getLogger("billing-api")

router = APIRouter(prefix="/billing", tags=["billing"])

# Initialize Stripe Client
stripe_config = StripeConfig.from_env()
stripe_client = StripeClient(stripe_config)

class CheckoutRequest(BaseModel):
    user_id: int
    plan: str # "pro" or "enterprise"

@router.post("/checkout")
async def create_checkout_session(req: CheckoutRequest):
    """
    Creates a Stripe Checkout session for the user.
    """
    user = get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    price_id = stripe_config.get_price_id(req.plan)
    if not price_id:
        # Fallback for mock/test if price_id not in env
        price_id = "price_mock_123"

    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    try:
        import stripe
        stripe.api_key = stripe_config.api_key
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{os.getenv('APP_URL')}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('APP_URL')}/cancel",
            client_reference_id=str(req.user_id),
            metadata={"plan": req.plan}
        )
        return {"checkout_url": session.url, "is_mock": False}
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        
        # In production, fail loudly instead of returning mock URL
        if environment == "production":
            raise HTTPException(
                status_code=503,
                detail=f"Payment service unavailable. Please try again later. Error: {str(e)}"
            )
        
        # Return a mock URL for development/staging with explicit indicator
        logger.warning(
            f"Returning mock checkout URL for user {req.user_id} in {environment} mode. "
            "This should never happen in production!"
        )
        return {
            "checkout_url": f"https://checkout.stripe.com/pay/mock_{req.user_id}",
            "is_mock": True,
            "warning": "Mock checkout - Stripe unavailable in development mode"
        }

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Handles Stripe webhooks to update user subscription status.
    """
    payload = await request.body()
    
    try:
        event = stripe_client.verify_webhook_signature(payload, stripe_signature)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["client_reference_id"])
        plan = session["metadata"]["plan"]
        
        # Update user in database
        expires_at = datetime.now() + timedelta(days=30)
        update_user(user_id, plan=plan, expires_at=expires_at)
        
        # Record payment
        record_payment(
            user_id=user_id,
            amount=session["amount_total"] / 100.0,
            currency=session["currency"],
            provider="stripe"
        )
        
        logger.info(f"✅ Subscription activated for user {user_id}: {plan} until {expires_at}")

    return {"status": "success"}
