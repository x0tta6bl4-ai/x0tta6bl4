import hashlib
import hmac
import importlib
import json
import logging
import os
import time
import uuid
import datetime
import threading
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


# Simplified import
try:
    from src.services.vpn_config_generator import generate_vless_link
except ImportError:
    generate_vless_link = None


from src.core.resilience.circuit_breaker import CircuitBreakerOpen, stripe_circuit
from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity_status
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import BillingWebhookEvent, Invoice, License, Payment, User, get_db
from src.services.xray_manager import XrayManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
limiter = Limiter(key_func=get_remote_address)

_BILLING_CONFIG_SOURCE_AGENT = "billing-api-config-read"
_BILLING_CHECKOUT_SOURCE_AGENT = "billing-api-checkout-session"
_BILLING_WEBHOOK_SOURCE_AGENT = "billing-api-stripe-webhook"
_BILLING_ORDER_STATUS_SOURCE_AGENT = "billing-api-order-status-read"
_BILLING_REVENUE_METRICS_SOURCE_AGENT = "billing-api-revenue-metrics-read"

_BILLING_CONFIG_LAYER = "api_billing_config_observed_state"
_BILLING_CHECKOUT_LAYER = "api_billing_checkout_intent"
_BILLING_WEBHOOK_LAYER = "api_billing_webhook_lifecycle"
_BILLING_ORDER_STATUS_LAYER = "api_billing_order_status_observed_state"
_BILLING_REVENUE_METRICS_LAYER = "api_billing_revenue_observed_state"

BILLING_API_EVENT_CLAIM_BOUNDARY = (
    "Commercial billing API evidence only. It records local route decisions, "
    "Stripe request/response metadata, idempotency/provisioning intent, and "
    "bounded aggregate billing state; it does not prove payment settlement, "
    "Stripe truth beyond the returned status code, VPN provisioning success, "
    "mesh provisioning success, or customer client installation."
)
BILLING_API_CLAIM_GATE_BOUNDARY = (
    "Billing claim gate allows local billing lifecycle, checkout-intent, webhook, "
    "or status-observation claims only. Stripe API responses, webhook handling, "
    "local DB writes, and VPN provisioning references do not prove provider "
    "settlement finality, bank settlement, customer dataplane delivery, customer "
    "client installation, or production readiness without separate proof."
)

_stripe_event_fallback_lock = threading.Lock()
_stripe_event_fallback: Dict[str, Dict[str, Any]] = {}

# Configuration for in-memory fallback limits
_FALLBACK_MAX_SIZE = int(os.getenv("STRIPE_FALLBACK_MAX_SIZE", "1000"))
_FALLBACK_TTL_SECONDS = int(os.getenv("STRIPE_FALLBACK_TTL_SECONDS", "3600"))


def _cleanup_stripe_fallback() -> None:
    """Remove expired entries from in-memory fallback cache."""
    global _stripe_event_fallback
    current_time = time.time()
    cutoff = current_time - _FALLBACK_TTL_SECONDS
    
    # Find expired entries
    expired_keys = [
        k for k, v in _stripe_event_fallback.items()
        if v.get("timestamp", 0) < cutoff
    ]
    
    for k in expired_keys:
        del _stripe_event_fallback[k]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired Stripe fallback entries")


def _evict_oldest_fallback_entries() -> None:
    """Evict oldest entries when max size is reached (LRU-style)."""
    global _stripe_event_fallback
    
    if len(_stripe_event_fallback) <= _FALLBACK_MAX_SIZE:
        return
    
    # Sort by timestamp and remove oldest 20%
    sorted_items = sorted(
        _stripe_event_fallback.items(),
        key=lambda x: x[1].get("timestamp", 0)
    )
    
    evict_count = max(1, len(sorted_items) // 5)
    for k, _ in sorted_items[:evict_count]:
        del _stripe_event_fallback[k]
    
    logger.info(f"Evicted {evict_count} oldest Stripe fallback entries (LRU)")


def _is_circuit_breaker_open_error(exc: Exception) -> bool:
    """Handle class-identity drift when circuit_breaker module is reloaded in tests."""
    return isinstance(exc, CircuitBreakerOpen) or exc.__class__.__name__ == "CircuitBreakerOpen"


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _billing_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    if state is None:
        return None
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize Billing API EventBus: %s", exc)
        return None


def _event_type_for_status(http_status_code: Optional[int]) -> EventType:
    if http_status_code is None or http_status_code < 400:
        return EventType.PIPELINE_STAGE_END
    if http_status_code >= 500:
        return EventType.TASK_FAILED
    return EventType.TASK_BLOCKED


def _billing_service_identity_summary(source_agent: str) -> Dict[str, Any]:
    try:
        return service_event_identity_status(service_name=source_agent)
    except Exception as exc:
        return {
            "service_name": source_agent,
            "configured_fields": 0,
            "complete": False,
            "redacted": True,
            "status": "unavailable",
            "error_type": exc.__class__.__name__,
        }


def _bounded_billing_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    allowed = {
        "active",
        "canceled",
        "created",
        "degraded",
        "failed",
        "not_paid",
        "paid",
        "processing",
        "ready",
        "received",
        "replayed",
        "verified",
    }
    if text in allowed:
        return text
    return "other"


def _billing_plan_bucket(plan: Any) -> str:
    text = str(plan or "").strip().lower()
    if text in {"free", "starter", "basic", "pro", "enterprise"}:
        return text
    if not text:
        return "unknown"
    return "custom_or_unknown"


def _billing_api_settlement_source_quality(
    *,
    source_agent: str,
    status_value: str,
    http_status_code: Optional[int],
    metadata: Dict[str, Any],
) -> str:
    if source_agent == _BILLING_CONFIG_SOURCE_AGENT:
        return "local_config_observation"
    if source_agent == _BILLING_REVENUE_METRICS_SOURCE_AGENT:
        return "local_db_aggregate_read"
    if source_agent == _BILLING_CHECKOUT_SOURCE_AGENT:
        if not metadata.get("stripe_call_attempted"):
            return "local_checkout_preflight"
        if http_status_code is not None and http_status_code < 400 and status_value == "created":
            return "stripe_checkout_session_api_response"
        return "stripe_checkout_session_api_error"
    if source_agent == _BILLING_WEBHOOK_SOURCE_AGENT:
        if not metadata.get("signature_verified"):
            return "local_webhook_preflight_or_rejected"
        if metadata.get("idempotency_cached_response"):
            return "stripe_webhook_idempotency_replay"
        return "verified_stripe_webhook_local_lifecycle"
    if source_agent == _BILLING_ORDER_STATUS_SOURCE_AGENT:
        if not metadata.get("stripe_call_attempted"):
            return "local_order_status_preflight"
        if http_status_code is not None and http_status_code < 400:
            return "stripe_checkout_session_status_read"
        return "stripe_checkout_session_status_error"
    return "local_billing_event"


def _billing_api_settlement_action(source_agent: str) -> str:
    if source_agent == _BILLING_CHECKOUT_SOURCE_AGENT:
        return "checkout_session_intent_only"
    if source_agent == _BILLING_WEBHOOK_SOURCE_AGENT:
        return "webhook_local_lifecycle_only"
    if source_agent == _BILLING_ORDER_STATUS_SOURCE_AGENT:
        return "order_status_observation_only"
    if source_agent == _BILLING_REVENUE_METRICS_SOURCE_AGENT:
        return "revenue_metrics_observation_only"
    if source_agent == _BILLING_CONFIG_SOURCE_AGENT:
        return "config_observation_only"
    return "billing_event_observation_only"


def _billing_api_provider(source_agent: str) -> str:
    if source_agent in {
        _BILLING_CHECKOUT_SOURCE_AGENT,
        _BILLING_WEBHOOK_SOURCE_AGENT,
        _BILLING_ORDER_STATUS_SOURCE_AGENT,
    }:
        return "stripe"
    if source_agent == _BILLING_REVENUE_METRICS_SOURCE_AGENT:
        return "local_db"
    if source_agent == _BILLING_CONFIG_SOURCE_AGENT:
        return "local_config"
    return "local_billing"


def _billing_api_claim_gate(
    *,
    source_agent: str,
    source_quality: str,
    http_status_code: Optional[int],
    metadata: Dict[str, Any],
    db_write_committed: bool,
) -> Dict[str, Any]:
    status_ok = http_status_code is not None and http_status_code < 400
    checkout_intent = bool(
        source_agent == _BILLING_CHECKOUT_SOURCE_AGENT
        and status_ok
        and metadata.get("stripe_call_attempted")
    )
    webhook_lifecycle = bool(
        source_agent == _BILLING_WEBHOOK_SOURCE_AGENT
        and metadata.get("signature_verified")
    )
    status_observation = bool(
        source_agent == _BILLING_ORDER_STATUS_SOURCE_AGENT
        and status_ok
        and metadata.get("stripe_call_attempted")
    )
    local_observation = source_agent in {
        _BILLING_CONFIG_SOURCE_AGENT,
        _BILLING_REVENUE_METRICS_SOURCE_AGENT,
    }
    local_billing_claim_allowed = bool(
        checkout_intent
        or webhook_lifecycle
        or status_observation
        or local_observation
        or db_write_committed
    )
    return {
        "decision": (
            "local_billing_lifecycle_only"
            if local_billing_claim_allowed
            else "blocked_or_unconfirmed_billing_lifecycle"
        ),
        "local_billing_lifecycle_claim_allowed": local_billing_claim_allowed,
        "checkout_intent_claim_allowed": checkout_intent,
        "webhook_lifecycle_claim_allowed": webhook_lifecycle,
        "stripe_status_observation_claim_allowed": status_observation,
        "payment_provider_settlement_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "customer_access_claim_allowed": False,
        "customer_dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_provider_settlement_evidence_for_payment_claim": True,
        "requires_bank_settlement_evidence_for_finality_claim": True,
        "requires_customer_dataplane_evidence_for_access_claim": True,
        "source_quality": source_quality,
        "vpn_provision_reference_present": bool(
            _billing_api_event_reference(
                metadata.get("vpn_provision_event_reference")
            ).get("available")
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": BILLING_API_CLAIM_GATE_BOUNDARY,
    }


def _billing_api_checkout_response_claim_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    source_quality = _billing_api_settlement_source_quality(
        source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
        status_value="created",
        http_status_code=200,
        metadata=metadata,
    )
    return {
        "claim_gate": _billing_api_claim_gate(
            source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
            source_quality=source_quality,
            http_status_code=200,
            metadata=metadata,
            db_write_committed=False,
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
            ),
            surface="billing_api.checkout_session",
        ),
        "claim_boundary": BILLING_API_CLAIM_GATE_BOUNDARY,
    }


def _billing_api_order_status_response_claim_metadata(
    *,
    status_value: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    source_quality = _billing_api_settlement_source_quality(
        source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
        status_value=status_value,
        http_status_code=200,
        metadata=metadata,
    )
    return {
        "claim_gate": _billing_api_claim_gate(
            source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
            source_quality=source_quality,
            http_status_code=200,
            metadata=metadata,
            db_write_committed=False,
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
            ),
            surface="billing_api.order_status",
        ),
        "claim_boundary": BILLING_API_CLAIM_GATE_BOUNDARY,
    }


def _billing_api_local_observation_response_claim_metadata(
    *,
    source_agent: str,
    surface: str,
    status_value: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    source_quality = _billing_api_settlement_source_quality(
        source_agent=source_agent,
        status_value=status_value,
        http_status_code=200,
        metadata=metadata,
    )
    return {
        "claim_gate": _billing_api_claim_gate(
            source_agent=source_agent,
            source_quality=source_quality,
            http_status_code=200,
            metadata=metadata,
            db_write_committed=False,
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
        "claim_boundary": BILLING_API_CLAIM_GATE_BOUNDARY,
    }


def _billing_api_webhook_response_claim_metadata(
    *,
    metadata: Dict[str, Any],
    status_value: str = "received",
) -> Dict[str, Any]:
    source_quality = _billing_api_settlement_source_quality(
        source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
        status_value=status_value,
        http_status_code=200,
        metadata=metadata,
    )
    return {
        "claim_gate": _billing_api_claim_gate(
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            source_quality=source_quality,
            http_status_code=200,
            metadata=metadata,
            db_write_committed=False,
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
            ),
            surface="billing_api.webhook",
        ),
        "claim_boundary": BILLING_API_CLAIM_GATE_BOUNDARY,
    }


def _billing_api_event_reference(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict) or not evidence:
        return {
            "available": False,
            "reason": "event_evidence_missing",
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    allowed = {
        "event_id",
        "source_agent",
        "layer",
        "operation",
        "stage",
        "status",
        "reason",
        "control_action",
        "claim_boundary",
    }
    reference = {
        key: evidence.get(key)
        for key in sorted(allowed)
        if key in evidence
    }
    reference.update(
        {
            "available": bool(reference.get("event_id")),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    )
    return reference


def _billing_api_settlement_evidence(
    *,
    source_agent: str,
    stage: str,
    operation: str,
    status_value: str,
    http_status_code: Optional[int],
    duration_ms: float,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    source_quality = _billing_api_settlement_source_quality(
        source_agent=source_agent,
        status_value=status_value,
        http_status_code=http_status_code,
        metadata=metadata,
    )
    db_write_attempted = bool(
        metadata.get("idempotency_reservation_attempted")
        or metadata.get("db_user_created")
        or metadata.get("license_created")
        or metadata.get("finalize_attempted")
        or metadata.get("subscription_revocation_attempted")
        or metadata.get("local_user_plan_write_committed")
    )
    db_write_committed = bool(
        metadata.get("license_created")
        or metadata.get("local_user_plan_write_committed")
    )
    output_summary = {
        "billing_stage": str(stage or "")[:80],
        "operation": str(operation or "")[:80],
        "status": str(status_value or "")[:40],
        "http_status_code": http_status_code,
        "stripe_http_status": metadata.get("stripe_http_status"),
        "stripe_call_attempted": metadata.get("stripe_call_attempted"),
        "signature_verified": metadata.get("signature_verified"),
        "idempotency_cached_response": metadata.get("idempotency_cached_response"),
        "event_type_bucket": metadata.get("event_type_bucket"),
        "payment_status_bucket": metadata.get("payment_status_bucket"),
        "checkout_url_present": metadata.get("checkout_url_present"),
        "vless_link_present": metadata.get("vless_link_present"),
        "db_user_found": metadata.get("db_user_found"),
        "db_user_created": metadata.get("db_user_created"),
        "license_created": metadata.get("license_created"),
        "vpn_provision_attempted": metadata.get("vpn_provision_attempted"),
        "vpn_provision_success": metadata.get("vpn_provision_success"),
        "mesh_provision_attempted": metadata.get("mesh_provision_attempted"),
        "mesh_provision_success": metadata.get("mesh_provision_success"),
        "subscription_revocation_attempted": metadata.get(
            "subscription_revocation_attempted"
        ),
        "subscription_revocation_success": metadata.get(
            "subscription_revocation_success"
        ),
        "vpn_provision_evidence": _billing_api_event_reference(
            metadata.get("vpn_provision_event_reference")
        ),
        "processing_failed": metadata.get("processing_failed"),
        "total_verified_payments": metadata.get("total_verified_payments"),
        "total_paid_invoices": metadata.get("total_paid_invoices"),
        "active_paying_users": metadata.get("active_paying_users"),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "settlement_action": _billing_api_settlement_action(source_agent),
        "duration_ms": round(duration_ms, 3),
        "dataplane_confirmed": False,
        "provider": _billing_api_provider(source_agent),
        "payment_status": metadata.get("payment_status_bucket"),
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
            "storage_backend": "sqlalchemy",
            "attempted": db_write_attempted,
            "committed": db_write_committed,
            "payloads_redacted": True,
        },
        "output_summary": output_summary,
        "claim_gate": _billing_api_claim_gate(
            source_agent=source_agent,
            source_quality=source_quality,
            http_status_code=http_status_code,
            metadata=metadata,
            db_write_committed=db_write_committed,
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_billing_api_event(
    request: Optional[Request],
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status_value: str,
    http_status_code: Optional[int],
    duration_ms: float,
    read_only: bool = False,
    observed_state: bool = False,
    control_action: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    event_type: Optional[EventType] = None,
    priority: int = 5,
) -> Optional[str]:
    event_bus = _billing_event_bus_from_request(request)
    if event_bus is None:
        return None
    payload: Dict[str, Any] = {
        "component": "api.billing",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status_value or "")[:40],
        "duration_ms": round(duration_ms, 3),
        "http_status_code": http_status_code,
        "service_identity": _billing_service_identity_summary(source_agent),
        "read_only": read_only,
        "observed_state": observed_state,
        "control_action": control_action,
        "raw_email_redacted": True,
        "raw_stripe_ids_redacted": True,
        "raw_stripe_secret_redacted": True,
        "raw_vpn_link_redacted": True,
        "claim_boundary": BILLING_API_EVENT_CLAIM_BOUNDARY,
    }
    if metadata:
        payload.update(metadata)
    payload.setdefault(
        "settlement_evidence",
        _billing_api_settlement_evidence(
            source_agent=source_agent,
            stage=stage,
            operation=operation,
            status_value=status_value,
            http_status_code=http_status_code,
            duration_ms=duration_ms,
            metadata=payload,
        ),
    )
    payload.setdefault("source_quality", payload["settlement_evidence"]["source_quality"])
    try:
        event = event_bus.publish(
            event_type or _event_type_for_status(http_status_code),
            source_agent,
            payload,
            priority=priority,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish Billing API event: %s", exc)
        return None


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


# Module-level reference — allows tests to patch `src.api.billing.mesh_provisioner`
mesh_provisioner = _resolve_mesh_provisioner()


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


def _billing_api_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit", "rollback"))


def _billing_api_stripe_checkout_config_available() -> bool:
    return bool(_get_env("STRIPE_SECRET_KEY") and _get_env("STRIPE_PRICE_ID"))


def _billing_api_stripe_webhook_config_available() -> bool:
    return bool(_get_env("STRIPE_WEBHOOK_SECRET"))


def _billing_api_stripe_transport_available() -> bool:
    return callable(getattr(httpx, "AsyncClient", None)) and callable(
        getattr(stripe_circuit, "call", None)
    )


def _billing_api_models_available() -> bool:
    required_model_attrs = (
        (
            BillingWebhookEvent,
            (
                "event_id",
                "event_type",
                "payload_hash",
                "status",
                "response_json",
                "created_at",
            ),
        ),
        (
            User,
            (
                "email",
                "plan",
                "vpn_uuid",
                "stripe_customer_id",
                "stripe_subscription_id",
            ),
        ),
        (License, ("token", "user_id", "tier", "is_active")),
        (Payment, ("status", "amount")),
        (Invoice, ("status", "total_amount")),
    )
    return all(
        hasattr(model, attr)
        for model, attrs in required_model_attrs
        for attr in attrs
    )


def _billing_api_vless_link_available() -> bool:
    return callable(generate_vless_link)


def _billing_api_provisioning_imports_available() -> bool:
    try:
        provisioning_module = importlib.import_module("src.services.provisioning_service")
        telegram_module = importlib.import_module("src.sales.telegram_bot_v2")
    except Exception:
        return False
    return (
        hasattr(provisioning_module, "ProvisioningSource")
        and hasattr(provisioning_module, "provisioning_service")
        and hasattr(telegram_module, "TokenGenerator")
    )


def _billing_api_readiness_status(db: Any) -> Dict[str, Any]:
    db_ready = _billing_api_db_session_available(db)
    stripe_checkout_config_ready = _billing_api_stripe_checkout_config_available()
    stripe_webhook_config_ready = _billing_api_stripe_webhook_config_available()
    stripe_transport_ready = _billing_api_stripe_transport_available()
    billing_models_ready = _billing_api_models_available()
    vless_link_ready = _billing_api_vless_link_available()
    provisioning_imports_ready = _billing_api_provisioning_imports_available()
    billing_api_runtime_ready = (
        db_ready
        and stripe_checkout_config_ready
        and stripe_webhook_config_ready
        and stripe_transport_ready
        and billing_models_ready
        and vless_link_ready
        and provisioning_imports_ready
    )

    degraded_dependencies = []
    if not db_ready:
        degraded_dependencies.append("database")
    if not stripe_checkout_config_ready:
        degraded_dependencies.append("stripe_checkout_config")
    if not stripe_webhook_config_ready:
        degraded_dependencies.append("stripe_webhook_config")
    if not stripe_transport_ready:
        degraded_dependencies.append("stripe_transport")
    if not billing_models_ready:
        degraded_dependencies.append("billing_models")
    if not vless_link_ready:
        degraded_dependencies.append("vless_link_generator")
    if not provisioning_imports_ready:
        degraded_dependencies.append("provisioning_imports")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "billing_api_runtime_ready": billing_api_runtime_ready,
        "billing_api_db_ready": db_ready,
        "stripe_checkout_config_ready": stripe_checkout_config_ready,
        "stripe_webhook_config_ready": stripe_webhook_config_ready,
        "stripe_transport_ready": stripe_transport_ready,
        "billing_models_ready": billing_models_ready,
        "vless_link_ready": vless_link_ready,
        "provisioning_imports_ready": provisioning_imports_ready,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/billing",
            "boundary": (
                "Commercial billing routes use the fixed /api/v1/billing prefix, "
                "so they are outside legacy MaaS catch-all matching and are "
                "registered in light mode."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Webhook idempotency, user subscription state, licenses, payments, "
                "invoices, order status, and revenue metrics require SQLAlchemy "
                "query/add/commit/rollback methods."
            ),
            "stripe_checkout_config": (
                "Checkout and order status require STRIPE_SECRET_KEY and "
                "STRIPE_PRICE_ID."
            ),
            "stripe_webhook_config": (
                "Webhook signature verification requires STRIPE_WEBHOOK_SECRET."
            ),
            "stripe_transport": (
                "Stripe calls require httpx.AsyncClient and the stripe circuit "
                "breaker call wrapper."
            ),
            "billing_models": (
                "BillingWebhookEvent, User, License, Payment, and Invoice models "
                "must expose the columns touched by billing routes."
            ),
            "vless_link_generator": (
                "Paid order status requires generate_vless_link to return the "
                "customer VPN client link."
            ),
            "provisioning_imports": (
                "Successful Stripe webhooks import provisioning_service, "
                "ProvisioningSource, and TokenGenerator at processing time."
            ),
        },
        "claim_boundary": (
            "Billing API readiness proves route availability and local dependency "
            "surfaces only. It does not call Stripe, query the database, verify a "
            "real webhook signature, create a license, provision VPN access, or "
            "prove payment settlement."
        ),
    }


@router.get("/readiness")
async def billing_api_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _billing_api_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/config")
async def billing_config(request: Request = None):
    started = time.monotonic()
    publishable_key = _get_env("STRIPE_PUBLISHABLE_KEY")
    price_id = _get_env("STRIPE_PRICE_ID")
    payload = {
        "configured": bool(_get_env("STRIPE_SECRET_KEY") and price_id),
        "publishable_key": publishable_key,
        "price_id": price_id,
    }
    metadata = {
        "configured": payload["configured"],
        "stripe_secret_configured": bool(_get_env("STRIPE_SECRET_KEY")),
        "stripe_price_configured": bool(price_id),
        "stripe_publishable_key_present": bool(publishable_key),
        "stripe_price_id_hash": _redacted_sha256_prefix(price_id),
        "raw_publishable_key_redacted": True,
        "raw_price_id_redacted": True,
    }
    payload.update(
        _billing_api_local_observation_response_claim_metadata(
            source_agent=_BILLING_CONFIG_SOURCE_AGENT,
            surface="billing_api.config",
            status_value="read",
            metadata=metadata,
        )
    )
    _publish_billing_api_event(
        request,
        source_agent=_BILLING_CONFIG_SOURCE_AGENT,
        layer=_BILLING_CONFIG_LAYER,
        stage="billing_config_read",
        operation="billing_config",
        status_value="read",
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        read_only=True,
        observed_state=True,
        metadata=metadata,
    )
    return payload


@router.post("/checkout-session")
@limiter.limit("10/minute")
async def create_checkout_session(request: Request, payload: CheckoutSessionRequest):
    started = time.monotonic()
    base_metadata = {
        "email_hash": _redacted_sha256_prefix(payload.email.lower()),
        "email_present": bool(payload.email),
        "plan_bucket": _billing_plan_bucket(payload.plan),
        "quantity": payload.quantity,
        "stripe_secret_configured": bool(_get_env("STRIPE_SECRET_KEY")),
        "stripe_price_configured": bool(_get_env("STRIPE_PRICE_ID")),
        "stripe_call_attempted": False,
        "raw_checkout_url_redacted": True,
    }
    if "@" not in payload.email:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
            layer=_BILLING_CHECKOUT_LAYER,
            stage="checkout_session_create",
            operation="create_checkout_session",
            status_value="blocked",
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**base_metadata, "reason": "invalid_email"},
        )
        raise HTTPException(status_code=400, detail="Invalid email")

    try:
        secret_key = _require_env("STRIPE_SECRET_KEY")
        price_id = _require_env("STRIPE_PRICE_ID")
    except HTTPException as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
            layer=_BILLING_CHECKOUT_LAYER,
            stage="checkout_session_create",
            operation="create_checkout_session",
            status_value="blocked",
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={
                **base_metadata,
                "stripe_secret_configured": bool(_get_env("STRIPE_SECRET_KEY")),
                "stripe_price_configured": bool(_get_env("STRIPE_PRICE_ID")),
                "reason": "missing_required_config",
            },
        )
        raise
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
    stripe_http_status: Optional[int] = None

    async def _call_stripe():
        nonlocal stripe_http_status
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            resp = await http_client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                auth=(secret_key, ""),
            )
        stripe_http_status = resp.status_code
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"error": {"message": resp.text}}
            raise HTTPException(status_code=502, detail=err)
        session = resp.json()
        return {"id": session.get("id"), "url": session.get("url")}

    try:
        result = await stripe_circuit.call(_call_stripe)
    except Exception as exc:
        if _is_circuit_breaker_open_error(exc):
            logger.error("Stripe API circuit breaker is open")
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
                layer=_BILLING_CHECKOUT_LAYER,
                stage="checkout_session_create",
                operation="create_checkout_session",
                status_value="blocked",
                http_status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                duration_ms=(time.monotonic() - started) * 1000.0,
                control_action=True,
                metadata={
                    **base_metadata,
                    "stripe_call_attempted": True,
                    "stripe_http_status": stripe_http_status,
                    "reason": "stripe_circuit_open",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service temporarily unavailable. Please try again later.",
            )
        if isinstance(exc, HTTPException):
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
                layer=_BILLING_CHECKOUT_LAYER,
                stage="checkout_session_create",
                operation="create_checkout_session",
                status_value="failed",
                http_status_code=exc.status_code,
                duration_ms=(time.monotonic() - started) * 1000.0,
                control_action=True,
                metadata={
                    **base_metadata,
                    "stripe_call_attempted": True,
                    "stripe_http_status": stripe_http_status,
                    "reason": "stripe_checkout_http_error",
                },
            )
            raise
        logger.error(f"Stripe API call failed: {exc}")
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
            layer=_BILLING_CHECKOUT_LAYER,
            stage="checkout_session_create",
            operation="create_checkout_session",
            status_value="failed",
            http_status_code=502,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={
                **base_metadata,
                "stripe_call_attempted": True,
                "stripe_http_status": stripe_http_status,
                "reason": "stripe_checkout_exception",
                "error_type": exc.__class__.__name__,
            },
        )
        raise HTTPException(status_code=502, detail="Payment service error")
    response_metadata = {
        **base_metadata,
        "stripe_call_attempted": True,
        "stripe_http_status": stripe_http_status,
        "checkout_session_id_hash": _redacted_sha256_prefix(result.get("id")),
        "checkout_url_present": bool(result.get("url")),
    }
    _publish_billing_api_event(
        request,
        source_agent=_BILLING_CHECKOUT_SOURCE_AGENT,
        layer=_BILLING_CHECKOUT_LAYER,
        stage="checkout_session_create",
        operation="create_checkout_session",
        status_value="created",
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        control_action=True,
        metadata=response_metadata,
    )
    return {
        **result,
        **_billing_api_checkout_response_claim_metadata(response_metadata),
    }


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


def _start_local_stripe_event_processing(
    event_id: Optional[str], payload_hash: str
) -> Optional[Dict[str, Any]]:
    """In-memory idempotency fallback when DB idempotency table is unavailable."""
    if not event_id:
        return None
    with _stripe_event_fallback_lock:
        # Periodic cleanup on every 10th call to avoid overhead
        if len(_stripe_event_fallback) > 0 and len(_stripe_event_fallback) % 10 == 0:
            _cleanup_stripe_fallback()
        
        # Evict if at capacity
        if len(_stripe_event_fallback) >= _FALLBACK_MAX_SIZE:
            _evict_oldest_fallback_entries()
        
        current_time = time.time()
        record = _stripe_event_fallback.get(event_id)
        if record is None:
            _stripe_event_fallback[event_id] = {
                "payload_hash": payload_hash,
                "status": "processing",
                "response": None,
                "timestamp": current_time,
            }
            return None

        if record.get("payload_hash") != payload_hash:
            raise HTTPException(status_code=409, detail="Stripe event_id payload mismatch")

        if record.get("status") == "done":
            cached = record.get("response")
            if isinstance(cached, dict):
                return dict(cached)
            return {"received": True}

        raise HTTPException(status_code=409, detail="Stripe event is already being processed")


def _finalize_local_stripe_event_processing(
    event_id: Optional[str], response_payload: Dict[str, Any]
) -> None:
    if not event_id:
        return
    with _stripe_event_fallback_lock:
        record = _stripe_event_fallback.get(event_id)
        if record is None:
            _stripe_event_fallback[event_id] = {
                "payload_hash": "",
                "status": "done",
                "response": dict(response_payload),
                "timestamp": time.time(),
            }
            return
        record["status"] = "done"
        record["response"] = dict(response_payload)
        record["timestamp"] = time.time()


def _fail_local_stripe_event_processing(event_id: Optional[str]) -> None:
    if not event_id:
        return
    with _stripe_event_fallback_lock:
        _stripe_event_fallback.pop(event_id, None)


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

    cached_local = _start_local_stripe_event_processing(event_id, payload_hash)
    if cached_local is not None:
        return cached_local

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
    _finalize_local_stripe_event_processing(event_id, response_payload)
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
    _fail_local_stripe_event_processing(event_id)
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
    started = time.monotonic()
    common_metadata: Dict[str, Any] = {
        "stripe_signature_present": bool(stripe_signature),
        "signature_verified": False,
        "payload_size_bytes": 0,
        "payload_sha256_prefix": None,
        "event_id_hash": None,
        "event_type_bucket": "unknown",
        "email_hash": None,
        "email_present": False,
        "payment_status_bucket": "unknown",
        "idempotency_cached_response": False,
        "idempotency_reservation_attempted": False,
        "db_user_found": None,
        "db_user_created": False,
        "local_user_plan_write_committed": False,
        "license_created": False,
        "vpn_provision_attempted": False,
        "vpn_provision_success": None,
        "vpn_provision_event_reference": None,
        "mesh_provision_attempted": False,
        "mesh_provision_success": None,
        "subscription_revocation_attempted": False,
        "subscription_revocation_success": None,
        "raw_payload_redacted": True,
        "raw_signature_redacted": True,
        "raw_license_token_redacted": True,
    }
    try:
        secret = _require_env("STRIPE_WEBHOOK_SECRET")
    except HTTPException as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={
                **common_metadata,
                "stripe_webhook_secret_configured": False,
                "reason": "missing_webhook_secret",
            },
        )
        raise
    if not stripe_signature:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**common_metadata, "reason": "missing_signature"},
        )
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    payload_hash = _stripe_payload_sha256(payload)
    common_metadata.update(
        {
            "payload_size_bytes": len(payload),
            "payload_sha256_prefix": payload_hash[:16],
        }
    )
    try:
        _verify_stripe_signature(payload, stripe_signature, secret)
        common_metadata["signature_verified"] = True
    except HTTPException as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**common_metadata, "reason": "signature_invalid"},
        )
        raise

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**common_metadata, "reason": "invalid_json"},
        )
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(event, dict):
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**common_metadata, "reason": "invalid_event_format"},
        )
        raise HTTPException(status_code=400, detail="Invalid Stripe event format")

    event_id = _extract_stripe_event_id(event)
    event_type = event.get("type")
    common_metadata.update(
        {
            "event_id_hash": _redacted_sha256_prefix(event_id),
            "event_type_bucket": str(event_type or "unknown")[:80],
            "idempotency_reservation_attempted": bool(event_id),
        }
    )
    try:
        cached_response = _start_stripe_event_processing(
            db, event_id, str(event_type), payload_hash
        )
    except HTTPException as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="blocked",
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata={**common_metadata, "reason": "idempotency_rejected"},
        )
        raise
    if cached_response is not None:
        cached_metadata = {**common_metadata, "idempotency_cached_response": True}
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
            layer=_BILLING_WEBHOOK_LAYER,
            stage="stripe_webhook_receive",
            operation="stripe_webhook",
            status_value="replayed",
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            control_action=True,
            metadata=cached_metadata,
        )
        if "claim_gate" not in cached_response:
            cached_response = {
                **cached_response,
                **_billing_api_webhook_response_claim_metadata(
                    metadata=cached_metadata,
                    status_value="replayed",
                ),
            }
        return cached_response

    obj = (event.get("data") or {}).get("object") or {}
    if isinstance(obj, dict):
        common_metadata["payment_status_bucket"] = _bounded_billing_status(
            obj.get("payment_status") or obj.get("status")
        )
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
    common_metadata.update(
        {
            "email_hash": _redacted_sha256_prefix(str(email).lower() if email else None),
            "email_present": bool(email),
        }
    )

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
            common_metadata["db_user_found"] = db_user is not None
            if not db_user:
                db_user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    password_hash="stripe_managed",
                    created_at=datetime.datetime.utcnow(),
                )
                db.add(db_user)
                common_metadata["db_user_created"] = True

            db_user.plan = "pro"
            db_user.stripe_customer_id = obj.get("customer")
            db_user.stripe_subscription_id = obj.get("subscription") or obj.get("id")

            # Generate license (legacy support) in the same transaction so failures rollback plan updates.
            from src.sales.telegram_bot_v2 import TokenGenerator

            license_token = TokenGenerator.generate(tier="pro")
            new_license = License(
                token=license_token, user_id=db_user.id, tier="pro", is_active=True
            )
            db.add(new_license)
            db.commit()
            common_metadata["license_created"] = True
            common_metadata["local_user_plan_write_committed"] = True
            logger.info(f"Generated pro license {license_token} for user {email}")

            # Unified VPN provisioning
            try:
                common_metadata["vpn_provision_attempted"] = True
                result = await provisioning_service.provision_vpn_user(
                    email=email,
                    plan="pro",
                    source=ProvisioningSource.STRIPE_WEBHOOK,
                    user_id=db_user.id,
                    event_bus=_billing_event_bus_from_request(request),
                )
                evidence_getter = getattr(
                    provisioning_service,
                    "get_last_event_evidence",
                    None,
                )
                if callable(evidence_getter):
                    common_metadata["vpn_provision_event_reference"] = (
                        evidence_getter()
                    )

                if result.success:
                    db_user.vpn_uuid = result.vpn_uuid
                    db.commit()
                    common_metadata["vpn_provision_success"] = True
                    logger.info(f"VPN provisioned for {email}: {result.vpn_uuid[:8]}...")
                else:
                    common_metadata["vpn_provision_success"] = False
                    logger.error(f"VPN provisioning failed for {email}: {result.error}")
            except Exception as provision_err:
                common_metadata["vpn_provision_success"] = False
                logger.error(f"VPN provisioning failed for {email}: {provision_err}")

            # Mesh provisioning (Phase 3)
            try:
                _provisioner = mesh_provisioner  # use module-level ref (patchable)
                if _provisioner is not None:
                    common_metadata["mesh_provision_attempted"] = True
                    instance = await _provisioner.create(
                        name=f"auto-mesh-{db_user.id[:8]}",
                        nodes=5,
                        owner_id=db_user.id,
                        pqc_enabled=True,
                    )
                    common_metadata["mesh_provision_success"] = True
                    logger.info(
                        f"Auto-provisioned mesh {instance.mesh_id} for user {email}"
                    )
                else:
                    common_metadata["mesh_provision_success"] = None
                    logger.warning("MaaS mesh provisioner unavailable; skipping")
            except Exception as ex:
                common_metadata["mesh_provision_success"] = False
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

            common_metadata["subscription_revocation_attempted"] = True
            revoked = await provisioning_service.revoke_vpn_user(email)
            common_metadata["subscription_revocation_success"] = bool(revoked)
            db_user = db.query(User).filter(User.email == email).first()
            common_metadata["db_user_found"] = db_user is not None
            if db_user:
                db_user.plan = "canceled"
                db.commit()
                common_metadata["local_user_plan_write_committed"] = True
            logger.info(f"Subscription revoked for {email}, vpn_revoked={revoked}")
        except Exception as e:
            logger.error(f"Revocation failed for {email}: {e}")
            db.rollback()
            processing_failed = True
            _fail_stripe_event_processing(
                db, event_id, f"{e.__class__.__name__}: {str(e)}"
            )

    response_metadata = {
        **common_metadata,
        "processing_failed": processing_failed,
        "finalize_attempted": not processing_failed,
    }
    response_payload = {
        "received": True,
        **_billing_api_webhook_response_claim_metadata(
            metadata=response_metadata,
            status_value="processing_failed" if processing_failed else "received",
        ),
    }
    if not processing_failed:
        _finalize_stripe_event_processing(db, event_id, response_payload)
    _publish_billing_api_event(
        request,
        source_agent=_BILLING_WEBHOOK_SOURCE_AGENT,
        layer=_BILLING_WEBHOOK_LAYER,
        stage="stripe_webhook_receive",
        operation="stripe_webhook",
        status_value="processing_failed" if processing_failed else "received",
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        control_action=True,
        metadata=response_metadata,
        event_type=EventType.TASK_FAILED if processing_failed else None,
    )
    return response_payload


@router.get("/order-status")
async def get_order_status(
    session_id: str,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Check order status and return VLESS link if paid."""
    # Since we don't track session_id in User directly in this simple MVP,
    # we verify against Stripe API or assume if User exists and is PRO, it's done.
    # But for MVP, session_id is key. We should query Stripe to get customer_email.
    started = time.monotonic()
    base_metadata = {
        "checkout_session_id_hash": _redacted_sha256_prefix(session_id),
        "stripe_call_attempted": False,
        "stripe_http_status": None,
        "payment_status_bucket": "unknown",
        "customer_email_hash": None,
        "customer_email_present": False,
        "db_user_found": None,
        "user_plan_bucket": "unknown",
        "vpn_uuid_present": False,
        "vless_link_present": False,
        "raw_session_id_redacted": True,
        "raw_customer_email_redacted": True,
    }

    try:
        secret_key = _require_env("STRIPE_SECRET_KEY")
    except HTTPException as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
            layer=_BILLING_ORDER_STATUS_LAYER,
            stage="order_status_read",
            operation="get_order_status",
            status_value="blocked",
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            read_only=True,
            observed_state=True,
            metadata={**base_metadata, "reason": "missing_stripe_secret"},
        )
        raise

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
            auth=(secret_key, ""),
        )
        base_metadata.update(
            {
                "stripe_call_attempted": True,
                "stripe_http_status": resp.status_code,
            }
        )
        if resp.status_code != 200:
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
                layer=_BILLING_ORDER_STATUS_LAYER,
                stage="order_status_read",
                operation="get_order_status",
                status_value="blocked",
                http_status_code=404,
                duration_ms=(time.monotonic() - started) * 1000.0,
                read_only=True,
                observed_state=True,
                metadata={**base_metadata, "reason": "session_not_found"},
            )
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = resp.json()

    payment_status = session_data.get("payment_status")
    base_metadata["payment_status_bucket"] = _bounded_billing_status(payment_status)
    if payment_status == "paid":
        customer_email = session_data.get("customer_details", {}).get("email")
        base_metadata.update(
            {
                "customer_email_hash": _redacted_sha256_prefix(
                    str(customer_email).lower() if customer_email else None
                ),
                "customer_email_present": bool(customer_email),
            }
        )
        if not customer_email:
            response_metadata = {**base_metadata, "reason": "missing_customer_email"}
            response = {
                "status": "processing",
                "message": "Email missing from payment",
                **_billing_api_order_status_response_claim_metadata(
                    status_value="processing",
                    metadata=response_metadata,
                ),
            }
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
                layer=_BILLING_ORDER_STATUS_LAYER,
                stage="order_status_read",
                operation="get_order_status",
                status_value="processing",
                http_status_code=200,
                duration_ms=(time.monotonic() - started) * 1000.0,
                read_only=True,
                observed_state=True,
                metadata=response_metadata,
            )
            return response

        db_user = db.query(User).filter(User.email == customer_email).first()
        base_metadata["db_user_found"] = db_user is not None
        if db_user and db_user.plan == "pro" and db_user.vpn_uuid:
            base_metadata.update(
                {
                    "user_plan_bucket": _billing_plan_bucket(db_user.plan),
                    "vpn_uuid_present": True,
                }
            )
            # Generate link
            host = os.getenv(
                "XRAY_HOST", "localhost"
            )  # For client side, should be public IP
            # Ideally get public IP or domain
            public_host = os.getenv("PUBLIC_DOMAIN", host)

            try:
                link = generate_vless_link(
                    db_user.vpn_uuid, server=public_host, port=443
                )
            except Exception as exc:
                _publish_billing_api_event(
                    request,
                    source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
                    layer=_BILLING_ORDER_STATUS_LAYER,
                    stage="order_status_read",
                    operation="get_order_status",
                    status_value="failed",
                    http_status_code=500,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    read_only=True,
                    observed_state=True,
                    metadata={
                        **base_metadata,
                        "reason": "vless_link_generation_failed",
                        "error_type": exc.__class__.__name__,
                    },
                )
                raise
            response_metadata = {**base_metadata, "vless_link_present": True}
            response = {
                "status": "paid",
                "vless_link": link,
                "instructions": "Copy this link into V2Ray/Xray client.",
                **_billing_api_order_status_response_claim_metadata(
                    status_value="paid",
                    metadata=response_metadata,
                ),
            }
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
                layer=_BILLING_ORDER_STATUS_LAYER,
                stage="order_status_read",
                operation="get_order_status",
                status_value="paid",
                http_status_code=200,
                duration_ms=(time.monotonic() - started) * 1000.0,
                read_only=True,
                observed_state=True,
                metadata=response_metadata,
            )
            return response
        else:
            if db_user is not None:
                base_metadata["user_plan_bucket"] = _billing_plan_bucket(db_user.plan)
                base_metadata["vpn_uuid_present"] = bool(db_user.vpn_uuid)
            response_metadata = {**base_metadata, "reason": "local_provisioning_pending"}
            response = {
                "status": "processing",
                "message": "Payment received, provisioning account...",
                **_billing_api_order_status_response_claim_metadata(
                    status_value="processing",
                    metadata=response_metadata,
                ),
            }
            _publish_billing_api_event(
                request,
                source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
                layer=_BILLING_ORDER_STATUS_LAYER,
                stage="order_status_read",
                operation="get_order_status",
                status_value="processing",
                http_status_code=200,
                duration_ms=(time.monotonic() - started) * 1000.0,
                read_only=True,
                observed_state=True,
                metadata=response_metadata,
            )
            return response
    else:
        response = {
            "status": payment_status,
            **_billing_api_order_status_response_claim_metadata(
                status_value="not_paid",
                metadata=base_metadata,
            ),
        }
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_ORDER_STATUS_SOURCE_AGENT,
            layer=_BILLING_ORDER_STATUS_LAYER,
            stage="order_status_read",
            operation="get_order_status",
            status_value="not_paid",
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            read_only=True,
            observed_state=True,
            metadata=base_metadata,
        )
        return response


@router.get("/revenue-metrics")
async def get_revenue_metrics(
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Get revenue metrics for dashboard."""
    started = time.monotonic()
    try:
        payment_repo = PaymentRepository(db)
        invoice_repo = InvoiceRepository(db)
        user_repo = UserRepository(db)

        # Calculate total revenue from verified payments (SQL aggregate)
        total_revenue = payment_repo.get_total_amount()

        # Calculate paid invoices (SQL aggregate)
        total_invoice_revenue = invoice_repo.get_total_paid_amount()

        # Simple MRR calculation (assuming monthly subscriptions)
        # This is a placeholder - in reality, calculate based on active subscriptions
        active_users = db.query(User).filter(User.plan.in_(["pro", "enterprise"])).count()
        estimated_mrr = active_users * 1000  # Assume 1000 RUB per month per user
    except Exception as exc:
        _publish_billing_api_event(
            request,
            source_agent=_BILLING_REVENUE_METRICS_SOURCE_AGENT,
            layer=_BILLING_REVENUE_METRICS_LAYER,
            stage="revenue_metrics_read",
            operation="get_revenue_metrics",
            status_value="failed",
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            read_only=True,
            observed_state=True,
            metadata={
                "reason": "revenue_metrics_query_failed",
                "error_type": exc.__class__.__name__,
            },
        )
        raise
    response = {
        "total_revenue_rub": total_revenue,
        "invoice_revenue_rub": total_invoice_revenue,
        "estimated_monthly_recurring_revenue_rub": estimated_mrr,
        "total_verified_payments": len(total_payments),
        "total_paid_invoices": len(paid_invoices),
        "active_paying_users": active_users,
        "currency": "RUB",
    }
    metadata = {
        "total_verified_payments": len(total_payments),
        "total_paid_invoices": len(paid_invoices),
        "active_paying_users": active_users,
        "currency": "RUB",
        "revenue_fields_present": True,
        "raw_payment_rows_redacted": True,
        "raw_invoice_rows_redacted": True,
    }
    response.update(
        _billing_api_local_observation_response_claim_metadata(
            source_agent=_BILLING_REVENUE_METRICS_SOURCE_AGENT,
            surface="billing_api.revenue_metrics",
            status_value="read",
            metadata=metadata,
        )
    )
    _publish_billing_api_event(
        request,
        source_agent=_BILLING_REVENUE_METRICS_SOURCE_AGENT,
        layer=_BILLING_REVENUE_METRICS_LAYER,
        stage="revenue_metrics_read",
        operation="get_revenue_metrics",
        status_value="read",
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        read_only=True,
        observed_state=True,
        metadata=metadata,
    )
    return response
