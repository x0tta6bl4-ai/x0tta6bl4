"""x0CHUNK: relay-transparent fragmentation for MAVLink v2.

x0tMQ — x0tta6bl4 MAVLink Quantum.

Fragments post-quantum payloads (ML-KEM ciphertexts, ML-DSA signatures)
into 245-byte chunks, each wrapped as a valid MAVLink v2 frame with
MSG_ID X0_CHUNK_MSG_ID (50000).  Legacy relays forward these frames
as opaque valid data.

Reassembly is keyed by (sys_id, comp_id, session_id).
"""

from __future__ import annotations

import struct
import time
from typing import Dict, List, Optional, Tuple

from .frame import MavlinkV2Frame

_BUFFER_TTL_SECONDS = 300  # 5 minutes


X0_CHUNK_MSG_ID = 50000          # x0CHUNK fragment
X0_SESSION_INIT_ID = 50001       # ML-KEM-1024 ciphertext
X0_SIGNED_CMD_ID = 50002         # ML-DSA-87 signature
X0_SESSION_ACK_ID = 50003        # Session acknowledgment (UAV → GCS)

_CHUNK_DATA_BYTES = 245
_CHUNK_HEADER_FMT = "<HHHI"
_CHUNK_HEADER_BYTES = struct.calcsize(_CHUNK_HEADER_FMT)


class X0Chunker:
    """Fragment and reassemble PQ payloads through x0CHUNK frames.

    Usage (sender):
        chunker = X0Chunker(sys_id=1, comp_id=1)
        frames = chunker.fragment(session_id=42, data=pq_ciphertext)
        for frame in frames:
            serialized = frame.serialize()

    Usage (receiver):
        chunker = X0Chunker(sys_id=2, comp_id=2)
        reassembled = chunker.process_chunk(incoming_frame)
        if reassembled is not None:
            # payload fully received
    """

    def __init__(self, sys_id: int, comp_id: int) -> None:
        self._sys_id = sys_id
        self._comp_id = comp_id
        self._buffers: Dict[Tuple[int, int, int], Dict[int, bytes]] = {}
        self._buffer_timestamps: Dict[Tuple[int, int, int], float] = {}
        self._last_seq: Dict[Tuple[int, int, int], int] = {}

    def fragment(self, session_id: int, data: bytes) -> List[MavlinkV2Frame]:
        """Split *data* into x0CHUNK frames.

        Each frame carries *session_id* and chunk metadata so the
        receiver can reassemble across independent MAVLink streams.
        """
        total = (len(data) + _CHUNK_DATA_BYTES - 1) // _CHUNK_DATA_BYTES
        frames: List[MavlinkV2Frame] = []
        for idx in range(total):
            start = idx * _CHUNK_DATA_BYTES
            chunk = data[start: start + _CHUNK_DATA_BYTES]
            payload = struct.pack(_CHUNK_HEADER_FMT, X0_CHUNK_MSG_ID, idx, total, session_id) + chunk
            frames.append(
                MavlinkV2Frame(
                    sys_id=self._sys_id,
                    comp_id=self._comp_id,
                    msg_id=X0_CHUNK_MSG_ID,
                    payload=payload,
                    seq=idx,
                )
            )
        return frames

    def _evict_expired_buffers(self) -> None:
        """Remove buffers older than _BUFFER_TTL_SECONDS."""
        now = time.monotonic()
        expired = [k for k, ts in self._buffer_timestamps.items()
                   if now - ts > _BUFFER_TTL_SECONDS]
        for k in expired:
            self._buffers.pop(k, None)
            self._buffer_timestamps.pop(k, None)
            self._last_seq.pop(k, None)

    def process_chunk(self, frame: MavlinkV2Frame) -> Optional[bytes]:
        """Feed one incoming x0CHUNK frame.

        Returns the reassembled payload when all chunks for a session
        have arrived, otherwise *None*.
        """
        self._evict_expired_buffers()

        if frame.msg_id != X0_CHUNK_MSG_ID:
            return None
        raw = frame.payload
        if len(raw) < _CHUNK_HEADER_BYTES:
            return None

        src_msgid, chunk_idx, total_chunks, session_id = struct.unpack(
            _CHUNK_HEADER_FMT, raw[:_CHUNK_HEADER_BYTES]
        )
        data = raw[_CHUNK_HEADER_BYTES:]

        key = (frame.sys_id, frame.comp_id, session_id)

        # Reject out-of-order chunks (seq must be >= last validated)
        if key in self._last_seq and chunk_idx < self._last_seq[key]:
            return None

        buf = self._buffers.setdefault(key, {})
        buf[chunk_idx] = data
        self._buffer_timestamps[key] = time.monotonic()
        self._last_seq[key] = chunk_idx

        if len(buf) == total_chunks:
            parts = [buf[i] for i in range(total_chunks) if i in buf]
            if len(parts) == total_chunks:
                del self._buffers[key]
                self._buffer_timestamps.pop(key, None)
                self._last_seq.pop(key, None)
                return b"".join(parts)
            return None
        return None

    def flush_session(self, session_id: int) -> None:
        """Drop any buffered state for *session_id* (e.g. on timeout)."""
        stale = [k for k in self._buffers if k[2] == session_id]
        for k in stale:
            del self._buffers[k]
