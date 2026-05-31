"""
MaaS Batman-adv Endpoints - Batman mesh networking management.

Provides REST API endpoints for Batman-adv mesh networking:
- Health monitoring
- Metrics collection
- Topology discovery
- MAPE-K integration
"""

import hashlib
import logging
import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from ..auth import UserContext, get_current_user, require_mesh_access
from ..registry import get_mesh
from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batman", tags=["batman"])

_MODULAR_BATMAN_HEALTH_SOURCE_AGENT = "maas-modular-batman-health-read"
_MODULAR_BATMAN_METRICS_SOURCE_AGENT = "maas-modular-batman-metrics-read"
_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT = "maas-modular-batman-topology-read"
_MODULAR_BATMAN_MAPEK_SOURCE_AGENT = "maas-modular-batman-mapek-control"
_MODULAR_BATMAN_HEALING_SOURCE_AGENT = "maas-modular-batman-healing-control"
_MODULAR_BATMAN_HEALTH_LAYER = "api_modular_batman_health_observed_state"
_MODULAR_BATMAN_METRICS_LAYER = "api_modular_batman_metrics_observed_state"
_MODULAR_BATMAN_TOPOLOGY_LAYER = "api_modular_batman_topology_observed_state"
_MODULAR_BATMAN_MAPEK_LAYER = "api_modular_batman_mapek_control_action"
_MODULAR_BATMAN_HEALING_LAYER = "api_modular_batman_healing_control_action"
_MODULAR_BATMAN_CLAIM_BOUNDARY = (
    "Modular MaaS BATMAN endpoint evidence only. It records local API calls, "
    "BATMAN helper/cache calls, MAPE-K loop calls, healing executor calls, "
    "batctl return codes, duration, and bounded output-shape metadata; it does "
    "not prove live batman-adv dataplane convergence, kernel forwarding "
    "correctness, physical link health, autonomous remediation completion, or "
    "that a healing action changed production routing."
)
_BATMAN_HEALTH_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_BATMAN_HEALTH_CLAIM_BOUNDARY = (
    "MaaS BATMAN health responses expose local health-monitor, helper, and "
    "cache observations only. Healthy status, health score, checks, history, "
    "or trend values do not prove physical link health, kernel forwarding "
    "correctness, routing convergence, dataplane delivery, production SLOs, "
    "customer traffic, external DPI bypass, settlement finality, or production "
    "readiness."
)
_BATMAN_HEALTH_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_batman_health_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _BATMAN_HEALTH_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Batman-Health-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Physical-Link-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Kernel-Forwarding-Correctness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
}
_BATMAN_METRICS_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_BATMAN_METRICS_CLAIM_BOUNDARY = (
    "MaaS BATMAN metrics expose local batman-adv helper, cache, and collector "
    "observations only. Originator, neighbor, link, gateway, throughput, latency, "
    "packet-loss, interface-up, Prometheus scrape, or history fields do not "
    "prove dataplane delivery, kernel forwarding correctness, routing "
    "convergence, production SLOs, customer traffic, external DPI bypass, "
    "settlement finality, or production readiness."
)
_BATMAN_METRICS_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_batman_metrics_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _BATMAN_METRICS_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Batman-Metrics-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
}
_BATMAN_TOPOLOGY_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_BATMAN_TOPOLOGY_CLAIM_BOUNDARY = (
    "MaaS BATMAN topology responses expose local topology-helper and batctl "
    "observations only. Nodes, links, originators, gateways, routing-table "
    "entries, and mesh diameter do not prove routing convergence, kernel "
    "forwarding correctness, physical link health, dataplane delivery, "
    "production SLOs, customer traffic, external DPI bypass, settlement "
    "finality, or production readiness."
)
_BATMAN_TOPOLOGY_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_batman_topology_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _BATMAN_TOPOLOGY_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Batman-Topology-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-Batctl-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Physical-Link-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Kernel-Forwarding-Correctness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
}
_BATMAN_CONTROL_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_BATMAN_CONTROL_CLAIM_BOUNDARY = (
    "MaaS BATMAN MAPE-K and healing responses expose local control-loop and "
    "executor outcomes only. MAPE-K running status, cycle success, started or "
    "stopped state, auto-heal configuration, healing success, or available "
    "healing actions do not prove autonomous remediation completion, restored "
    "dataplane, production route mutation, physical link health, kernel "
    "forwarding correctness, routing convergence, production SLOs, customer "
    "traffic, external DPI bypass, settlement finality, or production readiness."
)
_BATMAN_CONTROL_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_batman_control_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _BATMAN_CONTROL_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Batman-MAPEK-Control-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-Batman-Healing-Control-Claim-Allowed": "true",
    "X-X0TTA6BL4-Autonomous-Remediation-Completion-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Route-Mutation-Claim-Allowed": "false",
    "X-X0TTA6BL4-Post-Action-Dataplane-Revalidated": "false",
    "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Physical-Link-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Kernel-Forwarding-Correctness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
}
_BATMAN_MESH_STATUS_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_BATMAN_MESH_STATUS_CLAIM_BOUNDARY = (
    "MaaS BATMAN mesh status responses expose local mesh-registry and "
    "health-monitor aggregation only. Mesh node health status, health scores, "
    "node counts, and timestamps do not prove mesh-wide reachability, physical "
    "link health, kernel forwarding correctness, routing convergence, "
    "dataplane delivery, production SLOs, customer traffic, external DPI "
    "bypass, settlement finality, or production readiness."
)
_BATMAN_MESH_STATUS_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_batman_mesh_status_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _BATMAN_MESH_STATUS_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Batman-Mesh-Status-Observation-Claim-Allowed": "true",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Physical-Link-Health-Claim-Allowed": "false",
    "X-X0TTA6BL4-Kernel-Forwarding-Correctness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
}
_KNOWN_BATMAN_HEALING_ACTIONS = {
    "restart_interface",
    "reselect_gateway",
    "purge_originators",
    "adjust_routing",
    "isolate_node",
    "reconfigure_link",
    "restart_daemon",
    "escalate",
}


def _batman_health_claim_gate(surface: str = "maas_batman.health") -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_batman_health_claim_gate.v1",
        "surface": surface,
        "local_batman_health_observation_claim_allowed": True,
        "local_batman_helper_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _BATMAN_HEALTH_CLAIM_BOUNDARY,
    }


def _batman_health_claim_boundary_headers() -> Dict[str, str]:
    return dict(_BATMAN_HEALTH_CLAIM_HEADERS)


def _set_batman_health_claim_headers(response: Response | None) -> None:
    if response is None:
        return
    response.headers.update(_batman_health_claim_boundary_headers())


def _batman_metrics_claim_gate(surface: str = "maas_batman.metrics") -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_batman_metrics_claim_gate.v1",
        "surface": surface,
        "local_batman_metrics_observation_claim_allowed": True,
        "local_batman_helper_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _BATMAN_METRICS_CLAIM_BOUNDARY,
    }


def _batman_metrics_claim_boundary_headers() -> Dict[str, str]:
    return dict(_BATMAN_METRICS_CLAIM_HEADERS)


def _set_batman_metrics_claim_headers(response: Response | None) -> None:
    if response is None:
        return
    response.headers.update(_batman_metrics_claim_boundary_headers())


def _batman_topology_claim_gate(
    surface: str = "maas_batman.topology",
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_batman_topology_claim_gate.v1",
        "surface": surface,
        "local_batman_topology_observation_claim_allowed": True,
        "local_batctl_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _BATMAN_TOPOLOGY_CLAIM_BOUNDARY,
    }


def _batman_topology_claim_boundary_headers() -> Dict[str, str]:
    return dict(_BATMAN_TOPOLOGY_CLAIM_HEADERS)


def _set_batman_topology_claim_headers(response: Response | None) -> None:
    if response is None:
        return
    response.headers.update(_batman_topology_claim_boundary_headers())


def _batman_control_claim_gate(
    surface: str = "maas_batman.mapek",
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_batman_control_claim_gate.v1",
        "surface": surface,
        "local_batman_mapek_control_claim_allowed": True,
        "local_batman_healing_control_claim_allowed": True,
        "autonomous_remediation_completion_claim_allowed": False,
        "production_route_mutation_claim_allowed": False,
        "post_action_dataplane_revalidated": False,
        "restored_dataplane_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _BATMAN_CONTROL_CLAIM_BOUNDARY,
    }


def _batman_control_claim_boundary_headers() -> Dict[str, str]:
    return dict(_BATMAN_CONTROL_CLAIM_HEADERS)


def _set_batman_control_claim_headers(response: Response | None) -> None:
    if response is None:
        return
    response.headers.update(_batman_control_claim_boundary_headers())


def _batman_mesh_status_claim_gate(
    surface: str = "maas_batman.mesh.status",
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_batman_mesh_status_claim_gate.v1",
        "surface": surface,
        "local_batman_mesh_status_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "physical_link_health_claim_allowed": False,
        "kernel_forwarding_correctness_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _BATMAN_MESH_STATUS_CLAIM_BOUNDARY,
    }


def _batman_mesh_status_claim_boundary_headers() -> Dict[str, str]:
    return dict(_BATMAN_MESH_STATUS_CLAIM_HEADERS)


def _set_batman_mesh_status_claim_headers(response: Response | None) -> None:
    if response is None:
        return
    response.headers.update(_batman_mesh_status_claim_boundary_headers())


def _batman_metrics_prometheus_claim_boundary(output: str) -> str:
    return (
        "# x0tta6bl4_claim_gate_schema "
        "x0tta6bl4.maas_batman_metrics_claim_gate.v1\n"
        "# x0tta6bl4_claim_boundary "
        "local_batman_metrics_only_not_dataplane_or_production_proof\n"
        "# x0tta6bl4_production_readiness_claim_allowed false\n"
        "# x0tta6bl4_production_slo_claim_allowed false\n"
        "# x0tta6bl4_dataplane_delivery_claim_allowed false\n"
        "# x0tta6bl4_customer_traffic_claim_allowed false\n"
        "# x0tta6bl4_external_dpi_bypass_claim_allowed false\n"
        "# x0tta6bl4_settlement_finality_claim_allowed false\n"
        + output
    )


# ============================================================================
# Pydantic Models
# ============================================================================

class BatmanHealthResponse(BaseModel):
    """Response model for Batman health status."""
    
    node_id: str
    overall_status: str
    overall_score: float
    checks: List[Dict[str, Any]]
    recommendations: List[str]
    timestamp: str
    batman_health_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanMetricsResponse(BaseModel):
    """Response model for Batman metrics."""
    
    node_id: str
    timestamp: str
    originators_count: int
    neighbors_count: int
    total_links: int
    avg_link_quality: float
    routing_entries: int
    gateways_count: int
    has_gateway: bool
    throughput_mbps: float
    latency_ms: float
    packet_loss_percent: float
    interface_up: bool
    batman_metrics_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanTopologyResponse(BaseModel):
    """Response model for Batman topology."""
    
    mesh_id: str
    local_node_id: str
    total_nodes: int
    total_links: int
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    routing_table: Dict[str, str]
    mesh_diameter: int
    batman_topology_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanMAPEKStatusResponse(BaseModel):
    """Response model for Batman MAPE-K status."""
    
    node_id: str
    interface: str
    running: bool
    cycle_count: int
    auto_heal: bool
    last_health_report: Optional[Dict[str, Any]]
    knowledge_stats: Dict[str, Any]
    batman_control_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanMAPEKCycleResponse(BaseModel):
    """Response model for Batman MAPE-K cycle result."""
    
    cycle_id: int
    node_id: str
    started_at: str
    completed_at: str
    duration_seconds: float
    success: bool
    anomalies_count: int
    anomalies: List[Dict[str, Any]]
    plan: Optional[Dict[str, Any]]
    execution: Optional[Dict[str, Any]]
    batman_control_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanOriginatorsResponse(BaseModel):
    """Response model for Batman originators."""
    
    node_id: str
    interface: str
    originators: List[Dict[str, Any]]
    count: int
    timestamp: str
    batman_topology_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanGatewaysResponse(BaseModel):
    """Response model for Batman gateways."""
    
    node_id: str
    interface: str
    gateways: List[Dict[str, Any]]
    count: int
    has_selected: bool
    gateway_mode: str
    timestamp: str
    batman_topology_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


class BatmanHealingRequest(BaseModel):
    """Request model for triggering healing action."""
    
    action: str = Field(..., description="Healing action to perform")
    target_node: Optional[str] = Field(None, description="Target node for action")
    force: bool = Field(False, description="Force action even if healthy")


class BatmanHealingResponse(BaseModel):
    """Response model for healing action result."""
    
    action: str
    success: bool
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None
    batman_control_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Service Instances
# ============================================================================

# Global instances (can be overridden for testing)
_batman_health_monitors: Dict[str, Any] = {}
_batman_metrics_collectors: Dict[str, Any] = {}
_batman_mapek_loops: Dict[str, Any] = {}


def get_batman_health_monitor(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman health monitor for a node."""
    from src.libx0t.network.batman.health_monitor import BatmanHealthMonitor
    
    key = f"{node_id}:{interface}"
    if key not in _batman_health_monitors:
        _batman_health_monitors[key] = BatmanHealthMonitor(
            node_id=node_id,
            interface=interface,
        )
    return _batman_health_monitors[key]


def get_batman_metrics_collector(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman metrics collector for a node."""
    from src.libx0t.network.batman.metrics import BatmanMetricsCollector
    
    key = f"{node_id}:{interface}"
    if key not in _batman_metrics_collectors:
        _batman_metrics_collectors[key] = BatmanMetricsCollector(
            node_id=node_id,
            interface=interface,
        )
    return _batman_metrics_collectors[key]


def get_batman_mapek_loop(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman MAPE-K loop for a node."""
    from src.libx0t.network.batman.mape_k_integration import BatmanMAPEKLoop
    
    key = f"{node_id}:{interface}"
    if key not in _batman_mapek_loops:
        _batman_mapek_loops[key] = BatmanMAPEKLoop(
            node_id=node_id,
            interface=interface,
        )
    return _batman_mapek_loops[key]


# ============================================================================
# Helper Functions
# ============================================================================

def _batman_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize modular MaaS BATMAN EventBus: %s", exc)
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


def _interface_bucket(interface: Any) -> str:
    text = str(interface or "").strip().lower()
    if text == "bat0":
        return "bat0_default"
    if text.startswith("bat") and len(text) <= 16:
        return "batman_interface"
    return "other"


def _status_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {
        "degraded",
        "error",
        "failed",
        "healthy",
        "not_found",
        "ok",
        "running",
        "started",
        "stopped",
        "success",
        "timeout",
        "unavailable",
        "unknown",
    }:
        return text
    return "unknown" if not text else "other"


def _action_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _KNOWN_BATMAN_HEALING_ACTIONS else "other"


def _bounded_text_metadata(value: Any) -> Dict[str, Any]:
    text = str(value or "")
    return {
        "chars": min(len(text), 1_000_000),
        "lines": min(text.count("\n") + (1 if text else 0), 100_000),
        "sha256": _redacted_sha256_prefix(text),
        "payloads_redacted": True,
    }


def _subprocess_metadata(result: Any) -> Dict[str, Any]:
    return {
        "return_code": getattr(result, "returncode", None),
        "stdout": _bounded_text_metadata(getattr(result, "stdout", "")),
        "stderr": _bounded_text_metadata(getattr(result, "stderr", "")),
        "payloads_redacted": True,
    }


def _health_response_summary(response: BatmanHealthResponse) -> Dict[str, Any]:
    claim_gate = (
        response.batman_health_claim_gate
        if isinstance(response.batman_health_claim_gate, dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(response.cross_plane_claim_gate, dict)
        else {}
    )
    return {
        "payload_type": "BatmanHealthResponse",
        "node_id_present": bool(response.node_id),
        "overall_status": _status_bucket(response.overall_status),
        "overall_score": _safe_float(response.overall_score),
        "checks_count": len(response.checks),
        "recommendations_count": len(response.recommendations),
        "timestamp_present": bool(response.timestamp),
        "batman_health_claim_gate_present": bool(claim_gate),
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
        "physical_link_health_claim_allowed": (
            claim_gate.get("physical_link_health_claim_allowed")
            if isinstance(claim_gate.get("physical_link_health_claim_allowed"), bool)
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _dict_list_summary(values: Any, *, limit: int | None = None) -> Dict[str, Any]:
    if not isinstance(values, list):
        return {
            "payload_type": type(values).__name__[:40],
            "returned_count": None,
            "payloads_redacted": True,
        }
    return {
        "payload_type": "list",
        "returned_count": len(values),
        "limit_requested": _safe_count(limit),
        "dict_items": sum(1 for item in values if isinstance(item, dict)),
        "total_field_count": sum(len(item) for item in values if isinstance(item, dict)),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _metrics_response_summary(response: BatmanMetricsResponse) -> Dict[str, Any]:
    claim_gate = (
        response.batman_metrics_claim_gate
        if isinstance(response.batman_metrics_claim_gate, dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(response.cross_plane_claim_gate, dict)
        else {}
    )
    return {
        "payload_type": "BatmanMetricsResponse",
        "node_id_present": bool(response.node_id),
        "originators_count": _safe_count(response.originators_count),
        "neighbors_count": _safe_count(response.neighbors_count),
        "total_links": _safe_count(response.total_links),
        "routing_entries": _safe_count(response.routing_entries),
        "gateways_count": _safe_count(response.gateways_count),
        "has_gateway": bool(response.has_gateway),
        "interface_up": bool(response.interface_up),
        "throughput_mbps": _safe_float(response.throughput_mbps),
        "latency_ms": _safe_float(response.latency_ms),
        "packet_loss_percent": _safe_float(response.packet_loss_percent),
        "timestamp_present": bool(response.timestamp),
        "batman_metrics_claim_gate_present": bool(claim_gate),
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
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _topology_response_summary(response: BatmanTopologyResponse) -> Dict[str, Any]:
    claim_gate = (
        response.batman_topology_claim_gate
        if isinstance(response.batman_topology_claim_gate, dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(response.cross_plane_claim_gate, dict)
        else {}
    )
    return {
        "payload_type": "BatmanTopologyResponse",
        "mesh_id_present": bool(response.mesh_id),
        "local_node_id_present": bool(response.local_node_id),
        "total_nodes": _safe_count(response.total_nodes),
        "total_links": _safe_count(response.total_links),
        "nodes_count": len(response.nodes),
        "links_count": len(response.links),
        "routing_entries": len(response.routing_table),
        "mesh_diameter": _safe_count(response.mesh_diameter),
        "batman_topology_claim_gate_present": bool(claim_gate),
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
        "routing_convergence_claim_allowed": (
            claim_gate.get("routing_convergence_claim_allowed")
            if isinstance(
                claim_gate.get("routing_convergence_claim_allowed"), bool
            )
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _originators_summary(
    response: BatmanOriginatorsResponse,
    result: Any | None,
) -> Dict[str, Any]:
    claim_gate = (
        response.batman_topology_claim_gate
        if isinstance(response.batman_topology_claim_gate, dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(response.cross_plane_claim_gate, dict)
        else {}
    )
    return {
        "payload_type": "BatmanOriginatorsResponse",
        "node_id_present": bool(response.node_id),
        "count": _safe_count(response.count),
        "timestamp_present": bool(response.timestamp),
        "batctl": _subprocess_metadata(result) if result is not None else {},
        "batman_topology_claim_gate_present": bool(claim_gate),
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
        "routing_convergence_claim_allowed": (
            claim_gate.get("routing_convergence_claim_allowed")
            if isinstance(
                claim_gate.get("routing_convergence_claim_allowed"), bool
            )
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _gateways_summary(
    response: BatmanGatewaysResponse,
    gateways_result: Any | None,
    mode_result: Any | None,
) -> Dict[str, Any]:
    claim_gate = (
        response.batman_topology_claim_gate
        if isinstance(response.batman_topology_claim_gate, dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(response.cross_plane_claim_gate, dict)
        else {}
    )
    return {
        "payload_type": "BatmanGatewaysResponse",
        "node_id_present": bool(response.node_id),
        "count": _safe_count(response.count),
        "has_selected": bool(response.has_selected),
        "gateway_mode": (
            response.gateway_mode
            if response.gateway_mode in {"client", "server", "off", "unknown"}
            else "other"
        ),
        "timestamp_present": bool(response.timestamp),
        "batctl_gateways": (
            _subprocess_metadata(gateways_result) if gateways_result is not None else {}
        ),
        "batctl_gw_mode": (
            _subprocess_metadata(mode_result) if mode_result is not None else {}
        ),
        "batman_topology_claim_gate_present": bool(claim_gate),
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
        "routing_convergence_claim_allowed": (
            claim_gate.get("routing_convergence_claim_allowed")
            if isinstance(
                claim_gate.get("routing_convergence_claim_allowed"), bool
            )
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _control_claim_gate_summary(response: Any) -> Dict[str, Any]:
    claim_gate = (
        response.batman_control_claim_gate
        if isinstance(getattr(response, "batman_control_claim_gate", None), dict)
        else {}
    )
    cross_plane_claim_gate = (
        response.cross_plane_claim_gate
        if isinstance(getattr(response, "cross_plane_claim_gate", None), dict)
        else {}
    )
    return {
        "batman_control_claim_gate_present": bool(claim_gate),
        "cross_plane_claim_gate_present": bool(cross_plane_claim_gate),
        "autonomous_remediation_completion_claim_allowed": (
            claim_gate.get("autonomous_remediation_completion_claim_allowed")
            if isinstance(
                claim_gate.get(
                    "autonomous_remediation_completion_claim_allowed"
                ),
                bool,
            )
            else None
        ),
        "production_route_mutation_claim_allowed": (
            claim_gate.get("production_route_mutation_claim_allowed")
            if isinstance(
                claim_gate.get("production_route_mutation_claim_allowed"), bool
            )
            else None
        ),
        "post_action_dataplane_revalidated": (
            claim_gate.get("post_action_dataplane_revalidated")
            if isinstance(claim_gate.get("post_action_dataplane_revalidated"), bool)
            else None
        ),
        "restored_dataplane_claim_allowed": (
            claim_gate.get("restored_dataplane_claim_allowed")
            if isinstance(claim_gate.get("restored_dataplane_claim_allowed"), bool)
            else None
        ),
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
    }


def _control_claim_summary_for_surface(surface: str) -> Dict[str, Any]:
    return _control_claim_gate_summary(
        SimpleNamespace(
            batman_control_claim_gate=_batman_control_claim_gate(surface=surface),
            cross_plane_claim_gate=cross_plane_claim_gate_metadata(
                _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
                surface=surface,
            ),
        )
    )


def _mapek_status_summary(response: BatmanMAPEKStatusResponse) -> Dict[str, Any]:
    return {
        "payload_type": "BatmanMAPEKStatusResponse",
        "node_id_present": bool(response.node_id),
        "running": bool(response.running),
        "cycle_count": _safe_count(response.cycle_count),
        "auto_heal": bool(response.auto_heal),
        "last_health_report_present": bool(response.last_health_report),
        "knowledge_stats_fields": len(response.knowledge_stats),
        **_control_claim_gate_summary(response),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mapek_cycle_summary(response: BatmanMAPEKCycleResponse) -> Dict[str, Any]:
    return {
        "payload_type": "BatmanMAPEKCycleResponse",
        "node_id_present": bool(response.node_id),
        "cycle_id_present": response.cycle_id is not None,
        "duration_seconds": _safe_float(response.duration_seconds),
        "success": bool(response.success),
        "anomalies_count": _safe_count(response.anomalies_count),
        "plan_present": bool(response.plan),
        "execution_present": bool(response.execution),
        **_control_claim_gate_summary(response),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _healing_result_summary(response: BatmanHealingResponse) -> Dict[str, Any]:
    return {
        "payload_type": "BatmanHealingResponse",
        "action": _action_bucket(response.action),
        "success": bool(response.success),
        "message_present": bool(response.message),
        "details_present": bool(response.details),
        "timestamp_present": bool(response.timestamp),
        **_control_claim_gate_summary(response),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_batman_status_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
    claim_gate = (
        result.get("batman_mesh_status_claim_gate")
        if isinstance(result.get("batman_mesh_status_claim_gate"), dict)
        else {}
    )
    cross_plane_claim_gate = (
        result.get("cross_plane_claim_gate")
        if isinstance(result.get("cross_plane_claim_gate"), dict)
        else {}
    )
    status_counts: Dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        bucket = _status_bucket(node.get("health_status"))
        status_counts[bucket] = status_counts.get(bucket, 0) + 1
    return {
        "payload_type": "dict",
        "mesh_id_present": bool(result.get("mesh_id")),
        "nodes_count": len(nodes),
        "status_counts": status_counts,
        "timestamp_present": bool(result.get("timestamp")),
        "batman_mesh_status_claim_gate_present": bool(claim_gate),
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
        "physical_link_health_claim_allowed": (
            claim_gate.get("physical_link_health_claim_allowed")
            if isinstance(claim_gate.get("physical_link_health_claim_allowed"), bool)
            else None
        ),
        "routing_convergence_claim_allowed": (
            claim_gate.get("routing_convergence_claim_allowed")
            if isinstance(
                claim_gate.get("routing_convergence_claim_allowed"), bool
            )
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _batman_source_quality(operation: str, status_value: str) -> str:
    if status_value in {"unavailable", "timeout"}:
        return "local_batctl_dependency_unavailable"
    if operation in {
        "get_batman_health",
        "get_batman_health_history",
        "get_batman_health_trend",
        "get_mesh_batman_status",
    }:
        return "local_batman_health_observed_state"
    if operation in {
        "get_batman_metrics",
        "get_batman_metrics_prometheus",
        "get_batman_metrics_history",
    }:
        return "local_batman_metrics_observed_state"
    if operation in {
        "get_batman_topology",
        "get_batman_originators",
        "get_batman_gateways",
    }:
        return "local_batman_topology_observed_state"
    if operation in {
        "get_batman_mapek_status",
        "run_batman_mapek_cycle",
        "start_batman_mapek_loop",
        "stop_batman_mapek_loop",
    }:
        return "local_batman_mapek_control_state"
    if operation in {"trigger_batman_healing", "get_batman_healing_actions"}:
        return "local_batman_healing_control_state"
    return "local_batman_endpoint_event"


def _batman_endpoint_evidence(
    *,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    http_status_code: int,
    result_summary: Dict[str, Any],
    read_only: bool,
    control_action: bool,
    batctl_attempted: bool = False,
    mapek_call_attempted: bool = False,
    healing_call_attempted: bool = False,
) -> Dict[str, Any]:
    source_quality = _batman_source_quality(operation, status_value)
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "stage": stage,
        "operation": operation,
        "duration_ms": round(duration_ms, 3),
        "return_code": http_status_code,
        "http_status_code": http_status_code,
        "read_only": read_only,
        "control_action": control_action,
        "dataplane_confirmed": False,
        "kernel_forwarding_confirmed": False,
        "physical_link_health_confirmed": False,
        "routing_convergence_confirmed": False,
        "autonomous_remediation_confirmed": False,
        "production_route_mutation_confirmed": False,
        "batctl_evidence": {
            "attempted": batctl_attempted,
            "payloads_redacted": True,
        },
        "mapek_evidence": {
            "attempted": mapek_call_attempted,
            "payloads_redacted": True,
        },
        "healing_evidence": {
            "attempted": healing_call_attempted,
            "payloads_redacted": True,
        },
        "output_summary": {
            **result_summary,
            "status": status_value,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_batman_event(
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
    node_id: str | None = None,
    mesh_id: str | None = None,
    interface: str | None = None,
    target_node: str | None = None,
    action: str | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
    read_only: bool = True,
    control_action: bool = False,
    batctl_attempted: bool = False,
    mapek_call_attempted: bool = False,
    healing_call_attempted: bool = False,
    event_type: EventType = EventType.PIPELINE_STAGE_END,
) -> str | None:
    event_bus = _batman_event_bus_from_request(request)
    if event_bus is None:
        return None
    result = result_summary or {}
    evidence = _batman_endpoint_evidence(
        operation=operation,
        stage=stage,
        status_value=status_value,
        duration_ms=duration_ms,
        http_status_code=http_status_code,
        result_summary=result,
        read_only=read_only,
        control_action=control_action,
        batctl_attempted=batctl_attempted,
        mapek_call_attempted=mapek_call_attempted,
        healing_call_attempted=healing_call_attempted,
    )
    payload = {
        "component": "api.maas.endpoints.batman",
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
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "target_node_hash": _redacted_sha256_prefix(target_node),
        "interface_hash": _redacted_sha256_prefix(interface),
        "interface_bucket": _interface_bucket(interface),
        "node_id_present": bool(node_id),
        "mesh_id_present": bool(mesh_id),
        "target_node_present": bool(target_node),
        "action": _action_bucket(action),
        "source_quality": evidence["source_quality"],
        "batman_endpoint_evidence": evidence,
        "result_summary": result,
        "control_action": control_action,
        "read_only": read_only,
        "observed_state": read_only,
        "dataplane_confirmed": False,
        "kernel_forwarding_confirmed": False,
        "routing_convergence_confirmed": False,
        "raw_identifiers_redacted": True,
        "raw_batctl_output_redacted": True,
        "raw_topology_payload_redacted": True,
        "raw_mapek_payload_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _MODULAR_BATMAN_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, source_agent, payload, priority=6)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS BATMAN event: %s", exc)
        return None


async def _get_node_id_from_mesh(mesh_id: str, user: UserContext) -> str:
    """Get node ID from mesh ID."""
    instance = get_mesh(mesh_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )
    
    # Check access
    if instance.owner_id != user.user_id:
        await require_mesh_access(mesh_id, user)
    
    # Get first node ID from mesh
    nodes = getattr(instance, "node_instances", {}) or {}
    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No nodes found in mesh {mesh_id}",
        )
    
    return list(nodes.keys())[0]


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get(
    "/{node_id}/health",
    response_model=BatmanHealthResponse,
    summary="Get Batman node health",
    description="Get health status of a Batman-adv node.",
)
async def get_batman_health(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanHealthResponse:
    """Get health status of a Batman-adv node."""
    started = time.monotonic()
    monitor = get_batman_health_monitor(node_id, interface)
    _set_batman_health_claim_headers(http_response)
    
    # Run health checks
    report = await monitor.run_health_checks()
    
    response = BatmanHealthResponse(
        node_id=report.node_id,
        overall_status=report.overall_status.value,
        overall_score=report.overall_score,
        checks=[
            {
                "type": c.check_type.value,
                "status": c.status.value,
                "score": c.score,
                "message": c.message,
                "details": c.details,
            }
            for c in report.checks
        ],
        recommendations=report.recommendations,
        timestamp=report.timestamp.isoformat(),
        batman_health_claim_gate=_batman_health_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_HEALTH_CROSS_PLANE_CLAIMS,
            surface="maas_batman.health",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_HEALTH_LAYER,
        operation="get_batman_health",
        stage="batman_health_read",
        status_value=response.overall_status,
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_health_response_summary(response),
        reason="batman_health_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.get(
    "/{node_id}/health/history",
    summary="Get Batman health history",
    description="Get health history for a Batman-adv node.",
)
async def get_batman_health_history(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    limit: int = Query(10, ge=1, le=100, description="Number of reports to return"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> List[Dict[str, Any]]:
    """Get health history for a Batman-adv node."""
    started = time.monotonic()
    monitor = get_batman_health_monitor(node_id, interface)
    _set_batman_health_claim_headers(http_response)
    history = monitor.get_health_history(limit)
    
    response = [report.to_dict() for report in history]
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_HEALTH_LAYER,
        operation="get_batman_health_history",
        stage="batman_health_history_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_dict_list_summary(response, limit=limit),
        reason="batman_health_history_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.get(
    "/{node_id}/health/trend",
    summary="Get Batman health trend",
    description="Get health trend analysis for a Batman-adv node.",
)
async def get_batman_health_trend(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    window: int = Query(10, ge=2, le=50, description="Analysis window size"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> Dict[str, Any]:
    """Get health trend analysis for a Batman-adv node."""
    started = time.monotonic()
    monitor = get_batman_health_monitor(node_id, interface)
    _set_batman_health_claim_headers(http_response)
    trend = monitor.get_health_trend(window)
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_HEALTH_LAYER,
        operation="get_batman_health_trend",
        stage="batman_health_trend_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary={
            "payload_type": "dict",
            "payload_field_count": len(trend) if isinstance(trend, dict) else None,
            "window": _safe_count(window),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="batman_health_trend_observed",
        read_only=True,
        control_action=False,
    )
    return trend


# ============================================================================
# Metrics Endpoints
# ============================================================================

@router.get(
    "/{node_id}/metrics",
    response_model=BatmanMetricsResponse,
    summary="Get Batman node metrics",
    description="Get Prometheus metrics for a Batman-adv node.",
)
async def get_batman_metrics(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanMetricsResponse:
    """Get metrics for a Batman-adv node."""
    started = time.monotonic()
    collector = get_batman_metrics_collector(node_id, interface)
    _set_batman_metrics_claim_headers(http_response)
    
    # Collect metrics
    snapshot = await collector.collect()
    
    response = BatmanMetricsResponse(
        node_id=node_id,
        timestamp=snapshot.timestamp.isoformat(),
        originators_count=snapshot.originators_count,
        neighbors_count=snapshot.neighbors_count,
        total_links=snapshot.total_links,
        avg_link_quality=snapshot.avg_link_quality,
        routing_entries=snapshot.routing_entries,
        gateways_count=snapshot.gateways_count,
        has_gateway=snapshot.has_gateway,
        throughput_mbps=snapshot.throughput_mbps,
        latency_ms=snapshot.latency_ms,
        packet_loss_percent=snapshot.packet_loss_percent,
        interface_up=snapshot.interface_up,
        batman_metrics_claim_gate=_batman_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_METRICS_CROSS_PLANE_CLAIMS,
            surface="maas_batman.metrics",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_METRICS_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_METRICS_LAYER,
        operation="get_batman_metrics",
        stage="batman_metrics_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_metrics_response_summary(response),
        reason="batman_metrics_observed",
        read_only=True,
        control_action=False,
    )
    return response


@router.get(
    "/{node_id}/metrics/prometheus",
    summary="Get Prometheus metrics output",
    description="Get Prometheus-formatted metrics for scraping.",
    response_class=PlainTextResponse,
)
async def get_batman_metrics_prometheus(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> str:
    """Get Prometheus-formatted metrics."""
    started = time.monotonic()
    collector = get_batman_metrics_collector(node_id, interface)
    _set_batman_metrics_claim_headers(http_response)
    
    # Collect metrics first
    await collector.collect()
    
    # Return Prometheus output
    output = _batman_metrics_prometheus_claim_boundary(collector.get_metrics_output())
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_METRICS_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_METRICS_LAYER,
        operation="get_batman_metrics_prometheus",
        stage="batman_metrics_prometheus_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary={
            "payload_type": "prometheus_text",
            "output": _bounded_text_metadata(output),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="batman_prometheus_metrics_observed",
        read_only=True,
        control_action=False,
    )
    return output


@router.get(
    "/{node_id}/metrics/history",
    summary="Get Batman metrics history",
    description="Get metrics history for a Batman-adv node.",
)
async def get_batman_metrics_history(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    limit: int = Query(10, ge=1, le=100, description="Number of snapshots to return"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> List[Dict[str, Any]]:
    """Get metrics history for a Batman-adv node."""
    started = time.monotonic()
    collector = get_batman_metrics_collector(node_id, interface)
    _set_batman_metrics_claim_headers(http_response)
    snapshots = collector.get_snapshots(limit)
    
    response = [snapshot.to_dict() for snapshot in snapshots]
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_METRICS_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_METRICS_LAYER,
        operation="get_batman_metrics_history",
        stage="batman_metrics_history_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_dict_list_summary(response, limit=limit),
        reason="batman_metrics_history_observed",
        read_only=True,
        control_action=False,
    )
    return response


# ============================================================================
# Topology Endpoints
# ============================================================================

@router.get(
    "/{node_id}/topology",
    response_model=BatmanTopologyResponse,
    summary="Get Batman topology",
    description="Get mesh topology from Batman-adv node.",
)
async def get_batman_topology(
    node_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanTopologyResponse:
    """Get mesh topology from Batman-adv node."""
    started = time.monotonic()
    _set_batman_topology_claim_headers(http_response)
    try:
        from src.libx0t.network.batman.topology import MeshTopology, MeshNode, MeshLink, LinkQuality
        
        # Create a topology instance (in production, this would be shared state)
        topology = MeshTopology(mesh_id="default", local_node_id=node_id)
        
        # Get topology stats
        stats = topology.get_topology_stats()
        
        # Convert nodes and links to serializable format
        nodes = [
            {
                "node_id": n.node_id,
                "mac_address": n.mac_address,
                "ip_address": n.ip_address,
                "state": n.state.value,
                "last_seen": n.last_seen.isoformat(),
                "hop_count": n.hop_count,
            }
            for n in topology.nodes.values()
        ]
        
        links = [
            {
                "source": link.source,
                "destination": link.destination,
                "quality": link.quality.name,
                "throughput_mbps": link.throughput_mbps,
                "latency_ms": link.latency_ms,
                "packet_loss_percent": link.packet_loss_percent,
            }
            for link in topology.links.values()
        ]
        
        response = BatmanTopologyResponse(
            mesh_id=stats["mesh_id"],
            local_node_id=stats["local_node_id"],
            total_nodes=stats["total_nodes"],
            total_links=stats["total_links"],
            nodes=nodes,
            links=links,
            routing_table=topology.routing_table,
            mesh_diameter=stats.get("mesh_diameter", 0),
            batman_topology_claim_gate=_batman_topology_claim_gate(),
            cross_plane_claim_gate=cross_plane_claim_gate_metadata(
                _BATMAN_TOPOLOGY_CROSS_PLANE_CLAIMS,
                surface="maas_batman.topology",
            ),
        )
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_topology",
            stage="batman_topology_read",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            node_id=node_id,
            mesh_id=stats.get("mesh_id"),
            result_summary=_topology_response_summary(response),
            reason="batman_topology_observed",
            read_only=True,
            control_action=False,
        )
        return response
        
    except ImportError:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_topology",
            stage="batman_topology_import",
            status_value="unavailable",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            user=user,
            node_id=node_id,
            result_summary={
                "payload_type": "import_error",
                "topology_module_available": False,
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="ImportError",
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Batman topology module not available",
        )


@router.get(
    "/{node_id}/originators",
    response_model=BatmanOriginatorsResponse,
    summary="Get Batman originators",
    description="Get originator table from Batman-adv node.",
)
async def get_batman_originators(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanOriginatorsResponse:
    """Get originator table from Batman-adv node."""
    import subprocess
    
    started = time.monotonic()
    _set_batman_topology_claim_headers(http_response)
    originators = []
    result = None
    
    try:
        result = subprocess.run(
            ["batctl", "meshif", interface, "originators"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    originators.append({
                        "mac": parts[0],
                        "last_seen": parts[1] if len(parts) > 1 else "",
                        "next_hop": parts[2] if len(parts) > 2 else "",
                        "tq": parts[3] if len(parts) > 3 else "",
                    })
                    
    except FileNotFoundError:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_originators",
            stage="batctl_originators",
            status_value="unavailable",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            user=user,
            node_id=node_id,
            interface=interface,
            result_summary={
                "payload_type": "batctl_error",
                "batctl_available": False,
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="FileNotFoundError",
            read_only=True,
            control_action=False,
            batctl_attempted=True,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="batctl not available",
        )
    except subprocess.TimeoutExpired:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_originators",
            stage="batctl_originators",
            status_value="timeout",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            user=user,
            node_id=node_id,
            interface=interface,
            result_summary={
                "payload_type": "batctl_timeout",
                "timeout_seconds": 5,
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="TimeoutExpired",
            read_only=True,
            control_action=False,
            batctl_attempted=True,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout getting originators",
        )
    
    response = BatmanOriginatorsResponse(
        node_id=node_id,
        interface=interface,
        originators=originators,
        count=len(originators),
        timestamp=datetime.utcnow().isoformat(),
        batman_topology_claim_gate=_batman_topology_claim_gate(
            surface="maas_batman.originators",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_TOPOLOGY_CROSS_PLANE_CLAIMS,
            surface="maas_batman.originators",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
        operation="get_batman_originators",
        stage="batctl_originators",
        status_value="success" if getattr(result, "returncode", 1) == 0 else "error",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_originators_summary(response, result),
        reason="batman_originators_observed",
        read_only=True,
        control_action=False,
        batctl_attempted=True,
    )
    return response


@router.get(
    "/{node_id}/gateways",
    response_model=BatmanGatewaysResponse,
    summary="Get Batman gateways",
    description="Get gateway list from Batman-adv node.",
)
async def get_batman_gateways(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanGatewaysResponse:
    """Get gateway list from Batman-adv node."""
    import subprocess
    
    started = time.monotonic()
    _set_batman_topology_claim_headers(http_response)
    gateways = []
    has_selected = False
    gateway_mode = "unknown"
    gateways_result = None
    mode_result = None
    
    try:
        # Get gateways
        gateways_result = subprocess.run(
            ["batctl", "meshif", interface, "gateways"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if gateways_result.returncode == 0:
            output = gateways_result.stdout.strip()
            if "No gateways" not in output:
                for line in output.split("\n"):
                    if line.strip():
                        is_selected = line.startswith("=>") or "*" in line
                        if is_selected:
                            has_selected = True
                        gateways.append({
                            "mac": line.split()[0].replace("=>", "").replace("*", ""),
                            "selected": is_selected,
                            "line": line.strip(),
                        })
        
        # Get gateway mode
        mode_result = subprocess.run(
            ["batctl", "meshif", interface, "gw_mode"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if mode_result.returncode == 0:
            gateway_mode = mode_result.stdout.strip()
            
    except FileNotFoundError:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_gateways",
            stage="batctl_gateways",
            status_value="unavailable",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            user=user,
            node_id=node_id,
            interface=interface,
            result_summary={
                "payload_type": "batctl_error",
                "batctl_available": False,
                "batctl_gateways": (
                    _subprocess_metadata(gateways_result)
                    if gateways_result is not None
                    else {}
                ),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="FileNotFoundError",
            read_only=True,
            control_action=False,
            batctl_attempted=True,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="batctl not available",
        )
    except subprocess.TimeoutExpired:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
            operation="get_batman_gateways",
            stage="batctl_gateways",
            status_value="timeout",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            user=user,
            node_id=node_id,
            interface=interface,
            result_summary={
                "payload_type": "batctl_timeout",
                "timeout_seconds": 5,
                "batctl_gateways": (
                    _subprocess_metadata(gateways_result)
                    if gateways_result is not None
                    else {}
                ),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="TimeoutExpired",
            read_only=True,
            control_action=False,
            batctl_attempted=True,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout getting gateways",
        )
    
    response = BatmanGatewaysResponse(
        node_id=node_id,
        interface=interface,
        gateways=gateways,
        count=len(gateways),
        has_selected=has_selected,
        gateway_mode=gateway_mode,
        timestamp=datetime.utcnow().isoformat(),
        batman_topology_claim_gate=_batman_topology_claim_gate(
            surface="maas_batman.gateways",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_TOPOLOGY_CROSS_PLANE_CLAIMS,
            surface="maas_batman.gateways",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_TOPOLOGY_LAYER,
        operation="get_batman_gateways",
        stage="batctl_gateways",
        status_value=(
            "success"
            if getattr(gateways_result, "returncode", 1) == 0
            and getattr(mode_result, "returncode", 1) == 0
            else "error"
        ),
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_gateways_summary(response, gateways_result, mode_result),
        reason="batman_gateways_observed",
        read_only=True,
        control_action=False,
        batctl_attempted=True,
    )
    return response


# ============================================================================
# MAPE-K Endpoints
# ============================================================================

@router.get(
    "/{node_id}/mapek/status",
    response_model=BatmanMAPEKStatusResponse,
    summary="Get Batman MAPE-K status",
    description="Get MAPE-K loop status for Batman-adv node.",
)
async def get_batman_mapek_status(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanMAPEKStatusResponse:
    """Get MAPE-K loop status for Batman-adv node."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    loop = get_batman_mapek_loop(node_id, interface)
    status_data = loop.get_status()

    response = BatmanMAPEKStatusResponse(
        node_id=status_data["node_id"],
        interface=status_data["interface"],
        running=status_data["running"],
        cycle_count=status_data["cycle_count"],
        auto_heal=status_data["auto_heal"],
        last_health_report=status_data.get("last_health_report"),
        knowledge_stats=status_data["knowledge_stats"],
        batman_control_claim_gate=_batman_control_claim_gate(
            surface="maas_batman.mapek.status",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
            surface="maas_batman.mapek.status",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_MAPEK_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_MAPEK_LAYER,
        operation="get_batman_mapek_status",
        stage="batman_mapek_status_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary=_mapek_status_summary(response),
        reason="batman_mapek_status_observed",
        read_only=True,
        control_action=False,
        mapek_call_attempted=True,
    )
    return response


@router.post(
    "/{node_id}/mapek/cycle",
    response_model=BatmanMAPEKCycleResponse,
    summary="Run Batman MAPE-K cycle",
    description="Manually trigger a MAPE-K cycle for Batman-adv node.",
)
async def run_batman_mapek_cycle(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    auto_heal: bool = Query(True, description="Execute healing actions"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanMAPEKCycleResponse:
    """Manually trigger a MAPE-K cycle for Batman-adv node."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    loop = get_batman_mapek_loop(node_id, interface)
    loop.auto_heal = auto_heal
    
    # Run one cycle
    result = await loop.run_cycle()
    
    response = BatmanMAPEKCycleResponse(
        cycle_id=result["cycle_id"],
        node_id=result["node_id"],
        started_at=result["started_at"],
        completed_at=result["completed_at"],
        duration_seconds=result["duration_seconds"],
        success=result["success"],
        anomalies_count=result.get("anomalies_count", 0),
        anomalies=result.get("anomalies", []),
        plan=result.get("plan"),
        execution=result.get("execution"),
        batman_control_claim_gate=_batman_control_claim_gate(
            surface="maas_batman.mapek.cycle",
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
            surface="maas_batman.mapek.cycle",
        ),
    )
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_MAPEK_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_MAPEK_LAYER,
        operation="run_batman_mapek_cycle",
        stage="batman_mapek_cycle",
        status_value="success" if response.success else "failed",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary={
            **_mapek_cycle_summary(response),
            "auto_heal": bool(auto_heal),
        },
        reason="batman_mapek_cycle_completed",
        read_only=False,
        control_action=True,
        mapek_call_attempted=True,
    )
    return response


@router.post(
    "/{node_id}/mapek/start",
    summary="Start Batman MAPE-K loop",
    description="Start continuous MAPE-K loop for Batman-adv node.",
)
async def start_batman_mapek_loop(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    auto_heal: bool = Query(True, description="Execute healing actions automatically"),
    background_tasks: BackgroundTasks = None,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> Dict[str, Any]:
    """Start continuous MAPE-K loop for Batman-adv node."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    loop = get_batman_mapek_loop(node_id, interface)
    loop.auto_heal = auto_heal
    
    # Start loop in background using FastAPI BackgroundTasks
    if background_tasks:
        background_tasks.add_task(loop.start)
    else:
        # Fallback for testing without BackgroundTasks
        import asyncio
        asyncio.create_task(loop.start())
    
    response = {
        "node_id": node_id,
        "interface": interface,
        "status": "started",
        "auto_heal": auto_heal,
        "timestamp": datetime.utcnow().isoformat(),
        "batman_control_claim_gate": _batman_control_claim_gate(
            surface="maas_batman.mapek.start",
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
            surface="maas_batman.mapek.start",
        ),
    }
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_MAPEK_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_MAPEK_LAYER,
        operation="start_batman_mapek_loop",
        stage="batman_mapek_start",
        status_value="started",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary={
            "payload_type": "dict",
            "status": "started",
            "auto_heal": bool(auto_heal),
            "background_task_scheduled": bool(background_tasks),
            **_control_claim_summary_for_surface("maas_batman.mapek.start"),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="batman_mapek_loop_started",
        read_only=False,
        control_action=True,
        mapek_call_attempted=True,
    )
    return response


@router.post(
    "/{node_id}/mapek/stop",
    summary="Stop Batman MAPE-K loop",
    description="Stop MAPE-K loop for Batman-adv node.",
)
async def stop_batman_mapek_loop(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> Dict[str, Any]:
    """Stop MAPE-K loop for Batman-adv node."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    loop = get_batman_mapek_loop(node_id, interface)
    loop.stop()
    
    response = {
        "node_id": node_id,
        "interface": interface,
        "status": "stopped",
        "timestamp": datetime.utcnow().isoformat(),
        "batman_control_claim_gate": _batman_control_claim_gate(
            surface="maas_batman.mapek.stop",
        ),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
            surface="maas_batman.mapek.stop",
        ),
    }
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_MAPEK_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_MAPEK_LAYER,
        operation="stop_batman_mapek_loop",
        stage="batman_mapek_stop",
        status_value="stopped",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        interface=interface,
        result_summary={
            "payload_type": "dict",
            "status": "stopped",
            **_control_claim_summary_for_surface("maas_batman.mapek.stop"),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="batman_mapek_loop_stopped",
        read_only=False,
        control_action=True,
        mapek_call_attempted=True,
    )
    return response


# ============================================================================
# Healing Endpoints
# ============================================================================

@router.post(
    "/{node_id}/heal",
    response_model=BatmanHealingResponse,
    summary="Trigger Batman healing action",
    description="Manually trigger a healing action for Batman-adv node.",
)
async def trigger_batman_healing(
    node_id: str,
    request: BatmanHealingRequest,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> BatmanHealingResponse:
    """Manually trigger a healing action for Batman-adv node."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    from src.libx0t.network.batman.mape_k_integration import BatmanRecoveryAction, BatmanMAPEKExecutor
    
    try:
        action = BatmanRecoveryAction(request.action)
    except ValueError:
        valid_actions = [a.value for a in BatmanRecoveryAction]
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_HEALING_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_HEALING_LAYER,
            operation="trigger_batman_healing",
            stage="batman_healing_validate",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            node_id=node_id,
            interface=interface,
            target_node=request.target_node,
            action=request.action,
            result_summary={
                "payload_type": "validation_error",
                "action": _action_bucket(request.action),
                "target_node_present": bool(request.target_node),
                "force": bool(request.force),
                "valid_actions_count": len(valid_actions),
                **_control_claim_summary_for_surface("maas_batman.healing"),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="invalid_action",
            read_only=False,
            control_action=True,
            healing_call_attempted=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Valid actions: {valid_actions}",
        )
    
    executor = BatmanMAPEKExecutor(interface=interface)
    
    try:
        result = await executor._execute_action(action, None)
        
        response = BatmanHealingResponse(
            action=request.action,
            success=result.get("status") == "success",
            message=result.get("message", ""),
            timestamp=datetime.utcnow().isoformat(),
            details=result,
            batman_control_claim_gate=_batman_control_claim_gate(
                surface="maas_batman.healing",
            ),
            cross_plane_claim_gate=cross_plane_claim_gate_metadata(
                _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
                surface="maas_batman.healing",
            ),
        )
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_HEALING_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_HEALING_LAYER,
            operation="trigger_batman_healing",
            stage="batman_healing_execute",
            status_value="success" if response.success else "failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            node_id=node_id,
            interface=interface,
            target_node=request.target_node,
            action=request.action,
            result_summary={
                **_healing_result_summary(response),
                "target_node_present": bool(request.target_node),
                "force": bool(request.force),
            },
            reason="batman_healing_executed",
            read_only=False,
            control_action=True,
            healing_call_attempted=True,
        )
        return response
    except Exception as e:
        response = BatmanHealingResponse(
            action=request.action,
            success=False,
            message=f"Healing action failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
            batman_control_claim_gate=_batman_control_claim_gate(
                surface="maas_batman.healing",
            ),
            cross_plane_claim_gate=cross_plane_claim_gate_metadata(
                _BATMAN_CONTROL_CROSS_PLANE_CLAIMS,
                surface="maas_batman.healing",
            ),
        )
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_HEALING_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_HEALING_LAYER,
            operation="trigger_batman_healing",
            stage="batman_healing_execute",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            node_id=node_id,
            interface=interface,
            target_node=request.target_node,
            action=request.action,
            result_summary={
                **_healing_result_summary(response),
                "error_type": e.__class__.__name__[:80],
                "target_node_present": bool(request.target_node),
                "force": bool(request.force),
            },
            reason=e.__class__.__name__,
            read_only=False,
            control_action=True,
            healing_call_attempted=True,
            event_type=EventType.TASK_FAILED,
        )
        return response


@router.get(
    "/{node_id}/heal/actions",
    summary="Get available healing actions",
    description="Get list of available Batman healing actions.",
)
async def get_batman_healing_actions(
    node_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> List[Dict[str, Any]]:
    """Get list of available Batman healing actions."""
    started = time.monotonic()
    _set_batman_control_claim_headers(http_response)
    from src.libx0t.network.batman.mape_k_integration import BatmanRecoveryAction
    
    actions = []
    for action in BatmanRecoveryAction:
        actions.append({
            "action": action.value,
            "description": _get_action_description(action),
        })
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_HEALING_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_HEALING_LAYER,
        operation="get_batman_healing_actions",
        stage="batman_healing_actions_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        node_id=node_id,
        result_summary={
            "payload_type": "list",
            "actions_count": len(actions),
            "known_actions": sorted(
                {
                    _action_bucket(action.get("action"))
                    for action in actions
                    if isinstance(action, dict)
                }
                - {"other"}
            ),
            **_control_claim_summary_for_surface("maas_batman.healing.actions"),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        reason="batman_healing_actions_observed",
        read_only=True,
        control_action=False,
        healing_call_attempted=False,
    )
    return actions


def _get_action_description(action) -> str:
    """Get description for a healing action."""
    descriptions = {
        "restart_interface": "Restart the Batman-adv network interface",
        "reselect_gateway": "Force gateway reselection",
        "purge_originators": "Purge stale originator entries",
        "adjust_routing": "Adjust routing parameters",
        "isolate_node": "Isolate a problematic node from the mesh",
        "reconfigure_link": "Reconfigure link parameters",
        "restart_daemon": "Restart the Batman-adv daemon",
        "escalate": "Escalate issue to human operator",
    }
    return descriptions.get(action.value, "No description available")


# ============================================================================
# Mesh Integration Endpoints
# ============================================================================

@router.get(
    "/mesh/{mesh_id}/status",
    summary="Get Batman status for mesh",
    description="Get Batman-adv status for all nodes in a mesh.",
)
async def get_mesh_batman_status(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
    http_response: Response = None,
) -> Dict[str, Any]:
    """Get Batman-adv status for all nodes in a mesh."""
    started = time.monotonic()
    _set_batman_mesh_status_claim_headers(http_response)
    instance = get_mesh(mesh_id)
    if instance is None:
        _publish_batman_event(
            http_request,
            source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
            layer=_MODULAR_BATMAN_HEALTH_LAYER,
            operation="get_mesh_batman_status",
            stage="mesh_batman_access_check",
            status_value="not_found",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_404_NOT_FOUND,
            user=user,
            mesh_id=mesh_id,
            result_summary={
                "payload_type": "access_check",
                "mesh_id_present": bool(mesh_id),
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason="mesh_not_found",
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )
    
    # Check access
    if instance.owner_id != user.user_id:
        try:
            await require_mesh_access(mesh_id, user)
        except HTTPException as exc:
            _publish_batman_event(
                http_request,
                source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
                layer=_MODULAR_BATMAN_HEALTH_LAYER,
                operation="get_mesh_batman_status",
                stage="mesh_batman_access_check",
                status_value="access_denied",
                duration_ms=(time.monotonic() - started) * 1000,
                http_status_code=exc.status_code,
                user=user,
                mesh_id=mesh_id,
                result_summary={
                    "payload_type": "access_check",
                    "mesh_id_present": bool(mesh_id),
                    "owner_match": False,
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                },
                reason=exc.__class__.__name__,
                read_only=True,
                control_action=False,
                event_type=EventType.TASK_BLOCKED,
            )
            raise
    
    nodes = getattr(instance, "node_instances", {}) or {}
    
    node_statuses = []
    for node_id in nodes.keys():
        monitor = get_batman_health_monitor(node_id)
        last_report = monitor.get_last_report()
        
        if last_report:
            node_statuses.append({
                "node_id": node_id,
                "health_status": last_report.overall_status.value,
                "health_score": last_report.overall_score,
            })
        else:
            node_statuses.append({
                "node_id": node_id,
                "health_status": "unknown",
                "health_score": 0.0,
            })
    
    response = {
        "mesh_id": mesh_id,
        "nodes": node_statuses,
        "timestamp": datetime.utcnow().isoformat(),
        "batman_mesh_status_claim_gate": _batman_mesh_status_claim_gate(),
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            _BATMAN_MESH_STATUS_CROSS_PLANE_CLAIMS,
            surface="maas_batman.mesh.status",
        ),
    }
    _publish_batman_event(
        http_request,
        source_agent=_MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
        layer=_MODULAR_BATMAN_HEALTH_LAYER,
        operation="get_mesh_batman_status",
        stage="mesh_batman_status_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        result_summary=_mesh_batman_status_summary(response),
        reason="mesh_batman_status_observed",
        read_only=True,
        control_action=False,
    )
    return response


__all__ = ["router"]
