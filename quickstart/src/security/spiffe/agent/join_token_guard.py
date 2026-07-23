"""Local single-use guard for SPIRE join-token attestation."""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import asdict, dataclass
from typing import Any, Mapping


JOIN_TOKEN_GUARD_CLAIM_GATE_SCHEMA = (
    "x0tta6bl4.spire.join_token_replay_guard.v1"
)
JOIN_TOKEN_GUARD_CLAIM_BOUNDARY = (
    "Local SPIRE join-token replay/race guard evidence only. It records "
    "hash-only local token reservation state and fail-closed decisions; it "
    "does not prove live SPIRE mTLS, SVID issuance, node hardware identity, "
    "or production trust finality."
)

_JOIN_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{8,512}$")


@dataclass(frozen=True)
class JoinTokenDecision:
    accepted: bool
    reason: str
    token_sha256: str | None
    already_seen: bool
    inflight: bool
    claim_gate: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_safe_context(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "token_sha256": self.token_sha256,
            "already_seen": self.already_seen,
            "inflight": self.inflight,
            "raw_join_token_redacted": True,
            "claim_gate": dict(self.claim_gate),
        }


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", errors="replace")).hexdigest()


def _valid_join_token(token: Any) -> bool:
    return isinstance(token, str) and bool(_JOIN_TOKEN_RE.fullmatch(token))


def _claim_gate(
    *,
    accepted: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": JOIN_TOKEN_GUARD_CLAIM_GATE_SCHEMA,
        "claim_boundary": JOIN_TOKEN_GUARD_CLAIM_BOUNDARY,
        "local_join_token_single_use_claim_allowed": accepted,
        "local_join_token_replay_rejected_claim_allowed": not accepted,
        "live_spiffe_svid_claim_allowed": False,
        "production_spire_mtls_claim_allowed": False,
        "node_hardware_identity_claim_allowed": False,
        "production_trust_finality_claim_allowed": False,
        "fail_closed": True,
        "blockers": [] if accepted else [reason],
    }


class JoinTokenReplayGuard:
    """Thread-safe hash-only reservation guard for join-token attestation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen_hashes: set[str] = set()
        self._inflight_hashes: set[str] = set()

    def reserve(self, token: str) -> JoinTokenDecision:
        if not _valid_join_token(token):
            return JoinTokenDecision(
                accepted=False,
                reason="invalid_join_token",
                token_sha256=None,
                already_seen=False,
                inflight=False,
                claim_gate=_claim_gate(
                    accepted=False,
                    reason="invalid_join_token",
                ),
            )

        token_sha256 = _token_hash(token)
        with self._lock:
            already_seen = token_sha256 in self._seen_hashes
            inflight = token_sha256 in self._inflight_hashes
            if inflight:
                return JoinTokenDecision(
                    accepted=False,
                    reason="join_token_attestation_inflight",
                    token_sha256=token_sha256,
                    already_seen=already_seen,
                    inflight=True,
                    claim_gate=_claim_gate(
                        accepted=False,
                        reason="join_token_attestation_inflight",
                    ),
                )
            if already_seen:
                return JoinTokenDecision(
                    accepted=False,
                    reason="join_token_replay_detected",
                    token_sha256=token_sha256,
                    already_seen=True,
                    inflight=False,
                    claim_gate=_claim_gate(
                        accepted=False,
                        reason="join_token_replay_detected",
                    ),
                )

            self._seen_hashes.add(token_sha256)
            self._inflight_hashes.add(token_sha256)

        return JoinTokenDecision(
            accepted=True,
            reason="join_token_reserved",
            token_sha256=token_sha256,
            already_seen=False,
            inflight=False,
            claim_gate=_claim_gate(
                accepted=True,
                reason="join_token_reserved",
            ),
        )

    def complete(self, token: str, *, success: bool) -> JoinTokenDecision:
        if not _valid_join_token(token):
            return JoinTokenDecision(
                accepted=False,
                reason="invalid_join_token",
                token_sha256=None,
                already_seen=False,
                inflight=False,
                claim_gate=_claim_gate(
                    accepted=False,
                    reason="invalid_join_token",
                ),
            )

        token_sha256 = _token_hash(token)
        with self._lock:
            self._seen_hashes.add(token_sha256)
            self._inflight_hashes.discard(token_sha256)

        return JoinTokenDecision(
            accepted=success,
            reason="join_token_completed" if success else "join_token_failed_closed",
            token_sha256=token_sha256,
            already_seen=True,
            inflight=False,
            claim_gate=_claim_gate(
                accepted=success,
                reason="join_token_completed" if success else "join_token_failed_closed",
            ),
        )
