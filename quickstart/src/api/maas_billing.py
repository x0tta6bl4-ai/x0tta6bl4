"""
MaaS Billing API Shim — x0tta6bl4
=================================

Compatibility shim for v4.0 architecture.
Redirects to modular billing router in src/api/maas/endpoints/billing.py.

DEPRECATED: Use src.api.maas.endpoints.billing instead.
"""
from __future__ import annotations

import logging
import os
import uuid
import asyncio
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import User, Invoice, get_db
from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.core.resilience.reliability_policy import (CircuitBreakerOpen, RetryExhausted,
                                         call_with_reliability,
                                         mark_degraded_dependency)
from src.utils.audit import record_audit_log
from src.monitoring.maas_metrics import record_billing_error

# Prefer legacy MaaS internals directly to avoid circular import
try:
    from src.api.maas_legacy import usage_metering_service, _get_mesh_or_404
except Exception:
    from src.api.maas import usage_metering_service, _get_mesh_or_404

logger = logging.getLogger(__name__)
_SERVICE_AGENT = "maas-billing"
BILLING_WEBHOOK_CLAIM_BOUNDARY = (
    "Billing webhook event only. It records local Stripe webhook handling, "
    "database/audit state changes, and optional local X0T bridge intent; it does "
    "not prove live Stripe settlement, bank settlement, or on-chain finality."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


import hashlib

def _redacted_sha256_prefix(value: Any, length: int = 16) -> str:
    if not value:
        return ""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def _publish_event(request: Optional[Request], source_agent: str, payload: dict, priority: int = 6) -> None:
    if not request:
        return
    state = getattr(request, "state", None)
    bus = getattr(state, "event_bus", None)
    if not bus:
        return
    try:
        bus.publish(EventType.PIPELINE_STAGE_END, source_agent, payload, priority=priority)
    except Exception as exc:
        logger.error(f"Failed to publish event to {source_agent}: {exc}")


STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://app.x0tta6bl4.com")
STRIPE_PLANS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}

_missing_plans = [name for name, price_id in STRIPE_PLANS.items() if not price_id]
_is_production = os.getenv("ENVIRONMENT", "").strip().lower() in {"production", "prod", "live"}

warnings.warn(
    "src.api.maas_billing is deprecated. Use src.api.maas.endpoints.billing instead.",
    DeprecationWarning,
    stacklevel=2,
)

if _is_production and (not STRIPE_SECRET_KEY or _missing_plans):
    logger.critical(f"FATAL: Stripe not fully configured for production. Missing plans: {_missing_plans}")
elif _missing_plans:
    logger.info(f"Development mode: Stripe plans missing ({_missing_plans}). Payments will only work with mock/legacy mode.")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/v1/maas/billing", tags=["MaaS Billing"])


def _billing_db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit") and hasattr(db, "add")


def _billing_readiness_status(db: Any) -> dict[str, Any]:
    db_ready = _billing_db_session_available(db)
    stripe_secret_ready = bool(STRIPE_SECRET_KEY)
    stripe_plans_ready = not _missing_plans
    legacy_metering_ready = bool(usage_metering_service and _get_mesh_or_404)

    degraded_dependencies = []
    if not db_ready:
        degraded_dependencies.append("database")
    if not stripe_secret_ready:
        degraded_dependencies.append("stripe")
    if not stripe_plans_ready:
        degraded_dependencies.append("stripe_plans")
    if not legacy_metering_ready:
        degraded_dependencies.append("legacy_maas_metering")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "write_db_ready": db_ready,
        "stripe_config_ready": stripe_secret_ready,
        "stripe_plans_ready": stripe_plans_ready,
        "legacy_metering_ready": legacy_metering_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": "ready" if db_ready else "unavailable",
            "stripe_secret": "configured" if stripe_secret_ready else "missing",
            "stripe_plans": "configured" if stripe_plans_ready else "missing",
            "legacy_mesh_lookup": "imported" if legacy_metering_ready else "unavailable",
            "subscription_sync": "stripe_required",
            "invoice_generation": "database_and_legacy_metering_required",
        },
        "claim_boundary": (
            "Billing route readiness distinguishes route availability from "
            "Stripe configuration, invoice database writes, and legacy MaaS "
            "metering imports. It does not prove live Stripe API reachability, "
            "webhook signature validity, or successful customer payment state."
        ),
    }


def _billing_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS billing EventBus: %s", exc)
        return None


def _publish_webhook_event(
    request: Optional[Request],
    source_agent: str,
    stage: str,
    stripe_event_type: str,
    stripe_event_id: Optional[str] = None,
    session_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
    plan: Optional[str] = None,
    amount_total: Optional[int] = None,
    currency: Optional[str] = None,
    status: str = "success",
    reason: str = "",
    redact: bool = False,
    **kwargs,
) -> None:
    if not request:
        return
    state = getattr(request, "state", None)
    bus = getattr(state, "event_bus", None)
    if not bus:
        return

    payload = {
        "component": "api.maas_billing",
        "operation": kwargs.get("operation") or ("stripe_subscription_webhook" if "subscription" in stripe_event_type else "stripe_checkout_session_webhook"),
        "stage": stage,
        "stripe_event_type": stripe_event_type,
        "service_name": "maas-billing",
        "source_alias": source_agent,
        "layer": kwargs.get("layer") or ("billing_subscription_webhook_lifecycle" if "subscription" in stripe_event_type else "billing_webhook_to_commerce_bridge"),
        "status": status,
        "reason": reason,
        "raw_identifiers_redacted": True,
        "settlement_evidence": {
            "source_quality": "stripe_webhook_event",
            "dataplane_confirmed": False,
            "live_provider_settlement_confirmed": False,
            "bank_settlement_confirmed": False,
            "chain_finality_confirmed": False,
            "raw_identifiers_redacted": True,
        },
        "claim_boundary": BILLING_WEBHOOK_CLAIM_BOUNDARY,
    }
    
    # Hash raw identifiers
    if redact:
        if stripe_event_id:
            payload["stripe_event_id_hash"] = _redacted_sha256_prefix(stripe_event_id)
        if session_id:
            payload["session_id_hash"] = _redacted_sha256_prefix(session_id)
        if invoice_id:
            payload["invoice_id_hash"] = _redacted_sha256_prefix(invoice_id)
        if user_id:
            payload["user_id_hash"] = _redacted_sha256_prefix(user_id)
        if customer_id:
            payload["stripe_customer_id_hash"] = _redacted_sha256_prefix(customer_id)
        if subscription_id:
            payload["stripe_subscription_id_hash"] = _redacted_sha256_prefix(subscription_id)
    else:
        if stripe_event_id:
            payload["stripe_event_id"] = stripe_event_id
            payload["stripe_event_id_hash"] = _redacted_sha256_prefix(stripe_event_id)
        if session_id:
            payload["session_id"] = session_id
            payload["session_id_hash"] = _redacted_sha256_prefix(session_id)
        if invoice_id:
            payload["invoice_id"] = invoice_id
            payload["invoice_id_hash"] = _redacted_sha256_prefix(invoice_id)
        if user_id:
            payload["user_id"] = user_id
            payload["user_id_hash"] = _redacted_sha256_prefix(user_id)
        if customer_id:
            payload["stripe_customer_id"] = customer_id
            payload["stripe_customer_id_hash"] = _redacted_sha256_prefix(customer_id)
        if subscription_id:
            payload["stripe_subscription_id"] = subscription_id
            payload["stripe_subscription_id_hash"] = _redacted_sha256_prefix(subscription_id)

    # Simple/plain values
    payload["plan"] = plan
    if amount_total is not None:
        payload["amount_total"] = amount_total
    if currency:
        payload["currency"] = currency
        
    # Copy other kwargs
    for k, v in kwargs.items():
        if k not in {"operation", "layer"}:
            payload[k] = v
            
    try:
        bus.publish(EventType.PIPELINE_STAGE_END, source_agent, payload, priority=6)
    except Exception as exc:
        logger.error(f"Failed to publish webhook event to {source_agent}: {exc}")


def _publish_billing_webhook_event(
    request: Optional[Request],
    event_type: EventType,
    *,
    stage: str,
    stripe_event_type: str,
    stripe_event_id: Optional[str] = None,
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
    user_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    plan: Optional[str] = None,
    amount_total: Optional[int] = None,
    currency: Optional[str] = None,
    bridge_x0t_requested: bool = False,
    bridge_x0t_minted: bool = False,
    status: str = "success",
    reason: str = "",
) -> Optional[str]:
    _publish_webhook_event(
        request=request,
        source_agent="maas-billing",
        stage=stage,
        stripe_event_type=stripe_event_type,
        stripe_event_id=stripe_event_id,
        session_id=session_id,
        invoice_id=invoice_id,
        user_id=user_id,
        plan=plan,
        amount_total=amount_total,
        currency=currency,
        bridge_x0t_requested=bridge_x0t_requested,
        bridge_x0t_minted=bridge_x0t_minted,
        status=status,
        reason=reason,
    )
    return "dummy-event-id"


@router.get("/readiness")
async def billing_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _billing_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


async def _execute_stripe_call(
    operation,
    *,
    request: Optional[Request] = None,
):
    """Execute Stripe call via shared timeout/retry/circuit policy."""
    try:
        return await call_with_reliability(operation, dependency="stripe")
    except CircuitBreakerOpen:
        if request is not None:
            mark_degraded_dependency(request, "stripe")
        raise HTTPException(
            status_code=503,
            detail="Payment service temporarily unavailable",
        )
    except RetryExhausted:
        if request is not None:
            mark_degraded_dependency(request, "stripe")
        raise HTTPException(
            status_code=503,
            detail="Payment gateway timeout",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Stripe call failed: %s", exc)
        record_billing_error("stripe_timeout")
        if request is not None:
            mark_degraded_dependency(request, "stripe")
        raise HTTPException(status_code=503, detail="Payment gateway error")

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mesh_id: str
    total_amount: float
    status: str
    stripe_session_id: Optional[str] = None
    period_start: datetime
    period_end: datetime
    issued_at: datetime

class SubscriptionResponse(BaseModel):
    id: Optional[str]
    plan: str
    status: str
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool = False

@router.post("/subscriptions/checkout")
async def create_subscription_session(
    plan: str,
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for a subscription."""
    # Validate plan and ensure price ID is configured
    if plan not in STRIPE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan selected")
    
    price_id = STRIPE_PLANS.get(plan)
    if not price_id:
        raise HTTPException(
            status_code=500, 
            detail=f"Plan '{plan}' price not configured. Set STRIPE_PRICE_{plan.upper()}"
        )
 
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
 
    try:
        customer_created = False
        # Create or retrieve Stripe Customer
        if not current_user.stripe_customer_id:
            async def _create_customer():
                return await asyncio.to_thread(
                    stripe.Customer.create,
                    email=current_user.email,
                    name=current_user.full_name,
                    metadata={"user_id": current_user.id},
                )
 
            customer = await _execute_stripe_call(_create_customer, request=request)
            current_user.stripe_customer_id = customer.id
            db.commit()
            customer_created = True
 
        async def _create_checkout():
            return await asyncio.to_thread(
                stripe.checkout.Session.create,
                customer=current_user.stripe_customer_id,
                payment_method_types=["card"],
                allow_promotion_codes=True,
                line_items=[
                    {
                        "price": STRIPE_PLANS[plan],
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=APP_DOMAIN + "/billing/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=APP_DOMAIN + "/billing/cancel",
                metadata={
                    "user_id": current_user.id,
                    "plan": plan,
                },
            )
 
        checkout_session = await _execute_stripe_call(_create_checkout, request=request)
 
        record_audit_log(
            db, request, "SUBSCRIPTION_SESSION_CREATED",
            user_id=current_user.id,
            payload={"plan": plan},
            status_code=200
        )
        
        res = {
            "url": checkout_session.url,
            "claim_gate": {
                "checkout_intent_claim_allowed": True,
                "payment_provider_settlement_claim_allowed": False,
                "customer_dataplane_delivery_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
            "cross_plane_claim_gate": {
                "surface": "maas_billing.subscription_checkout",
                "allowed": False,
            },
            "claim_boundary": "checkout intent only, does not prove customer payment",
        }
        _publish_event(
            request,
            source_agent="maas-billing-subscription-checkout",
            payload={
                "component": "api.maas_billing",
                "operation": "create_subscription_session",
                "stage": "subscription_checkout_created",
                "status": "success",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-subscription-checkout",
                "layer": "billing_subscription_checkout_intent",
                "provider": "stripe",
                "plan": plan,
                "stripe_configured": True,
                "customer_created": customer_created,
                "checkout_url_present": True,
                "local_db_write": True,
                "audit_recorded": True,
                "raw_identifiers_redacted": True,
                "user_id_hash": _redacted_sha256_prefix(current_user.id),
                "stripe_customer_id_hash": _redacted_sha256_prefix(current_user.stripe_customer_id),
                "stripe_session_id_hash": _redacted_sha256_prefix(checkout_session.id),
                "price_id_hash": _redacted_sha256_prefix(STRIPE_PLANS[plan]),
            }
        )
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe subscription session: {e}")
        raise HTTPException(status_code=500, detail="Payment gateway error")
 
@router.post("/customer-portal")
async def create_customer_portal(
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Create a link to the Stripe Customer Portal for subscription management."""
    if not current_user.stripe_customer_id:
        _publish_event(
            request,
            source_agent="maas-billing-customer-portal",
            payload={
                "component": "api.maas_billing",
                "operation": "create_customer_portal",
                "stage": "customer_missing",
                "status": "failed",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-customer-portal",
                "layer": "billing_customer_portal_intent",
                "provider": "stripe",
                "stripe_configured": False,
                "portal_url_present": False,
                "local_db_write": False,
                "raw_identifiers_redacted": True,
                "user_id_hash": _redacted_sha256_prefix(current_user.id),
            }
        )
        raise HTTPException(status_code=400, detail="No billing history found")
 
    try:
        async def _create_portal():
            return await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=current_user.stripe_customer_id,
                return_url=APP_DOMAIN + "/billing",
            )
 
        session = await _execute_stripe_call(_create_portal, request=request)
        res = {
            "url": session.url,
            "claim_gate": {
                "checkout_intent_claim_allowed": True,
                "payment_provider_settlement_claim_allowed": False,
                "customer_dataplane_delivery_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
            "cross_plane_claim_gate": {
                "surface": "maas_billing.customer_portal",
                "allowed": False,
            },
            "claim_boundary": "portal session, does not prove subscription changes",
        }
        _publish_event(
            request,
            source_agent="maas-billing-customer-portal",
            payload={
                "component": "api.maas_billing",
                "operation": "create_customer_portal",
                "stage": "portal_session_created",
                "status": "success",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-customer-portal",
                "layer": "billing_customer_portal_intent",
                "provider": "stripe",
                "stripe_configured": True,
                "portal_url_present": True,
                "local_db_write": False,
                "raw_identifiers_redacted": True,
                "user_id_hash": _redacted_sha256_prefix(current_user.id),
                "stripe_customer_id_hash": _redacted_sha256_prefix(current_user.stripe_customer_id),
                "stripe_portal_session_id_hash": _redacted_sha256_prefix(session.id),
            }
        )
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe portal session: {e}")
        raise HTTPException(status_code=500, detail="Portal error")
 
async def sync_subscription_with_stripe(user: User, db: Session, request: Optional[Request] = None):
    """
    Directly query Stripe API to reconcile subscription status.
    Call this periodically or on critical user actions.
    """
    if not user.stripe_customer_id or not STRIPE_SECRET_KEY:
        return
    plan_before = user.plan
    price_id = None
    try:
        def _get_subs():
            return stripe.Subscription.list(customer=user.stripe_customer_id, status="active", limit=1)
 
        subs = await _execute_stripe_call(_get_subs, request=request)
        if subs.data:
            stripe_sub = subs.data[0]
            # Map Stripe price ID back to local plan (inverse lookup)
            price_id = stripe_sub['items']['data'][0]['price']['id']
            plan_name = next((k for k, v in STRIPE_PLANS.items() if v == price_id), "free")
            
            user.plan = plan_name
            user.stripe_subscription_id = stripe_sub.id
        else:
            user.plan = "free"
            user.stripe_subscription_id = None
        
        db.commit()
 
        _publish_event(
            request,
            source_agent="maas-billing-subscription-sync",
            payload={
                "component": "api.maas_billing",
                "operation": "sync_subscription_with_stripe",
                "stage": "subscription_synced",
                "status": "success",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-subscription-sync",
                "layer": "billing_subscription_sync",
                "provider": "stripe",
                "stripe_configured": True,
                "local_db_write": True,
                "plan_before": plan_before,
                "plan_after": user.plan,
                "subscription_status": "active" if user.stripe_subscription_id else "free",
                "raw_identifiers_redacted": True,
                "user_id_hash": _redacted_sha256_prefix(user.id),
                "stripe_customer_id_hash": _redacted_sha256_prefix(user.stripe_customer_id),
                "stripe_subscription_id_hash": _redacted_sha256_prefix(user.stripe_subscription_id),
                "price_id_hash": _redacted_sha256_prefix(price_id),
            }
        )
    except Exception as e:
        logger.error(f"Failed to sync subscription for user {user.id}: {e}")


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Sync with Stripe then fetch current subscription status."""
    await sync_subscription_with_stripe(current_user, db)
    return SubscriptionResponse(
        id=current_user.stripe_subscription_id,
        plan=current_user.plan,
        status="active" if current_user.stripe_subscription_id else "free",
        current_period_end=None, # In production, sync from stripe_sub['current_period_end']
        cancel_at_period_end=False
    )

@router.post("/invoices/generate/{mesh_id}", response_model=InvoiceResponse)
async def generate_invoice(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    usage = usage_metering_service.get_mesh_usage(instance)
    
    # Simple pricing: $0.01 per node-hour for starter, $0.05 for enterprise
    rate = 0.01 if current_user.plan != "enterprise" else 0.05
    subtotal_cents = int(usage["total_node_hours"] * rate * 100)
    minimum_invoice_applied = subtotal_cents < 50
    
    # Minimum invoice amount for Stripe is $0.50
    if subtotal_cents < 50:
        subtotal_cents = 50
 
    new_inv = Invoice(
        id=f"inv-{uuid.uuid4().hex[:8]}",
        user_id=current_user.id,
        mesh_id=mesh_id,
        total_amount=subtotal_cents,
        period_start=datetime.fromisoformat(usage["billing_period_start"]),
        period_end=datetime.fromisoformat(usage["billing_period_end"]),
        status="issued"
    )
    db.add(new_inv)
    db.commit()
    db.refresh(new_inv)
    
    res = InvoiceResponse.model_validate(new_inv)
    res.total_amount = new_inv.total_amount / 100.0
 
    _publish_event(
        request,
        source_agent="maas-billing-invoice",
        payload={
            "component": "api.maas_billing",
            "operation": "generate_invoice",
            "stage": "invoice_generated",
            "status": "success",
            "service_name": "maas-billing",
            "source_alias": "maas-billing-invoice",
            "layer": "billing_invoice_generation",
            "raw_identifiers_redacted": True,
            "local_db_write": True,
            "user_id_hash": _redacted_sha256_prefix(current_user.id),
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "invoice_id_hash": _redacted_sha256_prefix(new_inv.id),
            "subtotal_cents": subtotal_cents,
            "minimum_invoice_applied": minimum_invoice_applied,
            "currency": new_inv.currency,
            "usage_summary": {
                "active_nodes": usage.get("active_nodes"),
                "node_entries": len(usage.get("nodes", [])),
            },
        }
    )
    return res
 
@router.get("/invoices/history", response_model=List[InvoiceResponse])
async def list_invoices(
    request: Request,
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    history = db.query(Invoice).filter(Invoice.user_id == current_user.id).all()
    results = []
    status_counts = {}
    currencies = []
    total_amount_cents = 0
    with_stripe_session_count = 0
    for inv in history:
        r = InvoiceResponse.model_validate(inv)
        r.total_amount = inv.total_amount / 100.0
        results.append(r)
        status_counts[inv.status] = status_counts.get(inv.status, 0) + 1
        if inv.currency not in currencies:
            currencies.append(inv.currency)
        total_amount_cents += inv.total_amount
        if inv.stripe_session_id:
            with_stripe_session_count += 1
            
    _publish_event(
        request,
        source_agent="maas-billing-history",
        payload={
            "component": "api.maas_billing",
            "operation": "list_invoices",
            "stage": "observed_state",
            "status": "success",
            "service_name": "maas-billing",
            "source_alias": "maas-billing-history",
            "layer": "billing_history_observed_state",
            "read_only": True,
            "observed_state": True,
            "safe_actuator": False,
            "raw_identifiers_redacted": True,
            "user_id_hash": _redacted_sha256_prefix(current_user.id),
            "history_summary": {
                "invoice_count": len(history),
                "status_counts": status_counts,
                "currencies": currencies,
                "total_amount_cents": total_amount_cents,
                "with_stripe_session_count": with_stripe_session_count,
            }
        }
    )
    return results
 
@router.get("/invoices/{invoice_id}/checkout")
async def create_checkout_session(
    invoice_id: str,
    request: Request,
    current_user: User = Depends(require_permission("billing:pay")),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for a specific invoice."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if inv.status == "paid":
        res = {
            "message": "Invoice already paid",
            "url": None,
            "claim_gate": {
                "stripe_status_observation_claim_allowed": True,
                "payment_provider_settlement_claim_allowed": False,
                "bank_settlement_claim_allowed": False,
                "customer_dataplane_delivery_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
            "cross_plane_claim_gate": {
                "surface": "maas_billing.invoice_checkout",
                "allowed": False,
            },
            "claim_boundary": "already paid, does not prove customer payment",
        }
        return res
 
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
 
    try:
        async def _create_invoice_checkout():
            return await asyncio.to_thread(
                stripe.checkout.Session.create,
                customer_email=current_user.email,
                payment_method_types=["card"],
                allow_promotion_codes=True,
                line_items=[
                    {
                        "price_data": {
                            "currency": inv.currency.lower(),
                            "product_data": {
                                "name": f"MaaS Mesh Usage ({inv.mesh_id})",
                                "description": f"Period: {inv.period_start.date()} to {inv.period_end.date()}",
                            },
                            "unit_amount": inv.total_amount,
                        },
                        "quantity": 1,
                    },
                ],
                mode="payment",
                success_url=APP_DOMAIN
                + f"/billing/success?session_id={{CHECKOUT_SESSION_ID}}&invoice_id={inv.id}",
                cancel_url=APP_DOMAIN + f"/billing/cancel?invoice_id={inv.id}",
                metadata={
                    "invoice_id": inv.id,
                    "user_id": current_user.id,
                    "mesh_id": inv.mesh_id,
                },
            )
 
        checkout_session = await _execute_stripe_call(
            _create_invoice_checkout,
            request=request,
        )
        
        # Save session ID for reconciliation
        inv.stripe_session_id = checkout_session.id
        db.commit()
        
        res = {
            "url": checkout_session.url,
            "claim_gate": {
                "checkout_intent_claim_allowed": True,
                "payment_provider_settlement_claim_allowed": False,
                "customer_dataplane_delivery_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
            "cross_plane_claim_gate": {
                "surface": "maas_billing.invoice_checkout",
                "allowed": False,
            },
            "claim_boundary": "checkout intent only, does not prove customer payment",
        }
        _publish_event(
            request,
            source_agent="maas-billing-checkout",
            payload={
                "component": "api.maas_billing",
                "operation": "create_checkout_session",
                "stage": "checkout_session_created",
                "status": "success",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-checkout",
                "layer": "billing_checkout_intent",
                "provider": "stripe",
                "stripe_configured": True,
                "checkout_url_present": True,
                "local_db_write": True,
                "amount_total": inv.total_amount,
                "currency": inv.currency,
                "raw_identifiers_redacted": True,
                "user_id_hash": _redacted_sha256_prefix(current_user.id),
                "invoice_id_hash": _redacted_sha256_prefix(inv.id),
                "mesh_id_hash": _redacted_sha256_prefix(inv.mesh_id),
                "stripe_session_id_hash": _redacted_sha256_prefix(checkout_session.id),
                "checkout_url_hash": _redacted_sha256_prefix(checkout_session.url),
                "settlement_evidence": {
                    "present": True,
                    "provider": "stripe",
                    "source_quality": "stripe_checkout_intent_created",
                    "settlement_action": "checkout_session_intent_only",
                    "dataplane_confirmed": False,
                    "live_provider_settlement_confirmed": False,
                    "bank_settlement_confirmed": False,
                    "chain_finality_confirmed": False,
                    "db_write_evidence": {
                        "storage_backend": "sql_db",
                        "attempted": True,
                        "committed": True,
                    },
                    "output_summary": {
                        "stripe_session_present": True,
                    },
                },
            }
        )
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe checkout session: {e}")
        raise HTTPException(status_code=500, detail="Payment gateway error")

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks for payment confirmation and subscription lifecycle."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
 
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not set")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
 
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.warning(f"Invalid Stripe webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
 
    stripe_event_id = event.get("id")
    event_type = event['type']
    data_object = event['data']['object']
 
    if event_type == 'checkout.session.completed':
        session = data_object
        mode = session.get('mode')
        metadata = session.get('metadata', {})
        session_id = session.get('id')
        payment_status = session.get('payment_status')
        if payment_status and payment_status not in {"paid", "no_payment_required"}:
            logger.info(
                "Ignoring checkout session %s with payment_status=%s",
                session_id or "<missing>",
                payment_status,
            )
            invoice_id = metadata.get('invoice_id')
            _publish_webhook_event(
                request=request,
                source_agent="maas-billing",
                stage="payment_not_completed",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                session_id=session_id,
                invoice_id=invoice_id,
                status="skipped",
                payment_status=payment_status,
                redact=True,
            )
            return {"status": "success", "skipped": "payment_not_completed"}
        if session_id:
            existing_paid = db.query(Invoice).filter(
                Invoice.stripe_session_id == session_id,
                Invoice.status == "paid",
            ).first()
            if existing_paid:
                logger.info("Skipping already processed checkout session %s", session_id)
                user_id = metadata.get('user_id') or getattr(existing_paid, "user_id", None)
                _publish_webhook_event(
                    request=request,
                    source_agent="maas-billing",
                    stage="idempotent_replay",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    invoice_id=existing_paid.id,
                    user_id=user_id,
                    status="skipped",
                    redact=True,
                )
                return {"status": "success", "idempotent": True}
        elif mode == 'subscription':
            logger.error("Missing checkout session id in webhook payload for subscription")
            user_id = metadata.get('user_id')
            _publish_webhook_event(
                request=request,
                source_agent="maas-billing",
                stage="missing_session_id",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                user_id=user_id,
                status="failed",
                session_id_present=False,
                redact=True,
            )
            return {"status": "error", "reason": "missing_session_id"}
 
        if mode == 'subscription':
            user_id = metadata.get('user_id')
            user = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            customer_id = session.get('customer')
            if not user and customer_id:
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if not user:
                logger.error("User not found for completed session %s", session_id or "<missing>")
                _publish_webhook_event(
                    request=request,
                    source_agent="maas-billing",
                    stage="user_not_found",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    customer_id=customer_id,
                    subscription_id=session.get('subscription'),
                    user_id=user_id,
                    status="failed",
                    redact=True,
                )
                return {"status": "error", "reason": "user_not_found"}
 
            plan = metadata.get('plan')
            subscription_id = session.get('subscription')
            # Validate plan from metadata to prevent tampering
            if plan not in STRIPE_PLANS:
                logger.error(
                    "Invalid plan '%s' in Stripe webhook metadata for user %s",
                    plan,
                    user.id,
                )
                _publish_webhook_event(
                    request=request,
                    source_agent="maas-billing",
                    stage="invalid_plan",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    subscription_id=subscription_id,
                    user_id=user.id,
                    status="failed",
                    plan=None,
                    redact=True,
                )
                return {"status": "error", "reason": "invalid_plan"}
 
            user.plan = plan
            user.stripe_subscription_id = subscription_id
 
            # Stripe amounts are in cents
            try:
                amount_total = int(session.get('amount_total', 4900))
            except (TypeError, ValueError):
                amount_total = 4900
            if amount_total < 0:
                amount_total = 0
            currency = session.get('currency', 'usd').upper()
 
            existing_invoice = db.query(Invoice).filter(
                Invoice.stripe_session_id == session_id
            ).first()
            if existing_invoice:
                existing_invoice.status = "paid"
                existing_invoice.user_id = user.id
                new_invoice = existing_invoice
            else:
                new_invoice = Invoice(
                    id=f"inv_{uuid.uuid4().hex[:8]}",
                    user_id=user.id,
                    mesh_id="subscription",
                    total_amount=amount_total,
                    currency=currency,
                    status="paid",
                    stripe_session_id=session_id,
                    period_start=_utc_now(),
                    period_end=_utc_now() + timedelta(days=30),
                    issued_at=_utc_now(),
                )
                db.add(new_invoice)
 
            db.commit()
 
            # Optional fiat->X0T bridge: only when explicitly requested in metadata.
            bridge_flag = str(metadata.get("bridge_x0t", "")).strip().lower() in {"1", "true", "yes"}
            bridge_minted = False
            bridge_reason = ""
            if bridge_flag and amount_total > 0:
                try:
                    from src.api.maas_marketplace import _get_token_bridge
                    bridge = _get_token_bridge()
                    bridge.mesh_token.mint(
                        user.id,
                        float(amount_total),
                        f"stripe_payment_{session_id}",
                    )
                    bridge_minted = True
                    logger.info("Minted %s X0T for user %s via Stripe bridge", amount_total, user.id)
                except Exception as exc:
                    bridge_reason = type(exc).__name__
                    logger.error("Failed to bridge Stripe payment to X0T: %s", exc)
 
            record_audit_log(
                db, request, "SUBSCRIPTION_ACTIVATED",
                user_id=user.id,
                payload={"plan": plan, "subscription_id": subscription_id, "invoice_id": new_invoice.id},
                status_code=200
            )
            _publish_billing_webhook_event(
                request,
                EventType.PIPELINE_STAGE_END,
                stage="subscription_activated",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                session_id=session_id,
                mode=mode,
                user_id=user.id,
                invoice_id=new_invoice.id,
                plan=plan,
                amount_total=amount_total,
                currency=currency,
                bridge_x0t_requested=bridge_flag,
                bridge_x0t_minted=bridge_minted,
                reason=bridge_reason,
            )
        else:
            # payment mode or mode not set — handle invoice_id if present
            invoice_id = metadata.get('invoice_id')
            if invoice_id:
                inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                if inv:
                    if inv.status != "paid":
                        inv.status = "paid"
                        if session_id:
                            inv.stripe_session_id = session_id
                        db.commit()
                        record_audit_log(
                            db, request, "INVOICE_PAID",
                            user_id=inv.user_id,
                            payload={"invoice_id": invoice_id},
                            status_code=200
                        )
                        _publish_billing_webhook_event(
                            request,
                            EventType.PIPELINE_STAGE_END,
                            stage="invoice_paid",
                            stripe_event_type=event_type,
                            stripe_event_id=stripe_event_id,
                            session_id=session_id,
                            mode=mode,
                            user_id=inv.user_id,
                            invoice_id=invoice_id,
                            amount_total=session.get("amount_total"),
                            currency=str(session.get("currency", "")).upper() or None,
                        )
                    else:
                        logger.info("Invoice %s already marked paid", invoice_id)
                else:
                    logger.error("Invoice %s not found for webhook", invoice_id)
                    _publish_webhook_event(
                        request=request,
                        source_agent="maas-billing",
                        stage="invoice_not_found",
                        stripe_event_type=event_type,
                        stripe_event_id=stripe_event_id,
                        session_id=session_id,
                        invoice_id=invoice_id,
                        status="failed",
                        amount_total=session.get("amount_total"),
                        currency=str(session.get("currency", "")).upper() or None,
                        redact=True,
                    )
 
    elif event_type == 'customer.subscription.updated':
        subscription = data_object
        customer_id = subscription.get('customer')
        status = subscription.get('status')
        subscription_id = subscription.get('id')
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            plan_before = user.plan
            plan_after = user.plan
            record_audit_log(
                db, request, "SUBSCRIPTION_UPDATED",
                user_id=user.id,
                payload={"status": status, "sub_id": subscription_id},
                status_code=200
            )
            _publish_webhook_event(
                request=request,
                source_agent="maas-billing-subscription-webhook",
                stage="subscription_updated",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                user_id=user.id,
                status="success",
                subscription_status=status,
                plan_before=plan_before,
                plan_after=plan_after,
                local_db_write=False,
                audit_recorded=True,
                redact=True,
            )
 
    elif event_type == 'customer.subscription.deleted':
        subscription = data_object
        customer_id = subscription.get('customer')
        subscription_id = subscription.get('id')
        status = subscription.get('status') or "canceled"
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            plan_before = user.plan
            user.plan = "free"
            user.stripe_subscription_id = None
            db.commit()
            record_audit_log(
                db, request, "SUBSCRIPTION_CANCELLED",
                user_id=user.id,
                payload={"sub_id": subscription_id},
                status_code=200
            )
            _publish_webhook_event(
                request=request,
                source_agent="maas-billing-subscription-webhook",
                stage="subscription_cancelled",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                user_id=user.id,
                status="success",
                subscription_status=status,
                plan_before=plan_before,
                plan_after="free",
                local_db_write=True,
                audit_recorded=True,
                redact=True,
            )
    return {"status": "success"}

@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice_manual(
    invoice_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Legacy manual payment endpoint (mock)."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not inv:
        _publish_event(
            request,
            source_agent="maas-billing-manual-payment",
            payload={
                "component": "api.maas_billing",
                "operation": "pay_invoice_manual",
                "stage": "invoice_not_found",
                "status": "failed",
                "service_name": "maas-billing",
                "source_alias": "maas-billing-manual-payment",
                "layer": "billing_manual_payment_mock",
                "raw_identifiers_redacted": True,
                "local_db_write": False,
                "user_id_hash": _redacted_sha256_prefix(current_user.id),
                "invoice_id_hash": _redacted_sha256_prefix(invoice_id),
            }
        )
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice_status_before = inv.status
    inv.status = "paid"
    db.commit()

    _publish_event(
        request,
        source_agent="maas-billing-manual-payment",
        payload={
            "component": "api.maas_billing",
            "operation": "pay_invoice_manual",
            "stage": "manual_payment_recorded",
            "status": "success",
            "service_name": "maas-billing",
            "source_alias": "maas-billing-manual-payment",
            "layer": "billing_manual_payment_mock",
            "provider": "local_mock",
            "invoice_status_before": invoice_status_before,
            "invoice_status_after": "paid",
            "amount_total": inv.total_amount,
            "currency": inv.currency,
            "local_db_write": True,
            "raw_identifiers_redacted": True,
            "user_id_hash": _redacted_sha256_prefix(current_user.id),
            "invoice_id_hash": _redacted_sha256_prefix(inv.id),
            "mesh_id_hash": _redacted_sha256_prefix(inv.mesh_id),
        }
    )
    return {"status": "paid", "invoice_id": invoice_id}

