"""
Packet forwarding for Mesh Router.

Handles packet forwarding and broadcast operations.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Set

from .models import PacketType, RoutingPacket
from .routing_table import RoutingTable
from .security import PacketSecurity
from .statistics import RouterStatistics

logger = logging.getLogger(__name__)


class PacketForwarder:
    """
    Handles packet forwarding and broadcast in the mesh.
    
    Manages TTL, hop counting, and broadcast to neighbors.
    
    Example:
        >>> forwarder = PacketForwarder(node_id, routing_table, security, stats)
        >>> forwarder.set_send_callback(send_func)
        >>> await forwarder.forward(packet)
    """

    def __init__(
        self,
        node_id: str,
        routing_table: RoutingTable,
        security: PacketSecurity,
        statistics: RouterStatistics,
    ):
        """
        Initialize packet forwarder.
        
        Args:
            node_id: Local node ID
            routing_table: Routing table instance
            security: Packet security instance
            statistics: Statistics tracker instance
        """
        self._node_id = node_id
        self._routing_table = routing_table
        self._security = security
        self._statistics = statistics
        self._send_callback: Optional[Callable] = None

    def set_send_callback(self, callback: Callable) -> None:
        """
        Set callback for sending packets.
        
        Args:
            callback: Async function (packet_bytes, next_hop) -> bool
        """
        self._send_callback = callback

    async def forward(self, packet: RoutingPacket) -> bool:
        """
        Forward a packet to the next hop.
        
        Args:
            packet: Packet to forward
            
        Returns:
            True if forwarded successfully, False otherwise
        """
        # Check TTL
        if packet.ttl <= 1:
            logger.debug("Packet dropped: TTL expired")
            await self._statistics.increment("packets_dropped")
            return False

        # Find route
        routes = self._routing_table.get_route(packet.destination)

        if not routes:
            # For RREQ - broadcast
            if packet.packet_type == PacketType.RREQ:
                await self.broadcast(packet)
                return True
            else:
                logger.warning(f"No route to forward packet to {packet.destination}")
                await self._statistics.increment("packets_dropped")
                return False

        # Decrement TTL and increment hop count
        forward_packet = packet.decrement_ttl()

        sent = await self._send_packet(forward_packet, routes[0].next_hop)
        if sent:
            await self._statistics.increment("packets_forwarded")
        else:
            await self._statistics.increment("packets_dropped")

        return sent

    async def broadcast(self, packet: RoutingPacket) -> None:
        """
        Broadcast packet to all direct neighbors.
        
        Args:
            packet: Packet to broadcast
        """
        forward_packet = packet.decrement_ttl()
        neighbors = self._routing_table.get_direct_neighbors()

        for neighbor in neighbors:
            await self._send_packet(forward_packet, neighbor)

    async def _send_packet(self, packet: RoutingPacket, next_hop: str) -> bool:
        """
        Send a packet through the transport.
        
        Args:
            packet: Packet to send
            next_hop: Next hop node ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self._send_callback:
            logger.error("No send callback configured")
            return False

        try:
            signed_data = self._security.sign(packet.to_bytes())
            result = await self._send_callback(signed_data, next_hop)
            if result:
                await self._statistics.increment("packets_sent")
            return result
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False


class DeduplicationManager:
    """
    Manages packet deduplication to prevent loops.
    
    Tracks seen packet IDs and periodically cleans up old entries.
    """

    def __init__(self, cleanup_interval: float = 60.0):
        """
        Initialize deduplication manager.
        
        Args:
            cleanup_interval: Interval in seconds for cleanup
        """
        self._seen_packets: Set[str] = set()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self) -> None:
        """Periodically clean up seen packets."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            self._seen_packets.clear()

    def is_seen(self, packet_id: str) -> bool:
        """
        Check if packet has been seen.
        
        Args:
            packet_id: Packet ID to check
            
        Returns:
            True if packet was seen before
        """
        return packet_id in self._seen_packets

    def mark_seen(self, packet_id: str) -> None:
        """
        Mark packet as seen.
        
        Args:
            packet_id: Packet ID to mark
        """
        self._seen_packets.add(packet_id)


__all__ = ["PacketForwarder", "DeduplicationManager"]

