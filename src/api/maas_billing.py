"""
MaaS Automatic Invoicing (Production) — x0tta6bl4
================================================

SQLAlchemy-backed enterprise billing logic with Stripe integration.
"""

import logging
import os
import uuid
import asyncio
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.coordination.events import EventBus, EventType, get_event_bus
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
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
_SERVICE_AGENT = "maas-billing"
_INVOICE_SOURCE_AGENT = "maas-billing-invoice"
_CHECKOUT_SOURCE_AGENT = "maas-billing-checkout"
_CUSTOMER_PORTAL_SOURCE_AGENT = "maas-billing-customer-portal"
_HISTORY_SOURCE_AGENT = "maas-billing-history"
_MANUAL_PAYMENT_SOURCE_AGENT = "maas-billing-manual-payment"
_SUBSCRIPTION_CHECKOUT_SOURCE_AGENT = "maas-billing-subscription-checkout"
_SUBSCRIPTION_SYNC_SOURCE_AGENT = "maas-billing-subscription-sync"
_SUBSCRIPTION_WEBHOOK_SOURCE_AGENT = "maas-billing-subscription-webhook"
BILLING_WEBHOOK_CLAIM_BOUNDARY = (
    "Billing webhook event only. It records local Stripe webhook handling, "
    "database/audit state changes, and optional local X0T bridge intent; it does "
    "not prove live Stripe settlement, bank settlement, or on-chain finality."
)
BILLING_INVOICE_CLAIM_BOUNDARY = (
    "Billing invoice generation evidence only. It records local legacy usage "
    "metering input, computed invoice amount, and local database invoice write; "
    "it does not prove Stripe checkout completion, customer payment, bank "
    "settlement, or on-chain finality."
)
BILLING_CHECKOUT_CLAIM_BOUNDARY = (
    "Billing checkout intent evidence only. It records local invoice eligibility, "
    "a bounded Stripe Checkout session creation attempt, and local stripe_session_id "
    "persistence; it does not prove customer payment, webhook delivery, bank "
    "settlement, or on-chain finality."
)
BILLING_HISTORY_CLAIM_BOUNDARY = (
    "Billing invoice history observation only. It records a local read of invoice "
    "rows and bounded aggregate metadata for billing visibility; it does not "
    "prove customer payment, Stripe settlement, bank settlement, or on-chain "
    "finality."
)
BILLING_CUSTOMER_PORTAL_CLAIM_BOUNDARY = (
    "Billing customer portal intent evidence only. It records local customer "
    "eligibility and a bounded Stripe customer portal session creation attempt; "
    "it does not prove subscription changes, customer payment, bank settlement, "
    "webhook delivery, or on-chain finality."
)
BILLING_MANUAL_PAYMENT_CLAIM_BOUNDARY = (
    "Billing manual payment evidence only. It records a local mock/manual invoice "
    "status mutation in the database; it does not prove Stripe payment, customer "
    "funds movement, bank settlement, or on-chain finality."
)
BILLING_SUBSCRIPTION_CHECKOUT_CLAIM_BOUNDARY = (
    "Billing subscription checkout intent evidence only. It records local plan "
    "eligibility, bounded Stripe customer/session creation attempts, local "
    "customer-id persistence, and audit intent; it does not prove customer "
    "payment, webhook delivery, bank settlement, or on-chain finality."
)
BILLING_SUBSCRIPTION_SYNC_CLAIM_BOUNDARY = (
    "Billing subscription sync evidence only. It records a bounded Stripe "
    "subscription read and local user plan/subscription database mutation; it "
    "does not prove customer payment, bank settlement, webhook delivery, or "
    "on-chain finality."
)
BILLING_SUBSCRIPTION_WEBHOOK_CLAIM_BOUNDARY = (
    "Billing subscription webhook lifecycle evidence only. It records local "
    "handling of Stripe subscription updated/deleted webhooks, audit intent, "
    "and optional local user plan/subscription database mutation; it does not "
    "prove live Stripe settlement, customer payment, bank settlement, or "
    "on-chain finality."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

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
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
            ),
            surface="maas_billing_readiness",
        ),
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


def _redacted_sha256_prefix(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _invoice_usage_summary_for_evidence(usage: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(usage, dict):
        return {}
    nodes = usage.get("nodes") if isinstance(usage.get("nodes"), list) else []
    return {
        "total_node_hours": usage.get("total_node_hours"),
        "active_nodes": usage.get("active_nodes"),
        "node_entries": len(nodes),
        "billing_period_start_present": bool(usage.get("billing_period_start")),
        "billing_period_end_present": bool(usage.get("billing_period_end")),
    }


def _billing_settlement_evidence(
    *,
    decision_basis: str,
    source_quality: str,
    settlement_action: str,
    duration_ms: float = 0.0,
    provider: str = "local_billing",
    payment_status: Optional[Any] = None,
    db_write_attempted: bool = False,
    db_write_committed: bool = False,
    bridge_attempted: bool = False,
    bridge_status: Optional[str] = None,
    bridge_source_agent: Optional[str] = None,
    output_summary: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    safe_output = dict(output_summary or {})
    safe_output["raw_identifiers_redacted"] = True
    safe_output["payloads_redacted"] = True
    claim_gate = _billing_local_claim_gate(
        settlement_action=settlement_action,
        payment_status=payment_status,
        db_write_committed=db_write_committed,
    )
    return {
        "decision_basis": str(decision_basis or "")[:160],
        "source_quality": str(source_quality or "")[:80],
        "settlement_action": str(settlement_action or "")[:80],
        "duration_ms": round(duration_ms, 3),
        "dataplane_confirmed": False,
        "provider": str(provider or "")[:40],
        "payment_status": str(payment_status or "")[:80] or None,
        "live_provider_settlement_confirmed": False,
        "bank_settlement_confirmed": False,
        "chain_finality_confirmed": False,
        "bridge_evidence": {
            "attempted": bridge_attempted,
            "status": bridge_status or ("not_requested" if not bridge_attempted else "unknown"),
            "source_agent": bridge_source_agent,
            "payloads_redacted": True,
        },
        "db_write_evidence": {
            "storage_backend": "sqlalchemy",
            "attempted": db_write_attempted,
            "committed": db_write_committed,
            "payloads_redacted": True,
        },
        "output_summary": safe_output,
        "claim_gate": claim_gate,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _billing_local_claim_gate(
    *,
    settlement_action: str = "",
    payment_status: Optional[Any] = None,
    db_write_committed: bool = False,
) -> dict[str, Any]:
    action = str(settlement_action or "")
    status = str(payment_status or "")
    local_lifecycle_allowed = bool(db_write_committed or "local" in action or "subscription" in action)
    return {
        "present": True,
        "decision": "LOCAL_BILLING_ONLY",
        "local_billing_lifecycle_claim_allowed": local_lifecycle_allowed,
        "checkout_intent_claim_allowed": "checkout" in action or "intent" in action,
        "stripe_status_observation_claim_allowed": bool(status or "observation" in action),
        "webhook_lifecycle_claim_allowed": "webhook" in action,
        "payment_provider_settlement_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "customer_dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": [
            "provider_settlement_not_proven",
            "bank_settlement_not_proven",
            "customer_dataplane_delivery_not_proven",
            "traffic_delivery_not_proven",
            "production_readiness_not_proven",
        ],
        "claim_boundary": (
            "Billing claim gate allows only local billing lifecycle, checkout intent, "
            "webhook lifecycle, or Stripe status observation claims. It does not "
            "allow provider settlement, bank settlement, customer dataplane "
            "delivery, traffic delivery, external settlement finality, or "
            "production-readiness claims without separate proof."
        ),
        "redacted": True,
    }


def _billing_intent_response_claim_metadata(
    *,
    settlement_action: str,
    surface: str,
    claim_boundary: str,
    payment_status: Optional[Any] = None,
    db_write_committed: bool = False,
) -> dict[str, Any]:
    return {
        "claim_gate": _billing_local_claim_gate(
            settlement_action=settlement_action,
            payment_status=payment_status,
            db_write_committed=db_write_committed,
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
            ),
            surface=surface,
        ),
        "claim_boundary": claim_boundary,
    }


def _publish_billing_invoice_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    invoice_id: Optional[Any] = None,
    plan: Optional[str] = None,
    usage: Optional[dict[str, Any]] = None,
    subtotal_cents: Optional[int] = None,
    minimum_invoice_applied: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "generate_invoice",
        "service_name": _SERVICE_AGENT,
        "source_alias": _INVOICE_SOURCE_AGENT,
        "layer": "billing_invoice_generation",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "invoice_id_hash": _redacted_sha256_prefix(invoice_id),
        "plan": plan,
        "subtotal_cents": subtotal_cents,
        "currency": "USD",
        "minimum_invoice_applied": minimum_invoice_applied,
        "usage_source": "legacy_usage_metering_service",
        "usage_summary": _invoice_usage_summary_for_evidence(usage),
        "local_db_write": status == "success",
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="local_invoice_generation",
            source_quality="legacy_usage_metering_and_local_db",
            settlement_action="invoice_generation_only",
            duration_ms=duration_ms,
            db_write_attempted=status == "success",
            db_write_committed=status == "success",
            output_summary={
                "billing_stage": stage,
                "invoice_status_after": "issued" if status == "success" else None,
                "amount_total": subtotal_cents,
                "currency": "USD",
            },
        ),
        "claim_boundary": BILLING_INVOICE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _INVOICE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing invoice event: %s", exc)
        return None


def _publish_billing_checkout_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    invoice_id: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    stripe_session_id: Optional[Any] = None,
    invoice_status: Optional[str] = None,
    amount_total: Optional[int] = None,
    currency: Optional[str] = None,
    checkout_url_present: bool = False,
    stripe_configured: bool = False,
    local_db_write: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "create_checkout_session",
        "service_name": _SERVICE_AGENT,
        "source_alias": _CHECKOUT_SOURCE_AGENT,
        "layer": "billing_checkout_intent",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "invoice_id_hash": _redacted_sha256_prefix(invoice_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "stripe_session_id_hash": _redacted_sha256_prefix(stripe_session_id),
        "invoice_status": invoice_status,
        "amount_total": amount_total,
        "currency": currency,
        "provider": "stripe",
        "stripe_configured": stripe_configured,
        "checkout_url_present": checkout_url_present,
        "local_db_write": local_db_write,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="stripe_checkout_session_creation_attempt",
            source_quality=(
                "stripe_checkout_intent_created"
                if status == "success"
                else "local_preflight_or_stripe_call_failure"
            ),
            settlement_action="checkout_session_intent_only",
            duration_ms=duration_ms,
            provider="stripe",
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            output_summary={
                "billing_stage": stage,
                "invoice_status_after": invoice_status,
                "stripe_session_present": stripe_session_id is not None,
                "checkout_url_present": checkout_url_present,
                "amount_total": amount_total,
                "currency": currency,
            },
        ),
        "claim_boundary": BILLING_CHECKOUT_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _CHECKOUT_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing checkout event: %s", exc)
        return None


def _invoice_history_summary_for_evidence(invoices: list[Any]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    currencies: set[str] = set()
    total_amount_cents = 0
    with_stripe_session = 0
    for invoice in invoices:
        status = str(getattr(invoice, "status", "unknown") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        currency = getattr(invoice, "currency", None)
        if currency:
            currencies.add(str(currency).upper())
        amount = getattr(invoice, "total_amount", 0) or 0
        if isinstance(amount, (int, float)):
            total_amount_cents += int(amount)
        if getattr(invoice, "stripe_session_id", None):
            with_stripe_session += 1
    return {
        "invoice_count": len(invoices),
        "status_counts": status_counts,
        "currencies": sorted(currencies),
        "total_amount_cents": total_amount_cents,
        "with_stripe_session_count": with_stripe_session,
    }


def _publish_billing_history_event(
    request: Optional[Request],
    *,
    status: str,
    user_id: Optional[Any] = None,
    invoices: Optional[list[Any]] = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    safe_invoices = invoices or []
    payload = {
        "component": "api.maas_billing",
        "stage": "observed_state",
        "operation": "list_invoices",
        "service_name": _SERVICE_AGENT,
        "source_alias": _HISTORY_SOURCE_AGENT,
        "layer": "billing_history_observed_state",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "history_summary": _invoice_history_summary_for_evidence(safe_invoices),
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="local_invoice_history_read",
            source_quality="local_db_read_only",
            settlement_action="read_only_billing_observation",
            duration_ms=duration_ms,
            db_write_attempted=False,
            db_write_committed=False,
            output_summary={
                "billing_stage": "observed_state",
                "invoice_count": len(safe_invoices),
            },
        ),
        "claim_boundary": BILLING_HISTORY_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _HISTORY_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing history event: %s", exc)
        return None


def _publish_billing_customer_portal_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    stripe_customer_id: Optional[Any] = None,
    stripe_portal_session_id: Optional[Any] = None,
    portal_url_present: bool = False,
    stripe_configured: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "create_customer_portal",
        "service_name": _SERVICE_AGENT,
        "source_alias": _CUSTOMER_PORTAL_SOURCE_AGENT,
        "layer": "billing_customer_portal_intent",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "stripe_customer_id_hash": _redacted_sha256_prefix(stripe_customer_id),
        "stripe_portal_session_id_hash": _redacted_sha256_prefix(
            stripe_portal_session_id
        ),
        "provider": "stripe",
        "stripe_configured": stripe_configured,
        "portal_url_present": portal_url_present,
        "local_db_write": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="stripe_customer_portal_session_creation_attempt",
            source_quality=(
                "stripe_portal_intent_created"
                if status == "success"
                else "local_preflight_or_stripe_call_failure"
            ),
            settlement_action="customer_portal_intent_only",
            duration_ms=duration_ms,
            provider="stripe",
            db_write_attempted=False,
            db_write_committed=False,
            output_summary={
                "billing_stage": stage,
                "portal_url_present": portal_url_present,
                "stripe_portal_session_present": stripe_portal_session_id is not None,
            },
        ),
        "claim_boundary": BILLING_CUSTOMER_PORTAL_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _CUSTOMER_PORTAL_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing customer portal event: %s", exc)
        return None


def _publish_billing_manual_payment_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    invoice_id: Optional[Any] = None,
    mesh_id: Optional[Any] = None,
    invoice_status_before: Optional[str] = None,
    invoice_status_after: Optional[str] = None,
    amount_total: Optional[int] = None,
    currency: Optional[str] = None,
    local_db_write: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "pay_invoice_manual",
        "service_name": _SERVICE_AGENT,
        "source_alias": _MANUAL_PAYMENT_SOURCE_AGENT,
        "layer": "billing_manual_payment_mock",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "invoice_id_hash": _redacted_sha256_prefix(invoice_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "invoice_status_before": invoice_status_before,
        "invoice_status_after": invoice_status_after,
        "amount_total": amount_total,
        "currency": currency,
        "provider": "local_mock",
        "local_db_write": local_db_write,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="manual_local_invoice_status_mutation",
            source_quality="local_mock_payment_mutation",
            settlement_action="manual_status_mutation_only",
            duration_ms=duration_ms,
            provider="local_mock",
            payment_status=invoice_status_after,
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            output_summary={
                "billing_stage": stage,
                "invoice_status_before": invoice_status_before,
                "invoice_status_after": invoice_status_after,
                "amount_total": amount_total,
                "currency": currency,
            },
        ),
        "claim_boundary": BILLING_MANUAL_PAYMENT_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _MANUAL_PAYMENT_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing manual payment event: %s", exc)
        return None


def _publish_billing_subscription_checkout_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    stripe_customer_id: Optional[Any] = None,
    stripe_session_id: Optional[Any] = None,
    plan: Optional[str] = None,
    price_id: Optional[Any] = None,
    stripe_configured: bool = False,
    customer_created: bool = False,
    checkout_url_present: bool = False,
    local_db_write: bool = False,
    audit_recorded: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "create_subscription_session",
        "service_name": _SERVICE_AGENT,
        "source_alias": _SUBSCRIPTION_CHECKOUT_SOURCE_AGENT,
        "layer": "billing_subscription_checkout_intent",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "stripe_customer_id_hash": _redacted_sha256_prefix(stripe_customer_id),
        "stripe_session_id_hash": _redacted_sha256_prefix(stripe_session_id),
        "plan": plan,
        "price_id_hash": _redacted_sha256_prefix(price_id),
        "provider": "stripe",
        "stripe_configured": stripe_configured,
        "customer_created": customer_created,
        "checkout_url_present": checkout_url_present,
        "local_db_write": local_db_write,
        "audit_recorded": audit_recorded,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="stripe_subscription_checkout_session_creation_attempt",
            source_quality=(
                "stripe_subscription_checkout_intent_created"
                if status == "success"
                else "local_preflight_or_stripe_call_failure"
            ),
            settlement_action="subscription_checkout_intent_only",
            duration_ms=duration_ms,
            provider="stripe",
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            output_summary={
                "billing_stage": stage,
                "plan_after": plan,
                "customer_created": customer_created,
                "checkout_url_present": checkout_url_present,
                "stripe_session_present": stripe_session_id is not None,
                "audit_recorded": audit_recorded,
            },
        ),
        "claim_boundary": BILLING_SUBSCRIPTION_CHECKOUT_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SUBSCRIPTION_CHECKOUT_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing subscription checkout event: %s", exc)
        return None


def _publish_billing_subscription_sync_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    user_id: Optional[Any] = None,
    stripe_customer_id: Optional[Any] = None,
    stripe_subscription_id: Optional[Any] = None,
    plan_before: Optional[str] = None,
    plan_after: Optional[str] = None,
    subscription_status: Optional[str] = None,
    price_id: Optional[Any] = None,
    stripe_configured: bool = False,
    local_db_write: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "sync_subscription_with_stripe",
        "service_name": _SERVICE_AGENT,
        "source_alias": _SUBSCRIPTION_SYNC_SOURCE_AGENT,
        "layer": "billing_subscription_sync",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "stripe_customer_id_hash": _redacted_sha256_prefix(stripe_customer_id),
        "stripe_subscription_id_hash": _redacted_sha256_prefix(stripe_subscription_id),
        "plan_before": plan_before,
        "plan_after": plan_after,
        "subscription_status": subscription_status,
        "price_id_hash": _redacted_sha256_prefix(price_id),
        "provider": "stripe",
        "stripe_configured": stripe_configured,
        "local_db_write": local_db_write,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="bounded_stripe_subscription_read",
            source_quality=(
                "stripe_subscription_api_observation"
                if stripe_configured
                else "local_preflight_skipped"
            ),
            settlement_action="subscription_reconciliation_only",
            duration_ms=duration_ms,
            provider="stripe",
            payment_status=subscription_status,
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            output_summary={
                "billing_stage": stage,
                "plan_before": plan_before,
                "plan_after": plan_after,
                "subscription_status": subscription_status,
            },
        ),
        "claim_boundary": BILLING_SUBSCRIPTION_SYNC_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SUBSCRIPTION_SYNC_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing subscription sync event: %s", exc)
        return None


def _publish_billing_subscription_webhook_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    stripe_event_type: str,
    stripe_event_id: Optional[Any] = None,
    stripe_customer_id: Optional[Any] = None,
    stripe_subscription_id: Optional[Any] = None,
    user_id: Optional[Any] = None,
    plan_before: Optional[str] = None,
    plan_after: Optional[str] = None,
    subscription_status: Optional[str] = None,
    local_db_write: bool = False,
    audit_recorded: bool = False,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "stripe_subscription_webhook",
        "service_name": _SERVICE_AGENT,
        "source_alias": _SUBSCRIPTION_WEBHOOK_SOURCE_AGENT,
        "layer": "billing_subscription_webhook_lifecycle",
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "stripe_event_type": stripe_event_type,
        "stripe_event_id_hash": _redacted_sha256_prefix(stripe_event_id),
        "stripe_customer_id_hash": _redacted_sha256_prefix(stripe_customer_id),
        "stripe_subscription_id_hash": _redacted_sha256_prefix(
            stripe_subscription_id
        ),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "plan_before": plan_before,
        "plan_after": plan_after,
        "subscription_status": subscription_status,
        "provider": "stripe",
        "local_db_write": local_db_write,
        "audit_recorded": audit_recorded,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="stripe_subscription_lifecycle_webhook",
            source_quality="stripe_webhook_lifecycle_event",
            settlement_action="subscription_webhook_local_lifecycle_only",
            duration_ms=duration_ms,
            provider="stripe",
            payment_status=subscription_status,
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            output_summary={
                "billing_stage": stage,
                "plan_before": plan_before,
                "plan_after": plan_after,
                "subscription_status": subscription_status,
                "audit_recorded": audit_recorded,
            },
        ),
        "claim_boundary": BILLING_SUBSCRIPTION_WEBHOOK_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SUBSCRIPTION_WEBHOOK_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing subscription webhook event: %s", exc)
        return None


def _publish_billing_webhook_event(
    request: Optional[Request],
    event_type: EventType,
    *,
    stage: str,
    stripe_event_type: str,
    stripe_event_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    mode: Optional[str] = None,
    user_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    plan: Optional[str] = None,
    amount_total: Optional[int] = None,
    currency: Optional[str] = None,
    payment_status: Optional[str] = None,
    bridge_x0t_requested: bool = False,
    bridge_x0t_minted: bool = False,
    local_db_write: bool = False,
    duration_ms: float = 0.0,
    status: str = "success",
    reason: str = "",
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_billing",
        "stage": stage,
        "operation": "stripe_checkout_session_webhook",
        "service_name": _SERVICE_AGENT,
        "source_alias": _SERVICE_AGENT,
        "layer": "billing_webhook_to_commerce_bridge",
        "stripe_event_type": stripe_event_type,
        "stripe_event_id_hash": _redacted_sha256_prefix(stripe_event_id),
        "session_id_hash": _redacted_sha256_prefix(session_id),
        "session_id_present": bool(session_id),
        "stripe_customer_id_hash": _redacted_sha256_prefix(stripe_customer_id),
        "stripe_subscription_id_hash": _redacted_sha256_prefix(stripe_subscription_id),
        "mode": mode,
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "invoice_id_hash": _redacted_sha256_prefix(invoice_id),
        "plan": plan,
        "amount_total": amount_total,
        "currency": currency,
        "payment_status": str(payment_status or "")[:80] or None,
        "provider": "stripe",
        "bridge_x0t_requested": bridge_x0t_requested,
        "bridge_x0t_minted": bridge_x0t_minted,
        "local_db_write": local_db_write,
        "duration_ms": round(duration_ms, 3),
        "status": status,
        "reason": reason,
        "raw_identifiers_redacted": True,
        "settlement_evidence": _billing_settlement_evidence(
            decision_basis="stripe_checkout_webhook_local_handling",
            source_quality="stripe_webhook_event",
            settlement_action="webhook_local_mutation_only",
            duration_ms=duration_ms,
            provider="stripe",
            payment_status=payment_status,
            db_write_attempted=local_db_write,
            db_write_committed=local_db_write,
            bridge_attempted=bridge_x0t_requested,
            bridge_status=(
                "minted"
                if bridge_x0t_minted
                else ("requested_failed" if bridge_x0t_requested else "not_requested")
            ),
            bridge_source_agent="maas-billing" if bridge_x0t_requested else None,
            output_summary={
                "billing_stage": stage,
                "invoice_status_after": (
                    "paid"
                    if stage in {"subscription_activated", "invoice_paid"}
                    else None
                ),
                "plan_after": plan,
                "payment_status": str(payment_status or "")[:80] or None,
                "bridge_x0t_requested": bridge_x0t_requested,
                "bridge_x0t_minted": bridge_x0t_minted,
            },
        ),
        "claim_boundary": BILLING_WEBHOOK_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, _SERVICE_AGENT, payload, priority=6)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS billing webhook event: %s", exc)
        return None


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
    claim_gate: dict[str, Any] = Field(default_factory=dict)

@router.post("/subscriptions/checkout")
async def create_subscription_session(
    plan: str,
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for a subscription."""
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    stripe_customer_id = getattr(current_user, "stripe_customer_id", None)
    stripe_session_id = None
    checkout_url_present = False
    customer_created = False
    local_db_write = False
    audit_recorded = False

    # Validate plan and ensure price ID is configured
    if plan not in STRIPE_PLANS:
        _publish_billing_subscription_checkout_event(
            request,
            stage="plan_invalid",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Invalid plan selected",
        )
        raise HTTPException(status_code=400, detail="Invalid plan selected")

    price_id = STRIPE_PLANS.get(plan)
    if not price_id:
        _publish_billing_subscription_checkout_event(
            request,
            stage="plan_price_missing",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            plan=plan,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"Plan {plan} price not configured",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Plan '{plan}' price not configured. Set STRIPE_PRICE_{plan.upper()}"
        )

    if not STRIPE_SECRET_KEY:
        _publish_billing_subscription_checkout_event(
            request,
            stage="stripe_not_configured",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            plan=plan,
            price_id=price_id,
            stripe_configured=False,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Stripe not configured",
        )
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
            stripe_customer_id = customer.id
            customer_created = True
            local_db_write = True

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
        stripe_session_id = getattr(checkout_session, "id", None)
        checkout_url_present = bool(getattr(checkout_session, "url", None))

        record_audit_log(
            db, request, "SUBSCRIPTION_SESSION_CREATED",
            user_id=current_user.id,
            payload={"plan": plan},
            status_code=200
        )
        audit_recorded = True
        _publish_billing_subscription_checkout_event(
            request,
            stage="subscription_checkout_created",
            status="success",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_session_id=stripe_session_id,
            plan=plan,
            price_id=price_id,
            stripe_configured=True,
            customer_created=customer_created,
            checkout_url_present=checkout_url_present,
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )

        return {
            "url": checkout_session.url,
            **_billing_intent_response_claim_metadata(
                settlement_action="subscription_checkout_intent_only",
                surface="maas_billing.subscription_checkout",
                claim_boundary=BILLING_SUBSCRIPTION_CHECKOUT_CLAIM_BOUNDARY,
                db_write_committed=local_db_write,
            ),
        }
    except HTTPException as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_billing_subscription_checkout_event(
            request,
            stage="subscription_checkout_failed",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_session_id=stripe_session_id,
            plan=plan,
            price_id=price_id,
            stripe_configured=True,
            customer_created=customer_created,
            checkout_url_present=checkout_url_present,
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe subscription session: {e}")
        _publish_billing_subscription_checkout_event(
            request,
            stage="subscription_checkout_failed",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_session_id=stripe_session_id,
            plan=plan,
            price_id=price_id,
            stripe_configured=True,
            customer_created=customer_created,
            checkout_url_present=checkout_url_present,
            local_db_write=local_db_write,
            audit_recorded=audit_recorded,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="Payment gateway error")

@router.post("/customer-portal")
async def create_customer_portal(
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Create a link to the Stripe Customer Portal for subscription management."""
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    stripe_customer_id = getattr(current_user, "stripe_customer_id", None)

    if not current_user.stripe_customer_id:
        _publish_billing_customer_portal_event(
            request,
            stage="customer_missing",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="No billing history found",
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
        _publish_billing_customer_portal_event(
            request,
            stage="portal_session_created",
            status="success",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_portal_session_id=getattr(session, "id", None),
            portal_url_present=bool(getattr(session, "url", None)),
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
        return {
            "url": session.url,
            **_billing_intent_response_claim_metadata(
                settlement_action="customer_portal_intent_only",
                surface="maas_billing.customer_portal",
                claim_boundary=BILLING_CUSTOMER_PORTAL_CLAIM_BOUNDARY,
            ),
        }
    except HTTPException as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_billing_customer_portal_event(
            request,
            stage="portal_session_failed",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe portal session: {e}")
        _publish_billing_customer_portal_event(
            request,
            stage="portal_session_failed",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="Portal error")

async def sync_subscription_with_stripe(
    user: User,
    db: Session,
    request: Optional[Request] = None,
):
    """
    Directly query Stripe API to reconcile subscription status.
    Call this periodically or on critical user actions.
    """
    started = time.monotonic()
    user_id = getattr(user, "id", None)
    stripe_customer_id = getattr(user, "stripe_customer_id", None)
    plan_before = getattr(user, "plan", None)

    if not user.stripe_customer_id or not STRIPE_SECRET_KEY:
        _publish_billing_subscription_sync_event(
            request,
            stage="sync_skipped",
            status="skipped",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            plan_before=plan_before,
            plan_after=plan_before,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Stripe customer missing" if not stripe_customer_id else "Stripe not configured",
        )
        return

    try:
        def _get_subs():
            return stripe.Subscription.list(customer=user.stripe_customer_id, status="active", limit=1)

        subs = await _execute_stripe_call(_get_subs, request=request)
        if subs.data:
            stripe_sub = subs.data[0]
            # Map Stripe price ID back to local plan (inverse lookup)
            price_id = stripe_sub['items']['data'][0]['price']['id']
            plan_name = next((k for k, v in STRIPE_PLANS.items() if v == price_id), "free")
            stripe_subscription_id = getattr(stripe_sub, "id", None)
            if stripe_subscription_id is None and isinstance(stripe_sub, dict):
                stripe_subscription_id = stripe_sub.get("id")
            subscription_status = getattr(stripe_sub, "status", None)
            if subscription_status is None and isinstance(stripe_sub, dict):
                subscription_status = stripe_sub.get("status")
            
            user.plan = plan_name
            user.stripe_subscription_id = stripe_subscription_id
            stage = "subscription_synced"
        else:
            price_id = None
            stripe_subscription_id = None
            subscription_status = "none_active"
            user.plan = "free"
            user.stripe_subscription_id = None
            stage = "subscription_cleared"
        
        db.commit()
        _publish_billing_subscription_sync_event(
            request,
            stage=stage,
            status="success",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            plan_before=plan_before,
            plan_after=getattr(user, "plan", None),
            subscription_status=subscription_status,
            price_id=price_id,
            stripe_configured=True,
            local_db_write=True,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
    except Exception as e:
        reason = getattr(e, "detail", type(e).__name__)
        _publish_billing_subscription_sync_event(
            request,
            stage="subscription_sync_failed",
            status="failed",
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            plan_before=plan_before,
            plan_after=getattr(user, "plan", None),
            stripe_configured=True,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(e).__name__,
        )
        logger.error(f"Failed to sync subscription for user {user.id}: {e}")


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    request: Request,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Sync with Stripe then fetch current subscription status."""
    await sync_subscription_with_stripe(current_user, db, request=request)
    return SubscriptionResponse(
        id=current_user.stripe_subscription_id,
        plan=current_user.plan,
        status="active" if current_user.stripe_subscription_id else "free",
        current_period_end=None, # In production, sync from stripe_sub['current_period_end']
        cancel_at_period_end=False,
        claim_gate=_billing_local_claim_gate(
            settlement_action="subscription_status_observation_only",
            payment_status="active" if current_user.stripe_subscription_id else "free",
            db_write_committed=False,
        ),
    )

@router.post("/invoices/generate/{mesh_id}", response_model=InvoiceResponse)
async def generate_invoice(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    plan = getattr(current_user, "plan", None)
    usage: Optional[dict[str, Any]] = None
    invoice_id: Optional[str] = None
    subtotal_cents: Optional[int] = None
    minimum_invoice_applied = False

    try:
        instance = _get_mesh_or_404(mesh_id, user_id)
        usage = usage_metering_service.get_mesh_usage(instance)

        # Simple pricing: $0.01 per node-hour for starter, $0.05 for enterprise
        rate = 0.01 if plan != "enterprise" else 0.05
        usage_cents = int(usage["total_node_hours"] * rate * 100)

        # Minimum invoice amount for Stripe is $0.50
        minimum_invoice_applied = usage_cents < 50
        subtotal_cents = 50 if minimum_invoice_applied else usage_cents

        invoice_id = f"inv-{uuid.uuid4().hex[:8]}"
        new_inv = Invoice(
            id=invoice_id,
            user_id=user_id,
            mesh_id=mesh_id,
            total_amount=subtotal_cents,
            period_start=datetime.fromisoformat(usage["billing_period_start"]),
            period_end=datetime.fromisoformat(usage["billing_period_end"]),
            status="issued"
        )
        db.add(new_inv)
        db.commit()
        db.refresh(new_inv)

        _publish_billing_invoice_event(
            request,
            stage="invoice_generated",
            status="success",
            user_id=user_id,
            mesh_id=mesh_id,
            invoice_id=invoice_id,
            plan=plan,
            usage=usage,
            subtotal_cents=subtotal_cents,
            minimum_invoice_applied=minimum_invoice_applied,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )

        res = InvoiceResponse.model_validate(new_inv)
        res.total_amount = new_inv.total_amount / 100.0
        return res
    except Exception as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_billing_invoice_event(
            request,
            stage="invoice_generation_failed",
            status="failed",
            user_id=user_id,
            mesh_id=mesh_id,
            invoice_id=invoice_id,
            plan=plan,
            usage=usage,
            subtotal_cents=subtotal_cents,
            minimum_invoice_applied=minimum_invoice_applied,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise

@router.get("/invoices/history", response_model=List[InvoiceResponse])
async def list_invoices(
    request: Request,
    current_user: User = Depends(require_permission("billing:view")),
    db: Session = Depends(get_db)
):
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    history: list[Any] = []
    try:
        history = db.query(Invoice).filter(Invoice.user_id == user_id).all()
        results = []
        for inv in history:
            r = InvoiceResponse.model_validate(inv)
            r.total_amount = inv.total_amount / 100.0
            results.append(r)
        _publish_billing_history_event(
            request,
            status="success",
            user_id=user_id,
            invoices=history,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
        return results
    except Exception as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_billing_history_event(
            request,
            status="failed",
            user_id=user_id,
            invoices=history,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise

@router.get("/invoices/{invoice_id}/checkout")
async def create_checkout_session(
    invoice_id: str,
    request: Request,
    current_user: User = Depends(require_permission("billing:pay")),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for a specific invoice."""
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == user_id).first()
    if not inv:
        _publish_billing_checkout_event(
            request,
            stage="invoice_not_found",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Invoice not found",
        )
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if inv.status == "paid":
        _publish_billing_checkout_event(
            request,
            stage="invoice_already_paid",
            status="skipped",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            invoice_status=inv.status,
            amount_total=inv.total_amount,
            currency=inv.currency,
            stripe_configured=bool(STRIPE_SECRET_KEY),
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Invoice already paid",
        )
        return {
            "message": "Invoice already paid",
            "url": None,
            **_billing_intent_response_claim_metadata(
                settlement_action="invoice_paid_status_observation_only",
                payment_status=inv.status,
                surface="maas_billing.invoice_checkout",
                claim_boundary=BILLING_CHECKOUT_CLAIM_BOUNDARY,
            ),
        }

    if not STRIPE_SECRET_KEY:
        _publish_billing_checkout_event(
            request,
            stage="stripe_not_configured",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            invoice_status=inv.status,
            amount_total=inv.total_amount,
            currency=inv.currency,
            stripe_configured=False,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Stripe not configured",
        )
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
        _publish_billing_checkout_event(
            request,
            stage="checkout_session_created",
            status="success",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            stripe_session_id=getattr(checkout_session, "id", None),
            invoice_status=inv.status,
            amount_total=inv.total_amount,
            currency=inv.currency,
            checkout_url_present=bool(getattr(checkout_session, "url", None)),
            stripe_configured=True,
            local_db_write=True,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
        
        return {
            "url": checkout_session.url,
            **_billing_intent_response_claim_metadata(
                settlement_action="checkout_session_intent_only",
                surface="maas_billing.invoice_checkout",
                claim_boundary=BILLING_CHECKOUT_CLAIM_BOUNDARY,
                db_write_committed=True,
            ),
        }
    except HTTPException as exc:
        reason = getattr(exc, "detail", type(exc).__name__)
        _publish_billing_checkout_event(
            request,
            stage="checkout_session_failed",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            invoice_status=inv.status,
            amount_total=inv.total_amount,
            currency=inv.currency,
            stripe_configured=True,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=reason if isinstance(reason, str) else type(exc).__name__,
        )
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe checkout session: {e}")
        _publish_billing_checkout_event(
            request,
            stage="checkout_session_failed",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            invoice_status=inv.status,
            amount_total=inv.total_amount,
            currency=inv.currency,
            stripe_configured=True,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(e).__name__,
        )
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
    started = time.monotonic()

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
            _publish_billing_webhook_event(
                request,
                EventType.PIPELINE_STAGE_END,
                stage="payment_not_completed",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                session_id=session_id,
                stripe_customer_id=session.get("customer"),
                stripe_subscription_id=session.get("subscription"),
                mode=mode,
                invoice_id=metadata.get("invoice_id"),
                payment_status=payment_status,
                duration_ms=(time.monotonic() - started) * 1000.0,
                status="skipped",
                reason="payment_not_completed",
            )
            return {"status": "success", "skipped": "payment_not_completed"}
        if session_id:
            existing_paid = db.query(Invoice).filter(
                Invoice.stripe_session_id == session_id,
                Invoice.status == "paid",
            ).first()
            if existing_paid:
                logger.info("Skipping already processed checkout session %s", session_id)
                _publish_billing_webhook_event(
                    request,
                    EventType.PIPELINE_STAGE_END,
                    stage="idempotent_replay",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    stripe_customer_id=session.get("customer"),
                    stripe_subscription_id=session.get("subscription"),
                    mode=mode,
                    user_id=existing_paid.user_id,
                    invoice_id=existing_paid.id,
                    amount_total=session.get("amount_total"),
                    currency=str(session.get("currency", "")).upper() or None,
                    payment_status=payment_status,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    status="skipped",
                    reason="checkout_session_already_processed",
                )
                return {"status": "success", "idempotent": True}
        elif mode == 'subscription':
            logger.error("Missing checkout session id in webhook payload for subscription")
            _publish_billing_webhook_event(
                request,
                EventType.PIPELINE_STAGE_END,
                stage="missing_session_id",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                stripe_customer_id=session.get("customer"),
                stripe_subscription_id=session.get("subscription"),
                mode=mode,
                user_id=metadata.get("user_id"),
                plan=metadata.get("plan") if metadata.get("plan") in STRIPE_PLANS else None,
                amount_total=session.get("amount_total"),
                currency=str(session.get("currency", "")).upper() or None,
                payment_status=payment_status,
                duration_ms=(time.monotonic() - started) * 1000.0,
                status="failed",
                reason="missing_session_id",
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
                _publish_billing_webhook_event(
                    request,
                    EventType.PIPELINE_STAGE_END,
                    stage="user_not_found",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=session.get("subscription"),
                    mode=mode,
                    user_id=user_id,
                    plan=metadata.get("plan") if metadata.get("plan") in STRIPE_PLANS else None,
                    amount_total=session.get("amount_total"),
                    currency=str(session.get("currency", "")).upper() or None,
                    payment_status=payment_status,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    status="failed",
                    reason="user_not_found",
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
                _publish_billing_webhook_event(
                    request,
                    EventType.PIPELINE_STAGE_END,
                    stage="invalid_plan",
                    stripe_event_type=event_type,
                    stripe_event_id=stripe_event_id,
                    session_id=session_id,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    mode=mode,
                    user_id=user.id,
                    amount_total=session.get("amount_total"),
                    currency=str(session.get("currency", "")).upper() or None,
                    payment_status=payment_status,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    status="failed",
                    reason="invalid_plan_metadata",
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
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                mode=mode,
                user_id=user.id,
                invoice_id=new_invoice.id,
                plan=plan,
                amount_total=amount_total,
                currency=currency,
                payment_status=payment_status,
                bridge_x0t_requested=bridge_flag,
                bridge_x0t_minted=bridge_minted,
                local_db_write=True,
                duration_ms=(time.monotonic() - started) * 1000.0,
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
                            stripe_customer_id=session.get("customer"),
                            stripe_subscription_id=session.get("subscription"),
                            mode=mode,
                            user_id=inv.user_id,
                            invoice_id=invoice_id,
                            amount_total=session.get("amount_total"),
                            currency=str(session.get("currency", "")).upper() or None,
                            payment_status=payment_status,
                            local_db_write=True,
                            duration_ms=(time.monotonic() - started) * 1000.0,
                        )
                    else:
                        logger.info("Invoice %s already marked paid", invoice_id)
                        _publish_billing_webhook_event(
                            request,
                            EventType.PIPELINE_STAGE_END,
                            stage="idempotent_replay",
                            stripe_event_type=event_type,
                            stripe_event_id=stripe_event_id,
                            session_id=session_id,
                            mode=mode,
                            user_id=inv.user_id,
                            invoice_id=invoice_id,
                            amount_total=session.get("amount_total"),
                            currency=str(session.get("currency", "")).upper() or None,
                            payment_status=payment_status,
                            duration_ms=(time.monotonic() - started) * 1000.0,
                            status="skipped",
                            reason="invoice_already_paid",
                        )
                else:
                    logger.error("Invoice %s not found for webhook", invoice_id)
                    _publish_billing_webhook_event(
                        request,
                        EventType.PIPELINE_STAGE_END,
                        stage="invoice_not_found",
                        stripe_event_type=event_type,
                        stripe_event_id=stripe_event_id,
                        session_id=session_id,
                        mode=mode,
                        invoice_id=invoice_id,
                        amount_total=session.get("amount_total"),
                        currency=str(session.get("currency", "")).upper() or None,
                        payment_status=payment_status,
                        duration_ms=(time.monotonic() - started) * 1000.0,
                        status="failed",
                        reason="invoice_not_found",
                    )

    elif event_type == 'customer.subscription.updated':
        subscription = data_object
        customer_id = subscription.get('customer')
        status = subscription.get('status')
        subscription_id = subscription.get('id')
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
            _publish_billing_subscription_webhook_event(
                request,
                stage="subscription_updated",
                status="success",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                user_id=user.id,
                plan_before=user.plan,
                plan_after=user.plan,
                subscription_status=status,
                local_db_write=False,
                audit_recorded=True,
                duration_ms=(time.monotonic() - started) * 1000.0,
            )
        else:
            _publish_billing_subscription_webhook_event(
                request,
                stage="subscription_user_not_found",
                status="failed",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                subscription_status=status,
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="User not found for subscription update",
            )

    elif event_type == 'customer.subscription.deleted':
        subscription = data_object
        customer_id = subscription.get('customer')
        subscription_id = subscription.get('id')
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            plan_before = user.plan
            user.plan = "free"
            user.stripe_subscription_id = None
            db.commit()
            record_audit_log(
                db, request, "SUBSCRIPTION_CANCELLED",
                user_id=user.id,
                payload={"sub_id": subscription.get('id')},
                status_code=200
            )
            _publish_billing_subscription_webhook_event(
                request,
                stage="subscription_cancelled",
                status="success",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                user_id=user.id,
                plan_before=plan_before,
                plan_after=user.plan,
                subscription_status=subscription.get('status'),
                local_db_write=True,
                audit_recorded=True,
                duration_ms=(time.monotonic() - started) * 1000.0,
            )
        else:
            _publish_billing_subscription_webhook_event(
                request,
                stage="subscription_user_not_found",
                status="failed",
                stripe_event_type=event_type,
                stripe_event_id=stripe_event_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                subscription_status=subscription.get('status'),
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="User not found for subscription deletion",
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
    started = time.monotonic()
    user_id = getattr(current_user, "id", None)
    inv = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )
    if not inv:
        _publish_billing_manual_payment_event(
            request,
            stage="invoice_not_found",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="Invoice not found",
        )
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice_status_before = inv.status
    try:
        inv.status = "paid"
        db.commit()
    except Exception as exc:
        _publish_billing_manual_payment_event(
            request,
            stage="manual_payment_failed",
            status="failed",
            user_id=user_id,
            invoice_id=invoice_id,
            mesh_id=inv.mesh_id,
            invoice_status_before=invoice_status_before,
            invoice_status_after=getattr(inv, "status", None),
            amount_total=inv.total_amount,
            currency=inv.currency,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    _publish_billing_manual_payment_event(
        request,
        stage="manual_payment_recorded",
        status="success",
        user_id=user_id,
        invoice_id=invoice_id,
        mesh_id=inv.mesh_id,
        invoice_status_before=invoice_status_before,
        invoice_status_after=inv.status,
        amount_total=inv.total_amount,
        currency=inv.currency,
        local_db_write=True,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {"status": "paid", "invoice_id": invoice_id}
