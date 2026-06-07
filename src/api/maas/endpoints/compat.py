"""
MaaS Compatibility Endpoints
============================

Backwards-compatible aliases for historical client paths that are no longer
first-class in the canonical MaaS v1 router layout.
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

import src.api.maas.registry as maas_registry
from src.api.cross_plane_claim_gate import (
    cross_plane_claim_gate_metadata,
    readiness_cross_plane_claim_gate_metadata,
)
from src.api.maas.auth import (
    get_current_user as get_current_user_from_maas,
    require_permission,
    UserContext,
)
from src.api.maas.endpoints import mesh as modular_mesh
from src.api.maas.models import (
    MeshDeployRequest as ModularMeshDeployRequest,
    MeshDeployResponse as ModularMeshDeployResponse,
    MeshMetricsResponse,
    MeshStatusResponse,
    ScaleRequest,
)
from src.api.maas.endpoints.auth import register as register_v1
from src.api.maas_auth_models import TokenResponse, UserRegisterRequest
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.reliability_policy import mark_degraded_dependency
from src.database import User, get_db

router = APIRouter(tags=["MaaS Compatibility"])
logger = logging.getLogger(__name__)

_COMPAT_AUDIT_READ_SOURCE_AGENT = "maas-compat-audit-read"
_COMPAT_AUDIT_READ_LAYER = "api_compat_audit_observed_state"
_COMPAT_AUDIT_READ_CLAIM_BOUNDARY = (
    "MaaS compatibility audit-log read evidence only. It records bounded local "
    "reads of the modular in-memory audit log after compatibility permission and "
    "mesh ownership checks; it does not prove durable audit persistence, "
    "complete historical coverage, or dataplane enforcement."
)
_COMPAT_READ_LIST_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_read_list_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Audit-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Event-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Complete-Historical-Coverage-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}
_COMPAT_MAPEK_READ_SOURCE_AGENT = "maas-compat-mapek-read"
_COMPAT_MAPEK_READ_LAYER = "api_compat_mapek_observed_state"
_COMPAT_MAPEK_READ_CLAIM_BOUNDARY = (
    "MaaS compatibility MAPE-K event read evidence only. It records bounded "
    "local reads of the modular in-memory MAPE-K event stream after mesh "
    "ownership checks; it does not prove fresh dataplane health, completed "
    "autonomous remediation, or durable event persistence."
)
_COMPAT_LIFECYCLE_READ_SOURCE_AGENT = "maas-compat-lifecycle-read"
_COMPAT_LIFECYCLE_READ_LAYER = "api_compat_lifecycle_observed_state"
_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY = (
    "MaaS compatibility lifecycle read evidence only. It records bounded local "
    "reads of modular mesh list, status, and metrics state after compatibility "
    "auth/ownership checks; it does not prove fresh dataplane health, external "
    "node reachability, or durable lifecycle state."
)
_COMPAT_LIFECYCLE_READ_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_lifecycle_read_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Fresh-Dataplane-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}
_COMPAT_LIFECYCLE_CONTROL_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_lifecycle_control_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Durable-Lifecycle-Persistence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Node-Deployment-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Node-Shutdown-Claim-Allowed": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}
_COMPAT_SCALE_SOURCE_AGENT = "maas-compat-scale"
_COMPAT_SCALE_LAYER = "api_compat_lifecycle_control_action"
_COMPAT_SCALE_CLAIM_BOUNDARY = (
    "MaaS compatibility scale evidence only. It records local modular "
    "MeshInstance.scale mutation plus local audit-log and MAPE-K append attempts; "
    "it does not prove external node deployment, dataplane reachability, "
    "scheduler convergence, or durable lifecycle persistence."
)
_COMPAT_TERMINATE_SOURCE_AGENT = "maas-compat-terminate"
_COMPAT_TERMINATE_LAYER = "api_compat_lifecycle_control_action"
_COMPAT_TERMINATE_CLAIM_BOUNDARY = (
    "MaaS compatibility terminate evidence only. It records a local delegated "
    "modular terminate call and bounded result metadata; it does not prove "
    "external node shutdown, dataplane removal, durable lifecycle persistence, "
    "or successful cleanup outside the modular MaaS registry."
)
_COMPAT_BILLING_PAY_SOURCE_AGENT = "maas-compat-billing-pay"
_COMPAT_BILLING_PAY_LAYER = "api_compat_billing_pay_intent"
_COMPAT_BILLING_PAY_UPSTREAM_SOURCE_AGENT = "maas-billing-subscription-checkout"
_COMPAT_BILLING_PAY_CLAIM_BOUNDARY = (
    "MaaS compatibility billing/pay evidence only. It records the historical "
    "query-based payment intent, local crypto-disabled rejection, and bounded "
    "metadata from delegated subscription checkout; it does not prove provider "
    "settlement, subscription activation, crypto backend availability, or that "
    "a returned checkout URL was opened."
)
_COMPAT_BILLING_PAY_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_compat_billing_pay_claim_boundary_headers.v1"
    ),
    "X-X0TTA6BL4-Provider-Settlement-Claim-Allowed": "false",
    "X-X0TTA6BL4-Bank-Settlement-Claim-Allowed": "false",
    "X-X0TTA6BL4-Chain-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Token-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Subscription-Activation-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Access-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}
_COMPAT_AUTH_REGISTER_SOURCE_AGENT = "maas-compat-auth-register"
_COMPAT_AUTH_REGISTER_LAYER = "api_compat_auth_registration_intent"
_COMPAT_AUTH_REGISTER_CLAIM_BOUNDARY = (
    "MaaS compatibility auth/register evidence only. It records the historical "
    "v3 registration alias intent plus bounded delegated outcome metadata; it "
    "does not prove account ownership, email verification, session use, or "
    "that returned API credentials were stored by the caller."
)
_COMPAT_DEPLOY_SOURCE_AGENT = "maas-compat-deploy"
_COMPAT_DEPLOY_LAYER = "api_compat_lifecycle_control_action"
_COMPAT_DEPLOY_CLAIM_BOUNDARY = (
    "MaaS compatibility deploy evidence only. It records historical deploy "
    "alias intent, delegated modular deploy outcomes, and bounded response "
    "metadata; it does not prove external node enrollment, dataplane "
    "reachability, durable infrastructure convergence, or that the join token "
    "was consumed."
)


def _compat_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit"))


def _compat_auth_alias_available() -> bool:
    return callable(register_v1) and callable(get_current_user_from_maas)


def _compat_legacy_deploy_available() -> bool:
    return (
        callable(require_permission)
        and callable(getattr(modular_mesh, "deploy_mesh", None))
        and callable(getattr(modular_mesh, "get_mesh_status", None))
        and callable(getattr(modular_mesh, "get_mesh_metrics", None))
        and callable(getattr(modular_mesh, "terminate_mesh", None))
        and callable(getattr(modular_mesh, "get_provisioner", None))
        and callable(ModularMeshDeployRequest)
        and callable(ModularMeshDeployResponse)
    )


def _compat_billing_alias_available() -> bool:
    return callable(_resolve_create_subscription_session())


def _resolve_create_subscription_session():
    try:
        from src.api.maas.endpoints.billing import create_subscription_session
    except Exception:
        try:
            from src.api.maas.endpoints.billing import create_subscription_session
        except Exception:
            return None
    return create_subscription_session


def _compat_models_available() -> bool:
    return (
        callable(UserRegisterRequest)
        and callable(TokenResponse)
        and hasattr(User, "id")
        and hasattr(User, "api_key")
    )


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _compat_event_bus_from_request(request: Request | None) -> EventBus | None:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS compatibility EventBus: %s", exc)
        return None


def _compat_read_list_claim_boundary_headers(
    *,
    surface: str,
    claim_boundary: str,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> Dict[str, str]:
    headers = dict(_COMPAT_READ_LIST_CLAIM_HEADERS)
    headers.update(
        {
            "X-X0TTA6BL4-Claim-Surface": surface,
            "X-X0TTA6BL4-Claim-Boundary": claim_boundary,
            "X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed": (
                "true" if local_audit_log_claim_allowed else "false"
            ),
            "X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed": (
                "true" if local_mapek_event_claim_allowed else "false"
            ),
        }
    )
    return headers


def _set_compat_read_list_claim_headers(
    response: Response | None,
    *,
    surface: str,
    claim_boundary: str,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> None:
    if response is None:
        return
    response.headers.update(
        _compat_read_list_claim_boundary_headers(
            surface=surface,
            claim_boundary=claim_boundary,
            local_audit_log_claim_allowed=local_audit_log_claim_allowed,
            local_mapek_event_claim_allowed=local_mapek_event_claim_allowed,
        )
    )


def _compat_read_list_claim_summary(
    *,
    surface: str,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> Dict[str, Any]:
    return {
        "compat_read_list_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "local_audit_log_observation_claim_allowed": bool(
            local_audit_log_claim_allowed
        ),
        "local_mapek_event_observation_claim_allowed": bool(
            local_mapek_event_claim_allowed
        ),
        "autonomous_remediation_completion_claim_allowed": False,
        "durable_audit_persistence_claim_allowed": False,
        "durable_event_persistence_claim_allowed": False,
        "complete_historical_coverage_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _compat_lifecycle_read_claim_boundary_headers(
    *,
    surface: str,
    claim_boundary: str,
    local_lifecycle_state_claim_allowed: bool = False,
) -> Dict[str, str]:
    headers = dict(_COMPAT_LIFECYCLE_READ_CLAIM_HEADERS)
    headers.update(
        {
            "X-X0TTA6BL4-Claim-Surface": surface,
            "X-X0TTA6BL4-Claim-Boundary": claim_boundary,
            "X-X0TTA6BL4-Local-Lifecycle-State-Observation-Claim-Allowed": (
                "true" if local_lifecycle_state_claim_allowed else "false"
            ),
        }
    )
    return headers


def _set_compat_lifecycle_read_claim_headers(
    response: Response | None,
    *,
    surface: str,
    claim_boundary: str,
    local_lifecycle_state_claim_allowed: bool = False,
) -> None:
    if response is None:
        return
    response.headers.update(
        _compat_lifecycle_read_claim_boundary_headers(
            surface=surface,
            claim_boundary=claim_boundary,
            local_lifecycle_state_claim_allowed=(
                local_lifecycle_state_claim_allowed
            ),
        )
    )


def _compat_lifecycle_read_claim_summary(
    *,
    surface: str,
    local_lifecycle_state_claim_allowed: bool = False,
    mesh_lifecycle_claim_gate_present: bool = False,
    mesh_metrics_claim_gate_present: bool = False,
    cross_plane_claim_gate_present: bool = False,
) -> Dict[str, Any]:
    return {
        "compat_lifecycle_read_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "local_lifecycle_state_observation_claim_allowed": bool(
            local_lifecycle_state_claim_allowed
        ),
        "mesh_lifecycle_claim_gate_present": bool(
            mesh_lifecycle_claim_gate_present
        ),
        "mesh_metrics_claim_gate_present": bool(mesh_metrics_claim_gate_present),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate_present),
        "autonomous_remediation_completion_claim_allowed": False,
        "durable_lifecycle_persistence_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "fresh_dataplane_health_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _compat_lifecycle_control_claim_boundary_headers(
    *,
    surface: str,
    claim_boundary: str,
    local_registry_mutation_claim_allowed: bool = False,
    delegated_modular_lifecycle_claim_allowed: bool = False,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> Dict[str, str]:
    headers = dict(_COMPAT_LIFECYCLE_CONTROL_CLAIM_HEADERS)
    headers.update(
        {
            "X-X0TTA6BL4-Claim-Surface": surface,
            "X-X0TTA6BL4-Claim-Boundary": claim_boundary,
            "X-X0TTA6BL4-Local-Registry-Mutation-Claim-Allowed": (
                "true" if local_registry_mutation_claim_allowed else "false"
            ),
            "X-X0TTA6BL4-Delegated-Modular-Lifecycle-Claim-Allowed": (
                "true" if delegated_modular_lifecycle_claim_allowed else "false"
            ),
            "X-X0TTA6BL4-Local-Audit-Log-Append-Claim-Allowed": (
                "true" if local_audit_log_claim_allowed else "false"
            ),
            "X-X0TTA6BL4-Local-MAPE-K-Event-Append-Claim-Allowed": (
                "true" if local_mapek_event_claim_allowed else "false"
            ),
        }
    )
    return headers


def _set_compat_lifecycle_control_claim_headers(
    response: Response | None,
    *,
    surface: str,
    claim_boundary: str,
    local_registry_mutation_claim_allowed: bool = False,
    delegated_modular_lifecycle_claim_allowed: bool = False,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> None:
    if response is None:
        return
    response.headers.update(
        _compat_lifecycle_control_claim_boundary_headers(
            surface=surface,
            claim_boundary=claim_boundary,
            local_registry_mutation_claim_allowed=(
                local_registry_mutation_claim_allowed
            ),
            delegated_modular_lifecycle_claim_allowed=(
                delegated_modular_lifecycle_claim_allowed
            ),
            local_audit_log_claim_allowed=local_audit_log_claim_allowed,
            local_mapek_event_claim_allowed=local_mapek_event_claim_allowed,
        )
    )


def _compat_lifecycle_control_claim_gate(
    *,
    surface: str,
    claim_boundary: str,
    local_registry_mutation_claim_allowed: bool = False,
    delegated_modular_lifecycle_claim_allowed: bool = False,
    local_audit_log_claim_allowed: bool = False,
    local_mapek_event_claim_allowed: bool = False,
) -> Dict[str, Any]:
    allowed_claim_ids = [
        claim_id
        for claim_id, allowed in (
            ("local_registry_mutation", local_registry_mutation_claim_allowed),
            (
                "delegated_modular_lifecycle",
                delegated_modular_lifecycle_claim_allowed,
            ),
            ("local_audit_log_append", local_audit_log_claim_allowed),
            ("local_mapek_event_append", local_mapek_event_claim_allowed),
        )
        if allowed
    ]
    return {
        "schema": "x0tta6bl4.maas_compat_lifecycle_control_claim_gate.v1",
        "surface": surface,
        "allowed_claim_ids": allowed_claim_ids,
        "blocked_claim_ids": [
            "autonomous_remediation_completion",
            "durable_lifecycle_persistence",
            "external_infrastructure_convergence",
            "external_node_deployment",
            "external_node_shutdown",
            "restored_dataplane",
            "node_reachability",
            "routing_convergence",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
            "external_dpi_bypass",
            "settlement_finality",
            "production_slo",
            "production_readiness",
        ],
        "local_registry_mutation_claim_allowed": bool(
            local_registry_mutation_claim_allowed
        ),
        "delegated_modular_lifecycle_claim_allowed": bool(
            delegated_modular_lifecycle_claim_allowed
        ),
        "local_audit_log_append_claim_allowed": bool(
            local_audit_log_claim_allowed
        ),
        "local_mapek_event_append_claim_allowed": bool(
            local_mapek_event_claim_allowed
        ),
        "autonomous_remediation_completion_claim_allowed": False,
        "durable_lifecycle_persistence_claim_allowed": False,
        "external_infrastructure_convergence_claim_allowed": False,
        "external_node_deployment_claim_allowed": False,
        "external_node_shutdown_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": claim_boundary,
    }


def _compat_lifecycle_control_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        [
            "production_readiness",
            "production_slo",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
            "dpi_bypass",
            "settlement_finality",
        ],
        surface=surface,
    )


def _audit_log_summary_for_evidence(
    events: List[Dict[str, Any]],
    *,
    limit_requested: int,
    stored_event_count: int,
) -> Dict[str, Any]:
    known_events = {
        "mesh.scale",
        "mesh.deploy",
        "mesh.terminate",
        "node.approved",
        "node.revoked",
    }
    event_name_counts: Dict[str, int] = {}
    actor_mentions = 0
    timestamp_mentions = 0
    details_present_count = 0
    total_field_count = 0

    for event in events:
        if not isinstance(event, dict):
            continue
        total_field_count += len(event)
        event_name = str(event.get("event") or "unknown")
        event_bucket = event_name if event_name in known_events else "other"
        event_name_counts[event_bucket] = event_name_counts.get(event_bucket, 0) + 1
        if event.get("actor"):
            actor_mentions += 1
        if event.get("timestamp"):
            timestamp_mentions += 1
        if event.get("details"):
            details_present_count += 1

    return {
        "returned_event_count": len(events),
        "stored_event_count": stored_event_count,
        "limit_requested": limit_requested,
        "event_name_counts": event_name_counts,
        "actor_mentions": actor_mentions,
        "timestamp_mentions": timestamp_mentions,
        "details_present_count": details_present_count,
        "total_field_count": total_field_count,
        **_compat_read_list_claim_summary(
            surface="maas_compat.audit_logs",
            local_audit_log_claim_allowed=True,
        ),
    }


def _publish_compat_audit_read_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    owner_id: Any | None = None,
    limit_requested: int,
    stored_event_count: int | None = None,
    returned_event_count: int | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_audit_log_read",
        "service_name": _COMPAT_AUDIT_READ_SOURCE_AGENT,
        "source_alias": _COMPAT_AUDIT_READ_SOURCE_AGENT,
        "layer": _COMPAT_AUDIT_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": "compat_audit_logs",
        "permission_checked": True,
        "ownership_checked": stage != "permission_denied",
        "limit_requested": limit_requested,
        "stored_event_count": stored_event_count,
        "returned_event_count": returned_event_count,
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_AUDIT_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_AUDIT_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility audit read event: %s", exc)
        return None


def _mapek_event_summary_for_evidence(
    events: List[Dict[str, Any]],
    *,
    limit_requested: int,
    stored_event_count: int,
) -> Dict[str, Any]:
    known_types = {"scale", "node.heartbeat", "heartbeat"}
    known_actions = {"scale_up", "scale_down", "maintain"}
    known_phases = {"MONITOR", "ANALYZE", "PLAN", "EXECUTE", "KNOWLEDGE"}
    known_metric_fields = {
        "cpu_usage",
        "memory_usage",
        "neighbors_count",
        "routing_table_size",
        "uptime",
    }
    type_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}
    phase_counts: Dict[str, int] = {}
    node_id_mentions = 0
    timestamp_mentions = 0
    known_metric_mentions = 0
    total_field_count = 0

    for event in events:
        if not isinstance(event, dict):
            continue
        total_field_count += len(event)
        event_type = str(event.get("type") or event.get("event_type") or "unknown")
        type_bucket = event_type if event_type in known_types else "other"
        type_counts[type_bucket] = type_counts.get(type_bucket, 0) + 1

        action = str(event.get("action") or "unknown")
        action_bucket = action if action in known_actions else "other"
        action_counts[action_bucket] = action_counts.get(action_bucket, 0) + 1

        phase = str(event.get("phase") or "unknown").upper()
        phase_bucket = phase if phase in known_phases else "other"
        phase_counts[phase_bucket] = phase_counts.get(phase_bucket, 0) + 1

        if event.get("node_id"):
            node_id_mentions += 1
        if event.get("timestamp"):
            timestamp_mentions += 1
        known_metric_mentions += sum(
            1 for field_name in known_metric_fields if field_name in event
        )

    return {
        "returned_event_count": len(events),
        "stored_event_count": stored_event_count,
        "limit_requested": limit_requested,
        "type_counts": type_counts,
        "action_counts": action_counts,
        "phase_counts": phase_counts,
        "node_id_mentions": node_id_mentions,
        "timestamp_mentions": timestamp_mentions,
        "known_metric_mentions": known_metric_mentions,
        "total_field_count": total_field_count,
        **_compat_read_list_claim_summary(
            surface="maas_compat.mapek_events",
            local_mapek_event_claim_allowed=True,
        ),
    }


def _publish_compat_mapek_read_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    owner_id: Any | None = None,
    limit_requested: int,
    stored_event_count: int | None = None,
    returned_event_count: int | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_mapek_event_read",
        "service_name": _COMPAT_MAPEK_READ_SOURCE_AGENT,
        "source_alias": _COMPAT_MAPEK_READ_SOURCE_AGENT,
        "layer": _COMPAT_MAPEK_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": "compat_mapek_events",
        "ownership_checked": True,
        "limit_requested": limit_requested,
        "stored_event_count": stored_event_count,
        "returned_event_count": returned_event_count,
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_MAPEK_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_MAPEK_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility MAPE-K read event: %s", exc)
        return None


def _model_dict_for_evidence(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if isinstance(model, dict):
        return dict(model)
    return {
        key: getattr(model, key)
        for key in dir(model)
        if not key.startswith("_") and not callable(getattr(model, key, None))
    }


def _mesh_list_summary_for_evidence(meshes: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_nodes = 0
    healthy_nodes = 0
    peer_count = 0
    status_counts: Dict[str, int] = {}
    lifecycle_claim_gate_count = 0
    cross_plane_claim_gate_count = 0
    for mesh in meshes:
        total_nodes += int(mesh.get("nodes_total") or 0)
        healthy_nodes += int(mesh.get("nodes_healthy") or 0)
        peers = mesh.get("peers") if isinstance(mesh.get("peers"), list) else []
        peer_count += len(peers)
        status_value = str(mesh.get("status") or "unknown")[:40]
        status_counts[status_value] = status_counts.get(status_value, 0) + 1
        lifecycle_claim_gate_count += int(
            isinstance(mesh.get("mesh_lifecycle_claim_gate"), dict)
            and bool(mesh.get("mesh_lifecycle_claim_gate"))
        )
        cross_plane_claim_gate_count += int(
            isinstance(mesh.get("cross_plane_claim_gate"), dict)
            and bool(mesh.get("cross_plane_claim_gate"))
        )
    return {
        "mesh_count": len(meshes),
        "total_nodes": total_nodes,
        "healthy_nodes": healthy_nodes,
        "peer_count": peer_count,
        "status_counts": status_counts,
        "mesh_lifecycle_claim_gate_count": lifecycle_claim_gate_count,
        "cross_plane_claim_gate_count": cross_plane_claim_gate_count,
        **_compat_lifecycle_read_claim_summary(
            surface="maas_compat.lifecycle.list",
            local_lifecycle_state_claim_allowed=True,
            mesh_lifecycle_claim_gate_present=lifecycle_claim_gate_count > 0,
            cross_plane_claim_gate_present=cross_plane_claim_gate_count > 0,
        ),
    }


def _mesh_status_summary_for_evidence(response: Any) -> Dict[str, Any]:
    data = _model_dict_for_evidence(response)
    peers = data.get("peers") if isinstance(data.get("peers"), list) else []
    control_policy = (
        data.get("control_policy_evidence")
        if isinstance(data.get("control_policy_evidence"), dict)
        else {}
    )
    lifecycle_claim_gate = (
        data.get("mesh_lifecycle_claim_gate")
        if isinstance(data.get("mesh_lifecycle_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        data.get("cross_plane_claim_gate")
        if isinstance(data.get("cross_plane_claim_gate"), dict)
        else {}
    )
    return {
        "status": str(data.get("status") or "unknown")[:40],
        "nodes_total": int(data.get("nodes_total") or 0),
        "nodes_healthy": int(data.get("nodes_healthy") or 0),
        "peer_count": len(peers),
        "health_score": data.get("health_score"),
        "control_policy_evidence_present": bool(control_policy),
        "control_policy_evidence_field_count": len(control_policy),
        **_compat_lifecycle_read_claim_summary(
            surface="maas_compat.lifecycle.status",
            local_lifecycle_state_claim_allowed=True,
            mesh_lifecycle_claim_gate_present=bool(lifecycle_claim_gate),
            cross_plane_claim_gate_present=bool(cross_plane_claim_gate),
        ),
    }


def _mesh_metrics_summary_for_evidence(response: Any) -> Dict[str, Any]:
    data = _model_dict_for_evidence(response)
    consciousness = (
        data.get("consciousness") if isinstance(data.get("consciousness"), dict) else {}
    )
    mape_k = data.get("mape_k") if isinstance(data.get("mape_k"), dict) else {}
    network = data.get("network") if isinstance(data.get("network"), dict) else {}
    control_policy = (
        data.get("control_policy_evidence")
        if isinstance(data.get("control_policy_evidence"), dict)
        else {}
    )
    metrics_claim_gate = (
        data.get("mesh_metrics_claim_gate")
        if isinstance(data.get("mesh_metrics_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        data.get("cross_plane_claim_gate")
        if isinstance(data.get("cross_plane_claim_gate"), dict)
        else {}
    )
    return {
        "consciousness_metric_count": len(consciousness),
        "mape_k_metric_count": len(mape_k),
        "network_metric_count": len(network),
        "control_policy_evidence_present": bool(control_policy),
        "control_policy_evidence_field_count": len(control_policy),
        "has_timestamp": bool(data.get("timestamp")),
        **_compat_lifecycle_read_claim_summary(
            surface="maas_compat.lifecycle.metrics",
            local_lifecycle_state_claim_allowed=True,
            mesh_metrics_claim_gate_present=bool(metrics_claim_gate),
            cross_plane_claim_gate_present=bool(cross_plane_claim_gate),
        ),
    }


def _publish_compat_lifecycle_read_event(
    request: Request | None,
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    owner_id: Any | None = None,
    read_scope: str,
    mesh_count: int | None = None,
    node_count: int | None = None,
    healthy_node_count: int | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": operation,
        "service_name": _COMPAT_LIFECYCLE_READ_SOURCE_AGENT,
        "source_alias": _COMPAT_LIFECYCLE_READ_SOURCE_AGENT,
        "layer": _COMPAT_LIFECYCLE_READ_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "read_scope": str(read_scope or "")[:80],
        "mesh_count": mesh_count,
        "node_count": node_count,
        "healthy_node_count": healthy_node_count,
        "result_summary": result_summary or {},
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_LIFECYCLE_READ_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error(
            "Failed to publish MaaS compatibility lifecycle read event: %s",
            exc,
        )
        return None


def _scale_request_summary_for_evidence(req: Any) -> Dict[str, Any]:
    return {
        "action": str(getattr(req, "action", ""))[:40],
        "count": int(getattr(req, "count", 0) or 0),
    }


def _publish_compat_scale_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    req: Any,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    owner_id: Any | None = None,
    previous_nodes: int | None = None,
    current_nodes: int | None = None,
    registry_mutated: bool = False,
    audit_log_recorded: bool = False,
    mapek_event_recorded: bool = False,
    compat_lifecycle_control_claim_gate_present: bool = False,
    cross_plane_claim_gate_present: bool = False,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    delta_nodes = (
        current_nodes - previous_nodes
        if current_nodes is not None and previous_nodes is not None
        else None
    )
    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_mesh_scale",
        "service_name": _COMPAT_SCALE_SOURCE_AGENT,
        "source_alias": _COMPAT_SCALE_SOURCE_AGENT,
        "layer": _COMPAT_SCALE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _scale_request_summary_for_evidence(req),
        "previous_nodes": previous_nodes,
        "current_nodes": current_nodes,
        "delta_nodes": delta_nodes,
        "registry_mutated": registry_mutated,
        "audit_log_recorded": audit_log_recorded,
        "mapek_event_recorded": mapek_event_recorded,
        "compat_lifecycle_control_claim_gate_present": bool(
            compat_lifecycle_control_claim_gate_present
        ),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate_present),
        "read_only": not registry_mutated,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_SCALE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_SCALE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility scale event: %s", exc)
        return None


def _terminate_request_summary_for_evidence(reason: str) -> Dict[str, Any]:
    reason_text = str(reason or "")
    return {
        "reason_present": bool(reason_text),
        "reason_length": min(len(reason_text), 500),
    }


def _terminate_result_summary_for_evidence(result: Any) -> Dict[str, Any]:
    data = result if isinstance(result, dict) else {}
    claim_gate = (
        data.get("compat_lifecycle_control_claim_gate")
        if isinstance(data.get("compat_lifecycle_control_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        data.get("cross_plane_claim_gate")
        if isinstance(data.get("cross_plane_claim_gate"), dict)
        else {}
    )
    return {
        "status": str(data.get("status") or "unknown")[:40],
        "reason_present": bool(data.get("reason")),
        "result_field_count": len(data),
        "compat_lifecycle_control_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
    }


def _publish_compat_terminate_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    reason_value: str,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    owner_id: Any | None = None,
    previous_status: str | None = None,
    previous_node_count: int | None = None,
    delegated_to_modular: bool = False,
    registry_mutated: bool = False,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_mesh_terminate",
        "service_name": _COMPAT_TERMINATE_SOURCE_AGENT,
        "source_alias": _COMPAT_TERMINATE_SOURCE_AGENT,
        "layer": _COMPAT_TERMINATE_LAYER,
        "status": status,
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _terminate_request_summary_for_evidence(reason_value),
        "previous_status": str(previous_status or "")[:40] if previous_status else None,
        "previous_node_count": previous_node_count,
        "delegated_to_modular": delegated_to_modular,
        "registry_mutated": registry_mutated,
        "result_summary": result_summary or {},
        "read_only": not registry_mutated,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_TERMINATE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_TERMINATE_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility terminate event: %s", exc)
        return None


def _billing_pay_request_summary_for_evidence(
    *,
    plan: str,
    method: str,
) -> Dict[str, Any]:
    known_plans = {"starter", "pro", "enterprise"}
    known_methods = {"stripe", "crypto"}
    return {
        "plan": plan if plan in known_plans else "other",
        "method": method if method in known_methods else "other",
    }


def _billing_pay_result_summary_for_evidence(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "payload_type": type(payload).__name__[:40],
            "payload_field_count": None,
            "checkout_url_present": False,
            "compat_billing_pay_claim_gate_present": False,
            "cross_plane_claim_gate_present": False,
        }

    claim_gate = (
        payload.get("compat_billing_pay_claim_gate")
        if isinstance(payload.get("compat_billing_pay_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        payload.get("cross_plane_claim_gate")
        if isinstance(payload.get("cross_plane_claim_gate"), dict)
        else {}
    )
    claim_surface = str(
        claim_gate.get("surface") or cross_plane_claim_gate.get("surface") or ""
    )[:120]
    summary = {
        "payload_type": "dict",
        "payload_field_count": len(payload),
        "checkout_url_present": bool(payload.get("url") or payload.get("payment_url")),
        "status_present": "status" in payload,
        "provider_present": "provider" in payload,
        "compat_billing_pay_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
    }
    if claim_surface:
        summary["claim_surface"] = claim_surface
    return summary


def _compat_billing_pay_claim_boundary_headers(
    *,
    surface: str,
    claim_boundary: str,
    delegated_subscription_checkout_intent_claim_allowed: bool = False,
    local_crypto_disabled_rejection_claim_allowed: bool = False,
) -> Dict[str, str]:
    headers = dict(_COMPAT_BILLING_PAY_CLAIM_HEADERS)
    headers.update(
        {
            "X-X0TTA6BL4-Claim-Surface": surface,
            "X-X0TTA6BL4-Claim-Boundary": claim_boundary,
            "X-X0TTA6BL4-Delegated-Subscription-Checkout-Intent-Claim-Allowed": (
                "true"
                if delegated_subscription_checkout_intent_claim_allowed
                else "false"
            ),
            "X-X0TTA6BL4-Local-Crypto-Disabled-Rejection-Claim-Allowed": (
                "true" if local_crypto_disabled_rejection_claim_allowed else "false"
            ),
        }
    )
    return headers


def _set_compat_billing_pay_claim_headers(
    response: Response | None,
    *,
    surface: str,
    claim_boundary: str,
    delegated_subscription_checkout_intent_claim_allowed: bool = False,
    local_crypto_disabled_rejection_claim_allowed: bool = False,
) -> None:
    if response is None:
        return
    response.headers.update(
        _compat_billing_pay_claim_boundary_headers(
            surface=surface,
            claim_boundary=claim_boundary,
            delegated_subscription_checkout_intent_claim_allowed=(
                delegated_subscription_checkout_intent_claim_allowed
            ),
            local_crypto_disabled_rejection_claim_allowed=(
                local_crypto_disabled_rejection_claim_allowed
            ),
        )
    )


def _compat_billing_pay_claim_gate(
    *,
    surface: str,
    delegated_subscription_checkout_intent_claim_allowed: bool = False,
    local_crypto_disabled_rejection_claim_allowed: bool = False,
) -> Dict[str, Any]:
    allowed_claim_ids = [
        claim_id
        for claim_id, allowed in (
            (
                "delegated_subscription_checkout_intent",
                delegated_subscription_checkout_intent_claim_allowed,
            ),
            (
                "local_crypto_disabled_rejection",
                local_crypto_disabled_rejection_claim_allowed,
            ),
        )
        if allowed
    ]
    return {
        "schema": "x0tta6bl4.maas_compat_billing_pay_claim_gate.v1",
        "surface": surface,
        "allowed_claim_ids": allowed_claim_ids,
        "blocked_claim_ids": [
            "provider_settlement",
            "bank_settlement",
            "chain_finality",
            "external_settlement_finality",
            "token_settlement_finality",
            "subscription_activation",
            "customer_access",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
            "external_dpi_bypass",
            "production_slo",
            "production_readiness",
        ],
        "delegated_subscription_checkout_intent_claim_allowed": bool(
            delegated_subscription_checkout_intent_claim_allowed
        ),
        "local_crypto_disabled_rejection_claim_allowed": bool(
            local_crypto_disabled_rejection_claim_allowed
        ),
        "provider_settlement_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "chain_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "token_settlement_finality_claim_allowed": False,
        "subscription_activation_claim_allowed": False,
        "customer_access_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": _COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
    }


def _compat_billing_pay_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        [
            "settlement_finality",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
            "dpi_bypass",
            "production_slo",
            "production_readiness",
        ],
        surface=surface,
    )


def _billing_pay_upstream_evidence_for_request(
    request: Request | None,
    *,
    since: datetime,
    limit: int = 3,
) -> Dict[str, Any]:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return {}
    events = event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=_COMPAT_BILLING_PAY_UPSTREAM_SOURCE_AGENT,
        since=since,
        limit=limit + 1,
    )
    if not events:
        return {}
    limited_events = events[-limit:]
    return {
        "event_ids": [event.event_id for event in limited_events],
        "event_ids_limit": limit,
        "event_ids_truncated": len(events) > limit,
        "events_total": len(events),
        "source_agents": sorted({event.source_agent for event in limited_events}),
        "payloads_redacted": True,
    }


def _billing_pay_source_quality_for_evidence(
    *,
    status: str,
    method: str,
    delegated_to_billing: bool,
) -> str:
    if method == "crypto" and not delegated_to_billing:
        return "crypto_backend_disabled_local_rejection"
    if delegated_to_billing and status == "success":
        return "delegated_subscription_checkout_intent_created"
    if delegated_to_billing:
        return "delegated_subscription_checkout_failed"
    return "local_compat_payment_preflight"


def _billing_pay_settlement_evidence(
    *,
    stage: str,
    status: str,
    plan: str,
    method: str,
    provider: str,
    delegated_to_billing: bool,
    checkout_url_present: bool,
    result_summary: Dict[str, Any],
    http_status_code: int | None,
    duration_ms: float,
    upstream_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    source_quality = _billing_pay_source_quality_for_evidence(
        status=status,
        method=method,
        delegated_to_billing=delegated_to_billing,
    )
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "settlement_action": "compat_payment_intent_only",
        "duration_ms": round(duration_ms, 3),
        "dataplane_confirmed": False,
        "provider": provider,
        "payment_status": None,
        "live_provider_settlement_confirmed": False,
        "bank_settlement_confirmed": False,
        "chain_finality_confirmed": False,
        "telemetry_evidence": upstream_evidence,
        "bridge_evidence": {
            "attempted": False,
            "status": "not_requested",
            "source_agent": None,
            "payloads_redacted": True,
        },
        "db_write_evidence": {
            "storage_backend": "delegated_billing_route",
            "attempted": False,
            "committed": False,
            "payloads_redacted": True,
        },
        "output_summary": {
            "billing_stage": str(stage or "")[:80],
            "status": str(status or "")[:40],
            "plan": plan if plan in {"starter", "pro", "enterprise"} else "other",
            "method": method if method in {"stripe", "crypto"} else "other",
            "http_status_code": http_status_code,
            "delegated_to_billing": delegated_to_billing,
            "checkout_url_present": checkout_url_present,
            "payload_type": result_summary.get("payload_type"),
            "payload_field_count": result_summary.get("payload_field_count"),
            "upstream_events_total": upstream_evidence.get("events_total", 0),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_compat_billing_pay_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    plan: str,
    method: str,
    current_user: Any | None = None,
    delegated_to_billing: bool = False,
    checkout_url_present: bool = False,
    result_summary: Dict[str, Any] | None = None,
    upstream_evidence: Dict[str, Any] | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    provider = method if method in {"stripe", "crypto"} else "unknown"
    safe_result_summary = result_summary or {}
    safe_upstream_evidence = upstream_evidence or {}
    settlement_evidence = _billing_pay_settlement_evidence(
        stage=stage,
        status=status,
        plan=plan,
        method=method,
        provider=provider,
        delegated_to_billing=delegated_to_billing,
        checkout_url_present=checkout_url_present,
        result_summary=safe_result_summary,
        upstream_evidence=safe_upstream_evidence,
        http_status_code=http_status_code,
        duration_ms=duration_ms,
    )
    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_billing_pay",
        "service_name": _COMPAT_BILLING_PAY_SOURCE_AGENT,
        "source_alias": _COMPAT_BILLING_PAY_SOURCE_AGENT,
        "layer": _COMPAT_BILLING_PAY_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _billing_pay_request_summary_for_evidence(
            plan=plan,
            method=method,
        ),
        "provider": provider,
        "delegated_to_billing": delegated_to_billing,
        "checkout_url_present": checkout_url_present,
        "result_summary": safe_result_summary,
        "upstream_evidence": safe_upstream_evidence,
        "http_status_code": http_status_code,
        "read_only": not delegated_to_billing,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "economy_action": True,
        "source_quality": settlement_evidence["source_quality"],
        "settlement_evidence": settlement_evidence,
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_BILLING_PAY_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility billing/pay event: %s", exc)
        return None


def _auth_register_request_summary_for_evidence(req: Any) -> Dict[str, Any]:
    return {
        "email_present": bool(getattr(req, "email", "")),
        "password_present": bool(getattr(req, "password", "")),
        "full_name_present": bool(getattr(req, "full_name", None)),
        "company_present": bool(getattr(req, "company", None)),
    }


def _auth_register_result_summary_for_evidence(payload: Any) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "payload_type": "dict" if isinstance(payload, dict) else type(payload).__name__[:40],
        "payload_field_count": len(data) if isinstance(payload, dict) else None,
        "access_token_present": bool(data.get("access_token")),
        "token_type": str(data.get("token_type") or "")[:40] or None,
        "expires_in_present": "expires_in" in data,
    }


def _publish_compat_auth_register_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    req: Any,
    delegated_to_auth: bool = False,
    result_summary: Dict[str, Any] | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_auth_register",
        "service_name": _COMPAT_AUTH_REGISTER_SOURCE_AGENT,
        "source_alias": _COMPAT_AUTH_REGISTER_SOURCE_AGENT,
        "layer": _COMPAT_AUTH_REGISTER_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "request_summary": _auth_register_request_summary_for_evidence(req),
        "delegated_to_auth": delegated_to_auth,
        "result_summary": result_summary or {},
        "http_status_code": http_status_code,
        "read_only": not delegated_to_auth,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_AUTH_REGISTER_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_AUTH_REGISTER_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility auth/register event: %s", exc)
        return None


def _deploy_request_summary_for_evidence(req: Any) -> Dict[str, Any]:
    known_plans = {"starter", "pro", "enterprise"}
    known_obfuscation = {"none", "xor", "aes"}
    known_traffic = {"none", "gaming", "streaming", "voip"}
    known_optimization = {"standard", "ml_routing", "genetic_topo"}
    known_federated = {"fedavg", "hw_fedavg"}
    billing_plan = str(getattr(req, "billing_plan", "") or "")
    obfuscation = str(getattr(req, "obfuscation", "") or "")
    traffic_profile = str(getattr(req, "traffic_profile", "") or "")
    optimization_mode = str(getattr(req, "optimization_mode", "") or "")
    federated_strategy = str(getattr(req, "federated_strategy", "") or "")
    mesh_name = str(getattr(req, "name", "") or "")
    return {
        "name_present": bool(mesh_name),
        "name_length": min(len(mesh_name), 256),
        "nodes": int(getattr(req, "nodes", 0) or 0),
        "billing_plan": billing_plan if billing_plan in known_plans else "other",
        "pqc_enabled": bool(getattr(req, "pqc_enabled", False)),
        "obfuscation": obfuscation if obfuscation in known_obfuscation else "other",
        "traffic_profile": (
            traffic_profile if traffic_profile in known_traffic else "other"
        ),
        "optimization_mode": (
            optimization_mode if optimization_mode in known_optimization else "other"
        ),
        "federated_strategy": (
            federated_strategy if federated_strategy in known_federated else "other"
        ),
        "join_token_ttl_sec": int(getattr(req, "join_token_ttl_sec", 0) or 0),
    }


def _deploy_result_summary_for_evidence(
    result: Any,
    *,
    compat_lifecycle_control_claim_gate_present: bool = False,
    compat_lifecycle_control_headers_present: bool = False,
) -> Dict[str, Any]:
    data = _model_dict_for_evidence(result)
    join_config = data.get("join_config") if isinstance(data.get("join_config"), dict) else {}
    pqc_identity = (
        data.get("pqc_identity") if isinstance(data.get("pqc_identity"), dict) else {}
    )
    mesh_deploy_claim_gate = (
        data.get("mesh_deploy_claim_gate")
        if isinstance(data.get("mesh_deploy_claim_gate"), dict)
        else {}
    )
    mesh_provisioner_claim_gate = (
        data.get("mesh_provisioner_claim_gate")
        if isinstance(data.get("mesh_provisioner_claim_gate"), dict)
        else {}
    )
    provisioner_cross_plane_claim_gate = (
        data.get("provisioner_cross_plane_claim_gate")
        if isinstance(data.get("provisioner_cross_plane_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        data.get("cross_plane_claim_gate")
        if isinstance(data.get("cross_plane_claim_gate"), dict)
        else {}
    )
    return {
        "status": str(data.get("status") or "unknown")[:40],
        "plan": str(data.get("plan") or "")[:40] or None,
        "join_config_field_count": len(join_config),
        "join_token_present": bool(join_config.get("enrollment_token")),
        "dashboard_url_present": bool(data.get("dashboard_url")),
        "pqc_identity_present": bool(pqc_identity),
        "pqc_identity_field_count": len(pqc_identity),
        "created_at_present": bool(data.get("created_at")),
        "join_token_expires_at_present": bool(data.get("join_token_expires_at")),
        "mesh_deploy_claim_gate_present": bool(mesh_deploy_claim_gate),
        "mesh_provisioner_claim_gate_present": bool(mesh_provisioner_claim_gate),
        "provisioner_cross_plane_claim_gate_present": bool(
            provisioner_cross_plane_claim_gate
        ),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "compat_lifecycle_control_claim_gate_present": bool(
            compat_lifecycle_control_claim_gate_present
        ),
        "compat_lifecycle_control_claim_boundary_headers_present": bool(
            compat_lifecycle_control_headers_present
        ),
        "claim_surface": "maas_compat.lifecycle_control.deploy",
    }


def _publish_compat_deploy_event(
    request: Request | None,
    *,
    stage: str,
    status: str,
    req: Any,
    current_user: Any | None = None,
    mesh_id: Any | None = None,
    delegated_to_modular: bool = False,
    registry_mutated: bool = False,
    result_summary: Dict[str, Any] | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _compat_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_compat",
        "stage": stage,
        "operation": "compat_mesh_deploy",
        "service_name": _COMPAT_DEPLOY_SOURCE_AGENT,
        "source_alias": _COMPAT_DEPLOY_SOURCE_AGENT,
        "layer": _COMPAT_DEPLOY_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "actor_user_id_hash": _redacted_sha256_prefix(
            getattr(current_user, "id", None)
        )
        if current_user is not None
        else None,
        "actor_role": str(getattr(current_user, "role", ""))[:40]
        if current_user is not None
        else None,
        "actor_plan": str(getattr(current_user, "plan", ""))[:40]
        if current_user is not None
        else None,
        "request_summary": _deploy_request_summary_for_evidence(req),
        "delegated_to_modular": delegated_to_modular,
        "registry_mutated": registry_mutated,
        "result_summary": result_summary or {},
        "http_status_code": http_status_code,
        "read_only": not delegated_to_modular,
        "observed_state": False,
        "safe_actuator": False,
        "control_action": True,
        "raw_identifiers_redacted": True,
        "raw_join_token_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _COMPAT_DEPLOY_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _COMPAT_DEPLOY_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS compatibility deploy event: %s", exc)
        return None


def _compat_readiness_status(db: Any) -> Dict[str, Any]:
    compat_db_ready = _compat_db_session_available(db)
    auth_alias_ready = _compat_auth_alias_available()
    legacy_deploy_ready = _compat_legacy_deploy_available()
    billing_alias_ready = _compat_billing_alias_available()
    compat_models_ready = _compat_models_available()
    compat_runtime_ready = (
        compat_db_ready
        and auth_alias_ready
        and legacy_deploy_ready
        and billing_alias_ready
        and compat_models_ready
    )

    degraded_dependencies = []
    if not compat_db_ready:
        degraded_dependencies.append("database")
    if not auth_alias_ready:
        degraded_dependencies.append("auth_alias")
    if not legacy_deploy_ready:
        degraded_dependencies.append("legacy_deploy_alias")
    if not billing_alias_ready:
        degraded_dependencies.append("billing_alias")
    if not compat_models_ready:
        degraded_dependencies.append("compat_models")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "compat_runtime_ready": compat_runtime_ready,
        "compat_db_ready": compat_db_ready,
        "auth_alias_ready": auth_alias_ready,
        "legacy_deploy_ready": legacy_deploy_ready,
        "billing_alias_ready": billing_alias_ready,
        "compat_models_ready": compat_models_ready,
        "route_precedence": {
            "router_prefix": "",
            "absolute_paths": [
                "/api/v3/maas/auth/register",
                "/api/v1/maas/deploy",
                "/api/v1/maas/mesh/deploy",
                "/api/v1/maas/list",
                "/api/v1/maas/{mesh_id}/status",
                "/api/v1/maas/{mesh_id}/metrics",
                "/api/v1/maas/{mesh_id}/scale",
                "/api/v1/maas/{mesh_id}",
                "/api/v1/maas/{mesh_id}/audit-logs",
                "/api/v1/maas/{mesh_id}/mapek/events",
                "/api/v1/maas/billing/pay",
            ],
            "shadowed_by_legacy": [],
            "boundary": (
                "Compatibility routes are absolute aliases on a prefixless router. "
                "They delegate to canonical auth, legacy deploy, and MaaS billing "
                "handlers instead of owning separate runtime state."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Aliases pass the SQLAlchemy session through to canonical auth, "
                "legacy deploy, and billing handlers."
            ),
            "auth_alias": (
                "The v3 register alias delegates to maas_auth.register and uses "
                "get_current_user_from_maas for authenticated billing alias calls."
            ),
            "legacy_deploy_alias": (
                "The deploy/status/metrics lifecycle aliases keep the historical "
                "legacy_deploy_ready readiness field but delegate mesh runtime "
                "work to src.api.maas.endpoints.mesh."
            ),
            "billing_alias": (
                "The billing/pay alias delegates to create_subscription_session "
                "for stripe checkout and rejects crypto locally."
            ),
            "compat_models": (
                "Compatibility response validation depends on auth request/response "
                "models and User identity/API-key fields."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_compat_readiness"
        ),
        "claim_boundary": (
            "Compatibility readiness proves alias route availability and delegated "
            "function surfaces only. It does not register a user, deploy a mesh, "
            "create a checkout session, or prove historical clients still send "
            "valid payloads."
        ),
    }


@router.get("/api/v1/maas/compat/readiness", include_in_schema=False)
async def maas_compat_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _compat_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.post(
    "/api/v3/maas/auth/register",
    response_model=TokenResponse,
    include_in_schema=False,
)
async def register_v3_alias(
    req: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Alias /api/v3/maas/auth/register -> /api/v1/maas/auth/register."""
    started = time.monotonic()
    try:
        payload = await register_v1(req, db)
    except HTTPException as exc:
        _publish_compat_auth_register_event(
            request,
            stage="auth_register_failed",
            status="failed",
            req=req,
            delegated_to_auth=True,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_compat_auth_register_event(
            request,
            stage="auth_register_failed",
            status="failed",
            req=req,
            delegated_to_auth=True,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    _publish_compat_auth_register_event(
        request,
        stage="auth_register_delegated",
        status="success",
        req=req,
        delegated_to_auth=True,
        result_summary=_auth_register_result_summary_for_evidence(payload),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="delegated_register_created",
    )
    return payload


@router.post(
    "/api/v1/maas/deploy",
    response_model=ModularMeshDeployResponse,
    include_in_schema=False,
)
@router.post(
    "/api/v1/maas/mesh/deploy",
    response_model=ModularMeshDeployResponse,
    include_in_schema=False,
)
async def deploy_mesh_alias(
    req: ModularMeshDeployRequest,
    request: Request,
    http_response: Response = None,
    current_user: User = Depends(require_permission("mesh:create")),
    db: Session = Depends(get_db),
):
    """Alias historical deploy paths to the modular mesh lifecycle endpoint."""
    started = time.monotonic()
    try:
        result = await modular_mesh.deploy_mesh(
            request=req,
            user=_as_modular_user(current_user),
            db=db,
        )
    except HTTPException as exc:
        _publish_compat_deploy_event(
            request,
            stage="deploy_failed",
            status="failed",
            req=req,
            current_user=current_user,
            delegated_to_modular=True,
            registry_mutated=False,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_compat_deploy_event(
            request,
            stage="deploy_failed",
            status="failed",
            req=req,
            current_user=current_user,
            delegated_to_modular=True,
            registry_mutated=False,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    result_data = _model_dict_for_evidence(result)
    claim_surface = "maas_compat.lifecycle_control.deploy"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        surface=claim_surface,
        claim_boundary=_COMPAT_DEPLOY_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_DEPLOY_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    _publish_compat_deploy_event(
        request,
        stage="deploy_delegated",
        status="success",
        req=req,
        current_user=current_user,
        mesh_id=result_data.get("mesh_id"),
        delegated_to_modular=True,
        registry_mutated=True,
        result_summary=_deploy_result_summary_for_evidence(
            result,
            compat_lifecycle_control_claim_gate_present=bool(
                compat_lifecycle_control_claim_gate
            ),
            compat_lifecycle_control_headers_present=http_response is not None,
        ),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="delegated_deploy_recorded",
    )
    return result


def _as_modular_user(user: User) -> UserContext:
    return UserContext(
        user_id=str(user.id),
        plan=str(getattr(user, "plan", None) or "starter"),
    )


def _dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def _owned_modular_mesh(mesh_id: str, user: User) -> Any:
    instance = maas_registry.get_mesh(mesh_id)
    if instance is None or str(getattr(instance, "owner_id", "")) != str(user.id):
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")
    return instance


def _user_has_permission(user: User, permission: str) -> bool:
    if getattr(user, "role", "") == "admin":
        return True
    raw_permissions = getattr(user, "permissions", "") or ""
    permissions = {
        value.strip()
        for chunk in str(raw_permissions).split(",")
        for value in chunk.split()
        if value.strip()
    }
    return permission in permissions


@router.get("/api/v1/maas/list", include_in_schema=False)
async def list_meshes_alias(
    request: Request,
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    meshes: List[Dict[str, Any]] = []
    for instance in maas_registry.get_all_meshes().values():
        if str(getattr(instance, "owner_id", "")) != str(current_user.id):
            continue
        if getattr(instance, "status", "") == "terminated":
            continue
        meshes.append(_dump_model(modular_mesh._build_mesh_status_response(instance)))
    summary = _mesh_list_summary_for_evidence(meshes)
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.list",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    _publish_compat_lifecycle_read_event(
        request,
        operation="compat_mesh_list_read",
        stage="mesh_list_read",
        status="success",
        current_user=current_user,
        read_scope="compat_mesh_list",
        mesh_count=summary["mesh_count"],
        node_count=summary["total_nodes"],
        healthy_node_count=summary["healthy_nodes"],
        result_summary=summary,
        reason="mesh_list_read",
    )
    return {"meshes": meshes, "count": len(meshes)}


@router.get(
    "/api/v1/maas/{mesh_id}/status",
    response_model=MeshStatusResponse,
    include_in_schema=False,
)
async def get_mesh_status_alias(
    mesh_id: str,
    request: Request,
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    """Alias legacy status path to modular mesh observed-state response."""
    try:
        response = await modular_mesh.get_mesh_status(
            mesh_id=mesh_id,
            user=_as_modular_user(current_user),
        )
    except HTTPException as exc:
        _publish_compat_lifecycle_read_event(
            request,
            operation="compat_mesh_status_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="compat_mesh_status",
            reason=f"http_{exc.status_code}",
        )
        raise

    instance = maas_registry.get_mesh(mesh_id)
    summary = _mesh_status_summary_for_evidence(response)
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.status",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    _publish_compat_lifecycle_read_event(
        request,
        operation="compat_mesh_status_read",
        stage="mesh_status_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="compat_mesh_status",
        mesh_count=1,
        node_count=summary["nodes_total"],
        healthy_node_count=summary["nodes_healthy"],
        result_summary=summary,
        reason="mesh_status_read",
    )
    return response


@router.get(
    "/api/v1/maas/{mesh_id}/metrics",
    response_model=MeshMetricsResponse,
    include_in_schema=False,
)
async def get_mesh_metrics_alias(
    mesh_id: str,
    request: Request,
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    """Alias legacy metrics path to modular mesh evidence response."""
    try:
        response = await modular_mesh.get_mesh_metrics(
            mesh_id=mesh_id,
            user=_as_modular_user(current_user),
        )
    except HTTPException as exc:
        _publish_compat_lifecycle_read_event(
            request,
            operation="compat_mesh_metrics_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            read_scope="compat_mesh_metrics",
            reason=f"http_{exc.status_code}",
        )
        raise

    instance = maas_registry.get_mesh(mesh_id)
    summary = _mesh_metrics_summary_for_evidence(response)
    _set_compat_lifecycle_read_claim_headers(
        http_response,
        surface="maas_compat.lifecycle.metrics",
        claim_boundary=_COMPAT_LIFECYCLE_READ_CLAIM_BOUNDARY,
        local_lifecycle_state_claim_allowed=True,
    )
    _publish_compat_lifecycle_read_event(
        request,
        operation="compat_mesh_metrics_read",
        stage="mesh_metrics_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        read_scope="compat_mesh_metrics",
        mesh_count=1,
        result_summary=summary,
        reason="mesh_metrics_read",
    )
    return response


@router.post("/api/v1/maas/{mesh_id}/scale", include_in_schema=False)
async def scale_mesh_alias(
    mesh_id: str,
    req: ScaleRequest,
    request: Request,
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    """Accept legacy scale_up/scale_down payloads and call modular scaling."""
    try:
        instance = _owned_modular_mesh(mesh_id, current_user)
    except HTTPException as exc:
        _publish_compat_scale_event(
            request,
            stage="access_denied",
            status="denied",
            req=req,
            current_user=current_user,
            mesh_id=mesh_id,
            reason=f"http_{exc.status_code}",
        )
        raise

    previous_nodes = len(getattr(instance, "node_instances", {}) or {})
    current_nodes = instance.scale(req.action, req.count)
    audit_log_recorded = False
    mapek_event_recorded = False
    try:
        await maas_registry.record_audit_log(
            mesh_id,
            str(current_user.id),
            "mesh.scale",
            f"Scaled from {previous_nodes} to {current_nodes} nodes",
        )
        audit_log_recorded = True
        maas_registry.add_mapek_event(
            mesh_id,
            {
                "type": "scale",
                "action": req.action,
                "from": previous_nodes,
                "to": current_nodes,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        mapek_event_recorded = True
    except Exception as exc:
        _publish_compat_scale_event(
            request,
            stage="side_effect_failed",
            status="failed",
            req=req,
            current_user=current_user,
            mesh_id=mesh_id,
            owner_id=getattr(instance, "owner_id", None),
            previous_nodes=previous_nodes,
            current_nodes=current_nodes,
            registry_mutated=True,
            audit_log_recorded=audit_log_recorded,
            mapek_event_recorded=mapek_event_recorded,
            reason=type(exc).__name__,
        )
        raise

    claim_surface = "maas_compat.lifecycle_control.scale"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        surface=claim_surface,
        claim_boundary=_COMPAT_SCALE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        local_audit_log_claim_allowed=audit_log_recorded,
        local_mapek_event_claim_allowed=mapek_event_recorded,
    )
    cross_plane_claim_gate = _compat_lifecycle_control_cross_plane_gate(claim_surface)
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_SCALE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        local_audit_log_claim_allowed=audit_log_recorded,
        local_mapek_event_claim_allowed=mapek_event_recorded,
    )
    _publish_compat_scale_event(
        request,
        stage="scale_applied",
        status="success",
        req=req,
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        previous_nodes=previous_nodes,
        current_nodes=current_nodes,
        registry_mutated=True,
        audit_log_recorded=audit_log_recorded,
        mapek_event_recorded=mapek_event_recorded,
        compat_lifecycle_control_claim_gate_present=bool(
            compat_lifecycle_control_claim_gate
        ),
        cross_plane_claim_gate_present=bool(cross_plane_claim_gate),
        reason="scale_applied",
    )
    return {
        "mesh_id": mesh_id,
        "previous_nodes": previous_nodes,
        "current_nodes": current_nodes,
        "status": getattr(instance, "status", "active"),
        "compat_lifecycle_control_claim_gate": compat_lifecycle_control_claim_gate,
        "cross_plane_claim_gate": cross_plane_claim_gate,
    }


@router.delete("/api/v1/maas/{mesh_id}", include_in_schema=False)
async def terminate_mesh_alias(
    mesh_id: str,
    request: Request,
    http_response: Response = None,
    reason: str = Query("user_request"),
    current_user: User = Depends(get_current_user_from_maas),
):
    """Alias legacy terminate path to modular mesh lifecycle."""
    previous_instance = maas_registry.get_mesh(mesh_id)
    previous_status = (
        str(getattr(previous_instance, "status", ""))
        if previous_instance is not None
        else None
    )
    previous_nodes = (
        len(getattr(previous_instance, "node_instances", {}) or {})
        if previous_instance is not None
        else None
    )

    try:
        result = await modular_mesh.terminate_mesh(
            mesh_id=mesh_id,
            user=_as_modular_user(current_user),
            reason=reason,
        )
    except HTTPException as exc:
        _publish_compat_terminate_event(
            request,
            stage="access_denied",
            status="denied",
            reason_value=reason,
            current_user=current_user,
            mesh_id=mesh_id,
            previous_status=previous_status,
            previous_node_count=previous_nodes,
            delegated_to_modular=True,
            registry_mutated=False,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        _publish_compat_terminate_event(
            request,
            stage="terminate_failed",
            status="failed",
            reason_value=reason,
            current_user=current_user,
            mesh_id=mesh_id,
            owner_id=getattr(previous_instance, "owner_id", None),
            previous_status=previous_status,
            previous_node_count=previous_nodes,
            delegated_to_modular=True,
            registry_mutated=False,
            reason=type(exc).__name__,
        )
        raise

    claim_surface = "maas_compat.lifecycle_control.terminate"
    compat_lifecycle_control_claim_gate = _compat_lifecycle_control_claim_gate(
        surface=claim_surface,
        claim_boundary=_COMPAT_TERMINATE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    cross_plane_claim_gate = _compat_lifecycle_control_cross_plane_gate(claim_surface)
    _set_compat_lifecycle_control_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_TERMINATE_CLAIM_BOUNDARY,
        local_registry_mutation_claim_allowed=True,
        delegated_modular_lifecycle_claim_allowed=True,
    )
    result_payload = dict(result) if isinstance(result, dict) else {"result": result}
    result_payload.update(
        {
            "compat_lifecycle_control_claim_gate": (
                compat_lifecycle_control_claim_gate
            ),
            "cross_plane_claim_gate": cross_plane_claim_gate,
        }
    )
    _publish_compat_terminate_event(
        request,
        stage="terminate_applied",
        status="success",
        reason_value=reason,
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(previous_instance, "owner_id", None),
        previous_status=previous_status,
        previous_node_count=previous_nodes,
        delegated_to_modular=True,
        registry_mutated=True,
        result_summary=_terminate_result_summary_for_evidence(result_payload),
        reason="terminate_applied",
    )
    return result_payload


@router.get("/api/v1/maas/{mesh_id}/audit-logs", include_in_schema=False)
async def get_audit_logs_alias(
    mesh_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    _set_compat_read_list_claim_headers(
        http_response,
        surface="maas_compat.audit_logs",
        claim_boundary=_COMPAT_AUDIT_READ_CLAIM_BOUNDARY,
        local_audit_log_claim_allowed=True,
    )
    if not _user_has_permission(current_user, "audit:view"):
        _publish_compat_audit_read_event(
            request,
            stage="permission_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            limit_requested=limit,
            returned_event_count=0,
            reason="missing_audit_view_permission",
        )
        raise HTTPException(status_code=403, detail="audit:view permission required")

    try:
        instance = _owned_modular_mesh(mesh_id, current_user)
    except HTTPException as exc:
        _publish_compat_audit_read_event(
            request,
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            limit_requested=limit,
            returned_event_count=0,
            reason=f"http_{exc.status_code}",
        )
        raise

    stored_events = maas_registry.get_audit_log(mesh_id)
    events = stored_events[-limit:]
    _publish_compat_audit_read_event(
        request,
        stage="audit_log_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        limit_requested=limit,
        stored_event_count=len(stored_events),
        returned_event_count=len(events),
        result_summary=_audit_log_summary_for_evidence(
            events,
            limit_requested=limit,
            stored_event_count=len(stored_events),
        ),
        reason="audit_log_read",
    )
    return {"mesh_id": mesh_id, "events": events, "count": len(events)}


@router.get("/api/v1/maas/{mesh_id}/mapek/events", include_in_schema=False)
async def get_mapek_events_alias(
    mesh_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    http_response: Response = None,
    current_user: User = Depends(get_current_user_from_maas),
):
    _set_compat_read_list_claim_headers(
        http_response,
        surface="maas_compat.mapek_events",
        claim_boundary=_COMPAT_MAPEK_READ_CLAIM_BOUNDARY,
        local_mapek_event_claim_allowed=True,
    )
    try:
        instance = _owned_modular_mesh(mesh_id, current_user)
    except HTTPException as exc:
        _publish_compat_mapek_read_event(
            request,
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            limit_requested=limit,
            returned_event_count=0,
            reason=f"http_{exc.status_code}",
        )
        raise

    stored_events = maas_registry.get_mapek_events(mesh_id)
    events = stored_events[-limit:]
    _publish_compat_mapek_read_event(
        request,
        stage="mapek_event_list_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        limit_requested=limit,
        stored_event_count=len(stored_events),
        returned_event_count=len(events),
        result_summary=_mapek_event_summary_for_evidence(
            events,
            limit_requested=limit,
            stored_event_count=len(stored_events),
        ),
        reason="mapek_event_list_read",
    )
    return {"mesh_id": mesh_id, "events": events, "count": len(events)}


@router.post("/api/v1/maas/billing/pay", include_in_schema=False)
async def billing_pay_alias(
    request: Request,
    http_response: Response = None,
    plan: str = Query(..., pattern="^(starter|pro|enterprise)$"),
    method: str = Query("stripe", pattern="^(stripe|crypto)$"),
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """
    Alias /api/v1/maas/billing/pay -> /api/v1/maas/billing/subscriptions/checkout.

    The compatibility endpoint keeps historical query-based input shape.
    """
    started = time.monotonic()
    delegation_started_at = datetime.utcnow()
    claim_surface = "maas_compat.billing_pay"
    if method == "crypto":
        _publish_compat_billing_pay_event(
            request,
            stage="crypto_not_enabled",
            status="denied",
            plan=plan,
            method=method,
            current_user=current_user,
            delegated_to_billing=False,
            checkout_url_present=False,
            http_status_code=501,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="crypto_billing_not_enabled",
        )
        raise HTTPException(
            status_code=501,
            detail=(
                "Crypto billing is not enabled in this deployment. "
                "Use method=stripe or configure a crypto billing backend."
            ),
            headers=_compat_billing_pay_claim_boundary_headers(
                surface=claim_surface,
                claim_boundary=_COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
                local_crypto_disabled_rejection_claim_allowed=True,
            ),
        )

    create_subscription_session = _resolve_create_subscription_session()
    if not callable(create_subscription_session):
        _publish_compat_billing_pay_event(
            request,
            stage="subscription_checkout_unavailable",
            status="failed",
            method=method,
            plan=plan,
            current_user=current_user,
            delegated_to_billing=False,
            checkout_url_present=False,
            http_status_code=503,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="subscription_checkout_unavailable",
        )
        raise HTTPException(
            status_code=503,
            detail="Subscription checkout is unavailable",
            headers=_compat_billing_pay_claim_boundary_headers(
                surface=claim_surface,
                claim_boundary=_COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
            ),
        )

    try:
        payload = await create_subscription_session(
            plan=plan,
            request=request,
            current_user=current_user,
            db=db,
        )
    except HTTPException as exc:
        upstream_evidence = _billing_pay_upstream_evidence_for_request(
            request,
            since=delegation_started_at,
        )
        _publish_compat_billing_pay_event(
            request,
            stage="subscription_checkout_failed",
            status="failed",
            plan=plan,
            method=method,
            current_user=current_user,
            delegated_to_billing=True,
            checkout_url_present=False,
            upstream_evidence=upstream_evidence,
            http_status_code=exc.status_code,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"http_{exc.status_code}",
        )
        raise
    except Exception as exc:
        upstream_evidence = _billing_pay_upstream_evidence_for_request(
            request,
            since=delegation_started_at,
        )
        _publish_compat_billing_pay_event(
            request,
            stage="subscription_checkout_failed",
            status="failed",
            plan=plan,
            method=method,
            current_user=current_user,
            delegated_to_billing=True,
            checkout_url_present=False,
            upstream_evidence=upstream_evidence,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise

    checkout_url = payload.get("url") if isinstance(payload, dict) else None
    compat_billing_pay_claim_gate = _compat_billing_pay_claim_gate(
        surface=claim_surface,
        delegated_subscription_checkout_intent_claim_allowed=True,
    )
    cross_plane_claim_gate = _compat_billing_pay_cross_plane_gate(claim_surface)
    _set_compat_billing_pay_claim_headers(
        http_response,
        surface=claim_surface,
        claim_boundary=_COMPAT_BILLING_PAY_CLAIM_BOUNDARY,
        delegated_subscription_checkout_intent_claim_allowed=True,
    )
    response_payload = {
        "payment_url": checkout_url,
        "status": "created",
        "method": method,
        "plan": plan,
        "compat_billing_pay_claim_gate": compat_billing_pay_claim_gate,
        "cross_plane_claim_gate": cross_plane_claim_gate,
    }
    upstream_evidence = _billing_pay_upstream_evidence_for_request(
        request,
        since=delegation_started_at,
    )
    _publish_compat_billing_pay_event(
        request,
        stage="subscription_checkout_delegated",
        status="success",
        plan=plan,
        method=method,
        current_user=current_user,
        delegated_to_billing=True,
        checkout_url_present=bool(checkout_url),
        result_summary=_billing_pay_result_summary_for_evidence(response_payload),
        upstream_evidence=upstream_evidence,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="delegated_checkout_created",
    )

    return response_payload
