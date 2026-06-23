"""First-party VPN wire protocol frames."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct

from .crypto import FrameCrypto, FrameCryptoError


MAGIC = b"X0VPN001"
VERSION = 1
MAX_PAYLOAD_BYTES = 65535
HEADER = struct.Struct("!8sBBQQH")
HEADER_BYTES = HEADER.size


class FrameDecodeError(ValueError):
    """Raised when a frame cannot be decoded."""


class FrameAuthError(ValueError):
    """Raised when a protected frame fails authentication."""


class FrameType(IntEnum):
    HELLO = 1
    ACCEPT = 2
    DATA = 3
    PING = 4
    PONG = 5
    CLOSE = 6


@dataclass(frozen=True)
class Frame:
    frame_type: FrameType
    session_id: int
    sequence: int
    payload: bytes = b""


@dataclass(frozen=True)
class FrameHeader:
    frame_type: FrameType
    session_id: int
    sequence: int
    payload_len: int


def decode_frame_header(data: bytes) -> FrameHeader:
    """Decode only the public frame header used for session routing."""
    if len(data) < HEADER_BYTES:
        raise FrameDecodeError("frame too short")
    magic, version, frame_type_raw, session_id, sequence, payload_len = HEADER.unpack(
        data[:HEADER_BYTES]
    )
    if magic != MAGIC:
        raise FrameDecodeError("bad frame magic")
    if version != VERSION:
        raise FrameDecodeError("unsupported frame version")
    try:
        frame_type = FrameType(frame_type_raw)
    except ValueError as exc:
        raise FrameDecodeError("unknown frame type") from exc
    if payload_len > MAX_PAYLOAD_BYTES:
        raise FrameDecodeError("payload too large")
    return FrameHeader(
        frame_type=frame_type,
        session_id=session_id,
        sequence=sequence,
        payload_len=payload_len,
    )


class ReplayWindow:
    """Small sliding replay window for received frame sequences."""

    def __init__(self, size: int = 128) -> None:
        if size < 8:
            raise ValueError("replay window size must be at least 8")
        self.size = size
        self.highest = -1
        self.seen: set[int] = set()

    def accept(self, sequence: int) -> bool:
        if sequence < 0:
            return False
        if self.highest >= 0 and sequence <= self.highest - self.size:
            return False
        if sequence in self.seen:
            return False
        self.seen.add(sequence)
        if sequence > self.highest:
            self.highest = sequence
        floor = self.highest - self.size
        self.seen = {item for item in self.seen if item > floor}
        return True


class WireCodec:
    """Encode and decode authenticated first-party VPN frames."""

    def __init__(self, crypto: FrameCrypto | None = None) -> None:
        self.crypto = crypto

    def encode(self, frame: Frame, *, protect: bool = True) -> bytes:
        payload = frame.payload
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise FrameDecodeError("payload too large")
        header = HEADER.pack(
            MAGIC,
            VERSION,
            int(frame.frame_type),
            frame.session_id,
            frame.sequence,
            len(payload),
        )
        if protect:
            if self.crypto is None:
                raise FrameAuthError("protected encode requires crypto")
            payload = self.crypto.protect(
                sequence=frame.sequence,
                plaintext=payload,
                aad=header,
            )
        return header + payload

    def decode(self, data: bytes, *, protected: bool = True) -> Frame:
        if len(data) < HEADER_BYTES:
            raise FrameDecodeError("frame too short")
        magic, version, frame_type_raw, session_id, sequence, payload_len = HEADER.unpack(
            data[:HEADER_BYTES]
        )
        if magic != MAGIC:
            raise FrameDecodeError("bad frame magic")
        if version != VERSION:
            raise FrameDecodeError("unsupported frame version")
        try:
            frame_type = FrameType(frame_type_raw)
        except ValueError as exc:
            raise FrameDecodeError("unknown frame type") from exc

        header = data[:HEADER_BYTES]
        payload = data[HEADER_BYTES:]
        if protected:
            if self.crypto is None:
                raise FrameAuthError("protected decode requires crypto")
            try:
                payload = self.crypto.open(
                    sequence=sequence,
                    protected_payload=payload,
                    aad=header,
                )
            except FrameCryptoError as exc:
                raise FrameAuthError(str(exc)) from exc
        if len(payload) != payload_len:
            raise FrameDecodeError("payload length mismatch")
        return Frame(
            frame_type=frame_type,
            session_id=session_id,
            sequence=sequence,
            payload=payload,
        )
