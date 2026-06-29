"""CleitonQ package: IETF draft specification reference implementation.

Components
----------
* frame.py       — MAVLink v2 frame codec (CRC-16-CCITT)
* chunk.py       — CLEITONQ_CHUNK fragmentation / reassembly (MSG_ID 50000)
* session.py     — PQC-authenticated session (MSG_ID 50001, 50002)

All heavy PQC operations delegate to the first-party implementations
in src.network.firstparty_vpn.{mlkem, mldsa, crypto}.
"""

from .chunk import CleitonqChunker, CLEITONQ_CHUNK_MSG_ID
from .frame import MavlinkV2Frame
from .session import CleitonqSessionManager, MSG_SESSION_INIT, MSG_SIGNED_CMD

__all__ = [
    "CleitonqChunker",
    "CleitonqSessionManager",
    "MavlinkV2Frame",
    "CLEITONQ_CHUNK_MSG_ID",
    "MSG_SESSION_INIT",
    "MSG_SIGNED_CMD",
]
