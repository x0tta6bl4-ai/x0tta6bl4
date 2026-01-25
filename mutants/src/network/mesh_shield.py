"""
x0tta6bl4 MeshShield Quarantine Engine
Fast failure detection and automatic recovery.

Target: MTTR < 9 seconds (from ~20 seconds baseline)

Components:
1. Fast Failure Detection (1-2 sec) - Beacon-based heartbeat
2. Rapid Quarantine (2-3 sec) - Isolate failing nodes
3. Auto-Rerouting (3-5 sec) - Switch to backup paths
4. P2P Reputation (continuous) - Track node reliability
"""
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
import json

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    DEAD = "dead"


@dataclass
class NodeHealth:
    """Health metrics for a mesh node."""
    node_id: str
    status: NodeStatus = NodeStatus.HEALTHY
    last_beacon: float = 0.0
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    reputation: float = 1.0  # 0.0 - 1.0
    failure_count: int = 0
    recovery_count: int = 0
    quarantine_until: float = 0.0
    
    def is_alive(self, timeout: float = 3.0) -> bool:
        """Check if node responded within timeout."""
        return (time.time() - self.last_beacon) < timeout
    
    def is_quarantined(self) -> bool:
        """Check if node is in quarantine."""
        return time.time() < self.quarantine_until


@dataclass
class FailureEvent:
    """Record of a failure event for analysis."""
    node_id: str
    timestamp: float
    detection_time: float  # Time to detect failure
    recovery_time: float = 0.0  # Time to recover (MTTR)
    cause: str = "unknown"
    recovered: bool = False


class MeshShield:
    """
    Self-healing engine for mesh network.
    
    MAPE-K Loop:
    - Monitor: Beacon packets every 500ms
    - Analyze: Detect anomalies (latency, packet loss)
    - Plan: Calculate alternative routes
    - Execute: Switch traffic, quarantine bad nodes
    - Knowledge: Update reputation scores
    """
    
    # Configuration
    BEACON_INTERVAL = 0.5  # 500ms between beacons
    HEALTH_CHECK_INTERVAL = 1.0  # 1 second health evaluation
    FAILURE_THRESHOLD = 3.0  # 3 seconds without beacon = failure
    DEGRADED_THRESHOLD = 1.5  # 1.5 seconds = degraded
    QUARANTINE_DURATION = 30.0  # 30 seconds quarantine
    REPUTATION_DECAY = 0.95  # Reputation decay per failure
    REPUTATION_RECOVERY = 1.02  # Reputation recovery per success
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.nodes: Dict[str, NodeHealth] = {}
        self.failure_events: List[FailureEvent] = []
        self.active_routes: Dict[str, List[str]] = {}  # destination -> route
        self.backup_routes: Dict[str, List[str]] = {}  # destination -> backup route
        self._running = False
        self._metrics = {
            "mttr_samples": [],
            "mttd_samples": [],
            "failures_detected": 0,
            "failures_recovered": 0,
            "quarantines": 0,
        }
    
    async def start(self):
        """Start the MeshShield engine."""
        self._running = True
        logger.info(f"🛡️ MeshShield started for {self.node_id}")
        
        # Start background tasks
        asyncio.create_task(self._beacon_loop())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._reputation_loop())
    
    async def stop(self):
        """Stop the MeshShield engine."""
        self._running = False
        logger.info("🛡️ MeshShield stopped")
    
    def register_node(self, node_id: str):
        """Register a node for monitoring."""
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeHealth(node_id=node_id, last_beacon=time.time())
            logger.info(f"📡 Registered node: {node_id}")
    
    def receive_beacon(self, node_id: str, latency_ms: float):
        """Process incoming beacon from a node."""
        if node_id not in self.nodes:
            self.register_node(node_id)
        
        node = self.nodes[node_id]
        now = time.time()
        
        # Update health metrics
        node.last_beacon = now
        node.latency_ms = latency_ms
        
        # Check if recovering from failure
        if node.status in (NodeStatus.QUARANTINED, NodeStatus.DEAD):
            node.recovery_count += 1
            self._complete_recovery(node_id)
        
        # Update status based on latency
        if latency_ms > 500:  # High latency
            node.status = NodeStatus.DEGRADED
        else:
            node.status = NodeStatus.HEALTHY
        
        # Reputation recovery
        node.reputation = min(1.0, node.reputation * self.REPUTATION_RECOVERY)
    
    async def _beacon_loop(self):
        """Send beacons to all registered nodes."""
        while self._running:
            for node_id, node in list(self.nodes.items()):
                if not node.is_quarantined():
                    # In real implementation, send actual beacon
                    # Here we just check if we received one recently
                    pass
            
            await asyncio.sleep(self.BEACON_INTERVAL)
    
    async def _health_check_loop(self):
        """Evaluate node health and trigger actions."""
        while self._running:
            now = time.time()
            
            for node_id, node in list(self.nodes.items()):
                time_since_beacon = now - node.last_beacon
                
                # Skip quarantined nodes
                if node.is_quarantined():
                    continue
                
                # Check for failure
                if time_since_beacon > self.FAILURE_THRESHOLD:
                    if node.status != NodeStatus.DEAD:
                        await self._handle_failure(node_id, time_since_beacon)
                
                # Check for degradation
                elif time_since_beacon > self.DEGRADED_THRESHOLD:
                    if node.status == NodeStatus.HEALTHY:
                        node.status = NodeStatus.DEGRADED
                        logger.warning(f"⚠️ Node {node_id} degraded (beacon delay: {time_since_beacon:.2f}s)")
            
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
    
    async def _handle_failure(self, node_id: str, detection_time: float):
        """Handle detected node failure."""
        node = self.nodes[node_id]
        failure_start = time.time()
        
        # Record failure
        node.status = NodeStatus.DEAD
        node.failure_count += 1
        node.reputation *= self.REPUTATION_DECAY
        self._metrics["failures_detected"] += 1
        
        logger.error(f"❌ Node {node_id} FAILED (detected in {detection_time:.2f}s)")
        
        # Create failure event
        event = FailureEvent(
            node_id=node_id,
            timestamp=failure_start,
            detection_time=detection_time,
            cause="beacon_timeout"
        )
        self.failure_events.append(event)
        self._metrics["mttd_samples"].append(detection_time)
        
        # Step 1: Quarantine (immediate)
        await self._quarantine_node(node_id)
        
        # Step 2: Reroute traffic (async)
        await self._reroute_traffic(node_id)
        
        # Record MTTR
        mttr = time.time() - failure_start
        event.recovery_time = mttr
        event.recovered = True
        self._metrics["mttr_samples"].append(mttr)
        self._metrics["failures_recovered"] += 1
        
        logger.info(f"✅ Recovered from {node_id} failure in {mttr:.2f}s (MTTR)")
    
    async def _quarantine_node(self, node_id: str):
        """Put node in quarantine."""
        node = self.nodes[node_id]
        node.status = NodeStatus.QUARANTINED
        node.quarantine_until = time.time() + self.QUARANTINE_DURATION
        self._metrics["quarantines"] += 1
        
        logger.warning(f"🔒 Node {node_id} quarantined for {self.QUARANTINE_DURATION}s")
    
    async def _reroute_traffic(self, failed_node: str):
        """Reroute traffic away from failed node."""
        rerouted = 0
        
        for destination, route in list(self.active_routes.items()):
            if failed_node in route:
                # Try backup route
                if destination in self.backup_routes:
                    backup = self.backup_routes[destination]
                    if failed_node not in backup:
                        self.active_routes[destination] = backup
                        rerouted += 1
                        logger.info(f"🔀 Rerouted {destination}: {route} → {backup}")
                else:
                    # Calculate new route excluding failed node
                    new_route = self._calculate_route(destination, exclude=[failed_node])
                    if new_route:
                        self.active_routes[destination] = new_route
                        rerouted += 1
                        logger.info(f"🔀 New route for {destination}: {new_route}")
        
        if rerouted > 0:
            logger.info(f"🔀 Rerouted {rerouted} connections")
    
    def _calculate_route(self, destination: str, exclude: List[str] = None) -> List[str]:
        """Calculate best route to destination, excluding certain nodes."""
        exclude = exclude or []
        
        # Get healthy nodes sorted by reputation and latency
        candidates = [
            (node_id, node)
            for node_id, node in self.nodes.items()
            if node_id not in exclude
            and node.status == NodeStatus.HEALTHY
            and not node.is_quarantined()
        ]
        
        # Sort by reputation * (1 / latency)
        candidates.sort(key=lambda x: x[1].reputation / max(x[1].latency_ms, 1), reverse=True)
        
        if candidates:
            return [c[0] for c in candidates[:2]]  # Top 2 nodes as route
        return []
    
    def _complete_recovery(self, node_id: str):
        """Complete recovery process for a node."""
        node = self.nodes[node_id]
        node.status = NodeStatus.HEALTHY
        node.quarantine_until = 0.0
        
        logger.info(f"🔓 Node {node_id} recovered and active")
    
    async def _reputation_loop(self):
        """Periodically update reputation scores."""
        while self._running:
            for node_id, node in self.nodes.items():
                # Slowly recover reputation for healthy nodes
                if node.status == NodeStatus.HEALTHY:
                    node.reputation = min(1.0, node.reputation * 1.001)
                
                # Decay reputation for degraded nodes
                elif node.status == NodeStatus.DEGRADED:
                    node.reputation *= 0.999
            
            await asyncio.sleep(10.0)  # Every 10 seconds
    
    def get_metrics(self) -> dict:
        """Get current MTTR/MTTD metrics."""
        mttr_samples = self._metrics["mttr_samples"]
        mttd_samples = self._metrics["mttd_samples"]
        
        return {
            "mttr_avg": sum(mttr_samples) / len(mttr_samples) if mttr_samples else 0,
            "mttr_p95": sorted(mttr_samples)[int(len(mttr_samples) * 0.95)] if len(mttr_samples) > 1 else 0,
            "mttd_avg": sum(mttd_samples) / len(mttd_samples) if mttd_samples else 0,
            "failures_detected": self._metrics["failures_detected"],
            "failures_recovered": self._metrics["failures_recovered"],
            "recovery_rate": self._metrics["failures_recovered"] / max(self._metrics["failures_detected"], 1),
            "quarantines": self._metrics["quarantines"],
            "nodes_healthy": sum(1 for n in self.nodes.values() if n.status == NodeStatus.HEALTHY),
            "nodes_degraded": sum(1 for n in self.nodes.values() if n.status == NodeStatus.DEGRADED),
            "nodes_quarantined": sum(1 for n in self.nodes.values() if n.is_quarantined()),
        }
    
    def get_node_status(self) -> List[dict]:
        """Get status of all nodes."""
        return [
            {
                "node_id": node.node_id,
                "status": node.status.value,
                "latency_ms": round(node.latency_ms, 2),
                "reputation": round(node.reputation, 3),
                "failures": node.failure_count,
                "recoveries": node.recovery_count,
                "quarantined": node.is_quarantined(),
            }
            for node in self.nodes.values()
        ]
    
    def export_metrics(self, filepath: str = "mesh_shield_metrics.json"):
        """Export metrics to file."""
        data = {
            "timestamp": time.time(),
            "node_id": self.node_id,
            "metrics": self.get_metrics(),
            "nodes": self.get_node_status(),
            "failure_events": [
                {
                    "node_id": e.node_id,
                    "timestamp": e.timestamp,
                    "detection_time": e.detection_time,
                    "recovery_time": e.recovery_time,
                    "cause": e.cause,
                    "recovered": e.recovered,
                }
                for e in self.failure_events[-100:]  # Last 100 events
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"📊 Metrics exported to {filepath}")


# Integration with MeshRouter
class ShieldedMeshRouter:
    """MeshRouter with MeshShield integration."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.shield = MeshShield(node_id)
        # Import actual router
        try:
            from .mesh_router import MeshRouter
            self.router = MeshRouter(node_id)
        except ImportError:
            self.router = None
    
    async def start(self):
        """Start router with shield."""
        await self.shield.start()
        if self.router:
            await self.router.start()
        
        # Register known peers
        if self.router:
            for peer_id in self.router.peers:
                self.shield.register_node(peer_id)
    
    async def stop(self):
        """Stop router and shield."""
        await self.shield.stop()
        if self.router:
            await self.router.stop()
    
    def on_peer_beacon(self, peer_id: str, latency_ms: float):
        """Handle beacon from peer."""
        self.shield.receive_beacon(peer_id, latency_ms)
    
    def get_healthy_peers(self) -> List[str]:
        """Get list of healthy peers for routing."""
        return [
            node_id
            for node_id, node in self.shield.nodes.items()
            if node.status == NodeStatus.HEALTHY
            and not node.is_quarantined()
        ]


# Quick test
if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    async def test_shield():
        shield = MeshShield("local-node")
        await shield.start()
        
        # Register some nodes
        shield.register_node("node-vps1")
        shield.register_node("node-vps2")
        shield.register_node("node-vps3")
        
        # Simulate beacons
        for i in range(10):
            shield.receive_beacon("node-vps1", latency_ms=50)
            shield.receive_beacon("node-vps2", latency_ms=80)
            # node-vps3 stops responding after iteration 3
            if i < 3:
                shield.receive_beacon("node-vps3", latency_ms=100)
            
            await asyncio.sleep(1)
            
            # Print status
            metrics = shield.get_metrics()
            print(f"\n--- Iteration {i+1} ---")
            print(f"Healthy: {metrics['nodes_healthy']}, Degraded: {metrics['nodes_degraded']}, Quarantined: {metrics['nodes_quarantined']}")
            if metrics['mttr_avg'] > 0:
                print(f"MTTR avg: {metrics['mttr_avg']:.2f}s")
        
        await shield.stop()
        
        # Final metrics
        print("\n=== Final Metrics ===")
        metrics = shield.get_metrics()
        for k, v in metrics.items():
            print(f"  {k}: {v}")
    
    asyncio.run(test_shield())
