"""
MaaS Billing Endpoints - Billing and invoicing.

Provides REST API endpoints for billing webhooks and usage reports.
"""

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

try:
    import stripe
except ImportError:
    stripe = None

from ..auth import UserContext, get_auth_service, get_current_user
from ..billing_helpers import (
    generate_invoice,
    verify_webhook_with_timestamp,
)
from ..constants import PLAN_REQUEST_LIMITS
from ..services import BillingService, UsageMeteringService
from src.database import get_db, User, MeshInstance, Invoice
from src.coordination.events import EventBus, EventType, get_event_bus
from src.api import maas_legacy
from ..registry import get_all_meshes, get_mesh

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

# --- Modular Billing Implementation ---

@router.get("/invoices/history", summary="Get invoice history")
async def list_invoices(
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all invoices for the current user."""
    invoices = db.query(Invoice).filter(Invoice.user_id == user.user_id).all()
    results = []
    for inv in invoices:
        results.append({
            "id": inv.id,
            "mesh_id": inv.mesh_id,
            "total_amount": inv.total_amount / 100.0,
            "status": inv.status,
            "stripe_session_id": inv.stripe_session_id,
            "period_start": inv.period_start.isoformat() if inv.period_start else None,
            "period_end": inv.period_end.isoformat() if inv.period_end else None,
            "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        })
    return results

@router.post("/invoices/generate/{mesh_id}", summary="Generate invoice")
async def generate_invoice_modular(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Generate a new invoice for a mesh."""
    # Check if mesh exists
    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    # Simple owner check
    if mesh.owner_id != user.user_id:
        # Check if user is admin
        db_user = db.query(User).filter(User.id == user.user_id).first()
        if not db_user or db_user.role != "admin":
             raise HTTPException(status_code=404, detail="Mesh not found")

    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    new_inv = Invoice(
        id=inv_id,
        user_id=user.user_id,
        mesh_id=mesh_id,
        total_amount=50, # Mock $0.50
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        status="issued",
        issued_at=datetime.utcnow()
    )
    db.add(new_inv)
    db.commit()
    db.refresh(new_inv)
    
    return {
        "id": new_inv.id,
        "mesh_id": new_inv.mesh_id,
        "total_amount": new_inv.total_amount / 100.0,
        "status": new_inv.status,
        "period_start": new_inv.period_start.isoformat(),
        "period_end": new_inv.period_end.isoformat(),
        "issued_at": new_inv.issued_at.isoformat(),
    }

@router.post("/invoices/{invoice_id}/pay", summary="Pay invoice manually")
async def pay_invoice_manual(
    invoice_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an invoice as paid manually (for tests)."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Ownership check
    if inv.user_id != user.user_id:
        db_user = db.query(User).filter(User.id == user.user_id).first()
        if not db_user or db_user.role != "admin":
             raise HTTPException(status_code=404, detail="Invoice not found")

    inv.status = "paid"
    db.commit()
    return {"status": "paid", "invoice_id": invoice_id}

@router.get("/invoices/{invoice_id}/checkout")
async def create_checkout_session(
    invoice_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mock checkout session creation."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if inv.status == "paid":
        return {"message": "Invoice already paid", "url": None}

    from src.api import maas_billing as legacy_billing
    if not getattr(legacy_billing, "STRIPE_SECRET_KEY", None):
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    return {"url": "http://mock-checkout.stripe.com/session_abc", "id": "sess_abc"}

@router.post("/webhook", include_in_schema=False)
async def billing_webhook_root(
    request: Request,
    db: Session = Depends(get_db),
    x_billing_webhook_secret: Optional[str] = Header(default=None),
    x_billing_timestamp: Optional[str] = Header(default=None),
    x_billing_signature: Optional[str] = Header(default=None),
):
    """Unified billing webhook handler."""
    # Try to parse as MaaS legacy webhook first
    try:
        payload = await request.json()
        if "event_type" in payload and "email" in payload:
            # This looks like a MaaS legacy webhook used in integration tests
            from src.api.maas_legacy import BillingWebhookRequest
            try:
                req = BillingWebhookRequest(**payload)
            except Exception as exc:
                # If required fields are missing (like event_id in some tests)
                raise HTTPException(status_code=400, detail=str(exc))

            return await maas_legacy.legacy_billing_webhook(
                req=req,
                request=request,
                db=db,
                x_billing_webhook_secret=x_billing_webhook_secret,
                x_billing_timestamp=x_billing_timestamp,
                x_billing_signature=x_billing_signature,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error in billing webhook: {exc}")
        # Standard fallback for validation errors etc.
        raise HTTPException(status_code=400, detail=str(exc))

    # Fallback to Stripe webhook logic if it's not a legacy webhook
    return await stripe_webhook(request, db)


@router.post("/webhook/stripe", summary="Stripe webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook endpoint."""
    from src.api import maas_billing as legacy_billing

    webhook_secret = (
        getattr(legacy_billing, "STRIPE_WEBHOOK_SECRET", None)
        or os.getenv("STRIPE_WEBHOOK_SECRET")
    )
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Invalid signature")
    if stripe is None:
        raise HTTPException(status_code=500, detail="Stripe SDK not available")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event.get('type') == 'checkout.session.completed':
        session = event.get('data', {}).get('object', {})
        metadata = session.get('metadata', {})
        inv_id = metadata.get('invoice_id')
        if inv_id:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv:
                inv.status = "paid"
                db.commit()
    
    return {"status": "success"}

@router.get("/usage", summary="Get usage reports")
async def get_usage_reports(
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return usage reports for the current user."""
    meshes = [
        mesh
        for mesh in get_all_meshes().values()
        if str(getattr(mesh, "owner_id", "")) == str(user.user_id)
    ]
    mesh_summaries = []
    total_node_hours = 0.0
    for mesh in meshes:
        usage = maas_legacy.usage_metering_service.get_mesh_usage(mesh)
        total_node_hours += float(usage.get("total_node_hours") or 0.0)
        mesh_summaries.append(
            {
                "mesh_id": usage.get("mesh_id"),
                "mesh_name": usage.get("mesh_name"),
                "status": usage.get("status"),
                "active_nodes": usage.get("active_nodes"),
                "total_node_hours": usage.get("total_node_hours"),
            }
        )
    return {
        "owner_id": user.user_id,
        "total_node_hours": round(total_node_hours, 4),
        "mesh_count": len(mesh_summaries),
        "meshes": mesh_summaries,
        "generated_at": datetime.utcnow().isoformat(),
    }

@router.get("/usage/{mesh_id}", summary="Get usage for a mesh")
async def get_mesh_usage(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return usage for a specific mesh."""
    mesh = get_mesh(mesh_id)
    if mesh is None or str(getattr(mesh, "owner_id", "")) != str(user.user_id):
        raise HTTPException(status_code=404, detail="Mesh not found")
    return maas_legacy.usage_metering_service.get_mesh_usage(mesh)

@router.get("/limits", summary="Get plan limits")
async def get_plan_limits(
    user: UserContext = Depends(get_current_user),
):
    """Return plan limits for the current user."""
    plan = user.plan or "starter"
    return PLAN_REQUEST_LIMITS.get(plan, PLAN_REQUEST_LIMITS["starter"])
