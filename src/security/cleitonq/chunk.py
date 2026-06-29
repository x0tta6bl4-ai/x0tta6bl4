"""X0TMQ_CHUNK: relay-transparent fragmentation for MAVLink v2.

Fragments post-quantum payloads (ML-KEM ciphertexts, ML-DSA signatures)
into 245-byte chunks, each wrapped as a valid MAVLink v2 frame with
MSG_ID 50000.  Legacy relays forward these frames as opaque valid data.

Reassembly is keyed by (sys_id, comp_id, session_id).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

from .frame import MavlinkV2Frame


# MAVLink message ID reserved for x0tMQ chunk transport.
X0TMQ_CHUNK_MSG_ID = 50000

# Payload data per chunk (MAVLink v2 MTU is 280; we leave room for
# header overhead and CRC).
_CHUNK_DATA_BYTES = 245

# Chunk-wire header: src_msgid(2) chunk_idx(2) total_chunks(2) session_id(4)
_CHUNK_HEADER_FMT = "<HHHI"
_CHUNK_HEADER_BYTES = struct.calcsize(_CHUNK_HEADER_FMT)


class CleitonqChunker:
    """Fragment and reassemble PQ payloads through X0TMQ_CHUNK frames.

    Usage (sender):
        chunker = CleitonqChunker(sys_id=1, comp_id=1)
        frames = chunker.fragment(session_id=42, data=pq_ciphertext)
        for frame in frames:
            serialized = frame.serialize()

    Usage (receiver):
        chunker = CleitonqChunker(sys_id=2, comp_id=2)
        reassembled = chunker.process_chunk(incoming_frame)
        if reassembled is not None:
            # payload fully received
    """

    def __init__(self, sys_id: int, comp_id: int) -> None:
        self._sys_id = sys_id
        self._comp_id = comp_id
        # (sys_id, comp_id, session_id) -> {chunk_idx: data}
        self._buffers: Dict[Tuple[int, int, int], Dict[int, bytes]] = {}

    def fragment(self, session_id: int, data: bytes) -> List[MavlinkV2Frame]:
        """Split *data* into X0TMQ_CHUNK frames.

        Each frame carries *session_id* and chunk metadata so the
        receiver can reassemble across independent MAVLink streams.
        """
        total = (len(data) + _CHUNK_DATA_BYTES - 1) // _CHUNK_DATA_BYTES
        frames: List[MavlinkV2Frame] = []
        for idx in range(total):
            start = idx * _CHUNK_DATA_BYTES
            chunk = data[start : start + _CHUNK_DATA_BYTES]
            payload = struct.pack(_CHUNK_HEADER_FMT, idx, total, session_id) + chunk
            frames.append(
                MavlinkV2Frame(
                    sys_id=self._sys_id,
                    comp_id=self._comp_id,
                    msg_id=X0TMQ_CHUNK_MSG_ID,
                    payload=payload,
                    seq=idx,
                )
            )
        return frames

    def process_chunk(self, frame: MavlinkV2Frame) -> Optional[bytes]:
        """Feed one incoming X0TMQ_CHUNK frame.

        Returns the reassembled payload when all chunks for a session
        have arrived, otherwise *None*.
        """
        if frame.msg_id != X0TMQ_CHUNK_MSG_ID:
            return None
        raw = frame.payload
        if len(raw) < _CHUNK_HEADER_BYTES:
            return None

        chunk_idx, total_chunks, session_id = struct.unpack(
            _CHUNK_HEADER_FMT, raw[:_CHUNK_HEADER_BYTES]
        )
        data = raw[_CHUNK_HEADER_BYTES:]

        key = (frame.sys_id, frame.comp_id, session_id)
        buf = self._buffers.setdefault(key, {})
        buf[chunk_idx] = data

        if len(buf) == total_chunks:
            parts = [buf[i] for i in range(total_chunks) if i in buf]
            if len(parts) == total_chunks:
                del self._buffers[key]
                return b"".join(parts)
            # Missing a chunk — unlikely given the len check, but be safe.
            return None

        return None

    def flush_session(self, session_id: int) -> None:
        """Drop any buffered state for *session_id* (e.g. on timeout)."""
        stale = [k for k in self._buffers if k[2] == session_id]
        for k in stale:
            del self._buffers[k]
