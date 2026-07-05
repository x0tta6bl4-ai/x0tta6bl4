"""MAVLink v2 frame codec for x0tMQ transport layer.

x0tMQ — x0tta6bl4 MAVLink Quantum: post-quantum authentication for UAVs.

Simplified MAVLink v2 framing with CRC-16-CCITT-accumulated checksums,
compatible with standard MAVLink relays.  Only the subset needed for
x0CHUNK, X0_SESSION_INIT, and X0_SIGNED_CMD.
"""

from __future__ import annotations

import struct
from typing import Optional


_X25_INIT = 0xFFFF
_STX_V2 = 0xFD

# CRC_EXTRA bytes for custom x0tMQ message IDs (MAVLink v2 protocol).
# These MUST be identical on GCS and UAV for frames to validate.
CRC_EXTRA: dict[int, int] = {
    50000: 0xAB,  # x0CHUNK
    50001: 0xBC,  # X0_SESSION_INIT
    50002: 0xCD,  # X0_SIGNED_CMD
    50003: 0xDE,  # X0_SESSION_ACK
}


def _crc_accumulate(b: int, crc: int) -> int:
    """MAVLink CRC-16-CCITT accumulator (standard x25 flavor)."""
    accum = b ^ (crc & 0xFF)
    accum ^= (accum << 4) & 0xFF
    return (crc >> 8) ^ (accum << 8) ^ (accum << 3) ^ (accum >> 4)


def _crc_ccitt(data: bytes, crc_extra: int = 0) -> int:
    crc = _X25_INIT
    for b in data:
        crc = _crc_accumulate(b, crc)
    if crc_extra:
        crc = _crc_accumulate(crc_extra, crc)
    return crc


class MavlinkV2Frame:
    """Wire-format MAVLink v2 frame for one x0tMQ payload.

    Header layout (MAVLink v2):
        [0]   STX (0xFD)
        [1]   payload_len
        [2]   incompat_flags (0x00 for x0tMQ)
        [3]   compat_flags
        [4]   seq
        [5]   sys_id
        [6]   comp_id
        [7-9] msg_id (24-bit, little-endian)
        [10+] payload
        [-2:] CRC-16-CCITT
    """

    __slots__ = ("sys_id", "comp_id", "msg_id", "payload", "seq",
                 "incompat_flags", "compat_flags")

    def __init__(
        self,
        sys_id: int,
        comp_id: int,
        msg_id: int,
        payload: bytes,
        *,
        seq: int = 0,
        incompat_flags: int = 0x00,
        compat_flags: int = 0x00,
    ) -> None:
        self.sys_id = sys_id
        self.comp_id = comp_id
        self.msg_id = msg_id
        self.payload = payload
        self.seq = seq
        self.incompat_flags = incompat_flags
        self.compat_flags = compat_flags

    def serialize(self, crc_extra: int | None = None) -> bytes:
        plen = len(self.payload)
        if crc_extra is None:
            crc_extra = CRC_EXTRA.get(self.msg_id, 0)
        header = struct.pack(
            "<BBBBBBBBBB",
            _STX_V2,
            plen,
            self.incompat_flags,
            self.compat_flags,
            self.seq,
            self.sys_id,
            self.comp_id,
            self.msg_id & 0xFF,
            (self.msg_id >> 8) & 0xFF,
            (self.msg_id >> 16) & 0xFF,
        )
        packet = header[1:] + self.payload
        crc = _crc_ccitt(packet, crc_extra)
        return header + self.payload + struct.pack("<H", crc)

    @classmethod
    def deserialize(
        cls, data: bytes, crc_extra: int | None = None
    ) -> Optional["MavlinkV2Frame"]:
        if crc_extra is None:
            # Try to infer crc_extra from the msg_id embedded in the data.
            # data[7:10] is the 24-bit msg_id in little-endian.
            if len(data) >= 10:
                inferred_id = data[7] | (data[8] << 8) | (data[9] << 16)
                crc_extra = CRC_EXTRA.get(inferred_id, 0)
            else:
                crc_extra = 0
        if len(data) < 12:
            return None
        if data[0] != _STX_V2:
            return None
        plen = data[1]
        if len(data) < 12 + plen:
            return None
        (
            _plen,
            inc_flags,
            cmp_flags,
            seq,
            sys_id,
            comp_id,
            b0, b1, b2,
        ) = struct.unpack("<BBBBBBBBB", data[1:10])
        msg_id = b0 | (b1 << 8) | (b2 << 16)
        payload = data[10: 10 + plen]
        expected_crc = struct.unpack("<H", data[10 + plen: 12 + plen])[0]
        if _crc_ccitt(data[1: 10 + plen], crc_extra) != expected_crc:
            return None
        if inc_flags != 0:
            return None
        return cls(
            sys_id, comp_id, msg_id, payload,
            seq=seq, incompat_flags=inc_flags, compat_flags=cmp_flags,
        )

    def __repr__(self) -> str:
        return (
            f"MavlinkV2Frame(msg_id={self.msg_id}, seq={self.seq}, "
            f"payload={len(self.payload)}B)"
        )
