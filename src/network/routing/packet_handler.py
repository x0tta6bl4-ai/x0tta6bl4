"""
Packet Handler for Mesh Routing.

Handles routing protocol packets:
- RREQ (Route Request)
- RREP (Route Reply)
- RERR (Route Error)
- HELLO (Neighbor Discovery)
"""

import logging
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PacketType(IntEnum):
    """Routing packet types."""
    
    RREQ = 1   # Route Request
    RREP = 2   # Route Reply
    RERR = 3   # Route Error
    HELLO = 4  # Neighbor Hello
    DATA = 5   # Data packet (for forwarding)


@dataclass
class RoutingPacket:
    """
    Routing protocol packet.
    
    Binary format (variable length):
    - type: 1 byte
    - flags: 1 byte
    - seq_num: 4 bytes (uint32)
    - source: 16 bytes (IPv6 address or node ID)
    - destination: 16 bytes (IPv6 address or node ID)
    - hop_count: 1 byte
    - payload: variable
    """
    
    packet_type: PacketType
    source: str
    destination: str
    seq_num: int
    hop_count: int = 0
    flags: int = 0
    payload: bytes = b""
    timestamp: float = field(default_factory=time.time)
    
    # Additional fields for specific packet types
    origin: str = ""  # For RREQ: original source
    metric: float = 1.0  # Route metric
    
    def __post_init__(self):
        if isinstance(self.packet_type, int):
            self.packet_type = PacketType(self.packet_type)
    
    def to_bytes(self) -> bytes:
        """Serialize packet to bytes."""
        # Pack header
        header = struct.pack(
            "!BBII16s16sB",
            self.packet_type,
            self.flags,
            self.seq_num,
            0,  # Reserved
            self.source.encode()[:16].ljust(16, b'\x00'),
            self.destination.encode()[:16].ljust(16, b'\x00'),
            self.hop_count
        )
        
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "RoutingPacket":
        """Deserialize packet from bytes."""
        if len(data) < 43:
            raise ValueError("Packet too short")

        packet_type, flags, seq_num, _, source_raw, dest_raw, hop_count = struct.unpack(
            "!BBII16s16sB", data[:43]
        )

        source = source_raw.rstrip(b'\x00').decode()
        destination = dest_raw.rstrip(b'\x00').decode()
        payload = data[43:]
        
        return cls(
            packet_type=PacketType(packet_type),
            source=source,
            destination=destination,
            seq_num=seq_num,
            hop_count=hop_count,
            flags=flags,
            payload=payload
        )
    
    def increment_hop(self) -> "RoutingPacket":
        """Create a copy with incremented hop count."""
        return RoutingPacket(
            packet_type=self.packet_type,
            source=self.source,
            destination=self.destination,
            seq_num=self.seq_num,
            hop_count=self.hop_count + 1,
            flags=self.flags,
            payload=self.payload,
            origin=self.origin,
            metric=self.metric
        )


class PacketHandler:
    """
    Handles routing protocol packets.
    
    Responsibilities:
    - Parse and create routing packets
    - Process incoming packets
    - Generate route requests/replies
    - Handle neighbor discovery
    """
    
    MAX_HOPS = 15
    RREQ_RETRIES = 3
    RREQ_TIMEOUT = 2.0  # Seconds to wait for RREP
    
    def __init__(self, local_node_id: str):
        self.local_node_id = local_node_id
        self._seq_num = 0
        self._pending_requests: Dict[int, Tuple[str, float, int]] = {}  # seq_num -> (dest, timestamp, retries)
        self._seen_packets: Dict[int, float] = {}  # seq_num -> timestamp (for deduplication)
        
        # Callbacks for packet events
        self._on_route_request: Optional[Callable] = None
        self._on_route_reply: Optional[Callable] = None
        self._on_route_error: Optional[Callable] = None
        self._on_hello: Optional[Callable] = None
    
    def next_seq_num(self) -> int:
        """Get next sequence number."""
        self._seq_num = (self._seq_num + 1) & 0xFFFFFFFF
        return self._seq_num
    
    def create_rreq(self, destination: str) -> RoutingPacket:
        """Create a Route Request packet."""
        seq_num = self.next_seq_num()
        
        packet = RoutingPacket(
            packet_type=PacketType.RREQ,
            source=self.local_node_id,
            destination=destination,
            seq_num=seq_num,
            hop_count=0,
            origin=self.local_node_id
        )
        
        # Track pending request
        self._pending_requests[seq_num] = (destination, time.time(), 0)
        
        logger.debug(f"Created RREQ for {destination} (seq={seq_num})")
        return packet
    
    def create_rrep(self, rreq: RoutingPacket, hop_count: int) -> RoutingPacket:
        """Create a Route Reply packet in response to RREQ."""
        packet = RoutingPacket(
            packet_type=PacketType.RREP,
            source=self.local_node_id,
            destination=rreq.origin,
            seq_num=self.next_seq_num(),
            hop_count=hop_count,
            origin=rreq.destination
        )
        
        logger.debug(f"Created RREP to {rreq.origin} for {rreq.destination}")
        return packet
    
    def create_rerr(self, unreachable_node: str, seq_num: int) -> RoutingPacket:
        """Create a Route Error packet."""
        packet = RoutingPacket(
            packet_type=PacketType.RERR,
            source=self.local_node_id,
            destination="",  # Broadcast
            seq_num=seq_num,
            payload=unreachable_node.encode()[:16].ljust(16, b'\x00')
        )
        
        logger.debug(f"Created RERR for {unreachable_node}")
        return packet
    
    def create_hello(self) -> RoutingPacket:
        """Create a Hello packet for neighbor discovery."""
        return RoutingPacket(
            packet_type=PacketType.HELLO,
            source=self.local_node_id,
            destination="",  # Broadcast
            seq_num=self.next_seq_num(),
            hop_count=0
        )
    
    def process_packet(self, packet: RoutingPacket, from_neighbor: str) -> Optional[RoutingPacket]:
        """
        Process an incoming routing packet.
        
        Returns a packet to send in response, or None.
        """
        # Check for duplicate packets
        if self._is_duplicate(packet):
            logger.debug(f"Ignoring duplicate packet seq={packet.seq_num}")
            return None
        
        # Mark as seen
        self._seen_packets[packet.seq_num] = time.time()
        
        if packet.packet_type == PacketType.RREQ:
            return self._handle_rreq(packet, from_neighbor)
        elif packet.packet_type == PacketType.RREP:
            self._handle_rrep(packet, from_neighbor)
            return None
        elif packet.packet_type == PacketType.RERR:
            self._handle_rerr(packet, from_neighbor)
            return None
        elif packet.packet_type == PacketType.HELLO:
            self._handle_hello(packet, from_neighbor)
            return None
        
        return None
    
    def _is_duplicate(self, packet: RoutingPacket) -> bool:
        """Check if packet was already processed."""
        if packet.seq_num in self._seen_packets:
            return True
        
        # Cleanup old entries
        now = time.time()
        self._seen_packets = {
            seq: ts for seq, ts in self._seen_packets.items()
            if now - ts < 30.0
        }
        
        return False
    
    def _handle_rreq(self, packet: RoutingPacket, from_neighbor: str) -> Optional[RoutingPacket]:
        """Handle Route Request packet."""
        # Check if we are the destination
        if packet.destination == self.local_node_id:
            # Send RREP back
            return self.create_rrep(packet, packet.hop_count + 1)
        
        # Check hop limit
        if packet.hop_count >= self.MAX_HOPS:
            logger.debug(f"RREQ exceeded max hops for {packet.destination}")
            return None
        
        # Forward RREQ (will be done by router)
        if self._on_route_request:
            self._on_route_request(packet, from_neighbor)
        
        return None
    
    def _handle_rrep(self, packet: RoutingPacket, from_neighbor: str):
        """Handle Route Reply packet."""
        # Check if this is for us
        if packet.destination == self.local_node_id:
            # Check pending requests
            for seq_num, (dest, ts, retries) in list(self._pending_requests.items()):
                if dest == packet.origin:
                    del self._pending_requests[seq_num]
                    break
        
        if self._on_route_reply:
            self._on_route_reply(packet, from_neighbor)
    
    def _handle_rerr(self, packet: RoutingPacket, from_neighbor: str):
        """Handle Route Error packet."""
        unreachable = packet.payload.rstrip(b'\x00').decode()
        
        if self._on_route_error:
            self._on_route_error(unreachable, from_neighbor)
    
    def _handle_hello(self, packet: RoutingPacket, from_neighbor: str):
        """Handle Hello packet."""
        if self._on_hello:
            self._on_hello(packet.source, from_neighbor)
    
    def set_callbacks(
        self,
        on_route_request: Optional[Callable] = None,
        on_route_reply: Optional[Callable] = None,
        on_route_error: Optional[Callable] = None,
        on_hello: Optional[Callable] = None
    ):
        """Set callback functions for packet events."""
        if on_route_request:
            self._on_route_request = on_route_request
        if on_route_reply:
            self._on_route_reply = on_route_reply
        if on_route_error:
            self._on_route_error = on_route_error
        if on_hello:
            self._on_hello = on_hello
    
    def check_pending_requests(self) -> List[Tuple[str, int]]:
        """
        Check for timed-out route requests.
        
        Returns list of (destination, retries) for requests that need retry.
        """
        now = time.time()
        to_retry = []
        
        for seq_num, (dest, timestamp, retries) in list(self._pending_requests.items()):
            if now - timestamp > self.RREQ_TIMEOUT:
                if retries < self.RREQ_RETRIES:
                    # Update for retry
                    self._pending_requests[seq_num] = (dest, now, retries + 1)
                    to_retry.append((dest, retries + 1))
                else:
                    # Give up
                    del self._pending_requests[seq_num]
                    logger.warning(f"Route discovery failed for {dest}")
        
        return to_retry
    
    def get_stats(self) -> Dict[str, Any]:
        """Get packet handler statistics."""
        return {
            "sequence_number": self._seq_num,
            "pending_requests": len(self._pending_requests),
            "seen_packets_cache": len(self._seen_packets),
        }