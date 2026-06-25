"""
x0tta6bl4 Mesh Routing — Shared Types.

Common data types used by MeshRouter and other mesh networking
modules. Extracted from mesh_router.py to break circular imports.

Exports:
    - PacketType: Routing packet type enum
    - RouteEntry: Routing table entry dataclass
    - RoutingPacket: Wire-format routing packet dataclass
"""

import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum


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
    path: list[str] = field(default_factory=list)  # Добавляем путь в RouteEntry

    @property
    def age(self) -> float:
        return time.time() - self.timestamp


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
    # Новое поле для отслеживания пройденного пути (для Node-Disjointness)
    path_traversed: list[str] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        header = {
            "type": self.packet_type.value,
            "src": self.source,
            "dst": self.destination,
            "seq": self.seq_num,
            "hops": self.hop_count,
            "ttl": self.ttl,
            "id": self.packet_id,
            "path": self.path_traversed,  # Добавляем путь в заголовок
        }
        header_bytes = json.dumps(header).encode()
        return len(header_bytes).to_bytes(2, "big") + header_bytes + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "RoutingPacket":
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
            path_traversed=header.get(
                "path", []
            ),  # Извлекаем путь, по умолчанию пустой список
        )
