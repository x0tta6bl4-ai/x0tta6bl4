"""Signed policy snapshot distribution for the first-party VPN control plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable, Protocol

from .identity import (
    IdentitySignatureProvider,
    IdentitySigningKey,
    LocalIdentitySignatureProvider,
)
from .ops import PrivacySafeAuditLog, PrivacySafeAuditEvent, hash_identifier
from .policy_store import PolicyRefreshClient, PolicySnapshot, PolicyStoreError
from .protocol import Frame, FrameType

POLICY_DISTRIBUTION_MAGIC = b"X0POLICY"
POLICY_SNAPSHOT_REQUEST = b"policy-snapshot:get:v1"


class PolicyDistributionError(ValueError):
    """Raised when a policy snapshot envelope cannot be trusted or applied."""


class PolicySnapshotTransportClient(Protocol):
    """Transport contract used by the policy snapshot fetch client."""

    def send_data(self, payload: bytes) -> None: ...

    async def drain(self) -> None: ...

    async def recv(self, timeout: float = 1.0) -> Frame: ...


@dataclass(frozen=True)
class PolicySnapshotEnvelope:
    """A signed, replay-resistant wrapper around a policy snapshot."""

    version: int
    issuer: str
    key_id: str
    signature_algorithm: str
    sequence: int
    issued_at: int
    snapshot: PolicySnapshot
    signature: bytes

    def __post_init__(self) -> None:
        if self.version != 1:
            raise PolicyDistributionError("unsupported policy envelope version")
        if not self.issuer.strip():
            raise PolicyDistributionError("policy envelope issuer is required")
        if not self.key_id.strip():
            raise PolicyDistributionError("policy envelope key id is required")
        if not self.signature_algorithm.strip():
            raise PolicyDistributionError("policy envelope signature algorithm is required")
        if self.sequence < 1:
            raise PolicyDistributionError("policy envelope sequence must be positive")
        if self.issued_at < 0:
            raise PolicyDistributionError("policy envelope issued_at is invalid")
        if not self.signature:
            raise PolicyDistributionError("policy envelope signature is required")

    def signing_payload(self) -> bytes:
        return _envelope_signing_payload(
            issuer=self.issuer,
            key_id=self.key_id,
            signature_algorithm=self.signature_algorithm,
            sequence=self.sequence,
            issued_at=self.issued_at,
            snapshot=self.snapshot,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "issued_at": self.issued_at,
            "issuer": self.issuer,
            "key_id": self.key_id,
            "sequence": self.sequence,
            "signature": self.signature.hex(),
            "signature_algorithm": self.signature_algorithm,
            "snapshot": self.snapshot.to_json_dict(),
            "version": self.version,
        }

    def to_bytes(self) -> bytes:
        return POLICY_DISTRIBUTION_MAGIC + _canonical_json(self.to_json_dict())

    @classmethod
    def from_bytes(cls, payload: bytes) -> "PolicySnapshotEnvelope":
        if not payload.startswith(POLICY_DISTRIBUTION_MAGIC):
            raise PolicyDistributionError("policy envelope magic mismatch")
        raw_json = payload[len(POLICY_DISTRIBUTION_MAGIC) :]
        try:
            raw = json.loads(raw_json.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolicyDistributionError("policy envelope JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise PolicyDistributionError("policy envelope root must be a map")
        return cls.from_json_dict(raw)

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "PolicySnapshotEnvelope":
        snapshot_raw = value.get("snapshot")
        if not isinstance(snapshot_raw, dict):
            raise PolicyDistributionError("policy envelope snapshot must be a map")
        expected_hash = snapshot_raw.get("snapshot_hash")
        try:
            snapshot = PolicySnapshot.from_json_dict(snapshot_raw)
        except (PolicyStoreError, ValueError) as exc:
            raise PolicyDistributionError("policy envelope snapshot is invalid") from exc
        if expected_hash != snapshot.snapshot_hash():
            raise PolicyDistributionError("policy envelope snapshot hash mismatch")
        try:
            signature = bytes.fromhex(str(value.get("signature", "")))
        except ValueError as exc:
            raise PolicyDistributionError("policy envelope signature is invalid") from exc
        return cls(
            version=int(value.get("version", 0)),
            issuer=str(value.get("issuer", "")),
            key_id=str(value.get("key_id", "")),
            signature_algorithm=str(value.get("signature_algorithm", "")),
            sequence=int(value.get("sequence", 0)),
            issued_at=int(value.get("issued_at", -1)),
            snapshot=snapshot,
            signature=signature,
        )


class PolicySnapshotDistributor:
    """Issue signed policy snapshot envelopes for admitted endpoints."""

    def __init__(
        self,
        *,
        issuer: str,
        signing_key: IdentitySigningKey,
        signature_provider: IdentitySignatureProvider | None = None,
    ) -> None:
        if not issuer.strip():
            raise ValueError("policy distributor issuer is required")
        self.issuer = issuer
        self.signing_key = signing_key
        self.signature_provider = signature_provider or LocalIdentitySignatureProvider()

    def issue(
        self,
        snapshot: PolicySnapshot,
        *,
        sequence: int,
        now: int | None = None,
    ) -> PolicySnapshotEnvelope:
        now = now if now is not None else _utc_now()
        if sequence < 1:
            raise PolicyDistributionError("policy envelope sequence must be positive")
        if now < snapshot.issued_at:
            raise PolicyDistributionError("policy envelope issued_at predates snapshot")
        if not self.signing_key.active_at(now):
            raise PolicyDistributionError("policy envelope signing key is not active")
        payload = _envelope_signing_payload(
            issuer=self.issuer,
            key_id=self.signing_key.key_id,
            signature_algorithm=self.signing_key.signature_algorithm,
            sequence=sequence,
            issued_at=now,
            snapshot=snapshot,
        )
        signature = self.signature_provider.sign(self.signing_key, payload)
        return PolicySnapshotEnvelope(
            version=1,
            issuer=self.issuer,
            key_id=self.signing_key.key_id,
            signature_algorithm=self.signing_key.signature_algorithm,
            sequence=sequence,
            issued_at=now,
            snapshot=snapshot,
            signature=signature,
        )


@dataclass(frozen=True)
class PolicySequenceState:
    """Durable anti-rollback state for accepted policy snapshot envelopes."""

    issuer: str
    key_id: str
    sequence: int
    envelope_issued_at: int
    snapshot_hash: str
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise PolicyDistributionError("unsupported policy sequence state version")
        if not self.issuer.strip():
            raise PolicyDistributionError("policy sequence state issuer is required")
        if not self.key_id.strip():
            raise PolicyDistributionError("policy sequence state key id is required")
        if self.sequence < 1:
            raise PolicyDistributionError("policy sequence state sequence is invalid")
        if self.envelope_issued_at < 0:
            raise PolicyDistributionError("policy sequence state issued_at is invalid")
        if len(self.snapshot_hash) != 64:
            raise PolicyDistributionError("policy sequence state snapshot hash is invalid")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "envelope_issued_at": self.envelope_issued_at,
            "issuer": self.issuer,
            "key_id": self.key_id,
            "sequence": self.sequence,
            "snapshot_hash": self.snapshot_hash,
            "state_hash": self.state_hash(),
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "PolicySequenceState":
        state = cls(
            version=int(value.get("version", 0)),
            issuer=str(value.get("issuer", "")),
            key_id=str(value.get("key_id", "")),
            sequence=int(value.get("sequence", 0)),
            envelope_issued_at=int(value.get("envelope_issued_at", -1)),
            snapshot_hash=str(value.get("snapshot_hash", "")),
        )
        if value.get("state_hash") != state.state_hash():
            raise PolicyDistributionError("policy sequence state hash mismatch")
        return state

    def state_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "envelope_issued_at": self.envelope_issued_at,
            "issuer": self.issuer,
            "key_id": self.key_id,
            "sequence": self.sequence,
            "snapshot_hash": self.snapshot_hash,
            "version": self.version,
        }


class DurablePolicySequenceStore:
    """Atomic JSON store for the latest accepted policy envelope sequence."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def save(self, state: PolicySequenceState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_bytes(_canonical_json(state.to_json_dict()) + b"\n")
        tmp.replace(self.path)

    def load(self) -> PolicySequenceState | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolicyDistributionError("policy sequence state JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise PolicyDistributionError("policy sequence state root must be a map")
        return PolicySequenceState.from_json_dict(raw)


class PolicySnapshotServerHandler:
    """Dataplane handler that serves signed policy snapshots on request."""

    def __init__(
        self,
        *,
        distributor: PolicySnapshotDistributor,
        snapshot_source: Callable[[], PolicySnapshot],
        initial_sequence: int = 0,
        audit_log: PrivacySafeAuditLog | None = None,
        actor_id: str = "policy-snapshot-server",
        now_provider: Callable[[], int] | None = None,
    ) -> None:
        if initial_sequence < 0:
            raise ValueError("policy snapshot handler initial sequence is invalid")
        if not actor_id.strip():
            raise ValueError("policy snapshot handler actor id is required")
        self.distributor = distributor
        self.snapshot_source = snapshot_source
        self.current_sequence = initial_sequence
        self.audit_log = audit_log
        self.actor_id = actor_id
        self.now_provider = now_provider or _utc_now

    def __call__(self, payload: bytes, peer: tuple[str, int]) -> bytes | None:
        peer_hash = hash_identifier(f"{peer[0]}:{peer[1]}", namespace="policy-peer")
        if payload != POLICY_SNAPSHOT_REQUEST:
            _append_policy_audit(
                self.audit_log,
                event_type="policy_snapshot_request",
                outcome="rejected",
                actor_id=self.actor_id,
                subject_id="policy-snapshot",
                metadata={"reason": "unsupported_request", "peer_hash": peer_hash},
                now=self.now_provider(),
            )
            return None
        try:
            snapshot = self.snapshot_source()
            next_sequence = self.current_sequence + 1
            envelope = self.distributor.issue(
                snapshot,
                sequence=next_sequence,
                now=self.now_provider(),
            )
        except (PolicyDistributionError, PolicyStoreError, ValueError) as exc:
            _append_policy_audit(
                self.audit_log,
                event_type="policy_snapshot_issue",
                outcome="failed",
                actor_id=self.actor_id,
                subject_id="policy-snapshot",
                metadata={
                    "peer_hash": peer_hash,
                    "reason_hash": hash_identifier(
                        type(exc).__name__,
                        namespace="policy-error",
                    ),
                },
                now=self.now_provider(),
            )
            return None
        self.current_sequence = next_sequence
        _append_policy_audit(
            self.audit_log,
            event_type="policy_snapshot_issue",
            outcome="succeeded",
            actor_id=self.actor_id,
            subject_id=snapshot.snapshot_hash(),
            metadata={
                "peer_hash": peer_hash,
                "sequence": envelope.sequence,
                "snapshot_hash": snapshot.snapshot_hash(),
            },
            now=envelope.issued_at,
        )
        return envelope.to_bytes()


class PolicySnapshotReceiver:
    """Verify and apply signed policy snapshots fail-closed."""

    def __init__(
        self,
        *,
        expected_issuer: str,
        verification_key: IdentitySigningKey,
        refresh_client: PolicyRefreshClient,
        signature_provider: IdentitySignatureProvider | None = None,
        minimum_sequence: int = 0,
        sequence_store: DurablePolicySequenceStore | None = None,
    ) -> None:
        if not expected_issuer.strip():
            raise ValueError("policy receiver expected issuer is required")
        if minimum_sequence < 0:
            raise ValueError("policy receiver minimum sequence is invalid")
        self.expected_issuer = expected_issuer
        self.verification_key = verification_key
        self.refresh_client = refresh_client
        self.signature_provider = signature_provider or LocalIdentitySignatureProvider()
        self.sequence_store = sequence_store
        self.current_sequence = self._initial_sequence(minimum_sequence)

    def accept(self, envelope: PolicySnapshotEnvelope | bytes) -> PolicySnapshot:
        parsed = (
            PolicySnapshotEnvelope.from_bytes(envelope)
            if isinstance(envelope, bytes)
            else envelope
        )
        self._verify_envelope(parsed)
        try:
            snapshot = self.refresh_client.refresh_once(lambda: parsed.snapshot)
        except PolicyStoreError as exc:
            raise PolicyDistributionError("policy snapshot refresh failed") from exc
        if self.sequence_store is not None:
            self.sequence_store.save(
                PolicySequenceState(
                    issuer=parsed.issuer,
                    key_id=parsed.key_id,
                    sequence=parsed.sequence,
                    envelope_issued_at=parsed.issued_at,
                    snapshot_hash=parsed.snapshot.snapshot_hash(),
                )
            )
        self.current_sequence = parsed.sequence
        return snapshot

    def _initial_sequence(self, minimum_sequence: int) -> int:
        if self.sequence_store is None:
            return minimum_sequence
        state = self.sequence_store.load()
        if state is None:
            if self.refresh_client.store.path.exists():
                raise PolicyDistributionError(
                    "policy sequence state missing for existing snapshot"
                )
            return minimum_sequence
        if state.issuer != self.expected_issuer:
            raise PolicyDistributionError("policy sequence state issuer mismatch")
        if state.key_id != self.verification_key.key_id:
            raise PolicyDistributionError("policy sequence state key id mismatch")
        return max(minimum_sequence, state.sequence)

    def _verify_envelope(self, envelope: PolicySnapshotEnvelope) -> None:
        if envelope.issuer != self.expected_issuer:
            raise PolicyDistributionError("policy envelope issuer mismatch")
        if envelope.key_id != self.verification_key.key_id:
            raise PolicyDistributionError("policy envelope key id mismatch")
        if envelope.signature_algorithm != self.verification_key.signature_algorithm:
            raise PolicyDistributionError("policy envelope signature algorithm mismatch")
        if envelope.sequence <= self.current_sequence:
            raise PolicyDistributionError("policy envelope sequence rollback")
        if not self.verification_key.active_at(envelope.issued_at):
            raise PolicyDistributionError("policy envelope verification key is not active")
        if not self.signature_provider.verify(
            self.verification_key,
            envelope.signing_payload(),
            envelope.signature,
        ):
            raise PolicyDistributionError("policy envelope signature invalid")


class PolicySnapshotFetchClient:
    """Fetch, verify, persist, and audit a policy snapshot over first-party DATA."""

    def __init__(
        self,
        *,
        transport: PolicySnapshotTransportClient,
        receiver: PolicySnapshotReceiver,
        audit_log: PrivacySafeAuditLog | None = None,
        actor_id: str = "policy-snapshot-client",
        authority_id: str = "policy-snapshot-authority",
        now_provider: Callable[[], int] | None = None,
    ) -> None:
        if not actor_id.strip():
            raise ValueError("policy snapshot client actor id is required")
        if not authority_id.strip():
            raise ValueError("policy snapshot authority id is required")
        self.transport = transport
        self.receiver = receiver
        self.audit_log = audit_log
        self.actor_id = actor_id
        self.authority_id = authority_id
        self.now_provider = now_provider or _utc_now

    async def fetch_once(self, *, timeout: float = 1.0) -> PolicySnapshot:
        try:
            self.transport.send_data(POLICY_SNAPSHOT_REQUEST)
            await self.transport.drain()
            frame = await self.transport.recv(timeout=timeout)
            if frame.frame_type != FrameType.DATA:
                raise PolicyDistributionError("policy snapshot response is not DATA")
            envelope = PolicySnapshotEnvelope.from_bytes(frame.payload)
            snapshot = self.receiver.accept(envelope)
        except PolicyDistributionError as exc:
            self._audit_fetch("failed", reason=type(exc).__name__)
            raise
        except Exception as exc:
            self._audit_fetch("failed", reason=type(exc).__name__)
            raise PolicyDistributionError("policy snapshot fetch failed") from exc
        self._audit_fetch(
            "succeeded",
            sequence=envelope.sequence,
            snapshot_hash=snapshot.snapshot_hash(),
        )
        return snapshot

    def _audit_fetch(
        self,
        outcome: str,
        *,
        reason: str | None = None,
        sequence: int | None = None,
        snapshot_hash: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {}
        if reason is not None:
            metadata["reason_hash"] = hash_identifier(reason, namespace="policy-error")
        if sequence is not None:
            metadata["sequence"] = sequence
        if snapshot_hash is not None:
            metadata["snapshot_hash"] = snapshot_hash
        _append_policy_audit(
            self.audit_log,
            event_type="policy_snapshot_fetch",
            outcome=outcome,
            actor_id=self.actor_id,
            subject_id=self.authority_id,
            metadata=metadata,
            now=self.now_provider(),
        )


def _envelope_signing_payload(
    *,
    issuer: str,
    key_id: str,
    signature_algorithm: str,
    sequence: int,
    issued_at: int,
    snapshot: PolicySnapshot,
) -> bytes:
    return _canonical_json(
        {
            "issued_at": issued_at,
            "issuer": issuer,
            "key_id": key_id,
            "sequence": sequence,
            "signature_algorithm": signature_algorithm,
            "snapshot": snapshot.to_json_dict(),
            "version": 1,
        }
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _append_policy_audit(
    audit_log: PrivacySafeAuditLog | None,
    *,
    event_type: str,
    outcome: str,
    actor_id: str,
    subject_id: str,
    metadata: dict[str, object],
    now: int,
) -> None:
    if audit_log is None:
        return
    audit_log.append(
        PrivacySafeAuditEvent(
            event_type=event_type,
            outcome=outcome,
            occurred_at=now,
            actor_hash=hash_identifier(actor_id, namespace="policy-actor"),
            subject_hash=hash_identifier(subject_id, namespace="policy-subject"),
            metadata=metadata,
        )
    )


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
