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
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from ..auth import UserContext, get_auth_service, get_current_user
from ..billing_helpers import (
    generate_invoice,
    verify_webhook_with_timestamp,
)
from ..constants import PLAN_REQUEST_LIMITS
from ..services import BillingService, UsageMeteringService
from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

router = APIRouter( tags=["billing"])

_MODULAR_BILLING_PAYMENT_SOURCE_AGENT = "maas-modular-billing-payment-intent"
_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT = "maas-modular-billing-webhook"
_MODULAR_BILLING_USAGE_SOURCE_AGENT = "maas-modular-billing-usage-read"
_MODULAR_BILLING_ESTIMATE_SOURCE_AGENT = "maas-modular-billing-estimate-read"
_MODULAR_BILLING_PLAN_SOURCE_AGENT = "maas-modular-billing-plan-read"
_MODULAR_BILLING_INVOICE_SOURCE_AGENT = "maas-modular-billing-invoice-generation"
_MODULAR_BILLING_PAYMENT_LAYER = "api_modular_billing_payment_intent"
_MODULAR_BILLING_WEBHOOK_LAYER = "api_modular_billing_webhook_lifecycle"
_MODULAR_BILLING_USAGE_LAYER = "api_modular_billing_usage_observed_state"
_MODULAR_BILLING_ESTIMATE_LAYER = "api_modular_billing_estimate_observed_state"
_MODULAR_BILLING_PLAN_LAYER = "api_modular_billing_plan_observed_state"
_MODULAR_BILLING_INVOICE_LAYER = "api_modular_billing_invoice_generation"
_MODULAR_BILLING_CLAIM_BOUNDARY = (
    "Modular MaaS billing evidence only. It records local payment-session "
    "intent creation, webhook signature verification, local BillingService "
    "processing result metadata, local usage/plan/estimate/invoice metadata, "
    "and bounded output shape; it does not prove live provider settlement, "
    "bank settlement, chain finality, crypto payment confirmation, "
    "subscription activation outside local state, invoice persistence, or that "
    "a returned payment URL was opened."
)
_MODULAR_BILLING_READ_OPERATIONS = frozenset(
    {"get_usage_report", "estimate_cost", "list_plans", "get_limits"}
)


# Service instances
_billing_service: Optional[BillingService] = None
_usage_service: Optional[UsageMeteringService] = None
_LEGACY_COMPAT_BILLING_EVENTS: Dict[str, Dict[str, Any]] = {}


def _modular_billing_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize modular MaaS billing EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _plan_bucket(plan: Any) -> str:
    text = str(plan or "").strip().lower()
    return text if text in {"free", "starter", "pro", "enterprise"} else "other"


def _method_bucket(method: Any) -> str:
    text = str(method or "").strip().lower()
    return text if text in {"stripe", "crypto"} else "other"


def _safe_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {
        "awaiting_payment",
        "created",
        "error",
        "access_denied",
        "ignored",
        "not_found",
        "processed",
        "requires_payment",
        "signature_rejected",
        "failed",
        "success",
    }:
        return text
    return "unknown" if not text else "other"


def _node_type_bucket(node_type: Any) -> str:
    text = str(node_type or "").strip().lower()
    return text if text in {"standard", "high_memory", "gpu", "quantum_safe"} else "other"


def _region_bucket(region: Any) -> str:
    text = str(region or "").strip().lower()
    return (
        text
        if text
        in {
            "us-east-1",
            "us-west-1",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
        }
        else "other"
    )


def _safe_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return min(int(value), 1_000_000_000)
    return None


def _safe_hours(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return round(float(value), 3)
    return None


def _usage_metric_bucket(value: Any) -> str | None:
    count = _safe_count(value)
    if count is None:
        return None
    if count == 0:
        return "zero"
    if count <= 10:
        return "low"
    if count <= 1_000:
        return "medium"
    return "high"


def _payment_session_summary(session: Any) -> Dict[str, Any]:
    if not isinstance(session, dict):
        return {
            "payload_type": type(session).__name__[:40],
            "payload_field_count": None,
            "session_id_present": False,
            "payment_url_present": False,
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(session),
        "session_id_present": bool(session.get("session_id")),
        "payment_url_present": bool(session.get("payment_url")),
        "status": _safe_status(session.get("status")),
        "deposit_address_present": bool(session.get("deposit_address")),
        "amount_usd_present": session.get("amount_usd") is not None,
        "network": str(session.get("network") or "")[:40] or None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _usage_report_summary(report: Any) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return {
            "payload_type": type(report).__name__[:40],
            "payload_field_count": None,
            "mesh_id_present": False,
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(report),
        "mesh_id_present": bool(report.get("mesh_id")),
        "requests_bucket": _usage_metric_bucket(report.get("requests")),
        "bandwidth_bucket": _usage_metric_bucket(report.get("bandwidth_bytes")),
        "storage_bucket": _usage_metric_bucket(report.get("storage_bytes")),
        "report_time_present": report.get("report_time") is not None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _estimate_summary(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "payload_type": type(result).__name__[:40],
            "payload_field_count": None,
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(result),
        "node_count": _safe_count(result.get("node_count")),
        "node_type": _node_type_bucket(result.get("node_type")),
        "plan": _plan_bucket(result.get("plan")),
        "region": _region_bucket(result.get("region")),
        "hourly_cost_present": result.get("hourly_cost") is not None,
        "monthly_cost_present": result.get("monthly_cost") is not None,
        "monthly_cost_raw_present": result.get("monthly_cost_raw") is not None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _plan_limits_summary(limits: Any) -> Dict[str, Any]:
    if not isinstance(limits, dict):
        return {
            "payload_type": type(limits).__name__[:40],
            "payload_field_count": None,
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(limits),
        "max_nodes_present": limits.get("max_nodes") is not None,
        "api_rate_limit_present": limits.get("api_rate_limit") is not None,
        "feature_keys_count": (
            len(limits.get("features")) if isinstance(limits.get("features"), list) else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _plans_summary(plans: Any) -> Dict[str, Any]:
    if not isinstance(plans, list):
        return {
            "payload_type": type(plans).__name__[:40],
            "payload_field_count": None,
            "plans_count": None,
        }
    names = [
        _plan_bucket(plan.get("name"))
        for plan in plans
        if isinstance(plan, dict)
    ]
    return {
        "payload_type": "list",
        "payload_field_count": len(plans),
        "plans_count": len(plans),
        "plan_buckets": sorted(set(names)),
        "limits_present_count": sum(
            1
            for plan in plans
            if isinstance(plan, dict) and isinstance(plan.get("limits"), dict)
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _invoice_summary(invoice: Any) -> Dict[str, Any]:
    if not isinstance(invoice, dict):
        return {
            "payload_type": type(invoice).__name__[:40],
            "payload_field_count": None,
        }
    line_items = invoice.get("line_items")
    return {
        "payload_type": "dict",
        "payload_field_count": len(invoice),
        "invoice_id_present": bool(invoice.get("invoice_id")),
        "customer_id_present": bool(invoice.get("customer_id")),
        "line_items_count": len(line_items) if isinstance(line_items, list) else None,
        "subtotal_present": invoice.get("subtotal") is not None,
        "tax_present": invoice.get("tax") is not None,
        "total_present": invoice.get("total") is not None,
        "currency": str(invoice.get("currency") or "")[:12] or None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _webhook_result_summary(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "payload_type": type(result).__name__[:40],
            "payload_field_count": None,
            "status": "unknown",
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(result),
        "status": _safe_status(result.get("status")),
        "action": str(result.get("action") or "")[:80] or None,
        "reason": str(result.get("reason") or result.get("error") or "")[:80] or None,
        "event_type": str(result.get("event_type") or "")[:80] or None,
        "idempotent": result.get("_idempotent") if isinstance(result.get("_idempotent"), bool) else None,
        "customer_id_present": bool(result.get("customer_id")),
        "user_id_present": bool(result.get("user_id")),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _modular_billing_source_quality(
    *,
    operation: str,
    status_value: str,
    method: str | None = None,
    signature_verified: bool | None = None,
) -> str:
    if operation == "create_payment":
        if status_value == "success" and method == "stripe":
            return "stripe_payment_session_intent_created"
        if status_value == "success" and method == "crypto":
            return "crypto_payment_intent_created"
        return "payment_session_intent_failed"
    if operation == "billing_webhook":
        if signature_verified is False:
            return "billing_webhook_signature_rejected"
        if status_value == "success":
            return "verified_billing_webhook_local_lifecycle"
        return "billing_webhook_local_processing_failed"
    if operation == "get_usage_report":
        if status_value == "success":
            return "local_usage_report_observed_state"
        if status_value in {"access_denied", "not_found"}:
            return "local_usage_access_check_rejected"
        return "local_usage_report_failed"
    if operation == "estimate_cost":
        return (
            "local_billing_estimate_calculated"
            if status_value == "success"
            else "local_billing_estimate_failed"
        )
    if operation == "list_plans":
        return (
            "local_plan_catalog_observed_state"
            if status_value == "success"
            else "local_plan_catalog_failed"
        )
    if operation == "get_limits":
        return (
            "local_plan_limits_observed_state"
            if status_value == "success"
            else "local_plan_limits_failed"
        )
    if operation == "create_invoice":
        if status_value == "success":
            return "local_invoice_object_generated"
        if status_value in {"access_denied", "not_found"}:
            return "local_invoice_access_or_mesh_check_rejected"
        return "local_invoice_generation_failed"
    return "modular_billing_local_event"


def _modular_billing_settlement_action(operation: str) -> str:
    if operation == "create_payment":
        return "payment_session_intent_only"
    if operation == "billing_webhook":
        return "webhook_local_lifecycle_only"
    if operation == "create_invoice":
        return "invoice_generation_local_only"
    if operation in _MODULAR_BILLING_READ_OPERATIONS:
        return "read_only_observed_state_no_settlement"
    return "local_billing_event_no_settlement"


def _modular_billing_settlement_evidence(
    *,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    provider: str,
    method: str | None = None,
    plan: str | None = None,
    http_status_code: int | None = None,
    signature_verified: bool | None = None,
    event_type: str | None = None,
    result_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result = result_summary or {}
    source_quality = _modular_billing_source_quality(
        operation=operation,
        status_value=status_value,
        method=method,
        signature_verified=signature_verified,
    )
    local_db_write_committed = bool(
        operation == "billing_webhook"
        and result.get("status") == "processed"
        and result.get("action") == "subscription_extended"
        and result.get("user_id_present") is True
    )
    db_storage_backend = (
        "billing_service_local_state"
        if operation == "billing_webhook"
        else (
            "local_invoice_object_not_persisted"
            if operation == "create_invoice"
            else "local_billing_read_or_calculation"
        )
    )
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "settlement_action": _modular_billing_settlement_action(operation),
        "duration_ms": round(duration_ms, 3),
        "dataplane_confirmed": False,
        "provider": provider,
        "payment_status": result.get("status"),
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
            "attempted": operation == "billing_webhook",
            "committed": local_db_write_committed,
            "payloads_redacted": True,
        },
        "output_summary": {
            "billing_stage": stage,
            "operation": operation,
            "status": status_value,
            "method": _method_bucket(method),
            "plan": _plan_bucket(plan),
            "http_status_code": http_status_code,
            "signature_verified": signature_verified,
            "event_type_bucket": str(event_type or "unknown")[:80],
            "payment_url_present": result.get("payment_url_present"),
            "session_id_present": result.get("session_id_present"),
            "webhook_action": result.get("action"),
            "webhook_result_status": result.get("status"),
            "idempotent": result.get("idempotent"),
            "node_count": result.get("node_count"),
            "node_type": result.get("node_type"),
            "region": result.get("region"),
            "hours": result.get("hours"),
            "mesh_id_present": result.get("mesh_id_present"),
            "invoice_id_present": result.get("invoice_id_present"),
            "customer_id_present": result.get("customer_id_present"),
            "line_items_count": result.get("line_items_count"),
            "plans_count": result.get("plans_count"),
            "limits_fields_count": result.get("payload_field_count"),
            "usage_report_fields_count": (
                result.get("payload_field_count")
                if operation == "get_usage_report"
                else None
            ),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_modular_billing_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status_value: str,
    duration_ms: float,
    provider: str,
    method: str | None = None,
    plan: str | None = None,
    user: UserContext | None = None,
    mesh_id: str | None = None,
    event_id: str | None = None,
    event_type_bucket: str | None = None,
    http_status_code: int | None = None,
    signature_verified: bool | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
    node_count: int | None = None,
    node_type: str | None = None,
    region: str | None = None,
    hours: float | None = None,
    read_only: bool = False,
    control_action: bool = True,
    event_type: EventType = EventType.PIPELINE_STAGE_END,
) -> str | None:
    event_bus = _modular_billing_event_bus_from_request(request)
    if event_bus is None:
        return None
    result = result_summary or {}
    settlement_evidence = _modular_billing_settlement_evidence(
        operation=operation,
        stage=stage,
        status_value=status_value,
        duration_ms=duration_ms,
        provider=provider,
        method=method,
        plan=plan,
        http_status_code=http_status_code,
        signature_verified=signature_verified,
        event_type=event_type_bucket,
        result_summary=result,
    )
    payload = {
        "component": "api.maas.endpoints.billing",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": status_value,
        "duration_ms": round(duration_ms, 3),
        "http_status_code": http_status_code,
        "provider": provider,
        "method": _method_bucket(method),
        "plan": _plan_bucket(plan),
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "user_id", None)),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "event_id_hash": _redacted_sha256_prefix(event_id),
        "event_type_bucket": str(event_type_bucket or "unknown")[:80],
        "signature_verified": signature_verified,
        "node_count": _safe_count(node_count),
        "node_type": _node_type_bucket(node_type),
        "region": _region_bucket(region),
        "hours": _safe_hours(hours),
        "result_summary": result,
        "source_quality": settlement_evidence["source_quality"],
        "settlement_evidence": settlement_evidence,
        "control_action": control_action,
        "economy_action": True,
        "read_only": read_only,
        "raw_identifiers_redacted": True,
        "raw_payment_url_redacted": True,
        "raw_session_id_redacted": True,
        "raw_event_payload_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _MODULAR_BILLING_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, source_agent, payload, priority=6)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS billing event: %s", exc)
        return None


def get_billing_service() -> BillingService:
    """Get or create the billing service."""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service


def get_usage_service() -> UsageMeteringService:
    """Get or create the usage metering service."""
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageMeteringService()
    return _usage_service


@router.post(
    "/pay",
    summary="Create payment session",
    description="Create a Stripe Checkout session or crypto payment intent.",
)
async def create_payment(
    plan: str = Query(..., pattern="^(pro|enterprise)$"),
    method: str = Query("stripe", pattern="^(stripe|crypto)$"),
    user: UserContext = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Create a payment session.
    
    Args:
        plan: Subscription plan (pro or enterprise)
        method: Payment method - 'stripe' for card payments, 'crypto' for blockchain
        user: Authenticated user context
        
    Returns:
        Payment session details including URL for checkout
    """
    billing = get_billing_service()
    started = time.monotonic()

    try:
        if method == "crypto":
            # Create crypto payment intent
            session = await billing.create_crypto_payment_session(user.user_id, plan)
        else:
            # Default: Create Stripe Checkout session
            session = await billing.create_payment_session(user.user_id, plan)
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_PAYMENT_SOURCE_AGENT,
            layer=_MODULAR_BILLING_PAYMENT_LAYER,
            stage="payment_session_create",
            operation="create_payment",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider=method,
            method=method,
            plan=plan,
            user=user,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "status": "failed",
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise

    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PAYMENT_SOURCE_AGENT,
        layer=_MODULAR_BILLING_PAYMENT_LAYER,
        stage="payment_session_create",
        operation="create_payment",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider=method,
        method=method,
        plan=plan,
        user=user,
        http_status_code=status.HTTP_200_OK,
        result_summary=_payment_session_summary(session),
        reason="payment_session_created",
    )
    
    return {
        "payment_url": session["payment_url"],
        "session_id": session["session_id"],
        "status": session["status"],
        "method": method,
        "plan": plan,
    }


def _legacy_billing_tolerance_seconds() -> int:
    raw = os.getenv("X0T_BILLING_WEBHOOK_TOLERANCE_SEC", "300").strip()
    try:
        value = int(raw)
    except ValueError:
        return 300
    return max(30, min(value, 3600))


def _verify_legacy_billing_secret(provided_secret: Optional[str]) -> None:
    expected_secret = os.getenv("X0T_BILLING_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        return
    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid billing webhook secret")


def _verify_legacy_billing_hmac(
    payload: bytes,
    timestamp_header: Optional[str],
    signature_header: Optional[str],
) -> None:
    secret = os.getenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", "").strip()
    if not secret:
        return
    if not timestamp_header or not signature_header:
        raise HTTPException(
            status_code=401,
            detail="Missing HMAC headers: X-Billing-Timestamp and X-Billing-Signature",
        )
    try:
        timestamp_value = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Billing-Timestamp") from exc
    if abs(int(time.time()) - timestamp_value) > _legacy_billing_tolerance_seconds():
        raise HTTPException(status_code=401, detail="Billing webhook timestamp expired")

    signed_payload = f"{timestamp_header}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid billing webhook signature")


def _is_legacy_billing_payload(data: Any) -> bool:
    return isinstance(data, dict) and (
        "event_type" in data
        or "event_id" in data
        or "customer_id" in data
        or "subscription_id" in data
    )


def _legacy_billing_event_id(data: Dict[str, Any]) -> str:
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    event_id = data.get("event_id") or metadata.get("event_id") or metadata.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise HTTPException(status_code=400, detail="event_id is required for idempotency")
    return event_id.strip()


def _legacy_billing_plan(value: Any, fallback: str = "starter") -> str:
    plan = str(value or fallback).strip().lower()
    return plan if plan in PLAN_REQUEST_LIMITS else fallback


def _process_legacy_compat_billing_webhook(
    *,
    body: bytes,
    data: Dict[str, Any],
    x_billing_webhook_secret: Optional[str],
    x_billing_timestamp: Optional[str],
    x_billing_signature: Optional[str],
) -> Dict[str, Any]:
    _verify_legacy_billing_secret(x_billing_webhook_secret)
    _verify_legacy_billing_hmac(body, x_billing_timestamp, x_billing_signature)

    event_id = _legacy_billing_event_id(data)
    event_type = str(data.get("event_type") or "").strip()
    payload_hash = hashlib.sha256(body).hexdigest()
    cached = _LEGACY_COMPAT_BILLING_EVENTS.get(event_id)
    if cached is not None:
        if cached.get("payload_hash") != payload_hash:
            raise HTTPException(
                status_code=409,
                detail="Billing webhook event_id payload mismatch",
            )
        response = dict(cached["response"])
        response["idempotent_replay"] = True
        return response

    email = data.get("email")
    user_id = data.get("user_id")
    from .auth import _normalize_email, _user_store

    matched_user_id = None
    user_data = None
    if isinstance(user_id, str) and user_id in _user_store:
        matched_user_id = user_id
        user_data = _user_store[user_id]
    elif isinstance(email, str):
        normalized_email = _normalize_email(email)
        for candidate_id, candidate_data in _user_store.items():
            if candidate_data.get("email") == normalized_email:
                matched_user_id = candidate_id
                user_data = candidate_data
                break

    if not matched_user_id or user_data is None:
        raise HTTPException(status_code=404, detail="Billing user not found")

    plan_before = _legacy_billing_plan(user_data.get("plan"))
    if event_type in {"subscription.canceled", "subscription.deleted"}:
        plan_after = "starter"
    else:
        plan_after = _legacy_billing_plan(data.get("plan"), plan_before)

    user_data["plan"] = plan_after
    if data.get("customer_id"):
        user_data["customer_id"] = data.get("customer_id")
    if data.get("subscription_id"):
        user_data["subscription_id"] = data.get("subscription_id")
    get_auth_service().update_user_plan(matched_user_id, plan_after)

    response = {
        "processed": True,
        "event_id": event_id,
        "event_type": event_type,
        "user_id": matched_user_id,
        "plan_before": plan_before,
        "plan_after": plan_after,
        "requests_limit": PLAN_REQUEST_LIMITS.get(plan_after, PLAN_REQUEST_LIMITS["starter"]),
        "idempotent_replay": False,
    }
    _LEGACY_COMPAT_BILLING_EVENTS[event_id] = {
        "payload_hash": payload_hash,
        "response": dict(response),
    }
    return response


def _node_started_at_hours(started_at: Any) -> float:
    if not isinstance(started_at, str) or not started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return 0.0
    return max(0.0, (datetime.utcnow() - started).total_seconds() / 3600.0)


def _mesh_node_hours_report(mesh_id: str) -> Optional[Dict[str, Any]]:
    from ..registry import get_mesh

    instance = get_mesh(mesh_id)
    if instance is None:
        return None

    nodes = []
    total_node_hours = 0.0
    for node_id, node in (getattr(instance, "node_instances", {}) or {}).items():
        if not isinstance(node, dict):
            continue
        hours = _node_started_at_hours(node.get("started_at"))
        total_node_hours += hours
        nodes.append({
            "node_id": node_id,
            "status": node.get("status", "unknown"),
            "node_hours": round(hours, 4),
        })

    return {
        "mesh_id": mesh_id,
        "active_nodes": len(nodes),
        "total_node_hours": round(total_node_hours, 4),
        "nodes": nodes,
    }


def _account_node_hours_report(owner_id: str) -> Dict[str, Any]:
    from ..registry import get_all_meshes

    meshes = []
    total_node_hours = 0.0
    for mesh_id, instance in get_all_meshes().items():
        if str(getattr(instance, "owner_id", "")) != str(owner_id):
            continue
        if getattr(instance, "status", "") == "terminated":
            continue
        report = _mesh_node_hours_report(mesh_id)
        if report is None:
            continue
        total_node_hours += float(report.get("total_node_hours") or 0.0)
        meshes.append({
            "mesh_id": mesh_id,
            "active_nodes": report["active_nodes"],
            "total_node_hours": report["total_node_hours"],
        })

    return {
        "owner_id": owner_id,
        "mesh_count": len(meshes),
        "total_node_hours": round(total_node_hours, 4),
        "meshes": meshes,
    }


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Handle billing webhook",
    description="Receive and process billing webhooks from payment provider.",
)
async def billing_webhook(
    request: Request,
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(default=None, alias="X-Timestamp"),
    x_event_id: Optional[str] = Header(default=None, alias="X-Event-Id"),
    x_billing_webhook_secret: Optional[str] = Header(
        default=None,
        alias="X-Billing-Webhook-Secret",
    ),
    x_billing_timestamp: Optional[str] = Header(
        default=None,
        alias="X-Billing-Timestamp",
    ),
    x_billing_signature: Optional[str] = Header(
        default=None,
        alias="X-Billing-Signature",
    ),
) -> Dict[str, Any]:
    """
    Handle billing webhook from payment provider.

    Verifies HMAC signature and processes the event idempotently.
    """
    billing = get_billing_service()
    started = time.monotonic()

    body = await request.body()
    try:
        data = await request.json()
    except Exception:
        data = None

    if _is_legacy_billing_payload(data):
        return _process_legacy_compat_billing_webhook(
            body=body,
            data=data,
            x_billing_webhook_secret=x_billing_webhook_secret,
            x_billing_timestamp=x_billing_timestamp,
            x_billing_signature=x_billing_signature,
        )

    if not x_signature or not x_timestamp or not x_event_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required webhook headers",
        )

    # Verify signature
    if not verify_webhook_with_timestamp(
        payload=body,
        signature=x_signature,
        timestamp=x_timestamp,
        secret=billing.webhook_secret,
    ):
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_MODULAR_BILLING_WEBHOOK_LAYER,
            stage="billing_webhook_receive",
            operation="billing_webhook",
            status_value="signature_rejected",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="provider_webhook",
            event_id=x_event_id,
            event_type_bucket="unknown",
            http_status_code=status.HTTP_401_UNAUTHORIZED,
            signature_verified=False,
            result_summary={
                "payload_type": "rejected",
                "payload_field_count": None,
                "status": "signature_rejected",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="invalid_signature",
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    if not isinstance(data, dict):
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_MODULAR_BILLING_WEBHOOK_LAYER,
            stage="billing_webhook_receive",
            operation="billing_webhook",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="provider_webhook",
            event_id=x_event_id,
            event_type_bucket="unknown",
            http_status_code=status.HTTP_400_BAD_REQUEST,
            signature_verified=True,
            result_summary={
                "payload_type": "invalid_json",
                "payload_field_count": None,
                "status": "failed",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="invalid_json",
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    event_type = data.get("type", "unknown")

    try:
        result = await billing.process_webhook(
            event_type=event_type,
            event_data=data.get("data", {}),
            event_id=x_event_id,
            include_idempotency_metadata=True,
        )
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_MODULAR_BILLING_WEBHOOK_LAYER,
            stage="billing_webhook_receive",
            operation="billing_webhook",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="provider_webhook",
            event_id=x_event_id,
            event_type_bucket=event_type,
            http_status_code=status.HTTP_200_OK,
            signature_verified=True,
            result_summary=_webhook_result_summary(result),
            reason="webhook_processed",
        )
        return result
    except HTTPException as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_MODULAR_BILLING_WEBHOOK_LAYER,
            stage="billing_webhook_receive",
            operation="billing_webhook",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="provider_webhook",
            event_id=x_event_id,
            event_type_bucket=event_type,
            http_status_code=exc.status_code,
            signature_verified=True,
            result_summary={
                "payload_type": "http_error",
                "payload_field_count": None,
                "status": "failed",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_MODULAR_BILLING_WEBHOOK_LAYER,
            stage="billing_webhook_receive",
            operation="billing_webhook",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="provider_webhook",
            event_id=x_event_id,
            event_type_bucket=event_type,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            signature_verified=True,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "status": "failed",
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal billing webhook error",
        )


@router.get(
    "/usage",
    summary="Get account usage report",
    description="Get node-hour usage metrics for the authenticated account.",
)
async def get_account_usage_report(
    user: UserContext = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """Get account-level node-hour usage for modular MaaS meshes."""
    started = time.monotonic()
    report = _account_node_hours_report(user.user_id)
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_USAGE_SOURCE_AGENT,
        layer=_MODULAR_BILLING_USAGE_LAYER,
        stage="account_usage_report_read",
        operation="get_usage_report",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_usage_metering",
        user=user,
        http_status_code=status.HTTP_200_OK,
        result_summary={
            "payload_type": "dict",
            "payload_field_count": len(report),
            "mesh_count": report["mesh_count"],
            "total_node_hours_present": True,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="account_usage_report_read",
        read_only=True,
        control_action=False,
    )
    return report


@router.get(
    "/usage/{mesh_id}",
    summary="Get usage report",
    description="Get usage metrics for a mesh.",
)
async def get_usage_report(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """Get usage report for a mesh."""
    from ..auth import require_mesh_access

    started = time.monotonic()

    try:
        # Check access
        await require_mesh_access(mesh_id, user)
    except HTTPException as exc:
        status_value = (
            "not_found"
            if exc.status_code == status.HTTP_404_NOT_FOUND
            else "access_denied"
        )
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_USAGE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_USAGE_LAYER,
            stage="usage_report_access_check",
            operation="get_usage_report",
            status_value=status_value,
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_usage_metering",
            user=user,
            mesh_id=mesh_id,
            http_status_code=exc.status_code,
            result_summary={
                "payload_type": "access_check",
                "payload_field_count": None,
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=status_value,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    usage = get_usage_service()
    try:
        report = usage.get_usage_report(mesh_id)
        node_hours_report = _mesh_node_hours_report(mesh_id)
        if node_hours_report:
            report.update(node_hours_report)
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_USAGE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_USAGE_LAYER,
            stage="usage_report_read",
            operation="get_usage_report",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_usage_metering",
            user=user,
            mesh_id=mesh_id,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "mesh_id_present": bool(mesh_id),
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_FAILED,
        )
        raise

    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_USAGE_SOURCE_AGENT,
        layer=_MODULAR_BILLING_USAGE_LAYER,
        stage="usage_report_read",
        operation="get_usage_report",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_usage_metering",
        user=user,
        mesh_id=mesh_id,
        http_status_code=status.HTTP_200_OK,
        result_summary=_usage_report_summary(report),
        reason="usage_report_read",
        read_only=True,
        control_action=False,
    )
    return report


@router.get(
    "/estimate",
    summary="Estimate monthly cost",
    description="Estimate monthly cost for a mesh configuration.",
)
async def estimate_cost(
    node_count: int = Query(..., ge=1, le=1000),
    node_type: str = Query("standard", description="Node type"),
    plan: str = Query("pro", description="Subscription plan"),
    region: str = Query("us-east-1", description="Deployment region"),
    request: Request = None,
) -> Dict[str, Any]:
    """Estimate monthly cost for a mesh configuration."""
    from ..billing_helpers import (
        calculate_mesh_cost,
        estimate_monthly_cost,
        format_currency,
    )

    started = time.monotonic()
    try:
        monthly = estimate_monthly_cost(node_count, node_type, plan, region)
        hourly = calculate_mesh_cost(node_count, node_type, plan, region, 1)
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_ESTIMATE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_ESTIMATE_LAYER,
            stage="estimate_calculate",
            operation="estimate_cost",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_billing_calculator",
            plan=plan,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "node_count": _safe_count(node_count),
                "node_type": _node_type_bucket(node_type),
                "region": _region_bucket(region),
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            node_count=node_count,
            node_type=node_type,
            region=region,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_FAILED,
        )
        raise

    result = {
        "node_count": node_count,
        "node_type": node_type,
        "plan": plan,
        "region": region,
        "hourly_cost": format_currency(hourly),
        "monthly_cost": format_currency(monthly),
        "monthly_cost_raw": str(monthly),
    }
    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_ESTIMATE_SOURCE_AGENT,
        layer=_MODULAR_BILLING_ESTIMATE_LAYER,
        stage="estimate_calculate",
        operation="estimate_cost",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_billing_calculator",
        plan=plan,
        http_status_code=status.HTTP_200_OK,
        result_summary=_estimate_summary(result),
        reason="estimate_calculated",
        node_count=node_count,
        node_type=node_type,
        region=region,
        read_only=True,
        control_action=False,
    )
    return result


@router.get(
    "/plans",
    summary="List available plans",
    description="Get available subscription plans and their limits.",
)
async def list_plans(request: Request = None) -> List[Dict[str, Any]]:
    """List available subscription plans."""

    started = time.monotonic()
    plans = []
    try:
        for plan_name in ["free", "pro", "enterprise"]:
            billing = get_billing_service()
            limits = billing.get_plan_limits(plan_name)

            plans.append({
                "name": plan_name,
                "display_name": plan_name.title(),
                "limits": limits,
            })
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
            layer=_MODULAR_BILLING_PLAN_LAYER,
            stage="plan_catalog_read",
            operation="list_plans",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_plan_catalog",
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "plans_count": len(plans),
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_FAILED,
        )
        raise

    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
        layer=_MODULAR_BILLING_PLAN_LAYER,
        stage="plan_catalog_read",
        operation="list_plans",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_plan_catalog",
        http_status_code=status.HTTP_200_OK,
        result_summary=_plans_summary(plans),
        reason="plan_catalog_read",
        read_only=True,
        control_action=False,
    )
    return plans


@router.post(
    "/invoice/{mesh_id}",
    summary="Generate invoice",
    description="Generate an invoice for mesh usage.",
)
async def create_invoice(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    hours: float = Query(730, description="Billing period in hours"),
    request: Request = None,
) -> Dict[str, Any]:
    """Generate an invoice for mesh usage."""
    from ..auth import require_mesh_access
    from ..registry import get_mesh

    started = time.monotonic()

    try:
        # Check access
        await require_mesh_access(mesh_id, user)
    except HTTPException as exc:
        status_value = (
            "not_found"
            if exc.status_code == status.HTTP_404_NOT_FOUND
            else "access_denied"
        )
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_INVOICE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_INVOICE_LAYER,
            stage="invoice_access_check",
            operation="create_invoice",
            status_value=status_value,
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_invoice_generator",
            plan=getattr(user, "plan", None),
            user=user,
            mesh_id=mesh_id,
            http_status_code=exc.status_code,
            result_summary={
                "payload_type": "access_check",
                "payload_field_count": None,
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=status_value,
            hours=hours,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    instance = get_mesh(mesh_id)
    if not instance:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_INVOICE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_INVOICE_LAYER,
            stage="invoice_mesh_lookup",
            operation="create_invoice",
            status_value="not_found",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_invoice_generator",
            plan=getattr(user, "plan", None),
            user=user,
            mesh_id=mesh_id,
            http_status_code=status.HTTP_404_NOT_FOUND,
            result_summary={
                "payload_type": "mesh_lookup",
                "payload_field_count": None,
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="mesh_not_found",
            hours=hours,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    # Generate invoice
    node_count = len(instance.node_instances)
    try:
        invoice = generate_invoice(
            customer_id=user.user_id,
            mesh_usage=[{
                "mesh_id": mesh_id,
                "node_count": node_count,
                "node_type": "standard",  # Would come from instance config
                "plan": instance.plan,
                "region": instance.region,
                "hours": hours,
            }],
        )
        invoice_dict = invoice.to_dict()
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_INVOICE_SOURCE_AGENT,
            layer=_MODULAR_BILLING_INVOICE_LAYER,
            stage="invoice_generate",
            operation="create_invoice",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_invoice_generator",
            plan=instance.plan,
            user=user,
            mesh_id=mesh_id,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "mesh_id_present": bool(mesh_id),
                "node_count": _safe_count(node_count),
                "node_type": _node_type_bucket("standard"),
                "region": _region_bucket(instance.region),
                "hours": _safe_hours(hours),
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            node_count=node_count,
            node_type="standard",
            region=instance.region,
            hours=hours,
            event_type=EventType.TASK_FAILED,
        )
        raise

    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_INVOICE_SOURCE_AGENT,
        layer=_MODULAR_BILLING_INVOICE_LAYER,
        stage="invoice_generate",
        operation="create_invoice",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_invoice_generator",
        plan=instance.plan,
        user=user,
        mesh_id=mesh_id,
        http_status_code=status.HTTP_200_OK,
        result_summary={
            **_invoice_summary(invoice_dict),
            "mesh_id_present": bool(mesh_id),
            "node_count": _safe_count(node_count),
            "node_type": _node_type_bucket("standard"),
            "region": _region_bucket(instance.region),
            "hours": _safe_hours(hours),
        },
        reason="invoice_generated",
        node_count=node_count,
        node_type="standard",
        region=instance.region,
        hours=hours,
    )
    return invoice_dict


@router.get(
    "/limits",
    summary="Get plan limits",
    description="Get limits for the current user's plan.",
)
async def get_limits(
    user: UserContext = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """Get limits for the user's current plan."""
    billing = get_billing_service()
    started = time.monotonic()
    try:
        limits = billing.get_plan_limits(user.plan)
    except Exception as exc:
        _publish_modular_billing_event(
            request,
            source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
            layer=_MODULAR_BILLING_PLAN_LAYER,
            stage="plan_limits_read",
            operation="get_limits",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            provider="local_plan_catalog",
            plan=user.plan,
            user=user,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_FAILED,
        )
        raise

    _publish_modular_billing_event(
        request,
        source_agent=_MODULAR_BILLING_PLAN_SOURCE_AGENT,
        layer=_MODULAR_BILLING_PLAN_LAYER,
        stage="plan_limits_read",
        operation="get_limits",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        provider="local_plan_catalog",
        plan=user.plan,
        user=user,
        http_status_code=status.HTTP_200_OK,
        result_summary=_plan_limits_summary(limits),
        reason="plan_limits_read",
        read_only=True,
        control_action=False,
    )
    return limits


__all__ = ["router"]
