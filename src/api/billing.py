import hashlib
import hmac
import json
import logging
import os
import sys
import time
import uuid
import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.services.xray_manager import XrayManager

# Simplified import
try:
    from vpn_config_generator import generate_vless_link
except ImportError:
    generate_vless_link = None


from src.core.circuit_breaker import CircuitBreakerOpen, stripe_circuit
from src.database import BillingWebhookEvent, License, Payment, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
limiter = Limiter(key_func=get_remote_address)


def _is_circuit_breaker_open_error(exc: Exception) -> bool:
    """Handle class-identity drift when circuit_breaker module is reloaded in tests."""
    return isinstance(exc, CircuitBreakerOpen) or exc.__class__.__name__ == "CircuitBreakerOpen"


def _resolve_mesh_provisioner():
    """Support both legacy and refactored MaaS module layouts."""
    try:
        from src.api.maas import mesh_provisioner as provisioner
    except Exception:
        try:
            from src.api.maas_legacy import mesh_provisioner as provisioner
        except Exception:
            return None
    return provisioner


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
    success_url = (
        _get_env("STRIPE_SUCCESS_URL")
        or "http://localhost:8080/?success=1&session_id={CHECKOUT_SESSION_ID}"
    )
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
    except Exception as exc:
        if _is_circuit_breaker_open_error(exc):
            logger.error("Stripe API circuit breaker is open")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service temporarily unavailable. Please try again later.",
            )
        raise


def _verify_stripe_signature(
    payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300
) -> None:
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
        raise HTTPException(
            status_code=400, detail="Signature timestamp outside tolerance"
        )

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def _stripe_payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _extract_stripe_event_id(event: Dict[str, Any]) -> Optional[str]:
    raw = event.get("id")
    if isinstance(raw, str):
        event_id = raw.strip()
        if event_id:
            return event_id
    return None


def _stripe_event_storage_id(event_id: str) -> str:
    return f"stripe:{event_id}"


def _stripe_event_ttl_seconds() -> int:
    raw = os.getenv("STRIPE_WEBHOOK_EVENT_TTL_SEC", "86400").strip()
    try:
        value = int(raw)
    except ValueError:
        return 86_400
    return max(300, min(value, 604_800))


def _deserialize_cached_response(response_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not response_json:
        return None
    try:
        loaded = json.loads(response_json)
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _cleanup_expired_stripe_events(db: Session) -> None:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(
        seconds=_stripe_event_ttl_seconds()
    )
    try:
        (
            db.query(BillingWebhookEvent)
            .filter(
                BillingWebhookEvent.event_id.like("stripe:%"),
                BillingWebhookEvent.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Stripe webhook idempotency cleanup failed: %s", exc)


def _start_stripe_event_processing(
    db: Session, event_id: Optional[str], event_type: str, payload_hash: str
) -> Optional[Dict[str, Any]]:
    if not event_id:
        return None

    _cleanup_expired_stripe_events(db)
    storage_id = _stripe_event_storage_id(event_id)

    db.add(
        BillingWebhookEvent(
            event_id=storage_id,
            event_type=event_type,
            payload_hash=payload_hash,
            status="processing",
        )
    )
    try:
        db.commit()
        return None
    except IntegrityError:
        db.rollback()
    except Exception as exc:
        db.rollback()
        logger.warning("Stripe webhook idempotency reserve skipped: %s", exc)
        return None

    existing = (
        db.query(BillingWebhookEvent)
        .filter(BillingWebhookEvent.event_id == storage_id)
        .first()
    )
    if existing is None:
        raise HTTPException(
            status_code=409, detail="Stripe event state conflict; retry delivery"
        )

    if existing.payload_hash != payload_hash:
        raise HTTPException(status_code=409, detail="Stripe event_id payload mismatch")

    if existing.status == "done":
        cached = _deserialize_cached_response(existing.response_json)
        if cached is None:
            return {"received": True}
        return dict(cached)

    if existing.status == "processing":
        raise HTTPException(status_code=409, detail="Stripe event is already being processed")

    existing.status = "processing"
    existing.event_type = event_type
    existing.last_error = None
    existing.processed_at = None
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Stripe webhook idempotency resume failed: %s", exc)
    return None


def _finalize_stripe_event_processing(
    db: Session, event_id: Optional[str], response_payload: Dict[str, Any]
) -> None:
    if not event_id:
        return
    storage_id = _stripe_event_storage_id(event_id)
    try:
        event = (
            db.query(BillingWebhookEvent)
            .filter(BillingWebhookEvent.event_id == storage_id)
            .first()
        )
        if event is None:
            return
        event.status = "done"
        event.response_json = json.dumps(response_payload, ensure_ascii=False)
        event.last_error = None
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Stripe webhook idempotency finalize failed: %s", exc)


def _fail_stripe_event_processing(
    db: Session, event_id: Optional[str], error: str
) -> None:
    if not event_id:
        return
    storage_id = _stripe_event_storage_id(event_id)
    try:
        event = (
            db.query(BillingWebhookEvent)
            .filter(BillingWebhookEvent.event_id == storage_id)
            .first()
        )
        if event is None:
            return
        event.status = "failed"
        event.last_error = error[:2000]
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()


@router.post("/webhook")
@limiter.limit("120/minute")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
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
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid Stripe event format")

    event_id = _extract_stripe_event_id(event)
    event_type = event.get("type")
    payload_hash = _stripe_payload_sha256(payload)
    cached_response = _start_stripe_event_processing(db, event_id, str(event_type), payload_hash)
    if cached_response is not None:
        return cached_response

    obj = (event.get("data") or {}).get("object") or {}
    processing_failed = False

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

    if email and event_type in {
        "checkout.session.completed",
        "invoice.paid",
        "customer.subscription.created",
    }:
        try:
            from src.services.provisioning_service import (
                ProvisioningSource,
                provisioning_service,
            )

            # Update Stripe metadata in DB
            db_user = db.query(User).filter(User.email == email).first()
            if not db_user:
                db_user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    password_hash="stripe_managed",
                    created_at=datetime.datetime.utcnow(),
                )
                db.add(db_user)

            db_user.plan = "pro"
            db_user.stripe_customer_id = obj.get("customer")
            db_user.stripe_subscription_id = obj.get("subscription") or obj.get("id")

            # Generate license (legacy support) in the same transaction so failures rollback plan updates.
            from src.sales.telegram_bot import TokenGenerator

            license_token = TokenGenerator.generate(tier="pro")
            new_license = License(
                token=license_token, user_id=db_user.id, tier="pro", is_active=True
            )
            db.add(new_license)
            db.commit()
            logger.info(f"Generated pro license {license_token} for user {email}")

            # Unified VPN provisioning
            try:
                result = await provisioning_service.provision_vpn_user(
                    email=email,
                    plan="pro",
                    source=ProvisioningSource.STRIPE_WEBHOOK,
                    user_id=db_user.id,
                )

                if result.success:
                    db_user.vpn_uuid = result.vpn_uuid
                    db.commit()
                    logger.info(f"VPN provisioned for {email}: {result.vpn_uuid[:8]}...")
                else:
                    logger.error(f"VPN provisioning failed for {email}: {result.error}")
            except Exception as provision_err:
                logger.error(f"VPN provisioning failed for {email}: {provision_err}")

            # Mesh provisioning (Phase 3)
            try:
                mesh_provisioner = _resolve_mesh_provisioner()
                if mesh_provisioner is not None:
                    instance = await mesh_provisioner.create(
                        name=f"auto-mesh-{db_user.id[:8]}",
                        nodes=5,
                        owner_id=db_user.id,
                        pqc_enabled=True,
                    )
                    logger.info(
                        f"Auto-provisioned mesh {instance.mesh_id} for user {email}"
                    )
                else:
                    logger.warning("MaaS mesh provisioner unavailable; skipping")
            except Exception as ex:
                logger.error(f"Failed to auto-provision mesh for {email}: {ex}")

        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            db.rollback()
            processing_failed = True
            _fail_stripe_event_processing(
                db, event_id, f"{e.__class__.__name__}: {str(e)}"
            )

    # Handle subscription cancellation
    elif email and event_type == "customer.subscription.deleted":
        try:
            from src.services.provisioning_service import provisioning_service

            revoked = await provisioning_service.revoke_vpn_user(email)
            db_user = db.query(User).filter(User.email == email).first()
            if db_user:
                db_user.plan = "canceled"
                db.commit()
            logger.info(f"Subscription revoked for {email}, vpn_revoked={revoked}")
        except Exception as e:
            logger.error(f"Revocation failed for {email}: {e}")
            db.rollback()
            processing_failed = True
            _fail_stripe_event_processing(
                db, event_id, f"{e.__class__.__name__}: {str(e)}"
            )

    response_payload = {"received": True}
    if not processing_failed:
        _finalize_stripe_event_processing(db, event_id, response_payload)
    return response_payload


@router.get("/order-status")
async def get_order_status(session_id: str, db: Session = Depends(get_db)):
    """Check order status and return VLESS link if paid."""
    # Since we don't track session_id in User directly in this simple MVP,
    # we verify against Stripe API or assume if User exists and is PRO, it's done.
    # But for MVP, session_id is key. We should query Stripe to get customer_email.

    secret_key = _require_env("STRIPE_SECRET_KEY")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
            auth=(secret_key, ""),
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = resp.json()

    payment_status = session_data.get("payment_status")
    if payment_status == "paid":
        customer_email = session_data.get("customer_details", {}).get("email")
        if not customer_email:
            return {"status": "processing", "message": "Email missing from payment"}

        db_user = db.query(User).filter(User.email == customer_email).first()
        if db_user and db_user.plan == "pro" and db_user.vpn_uuid:
            # Generate link
            host = os.getenv(
                "XRAY_HOST", "localhost"
            )  # For client side, should be public IP
            # Ideally get public IP or domain
            public_host = os.getenv("PUBLIC_DOMAIN", host)

            link = generate_vless_link(db_user.vpn_uuid, server=public_host, port=443)
            return {
                "status": "paid",
                "vless_link": link,
                "instructions": "Copy this link into V2Ray/Xray client.",
            }
        else:
            return {
                "status": "processing",
                "message": "Payment received, provisioning account...",
            }
    else:
        return {"status": payment_status}
