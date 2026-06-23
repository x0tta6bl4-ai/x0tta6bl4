"""First-party TESLA-style delayed authentication primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import struct


TESLA_KEY_BYTES = 32
TESLA_TAG_BYTES = 32
TESLA_DOMAIN = b"x0vpn-tesla-v1"


class TeslaAuthError(ValueError):
    """Raised when a TESLA-style envelope cannot be verified."""


def derive_tesla_slot_key(master_secret: bytes, slot: int) -> bytes:
    if len(master_secret) < TESLA_KEY_BYTES:
        raise TeslaAuthError("TESLA master secret must be at least 32 bytes")
    if slot < 0:
        raise TeslaAuthError("TESLA slot must be non-negative")
    return hmac.new(
        master_secret,
        TESLA_DOMAIN + b":slot:" + struct.pack("!Q", slot),
        hashlib.sha256,
    ).digest()


def tesla_key_commitment(key: bytes) -> bytes:
    if len(key) != TESLA_KEY_BYTES:
        raise TeslaAuthError("TESLA slot key must be 32 bytes")
    return hashlib.sha256(TESLA_DOMAIN + b":commit:" + key).digest()


@dataclass(frozen=True)
class FirstPartyTeslaEnvelope:
    """Payload plus a MAC whose key can be disclosed later."""

    sequence: int
    slot: int
    payload: bytes
    tag: bytes
    key_commitment: bytes

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise TeslaAuthError("TESLA sequence must be non-negative")
        if self.slot < 0:
            raise TeslaAuthError("TESLA slot must be non-negative")
        if len(self.tag) != TESLA_TAG_BYTES:
            raise TeslaAuthError("TESLA tag must be 32 bytes")
        if len(self.key_commitment) != TESLA_KEY_BYTES:
            raise TeslaAuthError("TESLA key commitment must be 32 bytes")

    def authenticated_bytes(self) -> bytes:
        return (
            TESLA_DOMAIN
            + b":frame:"
            + struct.pack("!QQ", self.sequence, self.slot)
            + self.payload
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "slot": self.slot,
            "payload_hex": self.payload.hex(),
            "tag": self.tag.hex(),
            "key_commitment": self.key_commitment.hex(),
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, object]) -> "FirstPartyTeslaEnvelope":
        return cls(
            sequence=int(payload["sequence"]),
            slot=int(payload["slot"]),
            payload=bytes.fromhex(str(payload["payload_hex"])),
            tag=bytes.fromhex(str(payload["tag"])),
            key_commitment=bytes.fromhex(str(payload["key_commitment"])),
        )


@dataclass(frozen=True)
class FirstPartyTeslaPolicy:
    """Local policy for delayed key disclosure."""

    slot_seconds: int = 60
    disclosure_delay_slots: int = 1

    def __post_init__(self) -> None:
        if self.slot_seconds < 1:
            raise TeslaAuthError("TESLA slot seconds must be positive")
        if self.disclosure_delay_slots < 1:
            raise TeslaAuthError("TESLA disclosure delay must be positive")

    def slot_for_timestamp(self, timestamp: int) -> int:
        if timestamp < 0:
            raise TeslaAuthError("TESLA timestamp must be non-negative")
        return timestamp // self.slot_seconds

    def disclosure_slot(self, slot: int) -> int:
        if slot < 0:
            raise TeslaAuthError("TESLA slot must be non-negative")
        return slot + self.disclosure_delay_slots

    def disclosure_due(self, *, slot: int, current_timestamp: int) -> bool:
        return self.slot_for_timestamp(current_timestamp) >= self.disclosure_slot(slot)


class FirstPartyTeslaAuthenticator:
    """Create and verify TESLA-style delayed-auth envelopes."""

    def __init__(self, master_secret: bytes, policy: FirstPartyTeslaPolicy | None = None):
        if len(master_secret) < TESLA_KEY_BYTES:
            raise TeslaAuthError("TESLA master secret must be at least 32 bytes")
        self.master_secret = master_secret
        self.policy = policy or FirstPartyTeslaPolicy()

    def seal(
        self,
        payload: bytes,
        *,
        sequence: int,
        timestamp: int,
    ) -> FirstPartyTeslaEnvelope:
        slot = self.policy.slot_for_timestamp(timestamp)
        key = derive_tesla_slot_key(self.master_secret, slot)
        envelope = FirstPartyTeslaEnvelope(
            sequence=sequence,
            slot=slot,
            payload=payload,
            tag=b"\x00" * TESLA_TAG_BYTES,
            key_commitment=tesla_key_commitment(key),
        )
        tag = hmac.new(key, envelope.authenticated_bytes(), hashlib.sha256).digest()
        return FirstPartyTeslaEnvelope(
            sequence=sequence,
            slot=slot,
            payload=payload,
            tag=tag,
            key_commitment=envelope.key_commitment,
        )

    def disclose_key(self, slot: int, *, current_timestamp: int) -> bytes:
        if not self.policy.disclosure_due(slot=slot, current_timestamp=current_timestamp):
            raise TeslaAuthError("TESLA disclosure is not due yet")
        return derive_tesla_slot_key(self.master_secret, slot)

    def verify(self, envelope: FirstPartyTeslaEnvelope, disclosed_key: bytes) -> bool:
        if not hmac.compare_digest(
            tesla_key_commitment(disclosed_key),
            envelope.key_commitment,
        ):
            return False
        expected = hmac.new(
            disclosed_key,
            envelope.authenticated_bytes(),
            hashlib.sha256,
        ).digest()
        return hmac.compare_digest(expected, envelope.tag)
