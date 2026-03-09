"""
MaaS Automatic Invoicing (Production) — x0tta6bl4
================================================

SQLAlchemy-backed enterprise billing logic with Stripe integration.
"""

import logging
import os
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import User, Invoice, get_db
from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.core.reliability_policy import (CircuitBreakerOpen, RetryExhausted,
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

# --- Stripe Configuration ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://app.x0tta6bl4.com")

# Stripe Plan Price IDs (must be set via environment variables)
# We enforce real configuration for non-dev environments.
STRIPE_PLANS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}

# Validate Stripe configuration
_is_production = os.getenv("ENVIRONMENT", "").lower() in {"production", "prod"}
_missing_plans = [k for k, v in STRIPE_PLANS.items() if not v]

if _is_production and (not STRIPE_SECRET_KEY or _missing_plans):
    logger.critical(f"FATAL: Stripe not fully configured for production. Missing plans: {_missing_plans}")
elif _missing_plans:
    logger.warning(f"Development mode: Stripe plans missing ({_missing_plans}). Payments will only work with mock/legacy mode.")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/v1/maas/billing", tags=["MaaS Billing"])


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
    id: str
    mesh_id: str
    total_amount: float
    status: str
    stripe_session_id: Optional[str] = None
    period_start: datetime
    period_end: datetime
    issued_at: datetime

    class Config:
        from_attributes = True

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
        
        return {"url": checkout_session.url}
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
        raise HTTPException(status_code=400, detail="No billing history found")

    try:
        async def _create_portal():
            return await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=current_user.stripe_customer_id,
                return_url=APP_DOMAIN + "/billing",
            )

        session = await _execute_stripe_call(_create_portal, request=request)
        return {"url": session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe portal session: {e}")
        raise HTTPException(status_code=500, detail="Portal error")

async def sync_subscription_with_stripe(user: User, db: Session):
    """
    Directly query Stripe API to reconcile subscription status.
    Call this periodically or on critical user actions.
    """
    if not user.stripe_customer_id or not STRIPE_SECRET_KEY:
        return

    try:
        def _get_subs():
            return stripe.Subscription.list(customer=user.stripe_customer_id, status="active", limit=1)

        subs = await _execute_stripe_call(_get_subs)
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
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    instance = _get_mesh_or_404(mesh_id, current_user.id)
    usage = usage_metering_service.get_mesh_usage(instance)
    
    # Simple pricing: $0.01 per node-hour for starter, $0.05 for enterprise
    rate = 0.01 if current_user.plan != "enterprise" else 0.05
    subtotal_cents = int(usage["total_node_hours"] * rate * 100)
    
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
    
    res = InvoiceResponse.from_orm(new_inv)
    res.total_amount = new_inv.total_amount / 100.0
    return res

@router.get("/invoices/history", response_model=List[InvoiceResponse])
async def list_invoices(
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    history = db.query(Invoice).filter(Invoice.user_id == current_user.id).all()
    results = []
    for inv in history:
        r = InvoiceResponse.from_orm(inv)
        r.total_amount = inv.total_amount / 100.0
        results.append(r)
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
        return {"message": "Invoice already paid", "url": None}

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
        
        return {"url": checkout_session.url}
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
            return {"status": "success", "skipped": "payment_not_completed"}
        if session_id:
            existing_paid = db.query(Invoice).filter(
                Invoice.stripe_session_id == session_id,
                Invoice.status == "paid",
            ).first()
            if existing_paid:
                logger.info("Skipping already processed checkout session %s", session_id)
                return {"status": "success", "idempotent": True}
        elif mode == 'subscription':
            logger.error("Missing checkout session id in webhook payload for subscription")
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
                return {"status": "error", "reason": "invalid_plan"}

            user.plan = plan
            user.stripe_subscription_id = subscription_id

            # Sync plan with Tenant Quota Service
            from src.services.tenant_quota_service import TenantQuotaService
            quota_service = TenantQuotaService(db)
            quota_service.update_tenant_plan(user.tenant_id or user.id, plan)

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
                    period_start=datetime.utcnow(),
                    period_end=datetime.utcnow() + timedelta(days=30),
                    issued_at=datetime.utcnow(),
                )
                db.add(new_invoice)

            db.commit()

            # Optional fiat->X0T bridge: only when explicitly requested in metadata.
            bridge_flag = str(metadata.get("bridge_x0t", "")).strip().lower() in {"1", "true", "yes"}
            if bridge_flag and amount_total > 0:
                try:
                    from src.api.maas_marketplace import _get_token_bridge
                    bridge = _get_token_bridge()
                    bridge.mesh_token.mint(
                        user.id,
                        float(amount_total),
                        f"stripe_payment_{session_id}",
                    )
                    logger.info("Minted %s X0T for user %s via Stripe bridge", amount_total, user.id)
                except Exception as exc:
                    logger.error("Failed to bridge Stripe payment to X0T: %s", exc)

            record_audit_log(
                db, request, "SUBSCRIPTION_ACTIVATED",
                user_id=user.id,
                payload={"plan": plan, "subscription_id": subscription_id, "invoice_id": new_invoice.id},
                status_code=200
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
                    else:
                        logger.info("Invoice %s already marked paid", invoice_id)
                else:
                    logger.error("Invoice %s not found for webhook", invoice_id)

    elif event_type == 'customer.subscription.updated':
        subscription = data_object
        customer_id = subscription.get('customer')
        status = subscription.get('status')
        # Here we'd map Stripe price ID back to our plan name if needed
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            # Simple status sync
            record_audit_log(
                db, request, "SUBSCRIPTION_UPDATED",
                user_id=user.id,
                payload={"status": status, "sub_id": subscription.get('id')},
                status_code=200
            )

    elif event_type == 'customer.subscription.deleted':
        subscription = data_object
        customer_id = subscription.get('customer')
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.plan = "free"
            user.stripe_subscription_id = None
            
            instances = db.query(MeshInstance).filter(MeshInstance.owner_id == user.id).all()
            for inst in instances:
                inst.plan = "free"
                if inst.status == "active":
                    inst.status = "suspended"
                    logger.warning(f"Suspended mesh instance {inst.id} due to subscription cancellation")
            
            db.commit()
            record_audit_log(
                db, request, "SUBSCRIPTION_CANCELLED",
                user_id=user.id,
                payload={"sub_id": subscription.get('id')},
                status_code=200
            )

    elif event_type == 'invoice.payment_failed':
        invoice = data_object
        customer_id = invoice.get('customer')
        attempt_count = invoice.get('attempt_count', 1)
        
        logger.warning(f"Payment failed for customer {customer_id}, attempt {attempt_count}")
        
        if attempt_count >= 3:
            user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user:
                logger.warning(f"Downgrading user {user.id} to free plan due to repeated payment failures")
                user.plan = "free"
                
                instances = db.query(MeshInstance).filter(MeshInstance.owner_id == user.id).all()
                for inst in instances:
                    inst.plan = "free"
                    if inst.status == "active":
                        inst.status = "suspended"
                        logger.warning(f"Suspended mesh instance {inst.id} due to payment failure")
                        
                db.commit()
                record_audit_log(
                    db, request, "SUBSCRIPTION_DOWNGRADED",
                    user_id=user.id,
                    payload={"invoice_id": invoice.get('id'), "reason": "payment_failed"},
                    status_code=200
                )

    return {"status": "success"}

@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice_manual(
    invoice_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Legacy manual payment endpoint (mock)."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    inv.status = "paid"
    db.commit()
    return {"status": "paid", "invoice_id": invoice_id}
