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
import json

# Security Integration
try:
    from src.security.spiffe.workload.api_client import WorkloadAPIClient, X509SVID
    SPIFFE_AVAILABLE = True
except ImportError:
    SPIFFE_AVAILABLE = False

# Obfuscation Integration
try:
    from src.network.obfuscation import TransportManager, ObfuscationTransport
    OBFUSCATION_AVAILABLE = True
except ImportError:
    OBFUSCATION_AVAILABLE = False

# DAO Integration
try:
    from src.dao.governance import GovernanceEngine, VoteType
    DAO_AVAILABLE = True
except ImportError:
    DAO_AVAILABLE = False

# Traffic Shaping Integration
try:
    from src.network.obfuscation.traffic_shaping import TrafficShaper, TrafficProfile
    TRAFFIC_SHAPING_AVAILABLE = True
except ImportError:
    TRAFFIC_SHAPING_AVAILABLE = False

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
    
    def __init__(self, mesh_id: str, local_node_id: str, 
                 obfuscation_transport: Optional['ObfuscationTransport'] = None,
                 traffic_profile: str = "none"):
        self.mesh_id = mesh_id
        self.local_node_id = local_node_id
        self.nodes: Dict[str, Dict] = {}
        self.attestation_strategy = AttestationStrategy.SPIFFE
        self.bootstrap_nodes: List[str] = []
        self.obfuscation_transport = obfuscation_transport
        
        # Traffic Shaping
        self.traffic_shaper = None
        if TRAFFIC_SHAPING_AVAILABLE and traffic_profile != "none":
            try:
                profile = TrafficProfile(traffic_profile)
                self.traffic_shaper = TrafficShaper(profile)
                logger.info(f"Traffic shaping enabled with profile: {traffic_profile}")
                self._record_traffic_profile_active(traffic_profile)
            except ValueError:
                logger.warning(f"Unknown traffic profile: {traffic_profile}, shaping disabled")
        
        # DAO Governance
        self.governance = None
        if DAO_AVAILABLE:
            self.governance = GovernanceEngine(node_id=local_node_id)
            logger.info(f"DAO Governance initialized for {local_node_id}")

    def propose_network_update(self, title: str, action: Dict) -> Optional[str]:
        """Propose a network configuration update via DAO."""
        if not self.governance:
            logger.warning("Governance not available")
            return None
            
        proposal = self.governance.create_proposal(
            title=title,
            description=f"Network update: {action}",
            actions=[action]
        )
        return proposal.id

    def vote_on_proposal(self, proposal_id: str, vote_str: str) -> bool:
        """Vote on an existing proposal."""
        if not self.governance:
            return False
            
        try:
            vote = VoteType[vote_str.upper()]
            return self.governance.cast_vote(proposal_id, self.local_node_id, vote)
        except KeyError:
            logger.error(f"Invalid vote type: {vote_str}")
            return False

    def check_governance(self):
        """Periodic governance check (tally votes, execute)."""
        if self.governance:
            self.governance.check_proposals()
            # In a real loop, we would check for PASSED proposals and execute actions here
            # self._execute_passed_proposals()

    def _record_traffic_profile_active(self, profile: str):
        """Record active traffic profile metric."""
        try:
            from src.monitoring.metrics import traffic_profile_active
            traffic_profile_active.labels(node_id=self.local_node_id, profile=profile).set(1)
        except ImportError:
            pass

    def _record_traffic_shaping_metrics(self, original_len: int, shaped_len: int, delay: float, profile: str):
        """Record traffic shaping metrics."""
        try:
            from src.monitoring.metrics import (
                traffic_shaped_packets_total,
                traffic_shaping_bytes_total,
                traffic_shaping_padding_bytes_total,
                traffic_shaping_delay_seconds
            )
            traffic_shaped_packets_total.labels(node_id=self.local_node_id, profile=profile).inc()
            traffic_shaping_bytes_total.labels(node_id=self.local_node_id, profile=profile).inc(shaped_len)
            padding = shaped_len - original_len - 2  # -2 for length prefix
            if padding > 0:
                traffic_shaping_padding_bytes_total.labels(node_id=self.local_node_id, profile=profile).inc(padding)
            if delay > 0:
                traffic_shaping_delay_seconds.labels(node_id=self.local_node_id, profile=profile).observe(delay)
        except ImportError:
            pass

    def send_heartbeat(self, target_node: str) -> bool:
        """Send heartbeat to a target node (with obfuscation and traffic shaping)."""
        payload = {
            "type": "heartbeat",
            "node_id": self.local_node_id,
            "timestamp": datetime.now().isoformat()
        }
        data = json.dumps(payload).encode('utf-8')
        original_len = len(data)
        
        # Apply obfuscation first
        if self.obfuscation_transport:
            try:
                data = self.obfuscation_transport.obfuscate(data)
                try:
                    from src.monitoring.metrics import heartbeat_obfuscated_total
                    heartbeat_obfuscated_total.inc()
                except ImportError:
                    pass
            except Exception as e:
                logger.error(f"Obfuscation failed for heartbeat: {e}")
                return False
        
        # Apply traffic shaping
        delay = 0.0
        if self.traffic_shaper:
            shaped_data = self.traffic_shaper.shape_packet(data)
            delay = self.traffic_shaper.get_send_delay()
            profile = self.traffic_shaper.profile.value
            self._record_traffic_shaping_metrics(len(data), len(shaped_data), delay, profile)
            data = shaped_data
                
        # In a real system, we would apply delay and send 'data' over the network.
        # logger.debug(f"Sent heartbeat to {target_node} ({len(data)} bytes, delay={delay:.3f}s)")
        return True

    def send_topology_update(self, target_node: str, topology_data: Dict) -> bool:
        """Send topology update to a target node (with obfuscation and traffic shaping)."""
        payload = {
            "type": "topology_update",
            "node_id": self.local_node_id,
            "data": topology_data,
            "timestamp": datetime.now().isoformat()
        }
        data = json.dumps(payload).encode('utf-8')
        
        if self.obfuscation_transport:
            try:
                data = self.obfuscation_transport.obfuscate(data)
            except Exception as e:
                logger.error(f"Obfuscation failed for topology update: {e}")
                return False
        
        # Apply traffic shaping
        if self.traffic_shaper:
            shaped_data = self.traffic_shaper.shape_packet(data)
            delay = self.traffic_shaper.get_send_delay()
            profile = self.traffic_shaper.profile.value
            self._record_traffic_shaping_metrics(len(data), len(shaped_data), delay, profile)
            data = shaped_data
                
        # In a real system, we would apply delay and send 'data' over the network.
        return True

    def register_node(self, 
                     node_id: str,
                     mac_address: str,
                     ip_address: str,
                     spiffe_id: Optional[str] = None,
                     join_token: Optional[str] = None,
                     cert_pem: Optional[bytes] = None) -> bool:
        """Register a new node with the mesh"""
        if node_id in self.nodes:
            logger.warning(f"Node {node_id} already registered")
            return False
        
        # Attestation
        if not self._attest_node(node_id, spiffe_id, join_token, cert_pem):
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
    
    def _attest_node(self, node_id: str, spiffe_id: Optional[str], join_token: Optional[str], cert_pem: Optional[bytes] = None) -> bool:
        """Verify node identity before registration"""
        if self.attestation_strategy == AttestationStrategy.SPIFFE:
            if not spiffe_id or not spiffe_id.startswith("spiffe://"):
                return False
            
            # Enhanced Validation if module available and cert provided
            if SPIFFE_AVAILABLE and cert_pem:
                try:
                    # Construct SVID object for validation
                    # Note: In a real scenario, we would parse the cert to get expiry/chain
                    # For now, we create a wrapper to use the validation logic
                    svid = X509SVID(
                        spiffe_id=spiffe_id,
                        cert_chain=[cert_pem],
                        private_key=b"",  # Not needed for public validation
                        expiry=datetime.utcnow() + timedelta(hours=1) # Mock expiry for now as we don't parse yet
                    )
                    
                    # Use the WorkloadAPIClient logic (even if mocked)
                    # We instantiate client with default/dummy path as we only need logic
                    client = WorkloadAPIClient()
                    if not client.validate_peer_svid(svid, expected_id=spiffe_id):
                        logger.error(f"SPIFFE SVID validation failed for {node_id}")
                        return False
                        
                    logger.info(f"SPIFFE Strong Attestation success: {spiffe_id}")
                    
                    # Record metric
                    try:
                        from src.monitoring.metrics import set_node_spiffe_attested
                        set_node_spiffe_attested(node_id, spiffe_id, True)
                    except ImportError:
                        pass
                        
                except Exception as e:
                    logger.error(f"SPIFFE validation error: {e}")
                    return False

            logger.debug(f"SPIFFE attestation passed: {spiffe_id}")

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
