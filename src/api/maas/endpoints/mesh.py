"""
MaaS Mesh Endpoints - Mesh lifecycle management.

Provides REST API endpoints for mesh deployment, scaling, and termination.
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import MeshInstance as DBMeshInstance, User as DBUser, get_db
from src.mesh.metric_evidence_policy import latest_mesh_metric_policy_evidence

from ..auth import UserContext, get_current_user, require_mesh_access
from ..models import (
    MeshDeployRequest,
    MeshDeployResponse,
    MeshMetricsResponse,
    MeshScaleRequest,
    MeshStatusResponse,
)
from ..registry import get_all_meshes, get_mesh, get_audit_log, get_mapek_events
from ..services import MeshProvisioner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mesh"])


# Service instance (can be overridden for testing)
_provisioner: Optional[MeshProvisioner] = None

_MODULAR_MESH_DEPLOY_SOURCE_AGENT = "maas-modular-mesh-deploy"
_MODULAR_MESH_READ_SOURCE_AGENT = "maas-modular-mesh-read"
_MODULAR_MESH_SCALE_SOURCE_AGENT = "maas-modular-mesh-scale"
_MODULAR_MESH_TERMINATE_SOURCE_AGENT = "maas-modular-mesh-terminate"
_MODULAR_MESH_DEPLOY_LAYER = "api_modular_mesh_deploy_control_action"
_MODULAR_MESH_READ_LAYER = "api_modular_mesh_lifecycle_observed_state"
_MODULAR_MESH_SCALE_LAYER = "api_modular_mesh_scale_control_action"
_MODULAR_MESH_TERMINATE_LAYER = "api_modular_mesh_terminate_control_action"
_MODULAR_MESH_CLAIM_BOUNDARY = (
    "Modular MaaS mesh endpoint evidence only. It records local request "
    "metadata, access checks, provisioner calls, in-memory registry reads or "
    "mutations, DB persistence attempts, audit-log reads, MAPE-K event-stream "
    "reads, duration, and bounded output shape; it does not prove external "
    "node deployment, live dataplane reachability, agent enrollment, durable "
    "infrastructure convergence, autonomous remediation completion, or that a "
    "join token was consumed."
)
_MESH_DEPLOY_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_MESH_DEPLOY_RESPONSE_CLAIM_BOUNDARY = (
    "MaaS modular mesh deploy responses expose local API handling, local "
    "provisioner invocation, local DB persistence, returned join material, and "
    "bounded lifecycle evidence only. A 200 response, active status, dashboard "
    "URL, join token, DB row, or provisioner gate propagation does not prove "
    "external node deployment, node dataplane join, node reachability, routing "
    "convergence, customer traffic, external DPI bypass, settlement finality, "
    "production SLOs, or production readiness."
)
_MESH_LIFECYCLE_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_MESH_LIFECYCLE_RESPONSE_CLAIM_BOUNDARY = (
    "MaaS modular mesh lifecycle responses expose local registry reads, local "
    "status aggregation, local provisioner control calls, local registry "
    "mutations, duration, return-code, and bounded output shape only. Listed "
    "meshes, status health scores, scale success, or terminate success do not "
    "prove external infrastructure convergence, node dataplane join, node "
    "reachability, routing convergence, customer traffic, external DPI bypass, "
    "settlement finality, production SLOs, or production readiness."
)
_MESH_READ_LIST_CLAIM_BOUNDARY = (
    "MaaS modular mesh audit and MAPE-K list responses expose local audit-log "
    "or local MAPE-K event-stream reads only. Returned audit entries, returned "
    "MAPE-K events, phase counts, timestamps, actor mentions, node mentions, "
    "and metric-key mentions do not prove autonomous remediation completion, "
    "external infrastructure convergence, restored dataplane, node reachability, "
    "routing convergence, customer traffic, external DPI bypass, settlement "
    "finality, production SLOs, or production readiness."
)
_MESH_READ_LIST_CLAIM_HEADERS = {
    "X-x0tta6bl4-Claim-Gate-Schema": (
        "x0tta6bl4.maas_mesh_read_list_claim_boundary_headers.v1"
    ),
    "X-x0tta6bl4-Claim-Boundary": _MESH_READ_LIST_CLAIM_BOUNDARY,
    "X-x0tta6bl4-Local-Audit-Log-Observation-Claim-Allowed": "true",
    "X-x0tta6bl4-Local-MAPE-K-Event-Observation-Claim-Allowed": "true",
    "X-x0tta6bl4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-x0tta6bl4-External-Infrastructure-Convergence-Claim-Allowed": "false",
    "X-x0tta6bl4-Restored-Dataplane-Claim-Allowed": "false",
    "X-x0tta6bl4-Node-Reachability-Claim-Allowed": "false",
    "X-x0tta6bl4-Routing-Convergence-Claim-Allowed": "false",
    "X-x0tta6bl4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-x0tta6bl4-Traffic-Delivery-Claim-Allowed": "false",
    "X-x0tta6bl4-Customer-Traffic-Claim-Allowed": "false",
    "X-x0tta6bl4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-x0tta6bl4-Settlement-Finality-Claim-Allowed": "false",
    "X-x0tta6bl4-Production-SLO-Claim-Allowed": "false",
    "X-x0tta6bl4-Production-Readiness-Claim-Allowed": "false",
}
_MESH_METRICS_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_MESH_METRICS_CLAIM_BOUNDARY = (
    "MaaS mesh metrics responses expose local registry, local MAPE-K, local "
    "consciousness, local network-metric, and local control-policy observations "
    "only. Latency, throughput, health, harmony, phase, or policy fields do not "
    "prove production readiness, production SLOs, dataplane delivery, customer "
    "traffic, external DPI bypass, or settlement finality."
)


def _mesh_deploy_claim_gate(
    *,
    provisioner_call_committed: bool,
    db_write_committed: bool,
    response_created: bool,
    provisioner_claim_gate_present: bool,
    provisioner_cross_plane_claim_gate_present: bool,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_mesh_deploy_claim_gate.v1",
        "surface": "maas_mesh.deploy",
        "local_api_deploy_request_claim_allowed": bool(response_created),
        "local_mesh_provisioner_invocation_claim_allowed": bool(
            provisioner_call_committed
        ),
        "local_db_persistence_claim_allowed": bool(db_write_committed),
        "local_join_material_returned_claim_allowed": bool(response_created),
        "provisioner_claim_gate_present": bool(provisioner_claim_gate_present),
        "provisioner_cross_plane_claim_gate_present": bool(
            provisioner_cross_plane_claim_gate_present
        ),
        "external_infrastructure_provisioning_claim_allowed": False,
        "external_node_deployment_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": _MESH_DEPLOY_RESPONSE_CLAIM_BOUNDARY,
    }


def _mesh_deploy_cross_plane_gate() -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        _MESH_DEPLOY_CROSS_PLANE_CLAIMS,
        surface="maas_mesh.deploy",
    )


def _mesh_lifecycle_claim_gate(
    surface: str,
    *,
    read_only: bool,
    control_action: bool,
    registry_mutation_committed: bool = False,
    provisioner_call_committed: bool = False,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_mesh_lifecycle_claim_gate.v1",
        "surface": surface,
        "local_mesh_registry_read_claim_allowed": bool(read_only),
        "local_mesh_status_observation_claim_allowed": bool(read_only),
        "local_mesh_control_action_claim_allowed": bool(control_action),
        "local_mesh_registry_mutation_claim_allowed": bool(
            registry_mutation_committed
        ),
        "local_mesh_provisioner_invocation_claim_allowed": bool(
            provisioner_call_committed
        ),
        "external_infrastructure_convergence_claim_allowed": False,
        "external_node_deployment_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": _MESH_LIFECYCLE_RESPONSE_CLAIM_BOUNDARY,
    }


def _mesh_lifecycle_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        _MESH_LIFECYCLE_CROSS_PLANE_CLAIMS,
        surface=surface,
    )


def _mesh_read_list_claim_boundary_headers(surface: str) -> Dict[str, str]:
    headers = dict(_MESH_READ_LIST_CLAIM_HEADERS)
    headers["X-X0TTA6BL4-Claim-Surface"] = surface
    return headers


def _set_mesh_read_list_claim_headers(
    response: Optional[Response],
    *,
    surface: str,
) -> None:
    if response is None:
        return
    response.headers.update(_mesh_read_list_claim_boundary_headers(surface))


def _mesh_read_list_claim_boundary_summary(surface: str) -> Dict[str, Any]:
    headers = _mesh_read_list_claim_boundary_headers(surface)
    return {
        "mesh_read_list_claim_boundary_headers_present": True,
        "claim_surface": surface,
        "claim_header_count": len(headers),
        "local_audit_log_observation_claim_allowed": (
            headers[
                "X-X0TTA6BL4-Local-Audit-Log-Observation-Claim-Allowed"
            ]
            == "true"
        ),
        "local_mapek_event_observation_claim_allowed": (
            headers[
                "X-X0TTA6BL4-Local-MAPE-K-Event-Observation-Claim-Allowed"
            ]
            == "true"
        ),
        "autonomous_remediation_completion_claim_allowed": False,
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


def _mesh_metrics_claim_gate() -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_mesh_metrics_claim_gate.v1",
        "surface": "maas_mesh.metrics",
        "local_mesh_metrics_observation_claim_allowed": True,
        "local_mape_k_observation_claim_allowed": True,
        "local_control_policy_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "claim_boundary": _MESH_METRICS_CLAIM_BOUNDARY,
    }


def get_provisioner() -> MeshProvisioner:
    """Get or create the mesh provisioner."""
    global _provisioner
    if _provisioner is None:
        _provisioner = MeshProvisioner()
    return _provisioner


def _maas_control_policy_evidence() -> Dict[str, Any]:
    try:
        return latest_mesh_metric_policy_evidence(get_event_bus("."))
    except Exception:
        return latest_mesh_metric_policy_evidence(None)


def _mesh_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize modular MaaS mesh EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _safe_count(value: Any, *, max_value: int = 1_000_000) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return min(int(value), max_value)
    return None


def _safe_float(value: Any, *, max_value: float = 1_000_000_000.0) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return round(min(float(value), max_value), 3)
    return None


def _plan_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"free", "starter", "pro", "enterprise"} else "other"


def _obfuscation_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"none", "xor", "aes"} else "other"


def _traffic_profile_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"none", "gaming", "streaming", "voip"} else "other"


def _optimization_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"standard", "ml_routing", "genetic_topo"} else "other"


def _federated_strategy_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"fedavg", "hw_fedavg"} else "other"


def _mesh_status_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {
        "access_denied",
        "active",
        "available",
        "degraded",
        "failed",
        "not_found",
        "persistence_failed",
        "provisioning",
        "scaling",
        "success",
        "terminated",
        "validation_failed",
    }:
        return text
    return "unknown" if not text else "other"


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


def _claim_gate_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _attach_mesh_lifecycle_gates(
    result: Any,
    *,
    surface: str,
    read_only: bool,
    control_action: bool,
    registry_mutation_committed: bool = False,
    provisioner_call_committed: bool = False,
) -> Dict[str, Any]:
    response = dict(result) if isinstance(result, dict) else {
        "payload_type": type(result).__name__[:40],
        "status": _mesh_status_bucket(getattr(result, "status", None)),
    }
    response["mesh_lifecycle_claim_gate"] = _mesh_lifecycle_claim_gate(
        surface,
        read_only=read_only,
        control_action=control_action,
        registry_mutation_committed=registry_mutation_committed,
        provisioner_call_committed=provisioner_call_committed,
    )
    response["cross_plane_claim_gate"] = _mesh_lifecycle_cross_plane_gate(surface)
    return response


def _deploy_request_summary(request: MeshDeployRequest) -> Dict[str, Any]:
    return {
        "payload_type": "MeshDeployRequest",
        "mesh_name_present": bool(request.name),
        "nodes": _safe_count(request.nodes),
        "plan": _plan_bucket(request.billing_plan),
        "pqc_enabled": bool(request.pqc_enabled),
        "obfuscation": _obfuscation_bucket(request.obfuscation),
        "traffic_profile": _traffic_profile_bucket(request.traffic_profile),
        "optimization_mode": _optimization_bucket(request.optimization_mode),
        "federated_strategy": _federated_strategy_bucket(request.federated_strategy),
        "join_token_ttl_sec": _safe_count(request.join_token_ttl_sec),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_response_summary(response: Any) -> Dict[str, Any]:
    data = _model_dict_for_evidence(response)
    join_config = data.get("join_config") if isinstance(data.get("join_config"), dict) else {}
    pqc_identity = (
        data.get("pqc_identity") if isinstance(data.get("pqc_identity"), dict) else {}
    )
    deploy_claim_gate = _claim_gate_dict(data.get("mesh_deploy_claim_gate"))
    provisioner_claim_gate = _claim_gate_dict(data.get("mesh_provisioner_claim_gate"))
    provisioner_cross_plane_claim_gate = _claim_gate_dict(
        data.get("provisioner_cross_plane_claim_gate")
    )
    cross_plane_claim_gate = _claim_gate_dict(data.get("cross_plane_claim_gate"))
    return {
        "payload_type": type(response).__name__[:40],
        "payload_field_count": len(data),
        "mesh_id_present": bool(data.get("mesh_id")),
        "status": _mesh_status_bucket(data.get("status")),
        "join_token_present": bool(join_config.get("enrollment_token")),
        "join_token_ttl_sec": _safe_count(join_config.get("ttl_sec")),
        "dashboard_url_present": bool(data.get("dashboard_url")),
        "pqc_enabled": data.get("pqc_enabled") if isinstance(data.get("pqc_enabled"), bool) else None,
        "pqc_identity_field_count": len(pqc_identity),
        "plan": _plan_bucket(data.get("plan")),
        "join_token_expires_at_present": bool(data.get("join_token_expires_at")),
        "mesh_deploy_claim_gate_present": bool(deploy_claim_gate),
        "mesh_provisioner_claim_gate_present": bool(provisioner_claim_gate),
        "provisioner_cross_plane_claim_gate_present": bool(
            provisioner_cross_plane_claim_gate
        ),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "dataplane_delivery_claim_allowed": (
            deploy_claim_gate.get("dataplane_delivery_claim_allowed")
            if isinstance(
                deploy_claim_gate.get("dataplane_delivery_claim_allowed"), bool
            )
            else None
        ),
        "external_node_deployment_claim_allowed": (
            deploy_claim_gate.get("external_node_deployment_claim_allowed")
            if isinstance(
                deploy_claim_gate.get("external_node_deployment_claim_allowed"), bool
            )
            else None
        ),
        "production_readiness_claim_allowed": (
            deploy_claim_gate.get("production_readiness_claim_allowed")
            if isinstance(
                deploy_claim_gate.get("production_readiness_claim_allowed"), bool
            )
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_status_summary(response: Any) -> Dict[str, Any]:
    data = _model_dict_for_evidence(response)
    peers = data.get("peers") if isinstance(data.get("peers"), list) else []
    control_policy = (
        data.get("control_policy_evidence")
        if isinstance(data.get("control_policy_evidence"), dict)
        else {}
    )
    claim_gate = _claim_gate_dict(data.get("mesh_lifecycle_claim_gate"))
    cross_plane_claim_gate = _claim_gate_dict(data.get("cross_plane_claim_gate"))
    return {
        "payload_type": type(response).__name__[:40],
        "payload_field_count": len(data),
        "mesh_id_present": bool(data.get("mesh_id")),
        "status": _mesh_status_bucket(data.get("status")),
        "nodes_total": _safe_count(data.get("nodes_total")),
        "nodes_healthy": _safe_count(data.get("nodes_healthy")),
        "peer_count": len(peers),
        "health_score": _safe_float(data.get("health_score"), max_value=1.0),
        "control_policy_evidence_present": bool(control_policy),
        "control_policy_evidence_field_count": len(control_policy),
        "mesh_lifecycle_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "dataplane_delivery_claim_allowed": (
            claim_gate.get("dataplane_delivery_claim_allowed")
            if isinstance(claim_gate.get("dataplane_delivery_claim_allowed"), bool)
            else None
        ),
        "external_node_deployment_claim_allowed": (
            claim_gate.get("external_node_deployment_claim_allowed")
            if isinstance(
                claim_gate.get("external_node_deployment_claim_allowed"), bool
            )
            else None
        ),
        "production_readiness_claim_allowed": (
            claim_gate.get("production_readiness_claim_allowed")
            if isinstance(claim_gate.get("production_readiness_claim_allowed"), bool)
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_metrics_summary(response: Any) -> Dict[str, Any]:
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
    claim_gate = (
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
        "payload_type": type(response).__name__[:40],
        "payload_field_count": len(data),
        "mesh_id_present": bool(data.get("mesh_id")),
        "consciousness_metric_count": len(consciousness),
        "mape_k_metric_count": len(mape_k),
        "network_metric_count": len(network),
        "control_policy_evidence_present": bool(control_policy),
        "control_policy_evidence_field_count": len(control_policy),
        "mesh_metrics_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "production_readiness_claim_allowed": (
            claim_gate.get("production_readiness_claim_allowed")
            if isinstance(
                claim_gate.get("production_readiness_claim_allowed"), bool
            )
            else None
        ),
        "dataplane_delivery_claim_allowed": (
            claim_gate.get("dataplane_delivery_claim_allowed")
            if isinstance(claim_gate.get("dataplane_delivery_claim_allowed"), bool)
            else None
        ),
        "external_dpi_bypass_claim_allowed": (
            claim_gate.get("external_dpi_bypass_claim_allowed")
            if isinstance(claim_gate.get("external_dpi_bypass_claim_allowed"), bool)
            else None
        ),
        "timestamp_present": bool(data.get("timestamp")),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_result_summary(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "payload_type": type(result).__name__[:40],
            "payload_field_count": None,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    claim_gate = _claim_gate_dict(result.get("mesh_lifecycle_claim_gate"))
    cross_plane_claim_gate = _claim_gate_dict(result.get("cross_plane_claim_gate"))
    return {
        "payload_type": "dict",
        "payload_field_count": len(result),
        "status": _mesh_status_bucket(result.get("status")),
        "mesh_id_present": bool(result.get("mesh_id")),
        "actor_present": bool(result.get("actor")),
        "target_count": _safe_count(result.get("target_count")),
        "previous_nodes": _safe_count(result.get("previous_nodes")),
        "current_nodes": _safe_count(result.get("current_nodes")),
        "reason_present": bool(result.get("reason")),
        "mesh_lifecycle_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "dataplane_delivery_claim_allowed": (
            claim_gate.get("dataplane_delivery_claim_allowed")
            if isinstance(claim_gate.get("dataplane_delivery_claim_allowed"), bool)
            else None
        ),
        "external_node_deployment_claim_allowed": (
            claim_gate.get("external_node_deployment_claim_allowed")
            if isinstance(
                claim_gate.get("external_node_deployment_claim_allowed"), bool
            )
            else None
        ),
        "production_readiness_claim_allowed": (
            claim_gate.get("production_readiness_claim_allowed")
            if isinstance(claim_gate.get("production_readiness_claim_allowed"), bool)
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_current_node_count(instance: Any) -> int:
    value = getattr(instance, "target_nodes", None)
    if value is None:
        value = getattr(instance, "nodes", None)
    if value is None:
        value = len(getattr(instance, "mesh_nodes", []) or [])
    return max(1, _safe_count(value) or 1)


def _resolve_scale_target_count(request: MeshScaleRequest, instance: Any) -> int:
    if request.target_count is not None:
        return request.target_count

    current = _mesh_current_node_count(instance)
    delta = request.count or 1
    if request.action == "scale_down":
        return max(1, current - delta)

    plan = str(getattr(instance, "plan", None) or "starter").lower()
    max_nodes = {
        "free": 3,
        "starter": 3,
        "pilot": 3,
        "pro": 20,
        "enterprise": 100,
    }.get(plan, 3)
    return min(1000, max_nodes, current + delta)


def _mesh_list_summary(responses: List[MeshStatusResponse]) -> Dict[str, Any]:
    total_nodes = 0
    healthy_nodes = 0
    status_counts: Dict[str, int] = {}
    lifecycle_claim_gate_count = 0
    cross_plane_claim_gate_count = 0
    for response in responses:
        data = _model_dict_for_evidence(response)
        total_nodes += int(data.get("nodes_total") or 0)
        healthy_nodes += int(data.get("nodes_healthy") or 0)
        status_value = _mesh_status_bucket(data.get("status"))
        status_counts[status_value] = status_counts.get(status_value, 0) + 1
        lifecycle_claim_gate_count += int(
            isinstance(data.get("mesh_lifecycle_claim_gate"), dict)
            and bool(data.get("mesh_lifecycle_claim_gate"))
        )
        cross_plane_claim_gate_count += int(
            isinstance(data.get("cross_plane_claim_gate"), dict)
            and bool(data.get("cross_plane_claim_gate"))
        )
    return {
        "payload_type": "list",
        "mesh_count": len(responses),
        "total_nodes": total_nodes,
        "healthy_nodes": healthy_nodes,
        "status_counts": status_counts,
        "mesh_lifecycle_claim_gate_count": lifecycle_claim_gate_count,
        "cross_plane_claim_gate_count": cross_plane_claim_gate_count,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _audit_log_summary(
    log: Any,
    *,
    returned_count: int,
    limit: int,
    claim_surface: str = "maas_mesh.audit",
) -> Dict[str, Any]:
    stored_count = len(log) if isinstance(log, list) else None
    known_events = {"deploy", "scale", "terminate", "node_join", "node_leave"}
    event_counts: Dict[str, int] = {}
    timestamp_mentions = 0
    actor_mentions = 0
    if isinstance(log, list):
        for entry in log[-limit:]:
            if not isinstance(entry, dict):
                continue
            event_name = str(entry.get("event") or entry.get("action") or "").lower()
            bucket = event_name if event_name in known_events else "other"
            event_counts[bucket] = event_counts.get(bucket, 0) + 1
            if entry.get("timestamp"):
                timestamp_mentions += 1
            if entry.get("actor"):
                actor_mentions += 1
    return {
        "payload_type": "list" if isinstance(log, list) else type(log).__name__[:40],
        "stored_event_count": stored_count,
        "returned_event_count": returned_count,
        "limit_requested": _safe_count(limit),
        "event_counts": event_counts,
        "timestamp_mentions": timestamp_mentions,
        "actor_mentions": actor_mentions,
        **_mesh_read_list_claim_boundary_summary(claim_surface),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mapek_events_summary(
    events: Any,
    *,
    returned_count: int,
    limit: int,
    claim_surface: str = "maas_mesh.mapek",
) -> Dict[str, Any]:
    stored_count = len(events) if isinstance(events, list) else None
    known_phases = {"MONITOR", "ANALYZE", "PLAN", "EXECUTE"}
    phase_counts: Dict[str, int] = {}
    timestamp_mentions = 0
    node_id_mentions = 0
    known_metric_mentions = 0
    if isinstance(events, list):
        for event in events[-limit:]:
            if not isinstance(event, dict):
                continue
            phase = str(event.get("phase") or "unknown").upper()
            bucket = phase if phase in known_phases else "other"
            phase_counts[bucket] = phase_counts.get(bucket, 0) + 1
            if event.get("timestamp"):
                timestamp_mentions += 1
            if event.get("node_id"):
                node_id_mentions += 1
            known_metric_mentions += sum(
                1
                for field_name in ("cpu", "memory", "latency_ms", "loss_rate")
                if field_name in event
            )
    return {
        "payload_type": "list" if isinstance(events, list) else type(events).__name__[:40],
        "stored_event_count": stored_count,
        "returned_event_count": returned_count,
        "limit_requested": _safe_count(limit),
        "phase_counts": phase_counts,
        "timestamp_mentions": timestamp_mentions,
        "node_id_mentions": node_id_mentions,
        "known_metric_mentions": known_metric_mentions,
        **_mesh_read_list_claim_boundary_summary(claim_surface),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _control_policy_evidence_summary(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return {
            "present": False,
            "payloads_redacted": True,
        }
    policy = (
        evidence.get("mesh_metric_evidence_policy")
        if isinstance(evidence.get("mesh_metric_evidence_policy"), dict)
        else {}
    )
    return {
        "present": bool(evidence),
        "status": _mesh_status_bucket(evidence.get("status")),
        "events_total": _safe_count(evidence.get("events_total")),
        "source_agents_count": (
            len(evidence.get("source_agents"))
            if isinstance(evidence.get("source_agents"), list)
            else None
        ),
        "event_ids_count": (
            len(evidence.get("event_ids"))
            if isinstance(evidence.get("event_ids"), list)
            else None
        ),
        "decision_basis": str(policy.get("decision_basis") or "")[:80] or None,
        "redacted": bool(evidence.get("redacted")),
        "payloads_redacted": True,
    }


def _mesh_event_source_quality(operation: str, status_value: str) -> str:
    if operation == "deploy_mesh":
        if status_value == "success":
            return "local_mesh_deployment_recorded"
        if status_value == "persistence_failed":
            return "local_mesh_deployment_db_persist_failed"
        return "local_mesh_deployment_failed_before_commit"
    if operation == "scale_mesh":
        return (
            "local_mesh_scale_control_action"
            if status_value == "success"
            else "local_mesh_scale_failed"
        )
    if operation == "terminate_mesh":
        return (
            "local_mesh_terminate_control_action"
            if status_value == "success"
            else "local_mesh_terminate_failed"
        )
    if operation == "list_meshes":
        return "local_mesh_list_observed_state"
    if operation == "get_mesh_status":
        return (
            "local_mesh_status_observed_state"
            if status_value == "success"
            else "local_mesh_status_read_failed"
        )
    if operation == "get_mesh_metrics":
        return (
            "local_mesh_metrics_observed_state"
            if status_value == "success"
            else "local_mesh_metrics_read_failed"
        )
    if operation == "get_mesh_audit":
        return (
            "local_mesh_audit_log_observed_state"
            if status_value == "success"
            else "local_mesh_audit_log_read_failed"
        )
    if operation == "get_mesh_mapek":
        return (
            "local_mesh_mapek_event_observed_state"
            if status_value == "success"
            else "local_mesh_mapek_event_read_failed"
        )
    return "modular_mesh_local_event"


def _mesh_lifecycle_evidence(
    *,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    http_status_code: int,
    result_summary: Dict[str, Any],
    read_only: bool,
    registry_mutation_attempted: bool = False,
    registry_mutation_committed: bool = False,
    db_write_attempted: bool = False,
    db_write_committed: bool = False,
    provisioner_call_attempted: bool = False,
    provisioner_call_committed: bool = False,
    control_policy_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    source_quality = _mesh_event_source_quality(operation, status_value)
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "stage": stage,
        "operation": operation,
        "duration_ms": round(duration_ms, 3),
        "return_code": http_status_code,
        "http_status_code": http_status_code,
        "read_only": read_only,
        "observed_state": read_only,
        "dataplane_confirmed": False,
        "external_node_deployment_confirmed": False,
        "agent_enrollment_confirmed": False,
        "join_token_consumed": False,
        "durable_infrastructure_convergence_confirmed": False,
        "mapek_remediation_confirmed": False,
        "provisioner_call": {
            "attempted": provisioner_call_attempted,
            "committed": provisioner_call_committed,
            "payloads_redacted": True,
        },
        "registry_mutation": {
            "attempted": registry_mutation_attempted,
            "committed": registry_mutation_committed,
            "payloads_redacted": True,
        },
        "db_write_evidence": {
            "storage_backend": "maas_mesh_instance_db",
            "attempted": db_write_attempted,
            "committed": db_write_committed,
            "payloads_redacted": True,
        },
        "control_policy_evidence_summary": _control_policy_evidence_summary(
            control_policy_evidence
        ),
        "output_summary": {
            **result_summary,
            "status": status_value,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_modular_mesh_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    http_status_code: int,
    user: UserContext | None = None,
    mesh_id: str | None = None,
    owner_id: str | None = None,
    requested_nodes: int | None = None,
    target_nodes: int | None = None,
    plan: str | None = None,
    result_summary: Dict[str, Any] | None = None,
    control_policy_evidence: Dict[str, Any] | None = None,
    reason: str = "",
    read_only: bool = False,
    control_action: bool = True,
    registry_mutation_attempted: bool = False,
    registry_mutation_committed: bool = False,
    db_write_attempted: bool = False,
    db_write_committed: bool = False,
    provisioner_call_attempted: bool = False,
    provisioner_call_committed: bool = False,
    event_type: EventType = EventType.PIPELINE_STAGE_END,
) -> str | None:
    event_bus = _mesh_event_bus_from_request(request)
    if event_bus is None:
        return None
    result = result_summary or {}
    lifecycle_evidence = _mesh_lifecycle_evidence(
        operation=operation,
        stage=stage,
        status_value=status_value,
        duration_ms=duration_ms,
        http_status_code=http_status_code,
        result_summary=result,
        read_only=read_only,
        registry_mutation_attempted=registry_mutation_attempted,
        registry_mutation_committed=registry_mutation_committed,
        db_write_attempted=db_write_attempted,
        db_write_committed=db_write_committed,
        provisioner_call_attempted=provisioner_call_attempted,
        provisioner_call_committed=provisioner_call_committed,
        control_policy_evidence=control_policy_evidence,
    )
    payload = {
        "component": "api.maas.endpoints.mesh",
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "operation": operation,
        "stage": stage,
        "status": status_value,
        "duration_ms": round(duration_ms, 3),
        "return_code": http_status_code,
        "http_status_code": http_status_code,
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "user_id", None)),
        "owner_id_hash": _redacted_sha256_prefix(owner_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "mesh_id_present": bool(mesh_id),
        "owner_id_present": bool(owner_id),
        "requested_nodes": _safe_count(requested_nodes),
        "target_nodes": _safe_count(target_nodes),
        "plan": _plan_bucket(plan),
        "source_quality": lifecycle_evidence["source_quality"],
        "mesh_lifecycle_evidence": lifecycle_evidence,
        "result_summary": result,
        "control_policy_evidence_summary": _control_policy_evidence_summary(
            control_policy_evidence
        ),
        "control_action": control_action,
        "read_only": read_only,
        "observed_state": read_only,
        "dataplane_confirmed": False,
        "external_node_deployment_confirmed": False,
        "agent_enrollment_confirmed": False,
        "raw_identifiers_redacted": True,
        "raw_mesh_name_redacted": True,
        "raw_join_token_redacted": True,
        "raw_audit_payload_redacted": True,
        "raw_mapek_payload_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _MODULAR_MESH_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, source_agent, payload, priority=6)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS mesh event: %s", exc)
        return None


async def _resolve_mesh_for_user(mesh_id: str, user: UserContext) -> Any:
    """
    Resolve mesh instance and validate access.

    This keeps compatibility with tests that patch `get_mesh` in this module,
    while preserving ACL checks for non-owner access in real runtime.
    """
    instance = get_mesh(mesh_id)
    if instance is None:
        await require_mesh_access(mesh_id, user)
        instance = get_mesh(mesh_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mesh {mesh_id} not found",
            )

    if instance.owner_id != user.id:
        await require_mesh_access(mesh_id, user)

    return instance


def _build_mesh_status_response(
    instance: Any,
    *,
    control_policy_evidence: Optional[Dict[str, Any]] = None,
    claim_surface: str = "maas_mesh.status",
) -> MeshStatusResponse:
    """Convert mesh instance-like object into MeshStatusResponse."""
    nodes = getattr(instance, "node_instances", {}) or {}
    nodes_total = len(nodes)

    if hasattr(instance, "get_uptime") and callable(instance.get_uptime):
        uptime_seconds = float(instance.get_uptime())
    else:
        created_at = getattr(instance, "created_at", None)
        if created_at and hasattr(created_at, "__sub__"):
            uptime_seconds = max((datetime.utcnow() - created_at).total_seconds(), 0.0)
        else:
            uptime_seconds = 0.0

    if hasattr(instance, "get_health_score") and callable(instance.get_health_score):
        health_score = float(instance.get_health_score())
    else:
        health_score = 1.0 if nodes_total > 0 else 0.0

    nodes_healthy = 0
    peers: List[Dict[str, Any]] = []
    for node_id, node_data in nodes.items():
        node_status = (
            node_data.get("status")
            if isinstance(node_data, dict)
            else getattr(node_data, "status", "healthy")
        )
        if node_status == "healthy":
            nodes_healthy += 1
        peers.append({
            "node_id": str(node_id),
            "status": node_status or "unknown",
        })

    return MeshStatusResponse(
        mesh_id=instance.mesh_id,
        status=instance.status,
        nodes_total=nodes_total,
        nodes_healthy=nodes_healthy,
        uptime_seconds=uptime_seconds,
        pqc_enabled=bool(getattr(instance, "pqc_enabled", True)),
        obfuscation=str(getattr(instance, "obfuscation", "none")),
        traffic_profile=str(getattr(instance, "traffic_profile", "none")),
        peers=peers,
        health_score=max(0.0, min(1.0, health_score)),
        control_policy_evidence=control_policy_evidence or {},
        mesh_lifecycle_claim_gate=_mesh_lifecycle_claim_gate(
            claim_surface,
            read_only=True,
            control_action=False,
        ),
        cross_plane_claim_gate=_mesh_lifecycle_cross_plane_gate(claim_surface),
    )


@router.post(
    "/deploy",
    response_model=MeshDeployResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deploy a new mesh network",
    description="Create and deploy a new PQC-secured mesh network.",
)
async def deploy_mesh(
    request: MeshDeployRequest,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> MeshDeployResponse:
    """
    Deploy a new mesh network.

    Requires authentication. Plan limits apply to node count.
    """
    started = time.monotonic()
    provisioner = get_provisioner()

    try:
        instance = await provisioner.provision_mesh(
            owner_id=user.id,
            name=request.name,
            nodes=request.nodes,
            billing_plan=request.billing_plan,
            pqc_enabled=request.pqc_enabled,
            obfuscation=request.obfuscation,
            traffic_profile=request.traffic_profile,
            join_token_ttl_sec=request.join_token_ttl_sec,
        )

        # Persist to real DB so dashboard can see it
        try:
            db_mesh = DBMeshInstance(
                id=instance.mesh_id,
                name=instance.name,
                owner_id=instance.owner_id,
                plan=instance.plan,
                region=getattr(instance, "region", None) or "global",
                nodes=getattr(instance, "target_nodes", None) or request.nodes,
                pqc_profile=getattr(instance, "pqc_profile", None) or "edge",
                status=instance.status,
                join_token=instance.join_token,
                join_token_expires_at=instance.join_token_expires_at,
                pqc_enabled=getattr(instance, "pqc_enabled", request.pqc_enabled),
                obfuscation=getattr(instance, "obfuscation", request.obfuscation),
                traffic_profile=getattr(instance, "traffic_profile", request.traffic_profile),
            )
            db.add(db_mesh)
            # P1 Q2: Update user's plan in real DB
            try:
                db_user = db.query(DBUser).filter(DBUser.id == user.id).first()
                if db_user:
                    db_user.plan = instance.plan
            except Exception as user_err:
                logger.warning(f"Failed to update user plan in DB: {user_err}")

            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"Failed to persist mesh {instance.mesh_id} to DB: {db_err}")
            # Rollback in-memory creation to maintain consistency
            from ..registry import _mesh_registry, _registry_lock
            async with _registry_lock:
                _mesh_registry.pop(instance.mesh_id, None)
            _publish_modular_mesh_event(
                http_request,
                source_agent=_MODULAR_MESH_DEPLOY_SOURCE_AGENT,
                layer=_MODULAR_MESH_DEPLOY_LAYER,
                operation="deploy_mesh",
                stage="mesh_db_persist",
                status_value="persistence_failed",
                duration_ms=(time.monotonic() - started) * 1000,
                http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                user=user,
                mesh_id=getattr(instance, "mesh_id", None),
                owner_id=getattr(instance, "owner_id", None),
                requested_nodes=request.nodes,
                target_nodes=getattr(instance, "target_nodes", None) or request.nodes,
                plan=request.billing_plan,
                result_summary={
                    **_deploy_request_summary(request),
                    "mesh_id_present": bool(getattr(instance, "mesh_id", None)),
                    "db_error_type": db_err.__class__.__name__[:80],
                },
                reason="db_persistence_error",
                registry_mutation_attempted=True,
                registry_mutation_committed=False,
                db_write_attempted=True,
                db_write_committed=False,
                provisioner_call_attempted=True,
                provisioner_call_committed=True,
                event_type=EventType.TASK_FAILED,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Mesh creation failed - database persistence error. Please contact support.",
            )

        expires_at = getattr(instance, "join_token_expires_at", None)
        if expires_at and hasattr(expires_at, "isoformat"):
            expires_at_str = expires_at.isoformat()
        else:
            expires_at_str = ""

        provisioner_claim_gate = _claim_gate_dict(
            getattr(instance, "mesh_provisioner_claim_gate", None)
        )
        provisioner_cross_plane_claim_gate = _claim_gate_dict(
            getattr(instance, "cross_plane_claim_gate", None)
        )
        response = MeshDeployResponse(
            mesh_id=instance.mesh_id,
            join_config={
                "enrollment_token": str(getattr(instance, "join_token", "")),
                "token": str(getattr(instance, "join_token", "")),
                "ttl_sec": request.join_token_ttl_sec,
            },
            dashboard_url=f"/api/v1/maas/mesh/{instance.mesh_id}/status",
            status=instance.status,
            pqc_identity={
                "enabled": bool(getattr(instance, "pqc_enabled", request.pqc_enabled)),
                "did": f"did:x0t:{instance.mesh_id}",
                "profile": str(getattr(instance, "pqc_profile", "edge")),
                "keys": {
                    "sig_alg": "ML-DSA-65",
                    "kem_alg": "ML-KEM-768",
                },
            },
            pqc_enabled=bool(getattr(instance, "pqc_enabled", request.pqc_enabled)),
            created_at=(
                instance.created_at.isoformat()
                if getattr(instance, "created_at", None)
                else datetime.utcnow().isoformat()
            ),
            plan=str(getattr(instance, "plan", request.billing_plan)),
            join_token_expires_at=expires_at_str,
            mesh_deploy_claim_gate=_mesh_deploy_claim_gate(
                provisioner_call_committed=True,
                db_write_committed=True,
                response_created=True,
                provisioner_claim_gate_present=bool(provisioner_claim_gate),
                provisioner_cross_plane_claim_gate_present=bool(
                    provisioner_cross_plane_claim_gate
                ),
            ),
            mesh_provisioner_claim_gate=provisioner_claim_gate,
            provisioner_cross_plane_claim_gate=provisioner_cross_plane_claim_gate,
            cross_plane_claim_gate=_mesh_deploy_cross_plane_gate(),
        )
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_DEPLOY_SOURCE_AGENT,
            layer=_MODULAR_MESH_DEPLOY_LAYER,
            operation="deploy_mesh",
            stage="mesh_deploy",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            mesh_id=getattr(instance, "mesh_id", None),
            owner_id=getattr(instance, "owner_id", None),
            requested_nodes=request.nodes,
            target_nodes=getattr(instance, "target_nodes", None) or request.nodes,
            plan=str(getattr(instance, "plan", request.billing_plan)),
            result_summary={
                **_deploy_request_summary(request),
                **_mesh_response_summary(response),
            },
            reason="mesh_deploy_recorded",
            registry_mutation_attempted=True,
            registry_mutation_committed=True,
            db_write_attempted=True,
            db_write_committed=True,
            provisioner_call_attempted=True,
            provisioner_call_committed=True,
        )
        return response

    except ValueError as e:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_DEPLOY_SOURCE_AGENT,
            layer=_MODULAR_MESH_DEPLOY_LAYER,
            operation="deploy_mesh",
            stage="mesh_provision",
            status_value="validation_failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            requested_nodes=request.nodes,
            plan=request.billing_plan,
            result_summary=_deploy_request_summary(request),
            reason=e.__class__.__name__,
            registry_mutation_attempted=False,
            registry_mutation_committed=False,
            db_write_attempted=False,
            db_write_committed=False,
            provisioner_call_attempted=True,
            provisioner_call_committed=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy mesh: {e}")
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_DEPLOY_SOURCE_AGENT,
            layer=_MODULAR_MESH_DEPLOY_LAYER,
            operation="deploy_mesh",
            stage="mesh_provision",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user=user,
            requested_nodes=request.nodes,
            plan=request.billing_plan,
            result_summary={
                **_deploy_request_summary(request),
                "error_type": e.__class__.__name__[:80],
            },
            reason=e.__class__.__name__,
            registry_mutation_attempted=False,
            registry_mutation_committed=False,
            db_write_attempted=False,
            db_write_committed=False,
            provisioner_call_attempted=True,
            provisioner_call_committed=False,
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deploy mesh",
        )


@router.get(
    "/list",
    response_model=Dict[str, Any],
    summary="List user's meshes",
    description="Get all mesh networks owned by the authenticated user.",
)
async def list_meshes(
    user: UserContext = Depends(get_current_user),
    include_terminated: bool = Query(False, description="Include terminated meshes"),
    http_request: Request = None,
) -> Dict[str, Any]:
    """List all meshes owned by the user."""
    started = time.monotonic()
    all_meshes = get_all_meshes()

    user_meshes = [
        mesh for mesh in all_meshes.values()
        if mesh.owner_id == user.id
    ]

    if not include_terminated:
        user_meshes = [
            m for m in user_meshes
            if m.status != "terminated"
        ]

    responses = [
        _build_mesh_status_response(m, claim_surface="maas_mesh.list")
        for m in user_meshes
    ]
    summary = _mesh_list_summary(responses)
    _publish_modular_mesh_event(
        http_request,
        source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
        layer=_MODULAR_MESH_READ_LAYER,
        operation="list_meshes",
        stage="mesh_list_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        result_summary={
            **summary,
            "include_terminated": bool(include_terminated),
        },
        reason="mesh_list_observed",
        read_only=True,
        control_action=False,
    )
    return {
        "meshes": responses,
        "count": len(responses),
    }


@router.get(
    "/{mesh_id}/status",
    response_model=MeshStatusResponse,
    summary="Get mesh status",
    description="Get detailed status of a mesh network.",
)
async def get_mesh_status(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> MeshStatusResponse:
    """Get status of a specific mesh."""
    started = time.monotonic()
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
            layer=_MODULAR_MESH_READ_LAYER,
            operation="get_mesh_status",
            stage="mesh_status_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "access_check",
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    control_policy = _maas_control_policy_evidence()
    response = _build_mesh_status_response(
        instance,
        control_policy_evidence=control_policy,
    )
    _publish_modular_mesh_event(
        http_request,
        source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
        layer=_MODULAR_MESH_READ_LAYER,
        operation="get_mesh_status",
        stage="mesh_status_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        target_nodes=getattr(instance, "target_nodes", None),
        plan=getattr(instance, "plan", None),
        result_summary=_mesh_status_summary(response),
        control_policy_evidence=control_policy,
        reason="mesh_status_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.get(
    "/{mesh_id}/metrics",
    response_model=MeshMetricsResponse,
    summary="Get mesh metrics",
    description="Get consciousness and MAPE-K metrics for a mesh.",
)
async def get_mesh_metrics(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> MeshMetricsResponse:
    """Get consciousness and MAPE-K metrics for a mesh."""
    started = time.monotonic()
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
            layer=_MODULAR_MESH_READ_LAYER,
            operation="get_mesh_metrics",
            stage="mesh_metrics_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "access_check",
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    # Get metrics from instance
    if hasattr(instance, "get_consciousness_metrics") and callable(instance.get_consciousness_metrics):
        consciousness = instance.get_consciousness_metrics()
    else:
        status_snapshot = _build_mesh_status_response(instance)
        consciousness = {
            "phi_ratio": 1.0,
            "entropy": 1.0 - status_snapshot.health_score,
            "harmony": status_snapshot.health_score,
            "state": "AWARE",
            "nodes_total": status_snapshot.nodes_total,
            "nodes_healthy": status_snapshot.nodes_healthy,
        }

    if hasattr(instance, "get_mape_k_state") and callable(instance.get_mape_k_state):
        mape_k = instance.get_mape_k_state()
    else:
        mape_k = {"phase": "MONITOR", "interval_seconds": 30, "directives": {}}

    if hasattr(instance, "get_network_metrics") and callable(instance.get_network_metrics):
        network = instance.get_network_metrics()
    else:
        status_snapshot = _build_mesh_status_response(instance)
        network = {
            "nodes_active": status_snapshot.nodes_total,
            "avg_latency_ms": 0.0,
            "throughput_mbps": 0.0,
        }

    control_policy = _maas_control_policy_evidence()
    response = MeshMetricsResponse(
        mesh_id=mesh_id,
        consciousness=consciousness,
        mape_k=mape_k,
        network=network,
        control_policy_evidence=control_policy,
        mesh_metrics_claim_gate=_mesh_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _MESH_METRICS_CROSS_PLANE_CLAIMS,
            surface="maas_mesh.metrics",
        ),
        timestamp=datetime.utcnow().isoformat(),
    )
    _publish_modular_mesh_event(
        http_request,
        source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
        layer=_MODULAR_MESH_READ_LAYER,
        operation="get_mesh_metrics",
        stage="mesh_metrics_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        target_nodes=getattr(instance, "target_nodes", None),
        plan=getattr(instance, "plan", None),
        result_summary=_mesh_metrics_summary(response),
        control_policy_evidence=control_policy,
        reason="mesh_metrics_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.post(
    "/{mesh_id}/scale",
    summary="Scale mesh nodes",
    description="Scale the number of nodes in a mesh.",
)
async def scale_mesh(
    mesh_id: str,
    request: MeshScaleRequest,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> Dict[str, Any]:
    """Scale mesh to target node count."""
    started = time.monotonic()
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        requested_target = request.target_count or request.count
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_SCALE_SOURCE_AGENT,
            layer=_MODULAR_MESH_SCALE_LAYER,
            operation="scale_mesh",
            stage="mesh_scale_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            target_nodes=requested_target,
            result_summary={
                "payload_type": "MeshScaleRequest",
                "target_count": _safe_count(requested_target),
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            registry_mutation_attempted=False,
            registry_mutation_committed=False,
            provisioner_call_attempted=False,
            provisioner_call_committed=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    provisioner = get_provisioner()
    target_count = _resolve_scale_target_count(request, instance)

    try:
        result = await provisioner.scale_mesh(
            mesh_id=mesh_id,
            target_count=target_count,
            actor=user.id,
        )
        response = _attach_mesh_lifecycle_gates(
            result,
            surface="maas_mesh.scale",
            read_only=False,
            control_action=True,
            registry_mutation_committed=True,
            provisioner_call_committed=True,
        )
        if isinstance(response, dict):
            response.setdefault("previous_nodes", response.get("previous_count"))
            response.setdefault("current_nodes", response.get("current_count"))
            response.setdefault("target_count", target_count)
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_SCALE_SOURCE_AGENT,
            layer=_MODULAR_MESH_SCALE_LAYER,
            operation="scale_mesh",
            stage="mesh_scale",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            mesh_id=mesh_id,
            owner_id=getattr(instance, "owner_id", None),
            target_nodes=target_count,
            plan=getattr(instance, "plan", None),
            result_summary={
                "payload_type": "MeshScaleRequest",
                "target_count": _safe_count(target_count),
                **_mesh_result_summary(response),
            },
            reason="mesh_scale_recorded",
            registry_mutation_attempted=True,
            registry_mutation_committed=True,
            provisioner_call_attempted=True,
            provisioner_call_committed=True,
        )
        return response

    except ValueError as e:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_SCALE_SOURCE_AGENT,
            layer=_MODULAR_MESH_SCALE_LAYER,
            operation="scale_mesh",
            stage="mesh_scale",
            status_value="validation_failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            mesh_id=mesh_id,
            owner_id=getattr(instance, "owner_id", None),
            target_nodes=target_count,
            plan=getattr(instance, "plan", None),
            result_summary={
                "payload_type": "MeshScaleRequest",
                "target_count": _safe_count(target_count),
                "error_type": e.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=e.__class__.__name__,
            registry_mutation_attempted=True,
            registry_mutation_committed=False,
            provisioner_call_attempted=True,
            provisioner_call_committed=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{mesh_id}",
    status_code=status.HTTP_200_OK,
    summary="Terminate mesh",
    description="Terminate a mesh network and all its nodes.",
)
async def terminate_mesh(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    reason: str = Query("user_request", description="Termination reason"),
    http_request: Request = None,
) -> Dict[str, Any]:
    """Terminate a mesh network."""
    started = time.monotonic()
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_TERMINATE_SOURCE_AGENT,
            layer=_MODULAR_MESH_TERMINATE_LAYER,
            operation="terminate_mesh",
            stage="mesh_terminate_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "termination_request",
                "mesh_id_present": bool(mesh_id),
                "reason_present": bool(reason),
                "reason_length": min(len(str(reason or "")), 500),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            registry_mutation_attempted=False,
            registry_mutation_committed=False,
            provisioner_call_attempted=False,
            provisioner_call_committed=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    provisioner = get_provisioner()

    try:
        result = await provisioner.terminate_mesh(
            mesh_id=mesh_id,
            actor=user.id,
            reason=reason,
        )
        response = _attach_mesh_lifecycle_gates(
            result,
            surface="maas_mesh.terminate",
            read_only=False,
            control_action=True,
            registry_mutation_committed=True,
            provisioner_call_committed=True,
        )
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_TERMINATE_SOURCE_AGENT,
            layer=_MODULAR_MESH_TERMINATE_LAYER,
            operation="terminate_mesh",
            stage="mesh_terminate",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            mesh_id=mesh_id,
            owner_id=getattr(instance, "owner_id", None),
            target_nodes=getattr(instance, "target_nodes", None),
            plan=getattr(instance, "plan", None),
            result_summary={
                "reason_present": bool(reason),
                "reason_length": min(len(str(reason or "")), 500),
                **_mesh_result_summary(response),
            },
            reason="mesh_terminate_recorded",
            registry_mutation_attempted=True,
            registry_mutation_committed=True,
            provisioner_call_attempted=True,
            provisioner_call_committed=True,
        )
        return response

    except ValueError as e:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_TERMINATE_SOURCE_AGENT,
            layer=_MODULAR_MESH_TERMINATE_LAYER,
            operation="terminate_mesh",
            stage="mesh_terminate",
            status_value="not_found",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_404_NOT_FOUND,
            user=user,
            mesh_id=mesh_id,
            owner_id=getattr(instance, "owner_id", None),
            target_nodes=getattr(instance, "target_nodes", None),
            plan=getattr(instance, "plan", None),
            result_summary={
                "payload_type": "termination_request",
                "reason_present": bool(reason),
                "reason_length": min(len(str(reason or "")), 500),
                "error_type": e.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=e.__class__.__name__,
            registry_mutation_attempted=True,
            registry_mutation_committed=False,
            provisioner_call_attempted=True,
            provisioner_call_committed=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{mesh_id}/audit-logs",
    summary="Get mesh audit log alias",
    description="Compatibility alias for audit-log reads.",
)
async def get_mesh_audit_logs_alias(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Compatibility audit-log alias guarded by audit:view permission."""
    if user.role != "admin" and "audit:view" not in (user.scopes or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="audit:view permission required",
        )
    return {"mesh_id": mesh_id, "audit_logs": get_audit_log(mesh_id)}


@router.get(
    "/{mesh_id}/audit",
    summary="Get mesh audit log",
    description="Get audit log for mesh operations.",
)
async def get_mesh_audit(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    http_request: Request = None,
    http_response: Response = None,
) -> List[Dict[str, Any]]:
    """Get audit log for a mesh."""
    started = time.monotonic()
    _set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.audit")
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
            layer=_MODULAR_MESH_READ_LAYER,
            operation="get_mesh_audit",
            stage="mesh_audit_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "access_check",
                "mesh_id_present": bool(mesh_id),
                "limit_requested": _safe_count(limit),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    log = get_audit_log(mesh_id)
    response = log[-limit:]
    _publish_modular_mesh_event(
        http_request,
        source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
        layer=_MODULAR_MESH_READ_LAYER,
        operation="get_mesh_audit",
        stage="mesh_audit_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        target_nodes=getattr(instance, "target_nodes", None),
        plan=getattr(instance, "plan", None),
        result_summary=_audit_log_summary(
            log,
            returned_count=len(response),
            limit=limit,
            claim_surface="maas_mesh.audit",
        ),
        reason="mesh_audit_log_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.get(
    "/{mesh_id}/mapek/events",
    summary="Get MAPE-K events alias",
    description="Compatibility alias for MAPE-K event stream reads.",
)
async def get_mesh_mapek_events_alias(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    http_request: Request = None,
    http_response: Response = None,
) -> Dict[str, Any]:
    """Compatibility MAPE-K alias returning the legacy envelope."""
    events = await get_mesh_mapek(
        mesh_id,
        user=user,
        limit=limit,
        http_request=http_request,
        http_response=http_response,
    )
    return {"mesh_id": mesh_id, "events": events}


@router.get(
    "/{mesh_id}/mapek",
    summary="Get MAPE-K events",
    description="Get MAPE-K event stream for a mesh.",
)
async def get_mesh_mapek(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    http_request: Request = None,
    http_response: Response = None,
) -> List[Dict[str, Any]]:
    """Get MAPE-K events for a mesh."""
    started = time.monotonic()
    _set_mesh_read_list_claim_headers(http_response, surface="maas_mesh.mapek")
    try:
        instance = await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_modular_mesh_event(
            http_request,
            source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
            layer=_MODULAR_MESH_READ_LAYER,
            operation="get_mesh_mapek",
            stage="mesh_mapek_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "access_denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "access_check",
                "mesh_id_present": bool(mesh_id),
                "limit_requested": _safe_count(limit),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    events = get_mapek_events(mesh_id)
    response = events[-limit:]
    _publish_modular_mesh_event(
        http_request,
        source_agent=_MODULAR_MESH_READ_SOURCE_AGENT,
        layer=_MODULAR_MESH_READ_LAYER,
        operation="get_mesh_mapek",
        stage="mesh_mapek_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        target_nodes=getattr(instance, "target_nodes", None),
        plan=getattr(instance, "plan", None),
        result_summary=_mapek_events_summary(
            events,
            returned_count=len(response),
            limit=limit,
            claim_surface="maas_mesh.mapek",
        ),
        reason="mesh_mapek_events_observed",
        read_only=True,
        control_action=False,
    )
    return response


__all__ = ["router"]
