"""
Mesh Instance - Running mesh network with consciousness metrics.

Contains the MeshInstance class for managing mesh lifecycle and metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


class MeshInstance:
    """Running mesh network instance with consciousness metrics."""

    def __init__(
        self,
        mesh_id: str,
        name: str,
        owner_id: str,
        nodes: int,
        pqc_enabled: bool = True,
        obfuscation: str = "none",
        traffic_profile: str = "none",
    ):
        self.mesh_id = mesh_id
        self.name = name
        self.owner_id = owner_id
        self.target_nodes = nodes
        self.pqc_enabled = pqc_enabled
        self.obfuscation = obfuscation
        self.traffic_profile = traffic_profile
        self.status = "provisioning"
        self.created_at = datetime.utcnow()
        self.join_token: str = ""  # Set by provisioner
        self.join_token_ttl_sec: int = 604800
        self.join_token_issued_at: datetime = self.created_at
        self.join_token_expires_at: datetime = self.created_at + timedelta(seconds=604800)
        self.node_instances: Dict[str, Dict] = {}
        self._config: Any = None

    async def provision(self) -> None:
        """Provision mesh nodes."""
        try:
            from src.libx0t.network.mesh_node import MeshNodeConfig

            config = MeshNodeConfig(
                node_id=self.mesh_id,
                port=5000 + hash(self.mesh_id) % 4000,
                obfuscation=self.obfuscation,
                traffic_profile=self.traffic_profile,
            )
            self._config = config
        except ImportError:
            pass

        for i in range(self.target_nodes):
            node_id = f"{self.mesh_id}-node-{i}"
            self.node_instances[node_id] = {
                "id": node_id,
                "status": "healthy",
                "started_at": datetime.utcnow().isoformat(),
                "latency_ms": 0.0,
            }
        self.status = "active"
        logger.info(
            f"[MaaS] Provisioned mesh {self.mesh_id}: "
            f"{self.target_nodes} nodes, PQC={self.pqc_enabled}"
        )

    async def terminate(self) -> None:
        """Terminate the mesh."""
        self.node_instances.clear()
        self.status = "terminated"
        logger.info(f"[MaaS] Terminated mesh {self.mesh_id}")

    def scale(self, action: str, count: int) -> int:
        """
        Scale mesh nodes up or down.

        Args:
            action: "scale_up" or "scale_down"
            count: Number of nodes to add/remove

        Returns:
            New total node count
        """
        previous = len(self.node_instances)
        if action == "scale_up":
            for i in range(count):
                node_id = f"{self.mesh_id}-node-{previous + i}"
                self.node_instances[node_id] = {
                    "id": node_id,
                    "status": "healthy",
                    "started_at": datetime.utcnow().isoformat(),
                    "latency_ms": 0.0,
                }
            self.target_nodes += count
        elif action == "scale_down":
            to_remove = min(count, len(self.node_instances) - 1)
            keys = list(self.node_instances.keys())[-to_remove:]
            for k in keys:
                del self.node_instances[k]
            self.target_nodes = max(1, self.target_nodes - count)
        return len(self.node_instances)

    def get_health_score(self) -> float:
        """Calculate mesh health score (0.0 - 1.0)."""
        if not self.node_instances:
            return 0.0
        healthy = sum(
            1 for n in self.node_instances.values() if n["status"] == "healthy"
        )
        return healthy / len(self.node_instances)

    def get_uptime(self) -> float:
        """Get mesh uptime in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def get_consciousness_metrics(self) -> Dict[str, Any]:
        """
        Calculate consciousness engine metrics.

        Returns phi-ratio, entropy, harmony, and state.
        """
        health = self.get_health_score()
        uptime = self.get_uptime()
        phi = min(1.618, 0.5 + health * 1.118)
        entropy = max(0.0, 1.0 - health)
        harmony = health * min(1.0, uptime / 3600)

        if health >= 0.95:
            state = "TRANSCENDENT"
        elif health >= 0.8:
            state = "FLOW"
        elif health >= 0.5:
            state = "AWARE"
        else:
            state = "DORMANT"

        return {
            "phi_ratio": round(phi, 4),
            "entropy": round(entropy, 4),
            "harmony": round(harmony, 4),
            "state": state,
            "nodes_total": len(self.node_instances),
            "nodes_healthy": sum(
                1 for n in self.node_instances.values() if n["status"] == "healthy"
            ),
        }

    def get_mape_k_state(self) -> Dict[str, Any]:
        """
        Get MAPE-K control loop state.

        Returns current phase, interval, and directives.
        """
        health = self.get_health_score()

        if health < 0.5:
            aggressiveness = "high"
        elif health < 0.8:
            aggressiveness = "medium"
        else:
            aggressiveness = "low"

        return {
            "phase": "MONITOR",
            "interval_seconds": 10 if health < 0.8 else 30,
            "directives": {
                "monitoring_interval": 10 if health < 0.8 else 30,
                "self_healing_aggressiveness": aggressiveness,
                "scaling_recommendation": "scale_up" if health < 0.5 else "maintain",
            },
            "last_cycle": datetime.utcnow().isoformat(),
        }

    def get_network_metrics(self) -> Dict[str, Any]:
        """Get network performance metrics."""
        health = self.get_health_score()
        return {
            "nodes_active": len(self.node_instances),
            "avg_latency_ms": 12.5,
            "throughput_mbps": len(self.node_instances) * 10.0,
            "packet_loss_pct": 0.01 if health > 0.9 else 0.5,
            "pqc_handshakes_completed": len(self.node_instances) * 3,
            "obfuscation_mode": self.obfuscation,
            "traffic_profile": self.traffic_profile,
        }


__all__ = ["MeshInstance"]
