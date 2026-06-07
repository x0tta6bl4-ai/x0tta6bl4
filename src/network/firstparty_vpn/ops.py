"""Operational rollout gates, rollback plans, and privacy-safe evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .linux_policy import LinuxPolicyCommand
from .runtime import RuntimeStats
from .tun import TunBridgeStats

SENSITIVE_MARKERS = (
    "private_key",
    "secret",
    "password",
    "token",
    "pqc_shared_secret",
    "vless:/" "/",
    "vmess:/" "/",
    "trojan:/" "/",
    "ss:/" "/",
)


class OperationalEvidenceError(ValueError):
    """Raised when operational evidence is unsafe or incomplete."""


class RolloutPreflightEvidence(Protocol):
    @property
    def passed(self) -> bool: ...

    def evidence_hash(self) -> str: ...


class RolloutDataplaneEvidence(Protocol):
    @property
    def passed(self) -> bool: ...

    @property
    def covered_path_labels(self) -> tuple[str, ...]: ...

    def evidence_hash(self) -> str: ...


@dataclass(frozen=True)
class OperatorApproval:
    """Time-bounded approval gate for a rollout or rollback."""

    approval_id: str
    approved_by_hash: str
    scope: str
    issued_at: int
    expires_at: int

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval id is required")
        if not self.approved_by_hash.strip():
            raise ValueError("approved_by hash is required")
        if not self.scope.strip():
            raise ValueError("approval scope is required")
        if self.expires_at <= self.issued_at:
            raise ValueError("approval validity window is invalid")

    def valid_for(self, scope: str, *, now: int | None = None) -> bool:
        now = now if now is not None else _utc_now()
        return self.scope == scope and self.issued_at <= now < self.expires_at

    def to_json_dict(self) -> dict[str, object]:
        return {
            "approval_id_hash": hash_identifier(
                self.approval_id,
                namespace="operator-approval-id",
            ),
            "approved_by_hash": self.approved_by_hash,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "scope_hash": hash_identifier(
                self.scope,
                namespace="operator-approval-scope",
            ),
        }


@dataclass(frozen=True)
class TestEvidence:
    """Focused test evidence required before rollout."""

    command: tuple[str, ...]
    passed: int
    failed: int
    collected: int
    generated_at: int

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("test evidence command is required")
        if self.passed < 0 or self.failed < 0 or self.collected < 0:
            raise ValueError("test evidence counts cannot be negative")
        if self.passed + self.failed > self.collected:
            raise ValueError("test evidence counts exceed collected tests")
        if self.generated_at < 0:
            raise ValueError("test evidence generation time cannot be negative")

    @property
    def successful(self) -> bool:
        return self.failed == 0 and self.passed == self.collected and self.collected > 0

    def to_json_dict(self) -> dict[str, object]:
        return {
            "collected": self.collected,
            "command_hash": hash_identifier(" ".join(self.command), namespace="test-command"),
            "failed": self.failed,
            "generated_at": self.generated_at,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class CommandPlanEvidence:
    """Privacy-safe representation of apply and rollback command plans."""

    command_hashes: tuple[str, ...]
    command_count: int
    redacted_commands: tuple[tuple[str, ...], ...]

    @classmethod
    def from_commands(cls, commands: Sequence[LinuxPolicyCommand]) -> "CommandPlanEvidence":
        redacted = tuple(redact_command(command) for command in commands)
        return cls(
            command_hashes=tuple(
                hash_identifier(" ".join(command), namespace="command") for command in commands
            ),
            command_count=len(commands),
            redacted_commands=redacted,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "command_count": self.command_count,
            "command_hashes": list(self.command_hashes),
            "redacted_commands": [list(command) for command in self.redacted_commands],
        }

    def evidence_hash(self) -> str:
        return hash_identifier(
            json.dumps(
                self.to_json_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ),
            namespace="command-plan-evidence",
        )


@dataclass(frozen=True)
class RolloutPlan:
    """Rollout plan that can be audited before any OS mutation."""

    target: str
    apply_commands: tuple[LinuxPolicyCommand, ...]
    rollback_commands: tuple[LinuxPolicyCommand, ...]
    test_evidence: TestEvidence
    approval: OperatorApproval | None = None
    policy_snapshot_hash: str | None = None
    preflight_evidence: RolloutPreflightEvidence | None = None
    dataplane_evidence: RolloutDataplaneEvidence | None = None
    tun_dataplane_evidence: RolloutDataplaneEvidence | None = None
    mtu_validation_evidence: RolloutDataplaneEvidence | None = None

    def apply_evidence(self) -> CommandPlanEvidence:
        return CommandPlanEvidence.from_commands(self.apply_commands)

    def rollback_evidence(self) -> CommandPlanEvidence:
        return CommandPlanEvidence.from_commands(self.rollback_commands)


@dataclass(frozen=True)
class RolloutGateDecision:
    allowed: bool
    reasons: tuple[str, ...]
    evidence_hash: str

    def decision_hash(self) -> str:
        return hash_identifier(
            json.dumps(
                {
                    "allowed": self.allowed,
                    "evidence_hash": self.evidence_hash,
                    "reasons": list(self.reasons),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            namespace="rollout-gate-decision",
        )


def evaluate_rollout_gate(
    plan: RolloutPlan,
    *,
    expected_test_count: int,
    required_dataplane_paths: frozenset[str] = frozenset(),
    max_test_evidence_age_seconds: int = 3600,
    now: int | None = None,
) -> RolloutGateDecision:
    now = now if now is not None else _utc_now()
    reasons: list[str] = []
    if max_test_evidence_age_seconds < 1:
        raise OperationalEvidenceError("rollout test evidence age must be positive")
    if not plan.target.strip():
        reasons.append("rollout_target_missing")
    if not plan.apply_commands:
        reasons.append("apply_plan_missing")
    if not plan.rollback_commands:
        reasons.append("rollback_plan_missing")
    if not plan.test_evidence.successful:
        reasons.append("tests_not_successful")
    if plan.test_evidence.passed < expected_test_count:
        reasons.append("test_count_below_expected")
    if plan.test_evidence.generated_at > now:
        reasons.append("test_evidence_from_future")
    elif now - plan.test_evidence.generated_at > max_test_evidence_age_seconds:
        reasons.append("test_evidence_stale")
    if plan.approval is None:
        reasons.append("operator_approval_missing")
    elif not plan.approval.valid_for(plan.target, now=now):
        reasons.append("operator_approval_invalid")
    if not plan.policy_snapshot_hash:
        reasons.append("policy_snapshot_hash_missing")
    if plan.preflight_evidence is None:
        reasons.append("linux_preflight_missing")
    elif not plan.preflight_evidence.passed:
        reasons.append("linux_preflight_failed")
    if required_dataplane_paths:
        _evaluate_rollout_path_evidence(
            "dataplane",
            plan.dataplane_evidence,
            required_dataplane_paths,
            reasons,
        )
        _evaluate_rollout_path_evidence(
            "tun_dataplane",
            plan.tun_dataplane_evidence,
            required_dataplane_paths,
            reasons,
        )
        _evaluate_rollout_path_evidence(
            "mtu",
            plan.mtu_validation_evidence,
            required_dataplane_paths,
            reasons,
        )
    if _commands_contain_sensitive_material(plan.apply_commands + plan.rollback_commands):
        reasons.append("command_plan_contains_sensitive_material")

    evidence_hash = hash_identifier(
        json.dumps(
            _rollout_evidence_payload(
                plan,
                evaluated_at=now,
                expected_test_count=expected_test_count,
                max_test_evidence_age_seconds=max_test_evidence_age_seconds,
                required_dataplane_paths=required_dataplane_paths,
            ),
            sort_keys=True,
            separators=(",", ":"),
        ),
        namespace="rollout-evidence",
    )
    return RolloutGateDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        evidence_hash=evidence_hash,
    )


@dataclass(frozen=True)
class PrivacySafeAuditEvent:
    """Append-only audit event with hashed identities and redacted metadata."""

    event_type: str
    outcome: str
    occurred_at: int
    actor_hash: str
    subject_hash: str
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("audit event type is required")
        if not self.outcome.strip():
            raise ValueError("audit outcome is required")
        if not self.actor_hash.strip() or not self.subject_hash.strip():
            raise ValueError("audit actor and subject hashes are required")
        assert_privacy_safe(self.metadata)

    def canonical_json(self) -> bytes:
        return json.dumps(
            {
                "actor_hash": self.actor_hash,
                "event_type": self.event_type,
                "metadata": self.metadata,
                "occurred_at": self.occurred_at,
                "outcome": self.outcome,
                "subject_hash": self.subject_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def event_hash(self) -> str:
        return hashlib.sha256(b"x0vpn-audit-event-v1" + self.canonical_json()).hexdigest()


class PrivacySafeAuditLog:
    """JSONL audit log that rejects obvious secret-bearing metadata."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, event: PrivacySafeAuditEvent) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event_hash = event.event_hash()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.canonical_json().decode("utf-8") + "\n")
        return event_hash

    def read_events(self) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        events: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise OperationalEvidenceError("audit event root must be a map")
            assert_privacy_safe(raw)
            events.append(raw)
        return tuple(events)


@dataclass(frozen=True)
class MetricsSnapshot:
    """Payload-free dataplane and TUN bridge counters."""

    runtime: RuntimeStats
    tun: TunBridgeStats | None
    captured_at: int

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "captured_at": self.captured_at,
            "runtime": {
                "auth_drops": self.runtime.auth_drops,
                "decode_drops": self.runtime.decode_drops,
                "replay_drops": self.runtime.replay_drops,
                "rx_bytes": self.runtime.rx_bytes,
                "rx_data_frames": self.runtime.rx_data_frames,
                "rx_frames": self.runtime.rx_frames,
                "session_drops": self.runtime.session_drops,
                "tx_bytes": self.runtime.tx_bytes,
                "tx_data_frames": self.runtime.tx_data_frames,
                "tx_frames": self.runtime.tx_frames,
            },
        }
        if self.tun is not None:
            payload["tun"] = {
                "bytes_from_tun": self.tun.bytes_from_tun,
                "bytes_to_tun": self.tun.bytes_to_tun,
                "fragment_drops": self.tun.fragment_drops,
                "mtu_drops": self.tun.mtu_drops,
                "mtu_probe_updates": self.tun.mtu_probe_updates,
                "non_data_drops": self.tun.non_data_drops,
                "packets_from_tun": self.tun.packets_from_tun,
                "packets_to_tun": self.tun.packets_to_tun,
                "rx_fragments": self.tun.rx_fragments,
                "tx_fragments": self.tun.tx_fragments,
            }
        return payload


def hash_identifier(value: str, *, namespace: str = "x0vpn") -> str:
    if not value:
        raise ValueError("identifier value is required")
    return hashlib.sha256(f"{namespace}|{value}".encode("utf-8")).hexdigest()


def redact_command(command: LinuxPolicyCommand) -> tuple[str, ...]:
    return tuple(_redact_token(token) for token in command)


def assert_privacy_safe(value: object) -> None:
    encoded = json.dumps(value, sort_keys=True, default=str).lower()
    if any(marker in encoded for marker in SENSITIVE_MARKERS):
        raise OperationalEvidenceError("privacy-safe evidence contains sensitive marker")


def _redact_token(token: str) -> str:
    try:
        ipaddress.ip_address(token)
        return "<ip-redacted>"
    except ValueError:
        pass
    try:
        ipaddress.ip_network(token, strict=False)
        return "<network-redacted>"
    except ValueError:
        pass
    if any(marker in token.lower() for marker in SENSITIVE_MARKERS):
        return "<sensitive-redacted>"
    return token


def _commands_contain_sensitive_material(commands: Sequence[LinuxPolicyCommand]) -> bool:
    encoded = json.dumps(commands, sort_keys=True).lower()
    return any(marker in encoded for marker in SENSITIVE_MARKERS)


def _rollout_evidence_payload(
    plan: RolloutPlan,
    *,
    evaluated_at: int,
    expected_test_count: int,
    max_test_evidence_age_seconds: int,
    required_dataplane_paths: frozenset[str],
) -> dict[str, object]:
    return {
        "apply": plan.apply_evidence().to_json_dict(),
        "approval": (
            plan.approval.to_json_dict()
            if plan.approval is not None
            else None
        ),
        "evaluated_at": evaluated_at,
        "expected_test_count": expected_test_count,
        "max_test_evidence_age_seconds": max_test_evidence_age_seconds,
        "policy_snapshot_hash": plan.policy_snapshot_hash,
        "preflight_hash": (
            plan.preflight_evidence.evidence_hash()
            if plan.preflight_evidence is not None
            else None
        ),
        "dataplane_hash": (
            plan.dataplane_evidence.evidence_hash()
            if plan.dataplane_evidence is not None
            else None
        ),
        "tun_dataplane_hash": (
            plan.tun_dataplane_evidence.evidence_hash()
            if plan.tun_dataplane_evidence is not None
            else None
        ),
        "mtu_validation_hash": (
            plan.mtu_validation_evidence.evidence_hash()
            if plan.mtu_validation_evidence is not None
            else None
        ),
        "required_dataplane_paths": sorted(required_dataplane_paths),
        "rollback": plan.rollback_evidence().to_json_dict(),
        "target_hash": hash_identifier(plan.target, namespace="rollout-target"),
        "test": plan.test_evidence.to_json_dict(),
    }


def _evaluate_rollout_path_evidence(
    prefix: str,
    evidence: RolloutDataplaneEvidence | None,
    required_paths: frozenset[str],
    reasons: list[str],
) -> None:
    if evidence is None:
        reasons.append(f"{prefix}_evidence_missing")
        return
    if not evidence.passed:
        reasons.append(f"{prefix}_validation_failed")
    missing_paths = required_paths - set(evidence.covered_path_labels)
    if missing_paths:
        reasons.append(f"{prefix}_required_paths_missing")


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
