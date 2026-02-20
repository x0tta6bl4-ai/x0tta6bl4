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
    """Handle Stripe webhooks for payment confirmation."""
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        invoice_id = session.get('metadata', {}).get('invoice_id')
        
        if invoice_id:
            inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if inv:
                inv.status = "paid"
                db.commit()
                logger.info(f"Invoice {invoice_id} marked as PAID via Stripe webhook")
            else:
                logger.error(f"Invoice {invoice_id} not found from Stripe webhook")
        else:
            logger.warning("Stripe checkout.session.completed missing invoice_id metadata")

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
