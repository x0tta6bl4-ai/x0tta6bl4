"""
MaaS Automatic Invoicing (Production) — x0tta6bl4
================================================

SQLAlchemy-backed enterprise billing logic with Stripe integration.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import User, Invoice, get_db
from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.utils.audit import record_audit_log

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

# Stripe Plan Price IDs (should come from env in production)
STRIPE_PLANS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", "price_starter_id"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_id"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise_id"),
}

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    logger.warning("STRIPE_SECRET_KEY not set. Payments will fail.")

router = APIRouter(prefix="/api/v1/maas/billing", tags=["MaaS Billing"])

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
    if plan not in STRIPE_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan selected")

    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    try:
        # Create or retrieve Stripe Customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={"user_id": current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()

        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            allow_promotion_codes=True,
            line_items=[{
                'price': STRIPE_PLANS[plan],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=APP_DOMAIN + "/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=APP_DOMAIN + "/billing/cancel",
            metadata={
                "user_id": current_user.id,
                "plan": plan
            }
        )
        
        record_audit_log(
            db, request, "SUBSCRIPTION_SESSION_CREATED",
            user_id=current_user.id,
            payload={"plan": plan},
            status_code=200
        )
        
        return {"url": checkout_session.url}
    except Exception as e:
        logger.error(f"Failed to create Stripe subscription session: {e}")
        raise HTTPException(status_code=500, detail="Payment gateway error")

@router.post("/customer-portal")
async def create_customer_portal(
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Create a link to the Stripe Customer Portal for subscription management."""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing history found")

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=APP_DOMAIN + "/billing",
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Failed to create Stripe portal session: {e}")
        raise HTTPException(status_code=500, detail="Portal error")

@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user_from_maas)
):
    """Fetch current subscription status from User model/Stripe."""
    # In a real app, we'd sync this via webhooks. 
    # Here we just return what's in the DB for the POC.
    return SubscriptionResponse(
        id=current_user.stripe_subscription_id,
        plan=current_user.plan,
        status="active" if current_user.stripe_subscription_id else "free",
        current_period_end=None, # To be synced from Stripe
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
        checkout_session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=['card'],
            allow_promotion_codes=True,
            line_items=[
                {
                    'price_data': {
                        'currency': inv.currency.lower(),
                        'product_data': {
                            'name': f"MaaS Mesh Usage ({inv.mesh_id})",
                            'description': f"Period: {inv.period_start.date()} to {inv.period_end.date()}",
                        },
                        'unit_amount': inv.total_amount,
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=APP_DOMAIN + f"/billing/success?session_id={{CHECKOUT_SESSION_ID}}&invoice_id={inv.id}",
            cancel_url=APP_DOMAIN + f"/billing/cancel?invoice_id={inv.id}",
            metadata={
                "invoice_id": inv.id,
                "user_id": current_user.id,
                "mesh_id": inv.mesh_id
            }
        )
        
        # Save session ID for reconciliation
        inv.stripe_session_id = checkout_session.id
        db.commit()
        
        return {"url": checkout_session.url}
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
        user_id = metadata.get('user_id')
        
        if mode == 'subscription':
            plan = metadata.get('plan')
            subscription_id = session.get('subscription')
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # Validate plan from metadata to prevent tampering
                if plan not in STRIPE_PLANS:
                    logger.error(
                        "Invalid plan '%s' in Stripe webhook metadata for user %s",
                        plan, user.id
                    )
                    return {"status": "error", "reason": "invalid_plan"}
                user.plan = plan
                user.stripe_subscription_id = subscription_id
                db.commit()
                record_audit_log(
                    db, request, "SUBSCRIPTION_ACTIVATED",
                    user_id=user.id,
                    payload={"plan": plan, "subscription_id": subscription_id},
                    status_code=200
                )
        else:
            # payment mode or mode not set — handle invoice_id if present
            invoice_id = metadata.get('invoice_id')
            if invoice_id:
                inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                if inv:
                    inv.status = "paid"
                    db.commit()
                    record_audit_log(
                        db, request, "INVOICE_PAID",
                        user_id=inv.user_id,
                        payload={"invoice_id": invoice_id},
                        status_code=200
                    )
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
            db.commit()
            record_audit_log(
                db, request, "SUBSCRIPTION_CANCELLED",
                user_id=user.id,
                payload={"sub_id": subscription.get('id')},
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
