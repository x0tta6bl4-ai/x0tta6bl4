"""
Data structures for Mesh Router.

Contains all dataclasses and enums used across the mesh routing package.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PacketType(Enum):
    """Типы пакетов маршрутизации."""

    DATA = 0x01  # Данные приложения
    RREQ = 0x02  # Route Request
    RREP = 0x03  # Route Reply
    RERR = 0x04  # Route Error
    HELLO = 0x05  # Hello/keepalive
    CRDT_SYNC = 0x06  # CRDT Synchronization data


@dataclass
class RouteEntry:
    """Запись в routing table."""

    destination: str
    next_hop: str
    hop_count: int
    seq_num: int
    timestamp: float = field(default_factory=time.time)
    valid: bool = True
    path: List[str] = field(default_factory=list)

    @property
    def age(self) -> float:
        """Time elapsed since route creation."""
        return time.time() - self.timestamp

    def is_fresh(self, timeout: float = 60.0) -> bool:
        """Check if route is within timeout period."""
        return self.age < timeout


@dataclass
class RoutingPacket:
    """Пакет маршрутизации."""

    packet_type: PacketType
    source: str
    destination: str
    seq_num: int
    hop_count: int
    ttl: int
    payload: bytes
    packet_id: str = field(default_factory=lambda: secrets.token_hex(8))
    path_traversed: List[str] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        """Serialize packet to bytes for transmission."""
        header = {
            "type": self.packet_type.value,
            "src": self.source,
            "dst": self.destination,
            "seq": self.seq_num,
            "hops": self.hop_count,
            "ttl": self.ttl,
            "id": self.packet_id,
            "path": self.path_traversed,
        }
        header_bytes = json.dumps(header).encode()
        return len(header_bytes).to_bytes(2, "big") + header_bytes + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "RoutingPacket":
        """Deserialize packet from bytes."""
        header_len = int.from_bytes(data[:2], "big")
        header = json.loads(data[2 : 2 + header_len].decode())
        payload = data[2 + header_len :]

        return cls(
            packet_type=PacketType(header["type"]),
            source=header["src"],
            destination=header["dst"],
            seq_num=header["seq"],
            hop_count=header["hops"],
            ttl=header["ttl"],
            payload=payload,
            packet_id=header["id"],
            path_traversed=header.get("path", []),
        )

    def decrement_ttl(self) -> "RoutingPacket":
        """Create a new packet with decremented TTL and incremented hop count."""
        return RoutingPacket(
            packet_type=self.packet_type,
            source=self.source,
            destination=self.destination,
            seq_num=self.seq_num,
            hop_count=self.hop_count + 1,
            ttl=self.ttl - 1,
            payload=self.payload,
            packet_id=self.packet_id,
            path_traversed=self.path_traversed.copy(),
        )

    def with_path(self, additional_nodes: List[str]) -> "RoutingPacket":
        """Create a new packet with extended path."""
        return RoutingPacket(
            packet_type=self.packet_type,
            source=self.source,
            destination=self.destination,
            seq_num=self.seq_num,
            hop_count=self.hop_count,
            ttl=self.ttl,
            payload=self.payload,
            packet_id=self.packet_id,
            path_traversed=self.path_traversed + additional_nodes,
        )


__all__ = ["PacketType", "RouteEntry", "RoutingPacket"]

