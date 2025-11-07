"""
Batman-adv Node Manager & Health Monitoring
Lifecycle management and health checks for mesh nodes
"""
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class AttestationStrategy(Enum):
    """Node attestation strategies"""
    SELF_SIGNED = "self_signed"
    SPIFFE = "spiffe"
    TOKEN_BASED = "token_based"
    CHALLENGE_RESPONSE = "challenge_response"


@dataclass
class NodeMetrics:
    """Node health metrics"""
    cpu_percent: float
    memory_percent: float
    network_sent_bytes: int
    network_recv_bytes: int
    packet_loss_percent: float
    latency_to_gateway_ms: float
    timestamp: datetime = None
    
    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy node"""
        return (
            self.cpu_percent < 90 and
            self.memory_percent < 85 and
            self.packet_loss_percent < 5 and
            self.latency_to_gateway_ms < 500
        )


class NodeManager:
    """
    Batman-adv Node Manager
    
    Responsibilities:
    - Node lifecycle (join, leave, bootstrap)
    - Attestation (verify node identity via SPIFFE/tokens)
    - Registration & discovery
    - Heartbeat monitoring
    """
    
    def __init__(self, mesh_id: str, local_node_id: str):
        self.mesh_id = mesh_id
        self.local_node_id = local_node_id
        self.nodes: Dict[str, Dict] = {}
        self.attestation_strategy = AttestationStrategy.SPIFFE
        self.bootstrap_nodes: List[str] = []
        
    def register_node(self, 
                     node_id: str,
                     mac_address: str,
                     ip_address: str,
                     spiffe_id: Optional[str] = None,
                     join_token: Optional[str] = None) -> bool:
        """Register a new node with the mesh"""
        if node_id in self.nodes:
            logger.warning(f"Node {node_id} already registered")
            return False
        
        # Attestation
        if not self._attest_node(node_id, spiffe_id, join_token):
            logger.error(f"Node attestation failed: {node_id}")
            return False
        
        self.nodes[node_id] = {
            "mac_address": mac_address,
            "ip_address": ip_address,
            "spiffe_id": spiffe_id,
            "joined_at": datetime.now(),
            "last_heartbeat": datetime.now(),
            "status": "online",
            "metrics": None,
        }
        
        logger.info(f"Registered node: {node_id} ({ip_address})")
        return True
    
    def _attest_node(self, node_id: str, spiffe_id: Optional[str], join_token: Optional[str]) -> bool:
        """Verify node identity before registration"""
        if self.attestation_strategy == AttestationStrategy.SPIFFE:
            if not spiffe_id or not spiffe_id.startswith("spiffe://"):
                return False
            logger.debug(f"SPIFFE attestation: {spiffe_id}")
        elif self.attestation_strategy == AttestationStrategy.TOKEN_BASED:
            if not join_token:
                return False
            # Verify token (in production, check against token store)
            logger.debug(f"Token attestation: {join_token[:16]}...")
        
        return True
    
    def update_heartbeat(self, node_id: str) -> bool:
        """Update last heartbeat timestamp for node"""
        if node_id not in self.nodes:
            return False
        
        self.nodes[node_id]["last_heartbeat"] = datetime.now()
        return True
    
    def update_metrics(self, node_id: str, metrics: NodeMetrics) -> bool:
        """Update node health metrics"""
        if node_id not in self.nodes:
            return False
        
        self.nodes[node_id]["metrics"] = metrics
        
        # Update status based on metrics
        if metrics.is_healthy():
            self.nodes[node_id]["status"] = "online"
        else:
            self.nodes[node_id]["status"] = "degraded"
        
        return True
    
    def deregister_node(self, node_id: str, reason: str = "unknown") -> bool:
        """Deregister a node from the mesh"""
        if node_id not in self.nodes:
            return False
        
        del self.nodes[node_id]
        logger.info(f"Deregistered node: {node_id} (reason: {reason})")
        return True
    
    def get_node_status(self, node_id: str) -> Optional[Dict]:
        """Get status of a specific node"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> Dict[str, Dict]:
        """Get all registered nodes"""
        return self.nodes.copy()
    
    def get_online_nodes(self) -> List[str]:
        """Get list of online nodes"""
        return [nid for nid, n in self.nodes.items() if n["status"] == "online"]


class HealthMonitor:
    """
    Continuous Health Monitoring for Mesh Network
    
    Monitors:
    - Node availability
    - Link quality
    - Network performance
    - Anomalies & failures
    """
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval  # seconds
        self.health_checks: Dict[str, Callable] = {}
        self.alert_handlers: List[Callable] = []
        self.running = False
        
    def register_health_check(self, name: str, check_fn: Callable):
        """Register a custom health check"""
        self.health_checks[name] = check_fn
        logger.info(f"Registered health check: {name}")
    
    def register_alert_handler(self, handler: Callable):
        """Register callback for health alerts"""
        self.alert_handlers.append(handler)
    
    async def start_monitoring(self, node_manager: NodeManager, topology):
        """Start continuous health monitoring"""
        self.running = True
        logger.info("Starting health monitoring")
        
        while self.running:
            try:
                await self._perform_health_checks(node_manager, topology)
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    async def _perform_health_checks(self, node_manager: NodeManager, topology):
        """Execute all health checks"""
        # Check node heartbeats
        dead_nodes = self._check_node_heartbeats(node_manager)
        if dead_nodes:
            await self._handle_alert("dead_nodes", {"nodes": dead_nodes})
        
        # Check link quality
        degraded_links = self._check_link_quality(topology)
        if degraded_links:
            await self._handle_alert("degraded_links", {"links": degraded_links})
        
        # Run custom checks
        for check_name, check_fn in self.health_checks.items():
            try:
                result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
                if not result:
                    await self._handle_alert(f"check_failed", {"check": check_name})
            except Exception as e:
                logger.error(f"Check {check_name} failed: {e}")
    
    def _check_node_heartbeats(self, node_manager: NodeManager, timeout: int = 120) -> List[str]:
        """Check for nodes with missing heartbeats"""
        dead = []
        now = datetime.now()
        
        for node_id, node_info in node_manager.get_all_nodes().items():
            elapsed = (now - node_info["last_heartbeat"]).total_seconds()
            if elapsed > timeout:
                dead.append(node_id)
                logger.warning(f"Dead node detected: {node_id} (no heartbeat for {elapsed}s)")
        
        return dead
    
    def _check_link_quality(self, topology) -> List[Dict]:
        """Check for degraded links"""
        degraded = []
        for (src, dst), link in topology.links.items():
            if link.quality.value < 3:  # Less than FAIR
                degraded.append({
                    "source": src,
                    "destination": dst,
                    "quality": link.quality.name,
                })
        return degraded
    
    async def _handle_alert(self, alert_type: str, data: Dict):
        """Process health alert"""
        logger.warning(f"Health alert: {alert_type} - {data}")
        
        for handler in self.alert_handlers:
            try:
                result = await handler(alert_type, data) if asyncio.iscoroutinefunction(handler) else handler(alert_type, data)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.running = False
        logger.info("Health monitoring stopped")
