"""
MaaS Batman-adv Endpoints - Batman mesh networking management.

Provides REST API endpoints for Batman-adv mesh networking:
- Health monitoring
- Metrics collection
- Topology discovery
- MAPE-K integration
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth import UserContext, get_current_user, require_mesh_access
from ..registry import get_mesh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batman", tags=["batman"])


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


class BatmanMAPEKStatusResponse(BaseModel):
    """Response model for Batman MAPE-K status."""
    
    node_id: str
    interface: str
    running: bool
    cycle_count: int
    auto_heal: bool
    last_health_report: Optional[Dict[str, Any]]
    knowledge_stats: Dict[str, Any]


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


class BatmanOriginatorsResponse(BaseModel):
    """Response model for Batman originators."""
    
    node_id: str
    interface: str
    originators: List[Dict[str, Any]]
    count: int
    timestamp: str


class BatmanGatewaysResponse(BaseModel):
    """Response model for Batman gateways."""
    
    node_id: str
    interface: str
    gateways: List[Dict[str, Any]]
    count: int
    has_selected: bool
    gateway_mode: str
    timestamp: str


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


# ============================================================================
# Service Instances
# ============================================================================

# Global instances (can be overridden for testing)
_batman_health_monitors: Dict[str, Any] = {}
_batman_metrics_collectors: Dict[str, Any] = {}
_batman_mapek_loops: Dict[str, Any] = {}


def get_batman_health_monitor(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman health monitor for a node."""
    from libx0t.network.batman.health_monitor import BatmanHealthMonitor
    
    key = f"{node_id}:{interface}"
    if key not in _batman_health_monitors:
        _batman_health_monitors[key] = BatmanHealthMonitor(
            node_id=node_id,
            interface=interface,
        )
    return _batman_health_monitors[key]


def get_batman_metrics_collector(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman metrics collector for a node."""
    from libx0t.network.batman.metrics import BatmanMetricsCollector
    
    key = f"{node_id}:{interface}"
    if key not in _batman_metrics_collectors:
        _batman_metrics_collectors[key] = BatmanMetricsCollector(
            node_id=node_id,
            interface=interface,
        )
    return _batman_metrics_collectors[key]


def get_batman_mapek_loop(node_id: str, interface: str = "bat0") -> Any:
    """Get or create Batman MAPE-K loop for a node."""
    from libx0t.network.batman.mape_k_integration import BatmanMAPEKLoop
    
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
) -> BatmanHealthResponse:
    """Get health status of a Batman-adv node."""
    monitor = get_batman_health_monitor(node_id, interface)
    
    # Run health checks
    report = await monitor.run_health_checks()
    
    return BatmanHealthResponse(
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
    )


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
) -> List[Dict[str, Any]]:
    """Get health history for a Batman-adv node."""
    monitor = get_batman_health_monitor(node_id, interface)
    history = monitor.get_health_history(limit)
    
    return [report.to_dict() for report in history]


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
) -> Dict[str, Any]:
    """Get health trend analysis for a Batman-adv node."""
    monitor = get_batman_health_monitor(node_id, interface)
    trend = monitor.get_health_trend(window)
    
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
) -> BatmanMetricsResponse:
    """Get metrics for a Batman-adv node."""
    collector = get_batman_metrics_collector(node_id, interface)
    
    # Collect metrics
    snapshot = await collector.collect()
    
    return BatmanMetricsResponse(
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
    )


@router.get(
    "/{node_id}/metrics/prometheus",
    summary="Get Prometheus metrics output",
    description="Get Prometheus-formatted metrics for scraping.",
)
async def get_batman_metrics_prometheus(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
) -> str:
    """Get Prometheus-formatted metrics."""
    collector = get_batman_metrics_collector(node_id, interface)
    
    # Collect metrics first
    await collector.collect()
    
    # Return Prometheus output
    return collector.get_metrics_output()


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
) -> List[Dict[str, Any]]:
    """Get metrics history for a Batman-adv node."""
    collector = get_batman_metrics_collector(node_id, interface)
    snapshots = collector.get_snapshots(limit)
    
    return [snapshot.to_dict() for snapshot in snapshots]


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
) -> BatmanTopologyResponse:
    """Get mesh topology from Batman-adv node."""
    try:
        from libx0t.network.batman.topology import MeshTopology, MeshNode, MeshLink, LinkQuality
        
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
                "source": l.source,
                "destination": l.destination,
                "quality": l.quality.name,
                "throughput_mbps": l.throughput_mbps,
                "latency_ms": l.latency_ms,
                "packet_loss_percent": l.packet_loss_percent,
            }
            for l in topology.links.values()
        ]
        
        return BatmanTopologyResponse(
            mesh_id=stats["mesh_id"],
            local_node_id=stats["local_node_id"],
            total_nodes=stats["total_nodes"],
            total_links=stats["total_links"],
            nodes=nodes,
            links=links,
            routing_table=topology.routing_table,
            mesh_diameter=stats.get("mesh_diameter", 0),
        )
        
    except ImportError:
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
) -> BatmanOriginatorsResponse:
    """Get originator table from Batman-adv node."""
    import subprocess
    
    originators = []
    
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="batctl not available",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout getting originators",
        )
    
    return BatmanOriginatorsResponse(
        node_id=node_id,
        interface=interface,
        originators=originators,
        count=len(originators),
        timestamp=datetime.utcnow().isoformat(),
    )


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
) -> BatmanGatewaysResponse:
    """Get gateway list from Batman-adv node."""
    import subprocess
    
    gateways = []
    has_selected = False
    gateway_mode = "unknown"
    
    try:
        # Get gateways
        result = subprocess.run(
            ["batctl", "meshif", interface, "gateways"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
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
        result = subprocess.run(
            ["batctl", "meshif", interface, "gw_mode"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            gateway_mode = result.stdout.strip()
            
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="batctl not available",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout getting gateways",
        )
    
    return BatmanGatewaysResponse(
        node_id=node_id,
        interface=interface,
        gateways=gateways,
        count=len(gateways),
        has_selected=has_selected,
        gateway_mode=gateway_mode,
        timestamp=datetime.utcnow().isoformat(),
    )


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
) -> BatmanMAPEKStatusResponse:
    """Get MAPE-K loop status for Batman-adv node."""
    loop = get_batman_mapek_loop(node_id, interface)
    status = loop.get_status()
    
    return BatmanMAPEKStatusResponse(
        node_id=status["node_id"],
        interface=status["interface"],
        running=status["running"],
        cycle_count=status["cycle_count"],
        auto_heal=status["auto_heal"],
        last_health_report=status.get("last_health_report"),
        knowledge_stats=status["knowledge_stats"],
    )


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
) -> BatmanMAPEKCycleResponse:
    """Manually trigger a MAPE-K cycle for Batman-adv node."""
    loop = get_batman_mapek_loop(node_id, interface)
    loop.auto_heal = auto_heal
    
    # Run one cycle
    result = await loop.run_cycle()
    
    return BatmanMAPEKCycleResponse(
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
    )


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
) -> Dict[str, Any]:
    """Start continuous MAPE-K loop for Batman-adv node."""
    loop = get_batman_mapek_loop(node_id, interface)
    loop.auto_heal = auto_heal
    
    # Start loop in background using FastAPI BackgroundTasks
    if background_tasks:
        background_tasks.add_task(loop.start)
    else:
        # Fallback for testing without BackgroundTasks
        import asyncio
        asyncio.create_task(loop.start())
    
    return {
        "node_id": node_id,
        "interface": interface,
        "status": "started",
        "auto_heal": auto_heal,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post(
    "/{node_id}/mapek/stop",
    summary="Stop Batman MAPE-K loop",
    description="Stop MAPE-K loop for Batman-adv node.",
)
async def stop_batman_mapek_loop(
    node_id: str,
    interface: str = Query("bat0", description="Batman-adv interface"),
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Stop MAPE-K loop for Batman-adv node."""
    loop = get_batman_mapek_loop(node_id, interface)
    loop.stop()
    
    return {
        "node_id": node_id,
        "interface": interface,
        "status": "stopped",
        "timestamp": datetime.utcnow().isoformat(),
    }


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
) -> BatmanHealingResponse:
    """Manually trigger a healing action for Batman-adv node."""
    from libx0t.network.batman.mape_k_integration import BatmanRecoveryAction, BatmanMAPEKExecutor
    
    try:
        action = BatmanRecoveryAction(request.action)
    except ValueError:
        valid_actions = [a.value for a in BatmanRecoveryAction]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Valid actions: {valid_actions}",
        )
    
    executor = BatmanMAPEKExecutor(interface=interface)
    
    try:
        result = await executor._execute_action(action, None)
        
        return BatmanHealingResponse(
            action=request.action,
            success=result.get("status") == "success",
            message=result.get("message", ""),
            timestamp=datetime.utcnow().isoformat(),
            details=result,
        )
    except Exception as e:
        return BatmanHealingResponse(
            action=request.action,
            success=False,
            message=f"Healing action failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
        )


@router.get(
    "/{node_id}/heal/actions",
    summary="Get available healing actions",
    description="Get list of available Batman healing actions.",
)
async def get_batman_healing_actions(
    node_id: str,
    user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get list of available Batman healing actions."""
    from libx0t.network.batman.mape_k_integration import BatmanRecoveryAction
    
    actions = []
    for action in BatmanRecoveryAction:
        actions.append({
            "action": action.value,
            "description": _get_action_description(action),
        })
    
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
) -> Dict[str, Any]:
    """Get Batman-adv status for all nodes in a mesh."""
    instance = get_mesh(mesh_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )
    
    # Check access
    if instance.owner_id != user.user_id:
        await require_mesh_access(mesh_id, user)
    
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
    
    return {
        "mesh_id": mesh_id,
        "nodes": node_statuses,
        "timestamp": datetime.utcnow().isoformat(),
    }


__all__ = ["router"]
