"""Durable identity backend state for the first-party VPN control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from .identity import (
    IdentityAuthority,
    IdentityAuthorityError,
    IdentityIssueRequest,
    IdentitySignatureProvider,
    IdentitySigningKey,
    RevocationList,
    SignedIdentityToken,
)
from .zero_trust import ZeroTrustDecision, ZeroTrustPolicy


class IdentityBackendError(ValueError):
    """Raised when durable identity backend state cannot be trusted."""


@dataclass(frozen=True)
class IdentityBackendState:
    """Serializable identity authority state without private signing material."""

    issuer: str
    active_key_id: str
    policy_epoch: str
    serial_counter: int
    revocations: RevocationList = field(default_factory=RevocationList)
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise IdentityBackendError("unsupported identity backend state version")
        if not self.issuer.strip():
            raise IdentityBackendError("identity backend issuer is required")
        if not self.active_key_id.strip():
            raise IdentityBackendError("identity backend active key id is required")
        if not self.policy_epoch.strip():
            raise IdentityBackendError("identity backend policy epoch is required")
        if self.serial_counter < 0:
            raise IdentityBackendError("identity backend serial counter is invalid")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "active_key_id": self.active_key_id,
            "issuer": self.issuer,
            "policy_epoch": self.policy_epoch,
            "revocations": {
                "identity_serials": sorted(self.revocations.identity_serials),
                "key_ids": sorted(self.revocations.key_ids),
                "policy_epochs": sorted(self.revocations.policy_epochs),
            },
            "serial_counter": self.serial_counter,
            "state_hash": self.state_hash(),
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "IdentityBackendState":
        revocations_raw = value.get("revocations", {})
        if not isinstance(revocations_raw, dict):
            raise IdentityBackendError("identity backend revocations must be a map")
        state = cls(
            version=int(value.get("version", 0)),
            issuer=str(value.get("issuer", "")),
            active_key_id=str(value.get("active_key_id", "")),
            policy_epoch=str(value.get("policy_epoch", "")),
            serial_counter=int(value.get("serial_counter", -1)),
            revocations=RevocationList(
                identity_serials=set(_string_list(revocations_raw, "identity_serials")),
                key_ids=set(_string_list(revocations_raw, "key_ids")),
                policy_epochs=set(_string_list(revocations_raw, "policy_epochs")),
            ),
        )
        if value.get("state_hash") != state.state_hash():
            raise IdentityBackendError("identity backend state hash mismatch")
        return state

    def state_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "active_key_id": self.active_key_id,
            "issuer": self.issuer,
            "policy_epoch": self.policy_epoch,
            "revocations": {
                "identity_serials": sorted(self.revocations.identity_serials),
                "key_ids": sorted(self.revocations.key_ids),
                "policy_epochs": sorted(self.revocations.policy_epochs),
            },
            "serial_counter": self.serial_counter,
            "version": self.version,
        }


class DurableIdentityBackendStore:
    """Atomic JSON store for identity authority state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def save(self, state: IdentityBackendState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_bytes(_canonical_json(state.to_json_dict()) + b"\n")
        tmp.replace(self.path)

    def load(self) -> IdentityBackendState | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IdentityBackendError("identity backend state JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise IdentityBackendError("identity backend state root must be a map")
        return IdentityBackendState.from_json_dict(raw)


class DurableIdentityBackend:
    """Durable wrapper for first-party identity issuance and revocations."""

    def __init__(
        self,
        *,
        store: DurableIdentityBackendStore,
        issuer: str,
        signing_keys: tuple[IdentitySigningKey, ...],
        active_key_id: str,
        policy_epoch: str = "epoch-1",
        signature_provider: IdentitySignatureProvider | None = None,
        default_lifetime_seconds: int = 600,
        max_lifetime_seconds: int = 3600,
    ) -> None:
        self.store = store
        self._keys = {key.key_id: key for key in signing_keys}
        if active_key_id not in self._keys:
            raise IdentityBackendError("identity backend active key is not registered")
        loaded = store.load()
        if loaded is None:
            self.state = IdentityBackendState(
                issuer=issuer,
                active_key_id=active_key_id,
                policy_epoch=policy_epoch,
                serial_counter=0,
            )
            store.save(self.state)
        else:
            self.state = self._validate_loaded_state(loaded, issuer)
        self.authority = IdentityAuthority(
            issuer=self.state.issuer,
            policy_epoch=self.state.policy_epoch,
            signing_keys=signing_keys,
            active_key_id=self.state.active_key_id,
            signature_provider=signature_provider,
            default_lifetime_seconds=default_lifetime_seconds,
            max_lifetime_seconds=max_lifetime_seconds,
        )
        self.authority.restore_serial_counter(self.state.serial_counter)
        self.revocations = self.state.revocations

    def issue(
        self,
        request: IdentityIssueRequest,
        *,
        now: int | None = None,
        lifetime_seconds: int | None = None,
    ) -> SignedIdentityToken:
        token = self.authority.issue(
            request,
            now=now,
            lifetime_seconds=lifetime_seconds,
        )
        self._persist()
        return token

    def verify(
        self,
        token: SignedIdentityToken,
        *,
        policy: ZeroTrustPolicy,
        now: int | None = None,
    ) -> ZeroTrustDecision:
        return self.authority.verify(
            token,
            policy=policy,
            revocations=self.revocations,
            now=now,
        )

    def revoke_identity(self, token: SignedIdentityToken) -> None:
        self.revocations.revoke_identity(token)
        self._persist()

    def rotate_signing_key(
        self,
        key: IdentitySigningKey,
        *,
        revoke_previous: bool = False,
    ) -> str:
        self._keys[key.key_id] = key
        previous = self.authority.rotate_signing_key(
            key,
            revoke_previous=revoke_previous,
            revocations=self.revocations,
        )
        self._persist()
        return previous

    def rotate_policy_epoch(
        self,
        policy_epoch: str,
        *,
        revoke_previous: bool = False,
    ) -> str:
        previous = self.authority.rotate_policy_epoch(
            policy_epoch,
            revoke_previous=revoke_previous,
            revocations=self.revocations,
        )
        self._persist()
        return previous

    def _persist(self) -> None:
        self.state = IdentityBackendState(
            issuer=self.authority.issuer,
            active_key_id=self.authority.active_key_id,
            policy_epoch=self.authority.policy_epoch,
            serial_counter=self.authority.serial_counter,
            revocations=self.revocations,
        )
        self.store.save(self.state)

    def _validate_loaded_state(
        self,
        state: IdentityBackendState,
        expected_issuer: str,
    ) -> IdentityBackendState:
        if state.issuer != expected_issuer:
            raise IdentityBackendError("identity backend issuer mismatch")
        if state.active_key_id not in self._keys:
            raise IdentityBackendError("identity backend active key is unavailable")
        return state


def _string_list(value: dict[str, object], key: str) -> tuple[str, ...]:
    raw = value.get(key, [])
    if not isinstance(raw, list):
        raise IdentityBackendError(f"identity backend {key} must be a list")
    return tuple(str(item) for item in raw)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
