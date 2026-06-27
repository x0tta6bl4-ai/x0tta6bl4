"""Policy-driven first-party rekey gates and rollback evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .ops import assert_privacy_safe, hash_identifier


DEFAULT_REKEY_REQUEST_REASONS = frozenset(
    {
        "scheduled-rotation",
        "manual-operator",
        "emergency-rotation",
    }
)
DEFAULT_MANUAL_REKEY_REQUEST_REASONS = frozenset(
    {
        "manual-operator",
        "emergency-rotation",
    }
)


@dataclass(frozen=True)
class FirstPartyRekeyCadencePolicy:
    """Thresholds and operator reasons that are allowed to trigger rekey."""

    max_session_age_seconds: int | None = None
    max_tx_frames: int | None = None
    max_rx_frames: int | None = None
    max_tx_bytes: int | None = None
    max_rx_bytes: int | None = None
    min_seconds_between_rekeys: int = 0
    allowed_request_reasons: frozenset[str] = DEFAULT_REKEY_REQUEST_REASONS
    manual_request_reasons: frozenset[str] = DEFAULT_MANUAL_REKEY_REQUEST_REASONS
    require_rollback_evidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_request_reasons",
            frozenset(self.allowed_request_reasons),
        )
        object.__setattr__(
            self,
            "manual_request_reasons",
            frozenset(self.manual_request_reasons),
        )
        for field_name in (
            "max_session_age_seconds",
            "max_tx_frames",
            "max_rx_frames",
            "max_tx_bytes",
            "max_rx_bytes",
        ):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.min_seconds_between_rekeys < 0:
            raise ValueError("min_seconds_between_rekeys cannot be negative")
        if not self.allowed_request_reasons:
            raise ValueError("allowed rekey request reasons are required")
        if self.manual_request_reasons - self.allowed_request_reasons:
            raise ValueError("manual rekey reasons must be allowed request reasons")
        for reason in self.allowed_request_reasons | self.manual_request_reasons:
            if not reason.strip():
                raise ValueError("rekey request reasons cannot be blank")
        assert_privacy_safe(self.to_json_dict())

    def to_json_dict(self) -> dict[str, object]:
        return {
            "allowed_request_reasons": sorted(self.allowed_request_reasons),
            "manual_request_reasons": sorted(self.manual_request_reasons),
            "max_rx_bytes": self.max_rx_bytes,
            "max_rx_frames": self.max_rx_frames,
            "max_session_age_seconds": self.max_session_age_seconds,
            "max_tx_bytes": self.max_tx_bytes,
            "max_tx_frames": self.max_tx_frames,
            "min_seconds_between_rekeys": self.min_seconds_between_rekeys,
            "require_rollback_evidence": self.require_rollback_evidence,
        }


@dataclass(frozen=True)
class FirstPartyRekeyTelemetry:
    """Payload-free session counters used by the rekey cadence gate."""

    session_started_at: int
    now: int
    generation: int
    last_rekey_at: int | None = None
    tx_frames: int = 0
    rx_frames: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0

    def __post_init__(self) -> None:
        if self.generation < 1:
            raise ValueError("rekey generation must be positive")
        for field_name in ("tx_frames", "rx_frames", "tx_bytes", "rx_bytes"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def session_age_seconds(self) -> int:
        return self.now - self.session_started_at

    @property
    def seconds_since_last_rekey(self) -> int | None:
        if self.last_rekey_at is None:
            return None
        return self.now - self.last_rekey_at

    def to_json_dict(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "last_rekey_at": self.last_rekey_at,
            "now": self.now,
            "rx_bytes": self.rx_bytes,
            "rx_frames": self.rx_frames,
            "seconds_since_last_rekey": self.seconds_since_last_rekey,
            "session_age_seconds": self.session_age_seconds,
            "session_started_at": self.session_started_at,
            "tx_bytes": self.tx_bytes,
            "tx_frames": self.tx_frames,
        }


@dataclass(frozen=True)
class FirstPartyRekeyRollbackEvidence:
    """Privacy-safe proof that the new session can be rolled back."""

    rollback_id_hash: str
    previous_session_hash: str
    next_session_hash: str
    rollback_plan_hash: str
    generated_at: int

    def __post_init__(self) -> None:
        _assert_sha256_hex(self.rollback_id_hash, "rollback_id_hash")
        _assert_sha256_hex(self.previous_session_hash, "previous_session_hash")
        _assert_sha256_hex(self.next_session_hash, "next_session_hash")
        _assert_sha256_hex(self.rollback_plan_hash, "rollback_plan_hash")
        assert_privacy_safe(self.to_json_dict())

    @classmethod
    def from_session_bindings(
        cls,
        *,
        rollback_id: str,
        previous_session_id: int,
        previous_transcript_hash: str,
        next_session_id: int,
        next_transcript_hash: str,
        rollback_plan_id: str,
        generated_at: int,
    ) -> "FirstPartyRekeyRollbackEvidence":
        if not rollback_id.strip():
            raise ValueError("rollback id is required")
        if not rollback_plan_id.strip():
            raise ValueError("rollback plan id is required")
        return cls(
            rollback_id_hash=hash_identifier(rollback_id, namespace="rekey-rollback-id"),
            previous_session_hash=hash_identifier(
                f"{previous_session_id}|{previous_transcript_hash}",
                namespace="rekey-previous-session",
            ),
            next_session_hash=hash_identifier(
                f"{next_session_id}|{next_transcript_hash}",
                namespace="rekey-next-session",
            ),
            rollback_plan_hash=hash_identifier(
                rollback_plan_id,
                namespace="rekey-rollback-plan",
            ),
            generated_at=generated_at,
        )

    def evidence_hash(self) -> str:
        return _privacy_safe_payload_hash(
            self.to_json_dict(),
            namespace="rekey-rollback-evidence",
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "next_session_hash": self.next_session_hash,
            "previous_session_hash": self.previous_session_hash,
            "rollback_id_hash": self.rollback_id_hash,
            "rollback_plan_hash": self.rollback_plan_hash,
        }


@dataclass(frozen=True)
class FirstPartyRekeyPolicyDecision:
    """Decision returned by the rekey cadence gate."""

    required: bool
    allowed: bool
    trigger_reasons: tuple[str, ...]
    block_reasons: tuple[str, ...]
    evidence_hash: str
    rollback_evidence_hash: str | None = None
    rollback_plan_hash: str | None = None

    def __post_init__(self) -> None:
        if self.rollback_evidence_hash is not None:
            _assert_sha256_hex(self.rollback_evidence_hash, "rollback_evidence_hash")
        if self.rollback_plan_hash is not None:
            _assert_sha256_hex(self.rollback_plan_hash, "rollback_plan_hash")

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "allowed": self.allowed,
            "block_reasons": list(self.block_reasons),
            "evidence_hash": self.evidence_hash,
            "required": self.required,
            "rollback_evidence_hash": self.rollback_evidence_hash,
            "rollback_plan_hash": self.rollback_plan_hash,
            "trigger_reasons": list(self.trigger_reasons),
        }
        assert_privacy_safe(payload)
        return payload


def evaluate_firstparty_rekey_policy(
    policy: FirstPartyRekeyCadencePolicy,
    telemetry: FirstPartyRekeyTelemetry,
    *,
    requested_reason: str,
    rollback_evidence: FirstPartyRekeyRollbackEvidence | None = None,
) -> FirstPartyRekeyPolicyDecision:
    """Evaluate whether a live session is allowed to rotate now."""
    trigger_reasons = _trigger_reasons(policy, telemetry)
    block_reasons: list[str] = []

    if telemetry.now < telemetry.session_started_at:
        block_reasons.append("rekey_clock_before_session_start")
    if telemetry.last_rekey_at is not None and telemetry.now < telemetry.last_rekey_at:
        block_reasons.append("rekey_clock_before_last_rekey")

    clean_reason = requested_reason.strip()
    if not clean_reason:
        block_reasons.append("rekey_reason_missing")
    elif clean_reason not in policy.allowed_request_reasons:
        block_reasons.append("rekey_reason_not_allowed")

    required = bool(trigger_reasons) or clean_reason in policy.manual_request_reasons
    if not required:
        block_reasons.append("rekey_not_required")

    if (
        required
        and telemetry.seconds_since_last_rekey is not None
        and telemetry.seconds_since_last_rekey < policy.min_seconds_between_rekeys
    ):
        block_reasons.append("rekey_min_interval_not_elapsed")

    if required and policy.require_rollback_evidence:
        if rollback_evidence is None:
            block_reasons.append("rekey_rollback_evidence_missing")
        else:
            if rollback_evidence.generated_at < telemetry.session_started_at:
                block_reasons.append("rekey_rollback_evidence_stale")
            if rollback_evidence.generated_at > telemetry.now:
                block_reasons.append("rekey_rollback_evidence_from_future")

    rollback_evidence_hash = (
        rollback_evidence.evidence_hash() if rollback_evidence is not None else None
    )
    rollback_plan_hash = (
        rollback_evidence.rollback_plan_hash if rollback_evidence is not None else None
    )
    evidence_payload = {
        "block_reasons": sorted(block_reasons),
        "policy": policy.to_json_dict(),
        "requested_reason_hash": (
            hash_identifier(clean_reason, namespace="rekey-request-reason")
            if clean_reason
            else None
        ),
        "required": required,
        "rollback_evidence_hash": rollback_evidence_hash,
        "rollback_plan_hash": rollback_plan_hash,
        "telemetry": telemetry.to_json_dict(),
        "trigger_reasons": trigger_reasons,
    }
    evidence_hash = _privacy_safe_payload_hash(
        evidence_payload,
        namespace="rekey-policy-evidence",
    )
    return FirstPartyRekeyPolicyDecision(
        required=required,
        allowed=required and not block_reasons,
        trigger_reasons=trigger_reasons,
        block_reasons=tuple(block_reasons),
        evidence_hash=evidence_hash,
        rollback_evidence_hash=rollback_evidence_hash,
        rollback_plan_hash=rollback_plan_hash,
    )


def _trigger_reasons(
    policy: FirstPartyRekeyCadencePolicy,
    telemetry: FirstPartyRekeyTelemetry,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        policy.max_session_age_seconds is not None
        and telemetry.session_age_seconds >= policy.max_session_age_seconds
    ):
        reasons.append("session_age_exceeded")
    if policy.max_tx_frames is not None and telemetry.tx_frames >= policy.max_tx_frames:
        reasons.append("tx_frames_exceeded")
    if policy.max_rx_frames is not None and telemetry.rx_frames >= policy.max_rx_frames:
        reasons.append("rx_frames_exceeded")
    if policy.max_tx_bytes is not None and telemetry.tx_bytes >= policy.max_tx_bytes:
        reasons.append("tx_bytes_exceeded")
    if policy.max_rx_bytes is not None and telemetry.rx_bytes >= policy.max_rx_bytes:
        reasons.append("rx_bytes_exceeded")
    return tuple(reasons)


def _privacy_safe_payload_hash(value: object, *, namespace: str) -> str:
    assert_privacy_safe(value)
    return hash_identifier(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        namespace=namespace,
    )


def _assert_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64 or not all(character in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
