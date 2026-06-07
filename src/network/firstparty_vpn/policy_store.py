"""Durable zero-trust policy snapshots for first-party VPN control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
from .zero_trust import IdentityClaims, ZeroTrustDecision, ZeroTrustPolicy, identity_binding_hash


class PolicyStoreError(ValueError):
    """Raised when a durable policy snapshot cannot be loaded or applied."""


@dataclass(frozen=True)
class DevicePosturePolicy:
    """Fail-closed device posture checks embedded in identity attributes."""

    required_attributes: dict[str, str] = field(
        default_factory=lambda: {"posture_status": "healthy"}
    )
    posture_checked_at_attribute: str = "posture_checked_at"
    max_posture_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_posture_age_seconds < 1:
            raise ValueError("device posture max age must be positive")
        if not self.posture_checked_at_attribute.strip():
            raise ValueError("device posture timestamp attribute is required")
        for key, value in self.required_attributes.items():
            if not key.strip() or not value.strip():
                raise ValueError("device posture required attributes must be non-empty")

    def evaluate(self, claims: IdentityClaims, *, now: int | None = None) -> tuple[str, ...]:
        now = now if now is not None else _utc_now()
        reasons: list[str] = []
        for key, expected in self.required_attributes.items():
            actual = claims.attributes.get(key)
            if actual is None:
                reasons.append(f"device_posture_missing:{key}")
            elif actual != expected:
                reasons.append(f"device_posture_mismatch:{key}")
        checked_at_raw = claims.attributes.get(self.posture_checked_at_attribute)
        if checked_at_raw is None:
            reasons.append("device_posture_timestamp_missing")
        else:
            try:
                checked_at = int(checked_at_raw)
            except ValueError:
                reasons.append("device_posture_timestamp_invalid")
            else:
                if checked_at > now:
                    reasons.append("device_posture_timestamp_future")
                elif now - checked_at > self.max_posture_age_seconds:
                    reasons.append("device_posture_stale")
        return tuple(reasons)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "max_posture_age_seconds": self.max_posture_age_seconds,
            "posture_checked_at_attribute": self.posture_checked_at_attribute,
            "required_attributes": dict(sorted(self.required_attributes.items())),
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "DevicePosturePolicy":
        required_raw = value.get("required_attributes", {})
        if not isinstance(required_raw, dict):
            raise PolicyStoreError("device posture required attributes must be a map")
        return cls(
            required_attributes={str(key): str(item) for key, item in required_raw.items()},
            posture_checked_at_attribute=str(
                value.get("posture_checked_at_attribute", "posture_checked_at")
            ),
            max_posture_age_seconds=int(value.get("max_posture_age_seconds", 3600)),
        )


@dataclass(frozen=True)
class PolicySnapshot:
    """Serializable zero-trust policy refresh snapshot."""

    policy_epoch: str
    issued_at: int
    revocations: RevocationList = field(default_factory=RevocationList)
    posture_policy: DevicePosturePolicy = field(default_factory=DevicePosturePolicy)

    def __post_init__(self) -> None:
        if not self.policy_epoch.strip():
            raise ValueError("policy snapshot epoch is required")
        if self.issued_at < 0:
            raise ValueError("policy snapshot issued_at is invalid")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "issued_at": self.issued_at,
            "policy_epoch": self.policy_epoch,
            "posture_policy": self.posture_policy.to_json_dict(),
            "revocations": {
                "identity_serials": sorted(self.revocations.identity_serials),
                "key_ids": sorted(self.revocations.key_ids),
                "policy_epochs": sorted(self.revocations.policy_epochs),
            },
            "snapshot_hash": self.snapshot_hash(),
            "version": 1,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "PolicySnapshot":
        if int(value.get("version", 0)) != 1:
            raise PolicyStoreError("unsupported policy snapshot version")
        revocations_raw = value.get("revocations", {})
        if not isinstance(revocations_raw, dict):
            raise PolicyStoreError("policy snapshot revocations must be a map")
        posture_raw = value.get("posture_policy", {})
        if not isinstance(posture_raw, dict):
            raise PolicyStoreError("policy snapshot posture policy must be a map")
        return cls(
            policy_epoch=str(value.get("policy_epoch", "")),
            issued_at=int(value.get("issued_at", 0)),
            revocations=RevocationList(
                identity_serials=set(_string_list(revocations_raw, "identity_serials")),
                key_ids=set(_string_list(revocations_raw, "key_ids")),
                policy_epochs=set(_string_list(revocations_raw, "policy_epochs")),
            ),
            posture_policy=DevicePosturePolicy.from_json_dict(posture_raw),
        )

    def evaluate_signed_identity(
        self,
        authority: IdentityVerifier,
        token: SignedIdentityToken,
        *,
        policy: ZeroTrustPolicy,
        now: int | None = None,
    ) -> ZeroTrustDecision:
        now = now if now is not None else _utc_now()
        authority_decision = authority.verify(
            token,
            policy=policy,
            revocations=self.revocations,
            now=now,
        )
        reasons = list(authority_decision.reasons)
        reasons.extend(self.posture_policy.evaluate(token.claims, now=now))
        return ZeroTrustDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
            identity_hash=identity_binding_hash(token.claims),
        )

    def snapshot_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "issued_at": self.issued_at,
            "policy_epoch": self.policy_epoch,
            "posture_policy": self.posture_policy.to_json_dict(),
            "revocations": {
                "identity_serials": sorted(self.revocations.identity_serials),
                "key_ids": sorted(self.revocations.key_ids),
                "policy_epochs": sorted(self.revocations.policy_epochs),
            },
            "version": 1,
        }


class DurablePolicyStore:
    """Atomic JSON store for the latest zero-trust policy snapshot."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def save(self, snapshot: PolicySnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_bytes(_canonical_json(snapshot.to_json_dict()) + b"\n")
        tmp.replace(self.path)

    def load(self) -> PolicySnapshot:
        if not self.path.exists():
            raise PolicyStoreError("policy snapshot is missing")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise PolicyStoreError("policy snapshot root must be a map")
        expected_hash = raw.get("snapshot_hash")
        snapshot = PolicySnapshot.from_json_dict(raw)
        if expected_hash != snapshot.snapshot_hash():
            raise PolicyStoreError("policy snapshot hash mismatch")
        return snapshot


class PolicyRefreshClient:
    """Apply fetched policy snapshots into the durable store."""

    def __init__(self, *, store: DurablePolicyStore) -> None:
        self.store = store
        self.current: PolicySnapshot | None = None

    def refresh_once(self, fetch: Callable[[], PolicySnapshot]) -> PolicySnapshot:
        snapshot = fetch()
        if self.current is not None and snapshot.issued_at < self.current.issued_at:
            raise PolicyStoreError("policy refresh attempted to roll back snapshot time")
        self.store.save(snapshot)
        self.current = snapshot
        return snapshot

    def load_current(self) -> PolicySnapshot:
        self.current = self.store.load()
        return self.current


def _string_list(value: dict[str, object], key: str) -> tuple[str, ...]:
    raw = value.get(key, [])
    if not isinstance(raw, list):
        raise PolicyStoreError(f"policy snapshot {key} must be a list")
    return tuple(str(item) for item in raw)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
