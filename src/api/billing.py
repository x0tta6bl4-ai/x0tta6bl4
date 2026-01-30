import os
import time
import hmac
import hashlib
import json
import logging
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Header, status, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db, User, License
from src.core.circuit_breaker import stripe_circuit, CircuitBreakerOpen

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
limiter = Limiter(key_func=get_remote_address)


class CheckoutSessionRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    plan: str = Field(default="pro", min_length=1, max_length=32)
    quantity: int = Field(default=1, ge=1, le=100)


def _get_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_env(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing required configuration: {name}",
        )
    return value


@router.get("/config")
async def billing_config():
    publishable_key = _get_env("STRIPE_PUBLISHABLE_KEY")
    price_id = _get_env("STRIPE_PRICE_ID")
    return {
        "configured": bool(_get_env("STRIPE_SECRET_KEY") and price_id),
        "publishable_key": publishable_key,
        "price_id": price_id,
    }


@router.post("/checkout-session")
@limiter.limit("10/minute")
async def create_checkout_session(request: Request, payload: CheckoutSessionRequest):
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")

    secret_key = _require_env("STRIPE_SECRET_KEY")
    price_id = _require_env("STRIPE_PRICE_ID")
    success_url = _get_env("STRIPE_SUCCESS_URL") or "http://localhost:8080/?success=1"
    cancel_url = _get_env("STRIPE_CANCEL_URL") or "http://localhost:8080/?canceled=1"

    data: Dict[str, Any] = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_email": payload.email,
        "client_reference_id": payload.email,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": str(payload.quantity),
        "metadata[user_email]": payload.email,
        "metadata[plan]": payload.plan,
    }

    async def call_stripe_api():
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                auth=(secret_key, ""),
            )
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"error": {"message": resp.text}}
            raise HTTPException(status_code=502, detail=err)
        return resp.json()

    try:
        session = await stripe_circuit.call(call_stripe_api)
        return {"id": session.get("id"), "url": session.get("url")}
    except CircuitBreakerOpen:
        logger.error("Stripe API circuit breaker is open")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service temporarily unavailable. Please try again later."
        )


def _verify_stripe_signature(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
@limiter.limit("120/minute")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature")
):
    secret = _require_env("STRIPE_WEBHOOK_SECRET")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    _verify_stripe_signature(payload, stripe_signature, secret)

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type")
    obj = ((event.get("data") or {}).get("object") or {})

    email = None
    customer_details = obj.get("customer_details") if isinstance(obj, dict) else None
    if isinstance(customer_details, dict):
        email = customer_details.get("email")
    if not email:
        email = obj.get("customer_email") if isinstance(obj, dict) else None
    if not email:
        metadata = obj.get("metadata") if isinstance(obj, dict) else None
        if isinstance(metadata, dict):
            email = metadata.get("user_email")

    if email and event_type in {"checkout.session.completed", "invoice.paid", "customer.subscription.created"}:
        try:
            from src.api.users import users_db
            from src.sales.telegram_bot import TokenGenerator

            # Update in-memory user (for backward compatibility)
            user = users_db.get(email)
            if user is not None:
                user["plan"] = "pro"
                user["stripe_customer_id"] = obj.get("customer")
                user["stripe_subscription_id"] = obj.get("subscription")

            # Update database using injected session
            db_user = db.query(User).filter(User.email == email).first()
            if db_user:
                db_user.plan = "pro"
                db_user.stripe_customer_id = obj.get("customer")
                db_user.stripe_subscription_id = obj.get("subscription")

                # Generate license for pro plan
                license_token = TokenGenerator.generate(tier="pro")
                new_license = License(
                    token=license_token,
                    user_id=db_user.id,
                    tier="pro",
                    is_active=True
                )
                db.add(new_license)
                db.commit()
                db.refresh(db_user)

                logger.info(f"Generated pro license {license_token} for user {email}")

        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            db.rollback()

    return {"received": True}
