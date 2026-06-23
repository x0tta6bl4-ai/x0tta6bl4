"""First-party packet fragmentation for constrained UDP paths."""

from __future__ import annotations

import math
import struct
from collections import OrderedDict
from dataclasses import dataclass, field

from .protocol import MAX_PAYLOAD_BYTES

FRAGMENT_MAGIC = b"X0FRAG1!"
FRAGMENT_HEADER = struct.Struct("!8sQHHH")
FRAGMENT_HEADER_BYTES = FRAGMENT_HEADER.size
MAX_PACKET_BYTES = 65535
DEFAULT_MAX_PENDING_PACKET_BYTES = MAX_PACKET_BYTES * 128


class FragmentError(ValueError):
    """Raised when a first-party packet fragment is invalid."""


@dataclass(frozen=True)
class PacketFragment:
    packet_id: int
    index: int
    count: int
    total_len: int
    chunk: bytes

    def encode(self) -> bytes:
        if not 0 <= self.packet_id <= 0xFFFFFFFFFFFFFFFF:
            raise FragmentError("fragment packet id is out of range")
        if not 0 <= self.index < self.count <= 0xFFFF:
            raise FragmentError("fragment index/count is invalid")
        if not 1 <= self.total_len <= MAX_PACKET_BYTES:
            raise FragmentError("fragment total length is invalid")
        if self.count > self.total_len:
            raise FragmentError("fragment count exceeds packet length")
        if not self.chunk:
            raise FragmentError("fragment chunk is empty")
        if len(self.chunk) > self.total_len:
            raise FragmentError("fragment chunk exceeds packet length")
        return (
            FRAGMENT_HEADER.pack(
                FRAGMENT_MAGIC,
                self.packet_id,
                self.index,
                self.count,
                self.total_len,
            )
            + self.chunk
        )

    @staticmethod
    def decode(payload: bytes) -> "PacketFragment":
        if not payload.startswith(FRAGMENT_MAGIC):
            raise FragmentError("payload is not a first-party fragment")
        if len(payload) <= FRAGMENT_HEADER_BYTES:
            raise FragmentError("fragment is missing payload bytes")
        magic, packet_id, index, count, total_len = FRAGMENT_HEADER.unpack(
            payload[:FRAGMENT_HEADER_BYTES]
        )
        if magic != FRAGMENT_MAGIC:
            raise FragmentError("bad fragment magic")
        chunk = payload[FRAGMENT_HEADER_BYTES:]
        fragment = PacketFragment(
            packet_id=packet_id,
            index=index,
            count=count,
            total_len=total_len,
            chunk=chunk,
        )
        fragment.encode()
        return fragment


@dataclass
class PacketFragmenter:
    """Split a TUN packet into first-party DATA payload fragments."""

    max_payload_size: int = 1200
    next_packet_id: int = 1

    def __post_init__(self) -> None:
        if self.max_payload_size > MAX_PAYLOAD_BYTES:
            raise ValueError("fragment payload size exceeds wire frame limit")
        if self.max_payload_size <= FRAGMENT_HEADER_BYTES:
            raise ValueError("fragment payload size must fit header and data")

    @property
    def max_chunk_size(self) -> int:
        return self.max_payload_size - FRAGMENT_HEADER_BYTES

    def split(self, packet: bytes) -> tuple[bytes, ...]:
        if not packet:
            raise FragmentError("packet is empty")
        if len(packet) > MAX_PACKET_BYTES:
            raise FragmentError("packet exceeds maximum fragmentable size")
        count = math.ceil(len(packet) / self.max_chunk_size)
        if count > 0xFFFF:
            raise FragmentError("packet requires too many fragments")
        packet_id = self.next_packet_id
        self.next_packet_id = 1 if packet_id == 0xFFFFFFFFFFFFFFFF else packet_id + 1
        fragments: list[bytes] = []
        for index in range(count):
            start = index * self.max_chunk_size
            chunk = packet[start : start + self.max_chunk_size]
            fragments.append(
                PacketFragment(
                    packet_id=packet_id,
                    index=index,
                    count=count,
                    total_len=len(packet),
                    chunk=chunk,
                ).encode()
            )
        return tuple(fragments)


@dataclass
class _PacketAssembly:
    total_len: int
    count: int
    chunks: dict[int, bytes] = field(default_factory=dict)

    @property
    def received_len(self) -> int:
        return sum(len(chunk) for chunk in self.chunks.values())


class PacketReassembler:
    """Reassemble first-party DATA payload fragments into TUN packets."""

    def __init__(
        self,
        *,
        max_pending_packets: int = 128,
        max_pending_bytes: int = DEFAULT_MAX_PENDING_PACKET_BYTES,
    ) -> None:
        if max_pending_packets < 1:
            raise ValueError("max pending packets must be at least 1")
        if max_pending_bytes < 1:
            raise ValueError("max pending bytes must be at least 1")
        self.max_pending_packets = max_pending_packets
        self.max_pending_bytes = max_pending_bytes
        self._pending: OrderedDict[int, _PacketAssembly] = OrderedDict()

    def accept(self, payload: bytes) -> bytes | None:
        if not payload.startswith(FRAGMENT_MAGIC):
            return payload
        fragment = PacketFragment.decode(payload)
        assembly = self._pending.get(fragment.packet_id)
        if assembly is None:
            if fragment.total_len > self.max_pending_bytes:
                raise FragmentError("fragment packet exceeds pending byte budget")
            self._evict_oldest_to_fit(fragment.total_len)
            assembly = _PacketAssembly(
                total_len=fragment.total_len,
                count=fragment.count,
            )
            self._pending[fragment.packet_id] = assembly
        elif (
            assembly.total_len != fragment.total_len
            or assembly.count != fragment.count
        ):
            self._pending.pop(fragment.packet_id, None)
            raise FragmentError("fragment metadata changed for packet")
        elif fragment.index in assembly.chunks:
            self._pending.pop(fragment.packet_id, None)
            raise FragmentError("duplicate fragment index")

        if assembly.received_len + len(fragment.chunk) > assembly.total_len:
            self._pending.pop(fragment.packet_id, None)
            raise FragmentError("fragment chunks exceed packet length")

        assembly.chunks[fragment.index] = fragment.chunk
        self._pending.move_to_end(fragment.packet_id)
        if len(assembly.chunks) != assembly.count:
            return None
        packet = b"".join(assembly.chunks[index] for index in range(assembly.count))
        if len(packet) != assembly.total_len:
            raise FragmentError("reassembled packet length mismatch")
        del self._pending[fragment.packet_id]
        return packet

    @property
    def pending_packets(self) -> int:
        return len(self._pending)

    @property
    def pending_bytes(self) -> int:
        return sum(assembly.total_len for assembly in self._pending.values())

    def _evict_oldest_to_fit(self, next_packet_bytes: int) -> None:
        while self._pending and (
            len(self._pending) >= self.max_pending_packets
            or self.pending_bytes + next_packet_bytes > self.max_pending_bytes
        ):
            self._pending.popitem(last=False)
