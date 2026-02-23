"""
Batman-adv Mesh Networking Package
===================================

Layer 2 mesh networking implementation for x0tta6bl4.

Modules:
- node_manager: Node lifecycle management and attestation
- topology: Mesh topology discovery and routing
- optimizations: Performance optimizations from Paradox Zone
- slot_sync: Slot-based synchronization for collision avoidance
- health_monitor: Health monitoring and anomaly detection
- metrics: Prometheus metrics collection
- mape_k_integration: MAPE-K autonomic loop integration
"""

from .node_manager import (
    AttestationStrategy,
    HealthMonitor,
    NodeManager,
    NodeMetrics,
    create_incident_workflow_for_node_manager,
)
from .topology import (
    LinkQuality,
    MeshLink,
    MeshNode,
    MeshTopology,
    NodeState,
)
from .optimizations import (
    AODVFallback,
    BatmanAdvConfig,
    BatmanAdvOptimizations,
    MultiPathRouter,
)
from .slot_sync import (
    Beacon,
    SlotInfo,
    SlotState,
    SlotSynchronizer,
)
from .health_monitor import (
    BatmanHealthMonitor,
    HealthCheckResult,
    HealthCheckType,
    HealthStatus,
    NodeHealthReport,
    create_health_monitor_for_mapek,
)
from .metrics import (
    BatmanMetricsCollector,
    BatmanMetricsSnapshot,
    create_metrics_collector_for_mapek,
    integrate_with_x0tta6bl4_metrics,
)
from .mape_k_integration import (
    BatmanAnomaly,
    BatmanAnomalyType,
    BatmanMAPEKAnalyzer,
    BatmanMAPEKExecutor,
    BatmanMAPEKKnowledge,
    BatmanMAPEKLoop,
    BatmanMAPEKMonitor,
    BatmanMAPEKPlanner,
    BatmanRecoveryAction,
    BatmanRecoveryPlan,
    create_batman_mapek_loop,
    integrate_with_existing_mapek,
)

__all__ = [
    # Node Manager
    "AttestationStrategy",
    "HealthMonitor",
    "NodeManager",
    "NodeMetrics",
    "create_incident_workflow_for_node_manager",
    # Topology
    "LinkQuality",
    "MeshLink",
    "MeshNode",
    "MeshTopology",
    "NodeState",
    # Optimizations
    "AODVFallback",
    "BatmanAdvConfig",
    "BatmanAdvOptimizations",
    "MultiPathRouter",
    # Slot Sync
    "Beacon",
    "SlotInfo",
    "SlotState",
    "SlotSynchronizer",
    # Health Monitor
    "BatmanHealthMonitor",
    "HealthCheckResult",
    "HealthCheckType",
    "HealthStatus",
    "NodeHealthReport",
    "create_health_monitor_for_mapek",
    # Metrics
    "BatmanMetricsCollector",
    "BatmanMetricsSnapshot",
    "create_metrics_collector_for_mapek",
    "integrate_with_x0tta6bl4_metrics",
    # MAPE-K Integration
    "BatmanAnomaly",
    "BatmanAnomalyType",
    "BatmanMAPEKAnalyzer",
    "BatmanMAPEKExecutor",
    "BatmanMAPEKKnowledge",
    "BatmanMAPEKLoop",
    "BatmanMAPEKMonitor",
    "BatmanMAPEKPlanner",
    "BatmanRecoveryAction",
    "BatmanRecoveryPlan",
    "create_batman_mapek_loop",
    "integrate_with_existing_mapek",
]
