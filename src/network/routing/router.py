"""
Mesh Router - Simplified Facade.

Provides a unified interface for mesh routing that coordinates:
- TopologyManager: Node and link management
- RouteTable: Route storage and lookup
- PacketHandler: Protocol packet processing
- RouteRecovery: Failure detection and repair
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .packet_handler import PacketHandler, RoutingPacket
from .recovery import RouteRecovery
from .route_table import RouteEntry, RouteTable
from .topology import LinkQuality, NodeInfo, TopologyManager

logger = logging.getLogger(__name__)


class MeshRouter:
    """
    Simplified Mesh Router facade.
    
    Coordinates all routing components and provides a clean API
    for the rest of the system.
    
    Usage:
        router = MeshRouter("node-001")
        await router.start()
        
        # Add neighbors
        router.add_neighbor("node-002", link_quality=LinkQuality(latency_ms=10))
        
        # Send data
        next_hop = router.get_next_hop("node-003")
        if next_hop:
            send_to(next_hop, data)
        
        # Handle incoming packet
        response = router.handle_packet(packet, from_neighbor="node-002")
    """
    
    def __init__(
        self,
        local_node_id: str,
        max_hops: int = 15,
        hello_interval: float = 1.0,
        route_timeout: float = 60.0
    ):
        self.local_node_id = local_node_id
        
        # Initialize components
        self.topology = TopologyManager(local_node_id)
        self.route_table = RouteTable()
        self.packet_handler = PacketHandler(local_node_id)
        self.recovery = RouteRecovery(
            self.topology,
            self.route_table,
            local_node_id
        )
        
        # Configuration
        self.max_hops = max_hops
        self.hello_interval = hello_interval
        self.route_timeout = route_timeout
        
        # State
        self._running = False
        self._last_hello = 0.0
        self._last_cleanup = 0.0
        
        # Callbacks for external events
        self._send_packet: Optional[Callable] = None
        
        # Wire up internal callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup internal callback wiring between components."""
        
        def on_route_request(packet: RoutingPacket, from_neighbor: str):
            """Forward RREQ if we have a route or are not destination."""
            # Check if we have a route to destination
            route = self.route_table.get_best_route(packet.destination)
            
            if route:
                # Send RREP back through the path
                rrep = self.packet_handler.create_rrep(packet, route.hop_count + 1)
                if self._send_packet:
                    self._send_packet(rrep, from_neighbor)
            else:
                # Forward RREQ to neighbors
                forward = packet.increment_hop()
                if forward.hop_count < self.max_hops:
                    if self._send_packet:
                        for neighbor in self.topology.get_neighbors():
                            if neighbor != from_neighbor:
                                self._send_packet(forward, neighbor)
        
        def on_route_reply(packet: RoutingPacket, from_neighbor: str):
            """Process RREP and update route table."""
            # Create route entry from RREP
            route = RouteEntry(
                destination=packet.origin,
                next_hop=from_neighbor,
                hop_count=packet.hop_count,
                seq_num=packet.seq_num,
                path=[from_neighbor, packet.origin],
                metric=packet.metric
            )
            
            self.route_table.add_route(route)
            
            # Notify recovery if active
            self.recovery.handle_route_discovered(packet.origin, route)
            
            # Forward RREP if not for us
            if packet.destination != self.local_node_id:
                # Find route back to originator
                back_route = self.route_table.get_best_route(packet.destination)
                if back_route:
                    forward = packet.increment_hop()
                    if self._send_packet:
                        self._send_packet(forward, back_route.next_hop)
        
        def on_route_error(unreachable: str, from_neighbor: str):
            """Handle route error notification."""
            # Invalidate routes through unreachable node
            self.route_table.invalidate_route_by_hop(unreachable)
            
            # Start recovery for affected destinations
            self.recovery.handle_link_failure(unreachable)
        
        def on_hello(source: str, from_neighbor: str):
            """Handle hello packet."""
            self.recovery.handle_hello(source)
        
        def on_discovery(destination: str):
            """Initiate route discovery."""
            rreq = self.packet_handler.create_rreq(destination)
            if self._send_packet:
                for neighbor in self.topology.get_neighbors():
                    self._send_packet(rreq, neighbor)
        
        def on_recovery_success(destination: str, route: RouteEntry):
            """Handle successful recovery."""
            logger.info(f"Route to {destination} recovered via {route.next_hop}")
        
        def on_recovery_failure(destination: str):
            """Handle failed recovery."""
            logger.warning(f"Route to {destination} could not be recovered")
        
        # Register callbacks
        self.packet_handler.set_callbacks(
            on_route_request=on_route_request,
            on_route_reply=on_route_reply,
            on_route_error=on_route_error,
            on_hello=on_hello
        )
        
        self.recovery.set_callbacks(
            on_route_discovery=on_discovery,
            on_route_error=on_route_error,
            on_recovery_success=on_recovery_success,
            on_recovery_failure=on_recovery_failure
        )
    
    def set_send_callback(self, callback: Callable[[RoutingPacket, str], None]):
        """Set callback for sending packets to neighbors."""
        self._send_packet = callback
    
    # === Public API ===
    
    def start(self):
        """Start the router."""
        self._running = True
        logger.info(f"MeshRouter started for {self.local_node_id}")
    
    def stop(self):
        """Stop the router."""
        self._running = False
        logger.info(f"MeshRouter stopped for {self.local_node_id}")
    
    def add_neighbor(
        self,
        node_id: str,
        link_quality: Optional[LinkQuality] = None,
        hop_count: int = 1
    ) -> NodeInfo:
        """Add a direct neighbor node."""
        return self.topology.add_node(
            node_id=node_id,
            is_neighbor=True,
            hop_count=hop_count,
            link_quality=link_quality
        )
    
    def remove_neighbor(self, node_id: str) -> bool:
        """Remove a neighbor node."""
        # Remove from topology
        result = self.topology.remove_node(node_id)
        
        # Invalidate routes through this node
        self.route_table.invalidate_route_by_hop(node_id)
        
        return result
    
    def get_next_hop(self, destination: str) -> Optional[str]:
        """Get the next hop for a destination."""
        route = self.route_table.get_best_route(destination)
        return route.next_hop if route else None
    
    def get_routes(self, destination: str) -> List[RouteEntry]:
        """Get all routes to a destination."""
        return self.route_table.get_routes(destination)
    
    def has_route(self, destination: str) -> bool:
        """Check if a route exists."""
        return self.route_table.has_route(destination)
    
    def handle_packet(
        self,
        packet: RoutingPacket,
        from_neighbor: str
    ) -> Optional[RoutingPacket]:
        """
        Handle an incoming routing packet.
        
        Returns a packet to send in response, or None.
        """
        return self.packet_handler.process_packet(packet, from_neighbor)
    
    def send_data(
        self,
        destination: str,
        data: bytes
    ) -> Tuple[bool, Optional[str]]:
        """
        Send data to a destination.
        
        Returns (success, next_hop).
        """
        next_hop = self.get_next_hop(destination)
        
        if not next_hop:
            # Initiate route discovery
            rreq = self.packet_handler.create_rreq(destination)
            
            if self._send_packet:
                for neighbor in self.topology.get_neighbors():
                    self._send_packet(rreq, neighbor)
            
            return False, None
        
        return True, next_hop
    
    def create_hello(self) -> RoutingPacket:
        """Create a hello packet for neighbor discovery."""
        return self.packet_handler.create_hello()
    
    def tick(self):
        """
        Periodic maintenance tick.
        
        Should be called regularly (e.g., every 100ms).
        """
        if not self._running:
            return
        
        now = time.time()
        
        # Send hello packets
        if now - self._last_hello >= self.hello_interval:
            self._send_hello()
            self._last_hello = now
        
        # Check for failed neighbors
        failed = self.recovery.check_neighbor_status()
        for node_id in failed:
            self.recovery.handle_link_failure(node_id)
        
        # Check recovery timeouts
        self.recovery.check_recovery_timeouts()
        
        # Periodic cleanup
        if now - self._last_cleanup >= 30.0:
            self.topology.cleanup_stale_nodes()
            self.route_table.cleanup_expired()
            self.recovery.cleanup()
            self._last_cleanup = now
    
    def _send_hello(self):
        """Send hello packet to all neighbors."""
        hello = self.create_hello()
        
        if self._send_packet:
            for neighbor in self.topology.get_neighbors():
                self._send_packet(hello, neighbor)
    
    # === Information API ===
    
    def get_topology_stats(self) -> Dict[str, Any]:
        """Get topology statistics."""
        return self.topology.get_topology_stats()
    
    def get_route_stats(self) -> Dict[str, Any]:
        """Get routing table statistics."""
        return self.route_table.get_stats()
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        return self.recovery.get_stats()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get all statistics combined."""
        return {
            "local_node_id": self.local_node_id,
            "running": self._running,
            "topology": self.get_topology_stats(),
            "routes": self.get_route_stats(),
            "recovery": self.get_recovery_stats(),
            "packet_handler": self.packet_handler.get_stats(),
        }
    
    def get_neighbors(self) -> List[str]:
        """Get list of neighbor node IDs."""
        return self.topology.get_neighbors()
    
    def get_active_nodes(self) -> List[str]:
        """Get list of all active nodes."""
        return self.topology.get_active_nodes()
    
    def get_adjacency(self) -> Dict[str, List[str]]:
        """Get network adjacency list."""
        return self.topology.build_adjacency()