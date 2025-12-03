"""
x0tta6bl4 Mesh Router
Routes traffic through multiple nodes for anonymity.
Path: Client → Entry Node → Relay Nodes → Exit Node → Internet

Features:
- Multi-hop SOCKS5 chaining
- Post-Quantum Cryptography (Kyber768 + AES-256-GCM)
- Automatic failover
"""
import asyncio
import random
import logging
import json
import time
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Dict

try:
    from .pqc_tunnel import PQCTunnelManager, PQC_AVAILABLE
except ImportError:
    PQCTunnelManager = None
    PQC_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class MeshPeer:
    """Represents a peer in the mesh network."""
    node_id: str
    host: str
    port: int
    latency: float = 0.0
    last_seen: float = 0.0
    is_exit: bool = True
    capacity: int = 100  # Max concurrent connections
    
    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"
    
    def is_alive(self, timeout: float = 60.0) -> bool:
        return (time.time() - self.last_seen) < timeout


class MeshRouter:
    """
    Manages mesh routing with multi-hop paths.
    
    Features:
    - Peer discovery and health monitoring
    - Multi-hop path selection
    - Latency-based routing
    - Automatic failover
    """
    
    # Known bootstrap nodes
    BOOTSTRAP_NODES = [
        MeshPeer("node-vps1", "89.125.1.107", 10809, is_exit=True),
        MeshPeer("node-vps2", "62.133.60.252", 10809, is_exit=True),
    ]
    
    def __init__(self, node_id: str, local_port: int = 10809):
        self.node_id = node_id
        self.local_port = local_port
        self.peers: Dict[str, MeshPeer] = {}
        self.routes_cache: Dict[str, List[MeshPeer]] = {}
        self._running = False
        
        # Initialize PQC tunnel manager
        if PQCTunnelManager:
            self.pqc = PQCTunnelManager(node_id)
            logger.info(f"🔐 PQC encryption enabled ({'Kyber768' if PQC_AVAILABLE else 'simulated'})")
        else:
            self.pqc = None
        
        # Add bootstrap nodes
        for peer in self.BOOTSTRAP_NODES:
            if peer.node_id != node_id:  # Don't add self
                self.peers[peer.node_id] = peer
    
    async def start(self):
        """Start the mesh router."""
        self._running = True
        logger.info(f"🌐 Mesh Router started for {self.node_id}")
        logger.info(f"   Known peers: {len(self.peers)}")
        
        # Start background tasks
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._peer_discovery_loop())
    
    async def stop(self):
        """Stop the mesh router."""
        self._running = False
    
    async def _health_check_loop(self):
        """Periodically check peer health."""
        while self._running:
            for peer_id, peer in list(self.peers.items()):
                try:
                    latency = await self._ping_peer(peer)
                    if latency >= 0:
                        peer.latency = latency
                        peer.last_seen = time.time()
                    else:
                        logger.warning(f"Peer {peer_id} unreachable")
                except Exception as e:
                    logger.debug(f"Health check failed for {peer_id}: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _peer_discovery_loop(self):
        """Discover new peers from existing peers."""
        while self._running:
            for peer in list(self.peers.values()):
                if peer.is_alive():
                    try:
                        new_peers = await self._get_peers_from(peer)
                        for new_peer in new_peers:
                            if new_peer.node_id not in self.peers and new_peer.node_id != self.node_id:
                                self.peers[new_peer.node_id] = new_peer
                                logger.info(f"📡 Discovered new peer: {new_peer.node_id}")
                    except:
                        pass
            
            await asyncio.sleep(60)  # Discover every 60 seconds
    
    async def _ping_peer(self, peer: MeshPeer) -> float:
        """Ping a peer and return latency in ms. Returns -1 if unreachable."""
        try:
            start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(peer.host, peer.port),
                timeout=5.0
            )
            latency = (time.time() - start) * 1000
            writer.close()
            await writer.wait_closed()
            return latency
        except:
            return -1
    
    async def _get_peers_from(self, peer: MeshPeer) -> List[MeshPeer]:
        """Get peer list from another node (placeholder for real implementation)."""
        # In production, this would query the peer's /api/peers endpoint
        return []
    
    def get_route(self, destination: str, hops: int = 2) -> List[MeshPeer]:
        """
        Get a route to destination through mesh.
        
        Args:
            destination: Target host:port
            hops: Number of intermediate hops (1-3 recommended)
        
        Returns:
            List of peers to route through (last one is exit node)
        """
        # Check if destination is one of our peers (avoid loop)
        dest_host = destination.split(':')[0] if ':' in destination else destination
        for peer in self.peers.values():
            if peer.host == dest_host:
                logger.debug(f"Destination {dest_host} is a peer, using direct connection")
                return []
        
        # Get alive peers sorted by latency
        alive_peers = [p for p in self.peers.values() if p.is_alive() and p.is_exit]
        
        if not alive_peers:
            logger.warning("No alive peers available, using direct connection")
            return []
        
        # Sort by latency
        alive_peers.sort(key=lambda p: p.latency)
        
        # Select route
        if len(alive_peers) <= hops:
            route = alive_peers
        else:
            # Pick best latency for exit, random for relays
            exit_node = alive_peers[0]
            relay_candidates = alive_peers[1:]
            relays = random.sample(relay_candidates, min(hops - 1, len(relay_candidates)))
            route = relays + [exit_node]
        
        # Cache route
        route_key = hashlib.md5(destination.encode()).hexdigest()[:8]
        self.routes_cache[route_key] = route
        
        return route
    
    def get_best_exit(self) -> Optional[MeshPeer]:
        """Get the best exit node based on latency."""
        alive_exits = [p for p in self.peers.values() if p.is_alive() and p.is_exit]
        if not alive_exits:
            return None
        return min(alive_exits, key=lambda p: p.latency)
    
    def add_peer(self, node_id: str, host: str, port: int, is_exit: bool = True):
        """Manually add a peer."""
        peer = MeshPeer(node_id, host, port, is_exit=is_exit)
        peer.last_seen = time.time()
        self.peers[node_id] = peer
        logger.info(f"➕ Added peer: {node_id} ({host}:{port})")
    
    def get_stats(self) -> dict:
        """Get router statistics."""
        alive = sum(1 for p in self.peers.values() if p.is_alive())
        return {
            'node_id': self.node_id,
            'total_peers': len(self.peers),
            'alive_peers': alive,
            'routes_cached': len(self.routes_cache),
            'peers': [
                {
                    'id': p.node_id,
                    'address': p.address,
                    'latency': round(p.latency, 2),
                    'alive': p.is_alive()
                }
                for p in self.peers.values()
            ]
        }


class MeshConnection:
    """
    Handles a single connection through the mesh.
    Routes data through multiple hops using SOCKS5 chaining.
    
    Example: Client → Node1 → Node2 → Node3 → Internet
    Each hop is a SOCKS5 proxy that forwards to the next.
    """
    
    def __init__(self, router: MeshRouter, destination: str, crypto=None):
        self.router = router
        self.destination = destination
        self.route: List[MeshPeer] = []
        self.reader = None
        self.writer = None
        self.crypto = crypto  # PQC crypto for inter-node encryption
        self.hops_completed = 0
    
    async def connect_multi_hop(self, target_host: str, target_port: int) -> bool:
        """
        Establish multi-hop connection through mesh.
        
        SOCKS5 Chaining:
        1. Connect to first hop (Node1)
        2. Ask Node1 to connect to Node2 via SOCKS5
        3. Ask Node2 to connect to Node3 via SOCKS5
        4. Ask Node3 to connect to final target
        """
        self.route = self.router.get_route(f"{target_host}:{target_port}")
        
        if not self.route:
            # Direct connection (no mesh peers available)
            logger.info("📡 Direct connection (no mesh route)")
            return await self._connect_direct(target_host, target_port)
        
        logger.info(f"🔀 Multi-hop route: {' → '.join([p.node_id for p in self.route])} → target")
        
        try:
            # Step 1: Connect to first hop
            first_hop = self.route[0]
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(first_hop.host, first_hop.port),
                timeout=10.0
            )
            
            # SOCKS5 handshake with first hop
            if not await self._socks5_handshake():
                raise Exception(f"SOCKS5 handshake failed with {first_hop.node_id}")
            
            # PQC key exchange with first hop (if available)
            if self.router.pqc and not self.router.pqc.has_tunnel(first_hop.node_id):
                try:
                    if await self.router.pqc.establish_tunnel(self.reader, self.writer, first_hop.node_id):
                        logger.info(f"   🔐 PQC tunnel with {first_hop.node_id}")
                except Exception as e:
                    logger.debug(f"PQC handshake skipped: {e}")
            
            self.hops_completed = 1
            logger.info(f"   ✓ Hop 1: {first_hop.node_id}")
            
            # Step 2: Chain through remaining hops
            for i, next_hop in enumerate(self.route[1:], start=2):
                if not await self._socks5_connect(next_hop.host, next_hop.port):
                    raise Exception(f"Failed to chain to {next_hop.node_id}")
                
                # After connecting to next hop, do SOCKS5 handshake through the tunnel
                if not await self._socks5_handshake():
                    raise Exception(f"SOCKS5 handshake failed with {next_hop.node_id}")
                
                self.hops_completed = i
                logger.info(f"   ✓ Hop {i}: {next_hop.node_id}")
            
            # Step 3: Connect to final target through the chain
            if not await self._socks5_connect(target_host, target_port):
                raise Exception(f"Failed to connect to target {target_host}:{target_port}")
            
            logger.info(f"   ✓ Target: {target_host}:{target_port}")
            logger.info(f"🔗 Multi-hop tunnel established ({self.hops_completed} hops)")
            
            return True
            
        except asyncio.TimeoutError:
            logger.error("Multi-hop connection timed out")
            await self.close()
            return False
        except Exception as e:
            logger.error(f"Multi-hop connection failed at hop {self.hops_completed}: {e}")
            await self.close()
            return False
    
    async def _socks5_handshake(self) -> bool:
        """Perform SOCKS5 handshake."""
        try:
            # Send: VER NMETHODS METHODS
            self.writer.write(b'\x05\x01\x00')  # SOCKS5, 1 method, no auth
            await self.writer.drain()
            
            # Receive: VER METHOD
            response = await asyncio.wait_for(self.reader.read(2), timeout=5.0)
            return response == b'\x05\x00'
        except:
            return False
    
    async def _socks5_connect(self, host: str, port: int) -> bool:
        """Send SOCKS5 CONNECT request."""
        try:
            # Build request: VER CMD RSV ATYP DST.ADDR DST.PORT
            request = bytearray([0x05, 0x01, 0x00])  # SOCKS5, CONNECT, RSV
            
            # Check if host is IP or domain
            try:
                import socket
                socket.inet_aton(host)
                # IPv4
                request.append(0x01)
                request.extend(socket.inet_aton(host))
            except:
                # Domain name
                request.append(0x03)
                request.append(len(host))
                request.extend(host.encode())
            
            request.extend(port.to_bytes(2, 'big'))
            
            self.writer.write(bytes(request))
            await self.writer.drain()
            
            # Read response (at least 10 bytes for IPv4)
            response = await asyncio.wait_for(self.reader.read(10), timeout=10.0)
            
            # Check reply: VER REP RSV ATYP ...
            if len(response) >= 2 and response[1] == 0x00:
                return True
            else:
                logger.debug(f"SOCKS5 connect failed: rep={response[1] if len(response) > 1 else 'N/A'}")
                return False
                
        except Exception as e:
            logger.debug(f"SOCKS5 connect error: {e}")
            return False
    
    async def connect(self) -> bool:
        """Legacy single-hop connect (for backward compatibility)."""
        self.route = self.router.get_route(self.destination)
        
        if not self.route:
            return await self._connect_direct_legacy()
        
        # Use first available exit node
        exit_node = self.route[-1]
        try:
            self.reader, self.writer = await asyncio.open_connection(exit_node.host, exit_node.port)
            
            if not await self._socks5_handshake():
                raise Exception("SOCKS5 handshake failed")
            
            return True
        except Exception as e:
            logger.error(f"Single-hop connection failed: {e}")
            return False
    
    async def _connect_direct(self, host: str, port: int) -> bool:
        """Direct connection without mesh."""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
            return True
        except Exception as e:
            logger.error(f"Direct connection failed: {e}")
            return False
    
    async def _connect_direct_legacy(self) -> bool:
        """Legacy direct connection."""
        try:
            host, port = self.destination.rsplit(':', 1)
            return await self._connect_direct(host, int(port))
        except:
            return False
    
    def get_tunnel(self):
        """Get the tunnel (reader, writer) for data transfer."""
        return self.reader, self.writer
    
    async def close(self):
        """Close connection."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
        self.reader = None
        self.writer = None
