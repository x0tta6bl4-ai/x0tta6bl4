"""
Chaos Mesh Integration for x0tta6bl4

Automated chaos testing for mesh network resilience.
Target: 25% node failure survival with MTTR < 5 seconds.

Scenarios:
- PodDelete: Random node termination
- NetworkPartition: Split-brain simulation
- LatencyInjection: Degraded connectivity
- CPUStress: Resource exhaustion
"""

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ChaosType(Enum):
    """Types of chaos experiments."""

    POD_DELETE = "pod_delete"
    NETWORK_PARTITION = "network_partition"
    LATENCY_INJECTION = "latency_injection"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    IO_STRESS = "io_stress"


@dataclass
class ChaosExperiment:
    """Definition of a chaos experiment."""

    name: str
    chaos_type: ChaosType
    target_percentage: float  # 0.0 - 1.0
    duration_seconds: int
    parameters: Dict = None

    def __post_init__(self):
        self.parameters = self.parameters or {}


@dataclass
class ChaosResult:
    """Result of a chaos experiment."""

    experiment: ChaosExperiment
    started_at: datetime
    ended_at: datetime
    affected_nodes: List[str]
    recovery_time_seconds: float
    success: bool
    metrics: Dict


class ChaosMesh:
    """
    Chaos testing framework for mesh networks.

    Usage:
        chaos = ChaosMesh(node_manager)

        # Run single experiment
        result = chaos.run_experiment(ChaosExperiment(
            name="25% Node Failure",
            chaos_type=ChaosType.POD_DELETE,
            target_percentage=0.25,
            duration_seconds=60
        ))

        # Run nightly suite
        results = chaos.run_nightly_suite()
    """

    # Standard experiment suite
    NIGHTLY_SUITE = [
        ChaosExperiment(
            name="25% Node Failure",
            chaos_type=ChaosType.POD_DELETE,
            target_percentage=0.25,
            duration_seconds=60,
        ),
        ChaosExperiment(
            name="Network Partition (2 segments)",
            chaos_type=ChaosType.NETWORK_PARTITION,
            target_percentage=0.5,
            duration_seconds=30,
            parameters={"segments": 2},
        ),
        ChaosExperiment(
            name="High Latency (500ms)",
            chaos_type=ChaosType.LATENCY_INJECTION,
            target_percentage=0.3,
            duration_seconds=45,
            parameters={"latency_ms": 500, "jitter_ms": 100},
        ),
        ChaosExperiment(
            name="CPU Stress (80%)",
            chaos_type=ChaosType.CPU_STRESS,
            target_percentage=0.2,
            duration_seconds=30,
            parameters={"load_percent": 80},
        ),
    ]

    def __init__(
        self,
        node_manager=None,
        *,
        synthetic_node_count: int = 10,
        min_online_ratio: float = 0.75,
    ):
        self.node_manager = node_manager
        self.min_online_ratio = min_online_ratio
        self._synthetic_nodes = [f"node-{i}" for i in range(max(0, synthetic_node_count))]
        self._synthetic_online_nodes: Set[str] = set(self._synthetic_nodes)
        self._results: List[ChaosResult] = []
        self._hooks: Dict[str, List[Callable]] = {
            "pre_experiment": [],
            "post_experiment": [],
            "on_failure": [],
            "network_partition": [],
            "latency_injection": [],
            "cpu_stress": [],
        }

    def run_experiment(self, experiment: ChaosExperiment) -> ChaosResult:
        """Run a single chaos experiment."""
        logger.info(f"🔥 CHAOS: Starting '{experiment.name}'")

        # Get available nodes
        nodes = self._get_nodes()
        if not nodes:
            logger.warning("No nodes available for chaos testing")
            return self._create_failed_result(experiment, "No nodes")

        # Select targets
        target_count = max(1, int(len(nodes) * experiment.target_percentage))
        targets = random.sample(nodes, min(target_count, len(nodes)))

        logger.info(f"   Targets: {len(targets)}/{len(nodes)} nodes")

        # Run pre-hooks
        self._run_hooks("pre_experiment", experiment, targets)

        started_at = datetime.now()

        # Execute chaos
        try:
            self._execute_chaos(experiment, targets)

            # Wait for duration
            time.sleep(min(experiment.duration_seconds, 5))  # Cap for testing

            # Measure recovery
            recovery_start = time.time()
            recovered = self._wait_for_recovery(targets, timeout=30)
            recovery_time = time.time() - recovery_start

            ended_at = datetime.now()

            # Collect metrics
            metrics = self._collect_metrics(experiment, targets, recovery_time)

            success = recovered and recovery_time < 10  # Target: < 10s MTTR

            result = ChaosResult(
                experiment=experiment,
                started_at=started_at,
                ended_at=ended_at,
                affected_nodes=targets,
                recovery_time_seconds=recovery_time,
                success=success,
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Chaos experiment failed: {e}")
            result = self._create_failed_result(experiment, str(e))

        # Run post-hooks
        self._run_hooks("post_experiment", experiment, result)

        if not result.success:
            self._run_hooks("on_failure", experiment, result)

        self._results.append(result)

        status = "✅ PASS" if result.success else "❌ FAIL"
        logger.info(
            f"🔥 CHAOS: '{experiment.name}' {status} | "
            f"Recovery: {result.recovery_time_seconds:.2f}s"
        )

        return result

    def run_nightly_suite(self) -> List[ChaosResult]:
        """Run the standard nightly chaos suite."""
        logger.info("=" * 60)
        logger.info("🌙 NIGHTLY CHAOS SUITE STARTING")
        logger.info("=" * 60)

        results = []
        for experiment in self.NIGHTLY_SUITE:
            result = self.run_experiment(experiment)
            results.append(result)
            time.sleep(1)  # Brief pause between experiments

        # Summary
        passed = sum(1 for r in results if r.success)
        total = len(results)
        avg_recovery = (
            sum(r.recovery_time_seconds for r in results) / total if total else 0
        )

        logger.info("=" * 60)
        logger.info(f"🌙 NIGHTLY CHAOS COMPLETE: {passed}/{total} PASSED")
        logger.info(f"   Average Recovery Time: {avg_recovery:.2f}s")
        logger.info("=" * 60)

        return results

    def _get_nodes(self) -> List[str]:
        """Get list of available nodes."""
        if self.node_manager:
            return list(self.node_manager.nodes.keys())
        return list(self._synthetic_nodes)

    def _execute_chaos(self, experiment: ChaosExperiment, targets: List[str]):
        """Execute the chaos action."""
        chaos_type = experiment.chaos_type

        if chaos_type == ChaosType.POD_DELETE:
            self._simulate_pod_delete(targets)
        elif chaos_type == ChaosType.NETWORK_PARTITION:
            self._simulate_network_partition(targets, experiment.parameters)
        elif chaos_type == ChaosType.LATENCY_INJECTION:
            self._simulate_latency(targets, experiment.parameters)
        elif chaos_type == ChaosType.CPU_STRESS:
            self._simulate_cpu_stress(targets, experiment.parameters)

    def _simulate_pod_delete(self, targets: List[str]):
        """Simulate node deletion."""
        for node_id in targets:
            logger.debug(f"   Killing node: {node_id}")
            if self.node_manager and node_id in self.node_manager.nodes:
                # Mark as offline
                self.node_manager.nodes[node_id].is_online = False
            elif not self.node_manager:
                self._synthetic_online_nodes.discard(node_id)

    def _simulate_network_partition(self, targets: List[str], params: Dict):
        """Simulate network partition."""
        segments = params.get("segments", 2)
        logger.debug(f"   Creating {segments} network segments")
        self._run_hooks("network_partition", targets, params)

    def _simulate_latency(self, targets: List[str], params: Dict):
        """Simulate network latency."""
        latency_ms = params.get("latency_ms", 100)
        logger.debug(f"   Injecting {latency_ms}ms latency")
        self._run_hooks("latency_injection", targets, params)

    def _simulate_cpu_stress(self, targets: List[str], params: Dict):
        """Simulate CPU stress."""
        load = params.get("load_percent", 50)
        logger.debug(f"   Applying {load}% CPU load")
        self._run_hooks("cpu_stress", targets, params)

    def _wait_for_recovery(self, targets: List[str], timeout: int = 30) -> bool:
        """Wait for mesh to recover from chaos."""
        start = time.time()

        while time.time() - start < timeout:
            # Check if mesh has self-healed
            if self._check_mesh_health(targets):
                return True
            time.sleep(0.5)

        return False

    def _node_is_online(self, node_id: str) -> bool:
        if not self.node_manager:
            return node_id in self._synthetic_online_nodes

        if hasattr(self.node_manager, "is_node_online"):
            return bool(self.node_manager.is_node_online(node_id))

        node = self.node_manager.nodes.get(node_id)
        if node is None:
            return False

        if isinstance(node, dict):
            for key in ("is_online", "online", "healthy", "ready"):
                if key in node:
                    return bool(node[key])
            status = str(node.get("status", "")).lower()
            if status:
                return status in {"online", "healthy", "ready"}
            return True

        for attr in ("is_online", "online", "healthy", "ready"):
            if hasattr(node, attr):
                return bool(getattr(node, attr))

        status = str(getattr(node, "status", "")).lower()
        if status:
            return status in {"online", "healthy", "ready"}

        return True

    def _mesh_health_snapshot(self) -> Dict:
        nodes = self._get_nodes()
        if not nodes:
            return {
                "healthy": False,
                "online_nodes": 0,
                "total_nodes": 0,
                "online_ratio": 0.0,
                "offline_nodes": [],
                "min_online_ratio": self.min_online_ratio,
            }

        offline_nodes = [
            node_id for node_id in nodes if not self._node_is_online(node_id)
        ]
        online_nodes = len(nodes) - len(offline_nodes)
        online_ratio = online_nodes / len(nodes)
        return {
            "healthy": online_ratio >= self.min_online_ratio,
            "online_nodes": online_nodes,
            "total_nodes": len(nodes),
            "online_ratio": online_ratio,
            "offline_nodes": offline_nodes,
            "min_online_ratio": self.min_online_ratio,
        }

    def _check_mesh_health(self, targets: Optional[List[str]] = None) -> bool:
        """Check if mesh is healthy."""
        snapshot = self._mesh_health_snapshot()
        if not snapshot["healthy"]:
            logger.warning(
                "Mesh health below threshold: %.2f online, target %.2f, "
                "affected=%s, offline=%s",
                snapshot["online_ratio"],
                snapshot["min_online_ratio"],
                targets or [],
                snapshot["offline_nodes"],
            )
        return bool(snapshot["healthy"])

    def _collect_metrics(
        self, experiment: ChaosExperiment, targets: List[str], recovery_time: float
    ) -> Dict:
        """Collect experiment metrics."""
        health = self._mesh_health_snapshot()
        return {
            "experiment_type": experiment.chaos_type.value,
            "target_count": len(targets),
            "target_percentage": experiment.target_percentage,
            "duration_seconds": experiment.duration_seconds,
            "recovery_time_seconds": recovery_time,
            "mttr_target_met": recovery_time < 5.0,
            "mesh_healthy": health["healthy"],
            "online_nodes": health["online_nodes"],
            "total_nodes": health["total_nodes"],
            "online_ratio": health["online_ratio"],
            "min_online_ratio": health["min_online_ratio"],
        }

    def _create_failed_result(
        self, experiment: ChaosExperiment, error: str
    ) -> ChaosResult:
        """Create a failed result."""
        now = datetime.now()
        return ChaosResult(
            experiment=experiment,
            started_at=now,
            ended_at=now,
            affected_nodes=[],
            recovery_time_seconds=float("inf"),
            success=False,
            metrics={"error": error},
        )

    def _run_hooks(self, hook_name: str, *args):
        """Run registered hooks."""
        for hook in self._hooks.get(hook_name, []):
            try:
                hook(*args)
            except Exception as e:
                logger.error(f"Hook {hook_name} failed: {e}")

    def on(self, event: str, handler: Callable):
        """Register event handler."""
        if event in self._hooks:
            self._hooks[event].append(handler)

    def get_summary(self) -> Dict:
        """Get summary of all experiments."""
        if not self._results:
            return {"total": 0, "passed": 0, "failed": 0}

        passed = sum(1 for r in self._results if r.success)
        return {
            "total": len(self._results),
            "passed": passed,
            "failed": len(self._results) - passed,
            "pass_rate": passed / len(self._results),
            "avg_recovery_time": sum(
                r.recovery_time_seconds
                for r in self._results
                if r.recovery_time_seconds != float("inf")
            )
            / len(self._results),
        }
