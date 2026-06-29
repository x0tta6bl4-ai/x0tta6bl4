"""x0tMQ package: MAVLink v2 post-quantum authentication standard.

Specification: docs/rfc/draft-x0tmq-mavlink-pqc.md

Components
----------
* frame.py       — MAVLink v2 frame codec (CRC-16-CCITT)
* chunk.py       — x0CHUNK fragmentation / reassembly (MSG_ID 50000)
* session.py     — PQC-authenticated session (MSG_ID 50001, 50002, 50003)
* hkdf.py        — HKDF-SHA3-256 key derivation (draft §7)
"""

from .chunk import X0Chunker, X0_CHUNK_MSG_ID
from .frame import MavlinkV2Frame
from .session import X0SessionManager, X0_SESSION_INIT_ID, X0_SIGNED_CMD_ID, X0_SESSION_ACK_ID

__all__ = [
    "X0Chunker",
    "X0SessionManager",
    "MavlinkV2Frame",
    "X0_CHUNK_MSG_ID",
    "X0_SESSION_INIT_ID",
    "X0_SIGNED_CMD_ID",
    "X0_SESSION_ACK_ID",
]
