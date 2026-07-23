"""
Legacy MaaS Billing Helper - logic extracted from maas_legacy monolith.
Modular implementation for v4.0 architecture.
"""
from __future__ import annotations

import logging
import os
import hmac
import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database import User, get_db
from src.coordination.events import EventBus, EventType, get_event_bus
from src.api.maas.models import BillingWebhookRequest

logger = logging.getLogger(__name__)

# Simple in-memory cache for idempotency in tests
_PROCESSED_EVENTS: Dict[str, Dict[str, Any]] = {}

def _verify_billing_webhook_secret(provided_secret: Optional[str]) -> None:
    expected_secret = os.getenv("X0T_BILLING_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        return
    if not provided_secret or not secrets.compare_digest(
        provided_secret,
        expected_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid billing webhook secret")

def _verify_billing_hmac(
    body: bytes,
    timestamp: str,
    signature: str,
) -> None:
    secret = os.getenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", "").strip()
    if not secret:
        return
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    # Check tolerance
    tolerance = int(os.getenv("X0T_BILLING_WEBHOOK_TOLERANCE_SEC", "300"))
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            raise HTTPException(status_code=401, detail="Signature timestamp outside tolerance")
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid timestamp header")

    # Verify HMAC
    signed_payload = f"{timestamp}.".encode("utf-8") + body
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    # Support both raw hex and sha256= prefix
    actual_sig = signature.replace("sha256=", "")

    if not secrets.compare_digest(actual_sig, expected):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

async def legacy_billing_webhook(
    req: BillingWebhookRequest,
    request: Request,
    db: Session,
    x_billing_webhook_secret: Optional[str] = None,
    x_billing_timestamp: Optional[str] = None,
    x_billing_signature: Optional[str] = None,
):
    """Original logic for MaaS legacy billing webhook."""
    _verify_billing_webhook_secret(x_billing_webhook_secret)

    # Check HMAC
    body = await request.body()
    _verify_billing_hmac(body, x_billing_timestamp, x_billing_signature)

    if not req.event_id:
        raise HTTPException(status_code=400, detail="event_id is required")

    # Idempotency check
    current_payload = req.model_dump(exclude_unset=True)
    if req.event_id in _PROCESSED_EVENTS:
        cached = _PROCESSED_EVENTS[req.event_id]
        # Only compare important fields to avoid false mismatch on defaults
        important_fields = {"event_type", "email", "plan", "customer_id"}
        for field in important_fields:
             if cached["payload"].get(field) != current_payload.get(field):
                  raise HTTPException(status_code=409, detail="Event payload mismatch")

        return {**cached["response"], "idempotent_replay": True}

    # Simple plan mapping for tests
    email = (req.email or "").lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan_before = user.plan
    if req.event_type == "plan.upgraded":
        user.plan = req.plan
        if req.plan == "enterprise":
             user.requests_limit = 10000000
        elif req.plan == "pro":
             user.requests_limit = 1000000
        db.commit()
    elif req.event_type == "subscription.canceled":
        user.plan = "starter"
        user.requests_limit = 10000
        db.commit()

    response = {
        "status": "success",
        "message": "Webhook processed",
        "event_id": req.event_id,
        "processed": True,
        "plan_before": plan_before,
        "plan_after": user.plan,
        "requests_limit": user.requests_limit,
        "idempotent_replay": False,
    }

    _PROCESSED_EVENTS[req.event_id] = {
        "payload": current_payload,
        "response": response
    }

    return response

