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
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

try:
    import stripe
except ImportError:
    stripe = None

from ..auth import UserContext, get_auth_service, get_current_user
from ..billing_helpers import (
    calculate_mesh_cost,
    estimate_monthly_cost,
    format_currency,
    generate_invoice,
    verify_webhook_with_timestamp,
)
from ..constants import PLAN_REQUEST_LIMITS
from ..services import BillingService, UsageMeteringService
from src.database import get_db, User, MeshInstance, Invoice
from src.coordination.events import EventBus, EventType, get_event_bus
from .helpers.legacy_billing import legacy_billing_webhook as maas_legacy_webhook
from ..registry import get_all_meshes, get_mesh

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])
_billing_service: Optional[BillingService] = None
_usage_service: Optional[UsageMeteringService] = None

_MODULAR_BILLING_PAYMENT_SOURCE_AGENT = "maas-modular-billing-payment-intent"
_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT = "maas-modular-billing-webhook"
_MODULAR_BILLING_USAGE_SOURCE_AGENT = "maas-modular-billing-usage-read"
_MODULAR_BILLING_ESTIMATE_SOURCE_AGENT = "maas-modular-billing-estimate-read"
_MODULAR_BILLING_PLAN_SOURCE_AGENT = "maas-modular-billing-plan-read"
_MODULAR_BILLING_INVOICE_SOURCE_AGENT = "maas-modular-billing-invoice-generation"

_MODULAR_BILLING_LAYERS = {
    _MODULAR_BILLING_PAYMENT_SOURCE_AGENT: "api_modular_billing_payment_intent",
    _MODULAR_BILLING_WEBHOOK_SOURCE_AGENT: "api_modular_billing_webhook_lifecycle",
    _MODULAR_BILLING_USAGE_SOURCE_AGENT: "api_modular_billing_usage_observed_state",
    _MODULAR_BILLING_ESTIMATE_SOURCE_AGENT: "api_modular_billing_estimate_observed_state",
    _MODULAR_BILLING_PLAN_SOURCE_AGENT: "api_modular_billing_plan_observed_state",
    _MODULAR_BILLING_INVOICE_SOURCE_AGENT: "api_modular_billing_invoice_generation",
}

_MODULAR_BILLING_CLAIM_BOUNDARY = (
    "Modular MaaS billing endpoint evidence only. It records local billing "
    "intent, catalog, usage, invoice, or webhook lifecycle observations; it "
    "does not prove dataplane delivery, customer traffic, external settlement "
    "finality, bank settlement, revenue recognition, production SLOs, or "
    "production readiness."
)


def get_billing_service() -> BillingService:
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service


def get_usage_service() -> UsageMeteringService:
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageMeteringService()
    return _usage_service


def _billing_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", None) or getattr(
        state, "project_root", "."
    )
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize modular MaaS billing EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any, *, length: int = 16) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _safe_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _usage_bucket(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "unknown"
    if number <= 10:
        return "low"
    if number <= 1_000:
        return "medium"
    return "high"


def _modular_billing_claim_gate(
    *,
    local_lifecycle_allowed: bool,
    checkout_intent_allowed: bool = False,
    webhook_lifecycle_allowed: bool = False,
    read_only_observation_allowed: bool = False,
) -> Dict[str, Any]:
    return {
        "present": True,
        "decision": "LOCAL_BILLING_ONLY",
        "local_billing_lifecycle_claim_allowed": bool(local_lifecycle_allowed),
        "checkout_intent_claim_allowed": bool(checkout_intent_allowed),
        "webhook_lifecycle_claim_allowed": bool(webhook_lifecycle_allowed),
        "read_only_observation_claim_allowed": bool(read_only_observation_allowed),
        "payment_provider_settlement_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "serviceability_claim_allowed": False,
        "paid_customer_serviceability_claim_allowed": False,
        "customer_access_claim_allowed": False,
        "vpn_access_claim_allowed": False,
        "node_provisioning_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "customer_dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "revenue_recognition_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_provider_settlement_evidence": True,
        "requires_dataplane_evidence_for_delivery_claim": True,
        "requires_service_runtime_evidence_for_access_claim": True,
        "requires_external_finality_evidence_for_settlement_claim": True,
        "requires_cross_plane_proof_for_production_claim": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": _MODULAR_BILLING_CLAIM_BOUNDARY,
    }


def _modular_settlement_evidence(
    *,
    settlement_action: str,
    source_quality: str,
    provider: str,
    duration_ms: float,
    output_summary: Optional[Dict[str, Any]] = None,
    db_storage_backend: str = "modular_billing_route",
    db_write_attempted: bool = False,
    db_write_committed: bool = False,
    local_lifecycle_allowed: bool = True,
    checkout_intent_allowed: bool = False,
    webhook_lifecycle_allowed: bool = False,
    read_only_observation_allowed: bool = False,
) -> Dict[str, Any]:
    safe_output = dict(output_summary or {})
    safe_output["raw_identifiers_redacted"] = True
    safe_output["payloads_redacted"] = True
    return {
        "present": True,
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "settlement_action": settlement_action,
        "duration_ms": round(duration_ms, 3),
        "dataplane_confirmed": False,
        "provider": provider,
        "payment_status": None,
        "live_provider_settlement_confirmed": False,
        "bank_settlement_confirmed": False,
        "chain_finality_confirmed": False,
        "bridge_evidence": {
            "attempted": False,
            "status": "not_requested",
            "source_agent": None,
            "payloads_redacted": True,
        },
        "db_write_evidence": {
            "storage_backend": db_storage_backend,
            "attempted": bool(db_write_attempted),
            "committed": bool(db_write_committed),
            "payloads_redacted": True,
        },
        "output_summary": safe_output,
        "claim_gate": _modular_billing_claim_gate(
            local_lifecycle_allowed=local_lifecycle_allowed,
            checkout_intent_allowed=checkout_intent_allowed,
            webhook_lifecycle_allowed=webhook_lifecycle_allowed,
            read_only_observation_allowed=read_only_observation_allowed,
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _modular_cross_plane_claim_gate(surface: str) -> Dict[str, Any]:
    requested_claims = [
        "settlement_finality",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "production_readiness",
    ]
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "available": False,
        "surface": surface,
        "requested_claim_ids": requested_claims,
        "allowed_claim_ids": [],
        "blocked_claim_ids": requested_claims,
        "blockers": [
            "modular_billing_event_is_local_lifecycle_only",
            "external_settlement_finality_missing",
            "dataplane_delivery_artifact_not_verified",
            "production_readiness_cross_plane_missing",
        ],
        "claim_boundary": _MODULAR_BILLING_CLAIM_BOUNDARY,
        "payloads_redacted": True,
    }


def _publish_modular_billing_event(
    request: Optional[Request],
    *,
    source_agent: str,
    operation: str,
    status_text: str,
    started: float,
    source_quality: str,
    settlement_evidence: Dict[str, Any],
    read_only: bool,
    control_action: bool,
    priority: int = 6,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload: Dict[str, Any] = {
        "component": "api.maas.endpoints.billing",
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": _MODULAR_BILLING_LAYERS[source_agent],
        "status": status_text,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
        "source_quality": source_quality,
        "read_only": bool(read_only),
        "observed_state": bool(read_only),
        "control_action": bool(control_action),
        "economy_action": True,
        "safe_actuator": False,
        "settlement_evidence": settlement_evidence,
        "cross_plane_claim_gate": _modular_cross_plane_claim_gate(operation),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": _MODULAR_BILLING_CLAIM_BOUNDARY,
    }
    if extra:
        payload.update(extra)
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            source_agent,
            payload,
            priority=priority,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS billing event: %s", exc)
        return None


def _plan_catalog() -> List[Dict[str, Any]]:
    service = get_billing_service()
    return [
        {
            "name": plan,
            "limits": service.get_plan_limits(plan),
        }
        for plan in ("free", "pro", "enterprise")
    ]

# --- Modular Billing Implementation ---

@router.get("/billing/plans", summary="List billing plans")
async def list_plans(request: Request) -> List[Dict[str, Any]]:
    """Return the public modular billing plan catalog."""
    started = time.monotonic()
    plans = _plan_catalog()
    source_quality = "local_plan_catalog_observed_state"
    settlement = _modular_settlement_evidence(
        settlement_action="read_only_observed_state_no_settlement",
        source_quality=source_quality,
        provider="local_billing_catalog",
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "list_plans",
            "plans_count": len(plans),
        },
        local_lifecycle_allowed=False,
        read_only_observation_allowed=True,
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
        operation="list_plans",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=True,
        control_action=False,
        priority=4,
        extra={
            "result_summary": {
                "plans_count": len(plans),
                "plan_names": [plan["name"] for plan in plans],
                "payloads_redacted": True,
            },
        },
    )
    return plans


@router.get("/billing/estimate", summary="Estimate mesh cost")
async def estimate_cost(
    request: Request,
    node_count: int = Query(..., gt=0),
    node_type: str = "standard",
    plan: str = "starter",
    region: str = "us-east-1",
) -> Dict[str, Any]:
    """Estimate hourly and monthly cost without creating payment evidence."""
    started = time.monotonic()
    hourly = calculate_mesh_cost(node_count, node_type, plan, region, 1)
    monthly = estimate_monthly_cost(node_count, node_type, plan, region)
    response = {
        "node_count": node_count,
        "node_type": node_type,
        "plan": plan,
        "region": region,
        "hourly_cost": format_currency(hourly),
        "monthly_cost": format_currency(monthly),
        "hourly_cost_raw": _safe_money(hourly),
        "monthly_cost_raw": _safe_money(monthly),
    }
    source_quality = "local_billing_estimate_calculated"
    settlement = _modular_settlement_evidence(
        settlement_action="read_only_observed_state_no_settlement",
        source_quality=source_quality,
        provider="local_billing_estimator",
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "estimate_cost",
            "node_count": node_count,
            "monthly_cost_present": True,
        },
        local_lifecycle_allowed=False,
        read_only_observation_allowed=True,
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_ESTIMATE_SOURCE_AGENT,
        operation="estimate_cost",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=True,
        control_action=False,
        priority=4,
        extra={
            "node_count": node_count,
            "node_type": str(node_type or "")[:64],
            "plan": str(plan or "")[:64],
            "region": str(region or "")[:64],
            "result_summary": {
                "hourly_cost_present": True,
                "monthly_cost_present": True,
                "payloads_redacted": True,
            },
        },
    )
    return response


@router.get("/billing/limits", summary="Get billing limits")
async def get_limits(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return plan limits for the current modular MaaS user."""
    started = time.monotonic()
    plan = user.plan or "starter"
    limits = get_billing_service().get_plan_limits(plan)
    source_quality = "local_plan_limits_observed_state"
    settlement = _modular_settlement_evidence(
        settlement_action="read_only_observed_state_no_settlement",
        source_quality=source_quality,
        provider="local_billing_catalog",
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "get_limits",
            "plan_after": limits.get("plan"),
        },
        local_lifecycle_allowed=False,
        read_only_observation_allowed=True,
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
        operation="get_limits",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=True,
        control_action=False,
        priority=4,
        extra={
            "actor_user_id_hash": _redacted_sha256_prefix(user.user_id),
            "actor_plan": str(plan)[:64],
            "result_summary": {
                "plan": limits.get("plan"),
                "max_nodes_present": "max_nodes" in limits,
                "max_meshes_present": "max_meshes" in limits,
                "payloads_redacted": True,
            },
        },
    )
    return limits


@router.post("/billing/pay", summary="Create payment intent")
async def create_payment(
    plan: str,
    request: Request,
    method: str = "stripe",
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a local payment-session intent without claiming settlement."""
    started = time.monotonic()
    service = get_billing_service()
    if method == "crypto":
        result = await service.create_crypto_payment_session(user.user_id, plan)
    else:
        result = await service.create_payment_session(user.user_id, plan)
        method = "stripe"
    source_quality = f"{method}_payment_session_intent_created"
    settlement = _modular_settlement_evidence(
        settlement_action="payment_session_intent_only",
        source_quality=source_quality,
        provider=method,
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "create_payment",
            "payment_url_present": bool(result.get("payment_url")),
            "session_id_present": bool(result.get("session_id")),
            "method": method,
            "plan": plan,
        },
        checkout_intent_allowed=True,
    )
    response = {
        "payment_url": result.get("payment_url"),
        "session_id": result.get("session_id"),
        "status": result.get("status"),
        "method": method,
        "plan": plan,
        "claim_gate": settlement["claim_gate"],
        "cross_plane_claim_gate": _modular_cross_plane_claim_gate("create_payment"),
        "claim_boundary": _MODULAR_BILLING_CLAIM_BOUNDARY,
    }
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PAYMENT_SOURCE_AGENT,
        operation="create_payment",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=False,
        control_action=True,
        extra={
            "actor_user_id_hash": _redacted_sha256_prefix(user.user_id),
            "plan": str(plan or "")[:64],
            "method": method,
            "provider": method,
            "payment_url_present": bool(result.get("payment_url")),
            "session_id_hash": _redacted_sha256_prefix(result.get("session_id")),
            "raw_payment_url_redacted": True,
            "raw_session_id_redacted": True,
            "result_summary": {
                "payment_url_present": bool(result.get("payment_url")),
                "session_id_present": bool(result.get("session_id")),
                "payloads_redacted": True,
            },
        },
    )
    return response


@router.get("/billing/usage/{mesh_id}", summary="Get modular billing usage")
async def get_usage_report(
    mesh_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return local usage counters with redacted evidence metadata."""
    started = time.monotonic()
    report = get_usage_service().get_usage_report(mesh_id)
    source_quality = "local_usage_report_observed_state"
    settlement = _modular_settlement_evidence(
        settlement_action="read_only_observed_state_no_settlement",
        source_quality=source_quality,
        provider="local_usage_metering",
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "get_usage_report",
            "requests_bucket": _usage_bucket(report.get("requests")),
        },
        local_lifecycle_allowed=False,
        read_only_observation_allowed=True,
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_USAGE_SOURCE_AGENT,
        operation="get_usage_report",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=True,
        control_action=False,
        priority=4,
        extra={
            "actor_user_id_hash": _redacted_sha256_prefix(user.user_id),
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "result_summary": {
                "requests_bucket": _usage_bucket(report.get("requests")),
                "bandwidth_bytes_bucket": _usage_bucket(report.get("bandwidth_bytes")),
                "storage_bytes_bucket": _usage_bucket(report.get("storage_bytes")),
                "report_time_present": bool(report.get("report_time")),
                "payloads_redacted": True,
            },
        },
    )
    return report


@router.post("/billing/invoices/{mesh_id}", summary="Create modular invoice")
async def create_invoice(
    mesh_id: str,
    request: Request,
    hours: float = Query(1.0, gt=0),
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate a local invoice object without claiming payment or revenue."""
    started = time.monotonic()
    from src.api.maas import auth as maas_auth
    from src.api.maas import registry as maas_registry

    await maas_auth.require_mesh_access(mesh_id, user)
    mesh = maas_registry.get_mesh(mesh_id)
    node_instances = getattr(mesh, "node_instances", {}) if mesh is not None else {}
    node_count = len(node_instances) if isinstance(node_instances, dict) else 0
    invoice = generate_invoice(
        customer_id=user.user_id,
        mesh_usage=[
            {
                "mesh_id": mesh_id,
                "node_count": max(node_count, 1),
                "node_type": "standard",
                "plan": getattr(mesh, "plan", user.plan or "starter"),
                "region": getattr(mesh, "region", "global"),
                "hours": hours,
            }
        ],
    ).to_dict()
    source_quality = "local_invoice_object_generated"
    settlement = _modular_settlement_evidence(
        settlement_action="invoice_generation_local_only",
        source_quality=source_quality,
        provider="local_invoice_generator",
        duration_ms=(time.monotonic() - started) * 1000,
        db_storage_backend="local_invoice_object_not_persisted",
        output_summary={
            "billing_stage": "create_invoice",
            "invoice_status_after": "generated_not_persisted",
            "invoice_id_present": bool(invoice.get("invoice_id")),
            "line_items_count": len(invoice.get("line_items") or []),
        },
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_INVOICE_SOURCE_AGENT,
        operation="create_invoice",
        status_text="success",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=False,
        control_action=True,
        extra={
            "actor_user_id_hash": _redacted_sha256_prefix(user.user_id),
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "invoice_id_hash": _redacted_sha256_prefix(invoice.get("invoice_id")),
            "node_count": node_count,
            "hours": float(hours),
            "result_summary": {
                "invoice_id_present": bool(invoice.get("invoice_id")),
                "line_items_count": len(invoice.get("line_items") or []),
                "total_present": bool(invoice.get("total")),
                "payloads_redacted": True,
            },
        },
    )
    return invoice

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
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
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

@router.post("/billing/webhook", include_in_schema=False)
@router.post("/webhook", include_in_schema=False)
async def billing_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(default=None, alias="X-Timestamp"),
    x_event_id: Optional[str] = Header(default=None, alias="X-Event-Id"),
    x_billing_webhook_secret: Optional[str] = Header(default=None),
    x_billing_timestamp: Optional[str] = Header(default=None),
    x_billing_signature: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Unified billing webhook handler with modular evidence publication."""
    started = time.monotonic()
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Try to parse as MaaS legacy webhook first.
    try:
        if "event_type" in payload and "email" in payload:
            # This looks like a MaaS legacy webhook used in integration tests
            from ..models import BillingWebhookRequest
            try:
                req = BillingWebhookRequest(**payload)
            except Exception as exc:
                # If required fields are missing (like event_id in some tests)
                raise HTTPException(status_code=400, detail=str(exc))

            return await maas_legacy_webhook(
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

    service = get_billing_service()
    signature = x_signature or ""
    timestamp = x_timestamp or ""
    event_id = x_event_id or str(payload.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")
    if not signature or not timestamp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    if not verify_webhook_with_timestamp(
        body,
        signature,
        timestamp,
        service.webhook_secret,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    event_type = str(payload.get("type") or payload.get("event_type") or "")
    event_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    result = await service.process_webhook(
        event_type=event_type,
        event_data=event_data,
        event_id=event_id,
        include_idempotency_metadata=True,
    )
    source_quality = "verified_billing_webhook_local_lifecycle"
    settlement = _modular_settlement_evidence(
        settlement_action="webhook_local_lifecycle_only",
        source_quality=source_quality,
        provider="provider_webhook",
        duration_ms=(time.monotonic() - started) * 1000,
        output_summary={
            "billing_stage": "billing_webhook",
            "signature_verified": True,
            "event_type_bucket": event_type[:80],
            "webhook_action": str(result.get("action", ""))[:80],
            "idempotent": result.get("_idempotent") is True,
        },
        db_write_attempted=True,
        db_write_committed=result.get("status") == "processed",
        webhook_lifecycle_allowed=True,
    )
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
        operation="billing_webhook",
        status_text="success" if result.get("status") == "processed" else "ignored",
        started=started,
        source_quality=source_quality,
        settlement_evidence=settlement,
        read_only=False,
        control_action=True,
        extra={
            "signature_verified": True,
            "event_type_bucket": event_type[:80],
            "event_id_hash": _redacted_sha256_prefix(event_id),
            "result_status": str(result.get("status", ""))[:80],
            "result_action": str(result.get("action", ""))[:80],
            "raw_event_payload_redacted": True,
            "result_summary": {
                "status": str(result.get("status", ""))[:80],
                "action": str(result.get("action", ""))[:80],
                "idempotent": result.get("_idempotent") is True,
                "payloads_redacted": True,
            },
        },
    )
    return result


@router.post("/webhook/stripe", summary="Stripe webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
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
) -> Dict[str, Any]:
    """Return usage reports for the current user."""
    meshes = [
        mesh
        for mesh in get_all_meshes().values()
        if str(getattr(mesh, "owner_id", "")) == str(user.user_id)
    ]
    mesh_summaries = []
    total_node_hours = 0.0
    for mesh in meshes:
        usage = get_usage_service()._get_mesh_usage(mesh.mesh_id, db=db)
        total_node_hours += float(usage.get("total_node_hours") or 0.0)
        mesh_summaries.append(
            {
                "mesh_id": usage.get("mesh_id"),
                "mesh_name": getattr(mesh, "name", "Unnamed"),
                "status": usage.get("status"),
                "active_nodes": usage.get("active_nodes"),
                "total_node_hours": usage.get("total_node_hours"),
                "nodes": usage.get("nodes", []),
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
) -> Dict[str, Any]:
    """Return usage for a specific mesh."""
    mesh = get_mesh(mesh_id)
    if mesh is None or str(getattr(mesh, "owner_id", "")) != str(user.user_id):
        raise HTTPException(status_code=404, detail="Mesh not found")
    return get_usage_service()._get_mesh_usage(mesh_id, db=db)

@router.get("/limits", summary="Get plan limits")
async def get_plan_limits(
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return plan limits for the current user."""
    plan = user.plan or "starter"
    return PLAN_REQUEST_LIMITS.get(plan, PLAN_REQUEST_LIMITS["starter"])
