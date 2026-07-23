"""
Main Mesh Router implementation.

Provides an AODV-like mesh routing protocol with reactive route discovery,
multi-hop forwarding, and route maintenance.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from .forwarding import DeduplicationManager, PacketForwarder
from .models import PacketType, RouteEntry, RoutingPacket
from .routing_table import RoutingTable
from .security import PacketSecurity
from .statistics import RouterStatistics

logger = logging.getLogger(__name__)


class MeshRouter:
    """
    AODV-like Mesh Router.

    Features:
    - Reactive route discovery (RREQ/RREP)
    - Multi-hop forwarding
    - Route maintenance
    - Loop prevention via TTL and sequence numbers
    - Multi-path support (k-disjoint routes)
    - HMAC packet authentication

    Example:
        >>> router = MeshRouter("node_1", shared_secret=b"secret")
        >>> await router.start()
        >>> router.add_neighbor("node_2")
        >>> await router.send("node_3", b"Hello")
    """

    DEFAULT_TTL = 16
    ROUTE_TIMEOUT = 60.0
    RREQ_TIMEOUT = 5.0

    def __init__(self, node_id: str, shared_secret: Optional[bytes] = None):
        """
        Initialize mesh router.
        
        Args:
            node_id: Unique identifier for this node
            shared_secret: HMAC key for packet authentication (optional)
        """
        self.node_id = node_id
        self.seq_num = 0

        # Components
        self._security = PacketSecurity(shared_secret)
        self._routing_table = RoutingTable(node_id, self.ROUTE_TIMEOUT)
        self._statistics = RouterStatistics()
        self._deduplication = DeduplicationManager(self.ROUTE_TIMEOUT)
        self._forwarder = PacketForwarder(
            node_id, self._routing_table, self._security, self._statistics
        )

        # Pending route requests
        self._pending_rreq: Dict[str, asyncio.Future] = {}

        # Callbacks
        self._receive_callback: Optional[Callable] = None
        self._crdt_sync_callback: Optional[Callable] = None

    async def start(self) -> None:
        """Start the router."""
        await self._deduplication.start()
        logger.info(f"MeshRouter started for {self.node_id}")

    async def stop(self) -> None:
        """Stop the router."""
        await self._deduplication.stop()
        logger.info(f"MeshRouter stopped for {self.node_id}")

    def set_send_callback(self, callback: Callable) -> None:
        """Set callback for sending packets: (packet_bytes, next_hop) -> bool."""
        self._forwarder.set_send_callback(callback)

    def set_receive_callback(self, callback: Callable) -> None:
        """Set callback for received data: (source, payload) -> None."""
        self._receive_callback = callback

    def set_crdt_sync_callback(self, callback: Callable) -> None:
        """Set callback for CRDT sync: (peer_id, crdt_data) -> None."""
        self._crdt_sync_callback = callback

    def add_neighbor(self, neighbor_id: str) -> None:
        """Add a direct neighbor (1 hop)."""
        self._routing_table.add_neighbor(neighbor_id)

    def remove_neighbor(self, neighbor_id: str) -> None:
        """Remove a neighbor and related routes."""
        self._routing_table.remove_neighbor(neighbor_id)

    def get_route(self, destination: str) -> List[RouteEntry]:
        """Get active routes to destination."""
        return self._routing_table.get_route(destination)

    def get_routes(self) -> Dict[str, List[RouteEntry]]:
        """Get all active routes."""
        return self._routing_table.get_routes()

    async def send(self, destination: str, payload: bytes) -> bool:
        """
        Send data to destination.
        
        Performs route discovery if needed and tries alternative routes on failure.
        """
        # Local delivery
        if destination == self.node_id:
            if self._receive_callback:
                await self._receive_callback(self.node_id, payload)
            return True

        routes_to_try = self.get_route(destination)

        if not routes_to_try:
            logger.info(f"No existing routes to {destination}, starting discovery...")
            discovered = await self._discover_route(destination)
            if discovered:
                routes_to_try = self.get_route(destination)

            if not routes_to_try:
                logger.warning(f"Route discovery failed for {destination}")
                await self._statistics.increment("packets_dropped")
                return False

        # Try each route
        for route in routes_to_try:
            self.seq_num += 1
            packet = RoutingPacket(
                packet_type=PacketType.DATA,
                source=self.node_id,
                destination=destination,
                seq_num=self.seq_num,
                hop_count=0,
                ttl=self.DEFAULT_TTL,
                payload=payload,
            )

            logger.debug(f"Sending packet to {destination} via {route.next_hop}")
            sent = await self._forwarder._send_packet(packet, route.next_hop)

            if sent:
                return True
            else:
                logger.warning(f"Failed via {route.next_hop}, handling failure")
                await self._handle_route_failure(destination, route.next_hop)

        logger.error(f"All routes to {destination} failed")
        await self._statistics.increment("packets_dropped")
        return False

    async def handle_packet(self, data: bytes, from_neighbor: str) -> None:
        """Handle incoming packet."""
        # Verify signature
        verified_data = self._security.verify(data)
        if verified_data is None:
            await self._statistics.increment("packets_dropped")
            return

        # Parse packet
        try:
            packet = RoutingPacket.from_bytes(verified_data)
        except Exception as e:
            logger.error(f"Failed to parse packet: {e}")
            return

        # Deduplication
        if self._deduplication.is_seen(packet.packet_id):
            return
        self._deduplication.mark_seen(packet.packet_id)

        await self._statistics.increment("packets_received")

        # Update reverse route
        self._routing_table.update_route(
            packet.source, from_neighbor, packet.hop_count + 1, packet.seq_num
        )

        # Handle by type
        handlers = {
            PacketType.DATA: self._handle_data,
            PacketType.RREQ: self._handle_rreq,
            PacketType.RREP: self._handle_rrep,
            PacketType.RERR: self._handle_rerr,
            PacketType.CRDT_SYNC: self._handle_crdt_sync,
        }

        handler = handlers.get(packet.packet_type)
        if handler:
            await handler(packet, from_neighbor)

    async def _handle_data(self, packet: RoutingPacket, from_neighbor: str) -> None:
        """Handle DATA packet."""
        if packet.destination == self.node_id:
            logger.debug(f"Received data from {packet.source}")
            if self._receive_callback:
                await self._receive_callback(packet.source, packet.payload)
        else:
            await self._forwarder.forward(packet)

    async def _handle_rreq(self, packet: RoutingPacket, from_neighbor: str) -> None:
        """Handle Route Request."""
        await self._statistics.increment("rreq_received")
        target = packet.payload.decode()

        # Loop prevention
        if self.node_id in packet.path_traversed:
            logger.debug(f"RREQ dropped: {self.node_id} already in path")
            await self._statistics.increment("packets_dropped")
            return

        current_path = packet.path_traversed + [self.node_id]
        logger.debug(f"RREQ from {packet.source} for {target}, path: {current_path}")

        # Update reverse route
        self._routing_table.update_route(
            packet.source, from_neighbor, packet.hop_count + 1,
            packet.seq_num, current_path
        )

        if target == self.node_id:
            # We are the target - send RREP
            await self._send_rrep(packet.source, from_neighbor, current_path)
        else:
            routes = self.get_route(target)
            if routes:
                # Proxy reply
                await self._send_rrep(
                    packet.source, from_neighbor, current_path,
                    target, routes[0].hop_count
                )
            else:
                # Forward RREQ
                forward_packet = packet.with_path([self.node_id])
                await self._forwarder.forward(forward_packet)

    async def _handle_rrep(self, packet: RoutingPacket, from_neighbor: str) -> None:
        """Handle Route Reply."""
        await self._statistics.increment("rrep_received")

        rrep_data = json.loads(packet.payload.decode())
        target = rrep_data["target"]
        hop_count = rrep_data["hop_count"]
        path = rrep_data["path"]

        logger.debug(f"RREP: route to {target}, hops={hop_count}")

        final_hop_count = hop_count + 1
        self._routing_table.update_route(
            target, from_neighbor, final_hop_count, packet.seq_num, path
        )

        if packet.destination == self.node_id:
            if target in self._pending_rreq:
                future = self._pending_rreq.pop(target)
                if not future.done():
                    routes = self.get_route(target)
                    future.set_result(routes[0] if routes else None)
        else:
            await self._forwarder.forward(packet)

    async def _handle_rerr(self, packet: RoutingPacket, from_neighbor: str) -> None:
        """Handle Route Error."""
        broken_dest = packet.payload.decode()
        self._routing_table.invalidate_route(broken_dest, broken_dest)
        await self._forwarder.forward(packet)

    async def _handle_crdt_sync(self, packet: RoutingPacket, from_neighbor: str) -> None:
        """Handle CRDT Sync packet."""
        if packet.destination == self.node_id:
            logger.debug(f"Received CRDT_SYNC from {packet.source}")
            if self._crdt_sync_callback:
                try:
                    crdt_data = json.loads(packet.payload.decode("utf-8"))
                    await self._crdt_sync_callback(packet.source, crdt_data)
                except Exception as e:
                    logger.error(f"Failed to process CRDT_SYNC: {e}")
        else:
            await self._forwarder.forward(packet)

    async def _discover_route(self, destination: str) -> Optional[RouteEntry]:
        """Perform route discovery."""
        future = asyncio.get_event_loop().create_future()
        self._pending_rreq[destination] = future

        self.seq_num += 1
        rreq = RoutingPacket(
            packet_type=PacketType.RREQ,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=destination.encode(),
            path_traversed=[self.node_id],
        )

        await self._forwarder.broadcast(rreq)
        await self._statistics.increment("rreq_sent")

        try:
            route = await asyncio.wait_for(future, timeout=self.RREQ_TIMEOUT)
            await self._statistics.increment("routes_discovered")
            return route
        except asyncio.TimeoutError:
            logger.warning(f"Route discovery timeout for {destination}")
            self._pending_rreq.pop(destination, None)
            return None

    async def _send_rrep(
        self,
        requester: str,
        next_hop: str,
        path_to_target: List[str],
        target: Optional[str] = None,
        hop_count: int = 0,
    ) -> None:
        """Send Route Reply."""
        target = target or self.node_id

        self.seq_num += 1
        rrep_payload = json.dumps({
            "target": target,
            "hop_count": hop_count,
            "path": path_to_target,
        }).encode()

        rrep = RoutingPacket(
            packet_type=PacketType.RREP,
            source=self.node_id,
            destination=requester,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=rrep_payload,
        )

        await self._forwarder._send_packet(rrep, next_hop)
        await self._statistics.increment("rrep_sent")

    async def _handle_route_failure(
        self, broken_destination: str, failed_next_hop: str
    ) -> None:
        """Handle route failure."""
        logger.info(f"Route failure: {broken_destination} via {failed_next_hop}")

        self._routing_table.invalidate_route(broken_destination, failed_next_hop)

        # Broadcast RERR
        self.seq_num += 1
        rerr = RoutingPacket(
            packet_type=PacketType.RERR,
            source=self.node_id,
            destination="",
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=failed_next_hop.encode(),
        )

        await self._forwarder.broadcast(rerr)

    async def send_crdt_update(
        self, destination: str, crdt_data: Dict[str, Any]
    ) -> bool:
        """Send CRDT data to destination."""
        if destination == self.node_id:
            return True

        routes_to_try = self.get_route(destination)
        if not routes_to_try:
            discovered = await self._discover_route(destination)
            if discovered:
                routes_to_try = self.get_route(destination)
            if not routes_to_try:
                logger.warning(f"No route for CRDT_SYNC to {destination}")
                return False

        try:
            payload_bytes = json.dumps(crdt_data).encode("utf-8")
        except Exception as e:
            logger.error(f"Failed to serialize CRDT data: {e}")
            return False

        self.seq_num += 1
        packet = RoutingPacket(
            packet_type=PacketType.CRDT_SYNC,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=payload_bytes,
        )

        for route in routes_to_try:
            sent = await self._forwarder._send_packet(packet, route.next_hop)
            if sent:
                return True
            await self._handle_route_failure(destination, route.next_hop)

        return False

    async def get_stats(self) -> dict:
        """Get router statistics."""
        stats = await self._statistics.get_stats()
        return {
            "node_id": self.node_id,
            "routes_count": len(self.get_routes()),
            **stats,
        }

    async def get_mape_k_metrics(self) -> Dict[str, float]:
        """Get MAPE-K metrics for adaptive routing."""
        return await self._statistics.get_mape_k_metrics(self.get_routes)


__all__ = ["MeshRouter"]

