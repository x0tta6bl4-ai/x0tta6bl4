from __future__ import annotations

from src.security.spiffe.agent.join_token_guard import JoinTokenReplayGuard


def test_join_token_guard_rejects_invalid_tokens_fail_closed() -> None:
    guard = JoinTokenReplayGuard()

    decision = guard.reserve("bad token with spaces")

    assert decision.accepted is False
    assert decision.reason == "invalid_join_token"
    assert decision.token_sha256 is None
    assert decision.claim_gate["fail_closed"] is True
    assert decision.claim_gate["production_spire_mtls_claim_allowed"] is False


def test_join_token_guard_blocks_inflight_parallel_reservation() -> None:
    guard = JoinTokenReplayGuard()

    first = guard.reserve("join-token-123456")
    second = guard.reserve("join-token-123456")

    assert first.accepted is True
    assert first.reason == "join_token_reserved"
    assert second.accepted is False
    assert second.reason == "join_token_attestation_inflight"
    assert second.inflight is True


def test_join_token_guard_blocks_replay_after_completion() -> None:
    guard = JoinTokenReplayGuard()

    reserved = guard.reserve("join-token-abcdef")
    completed = guard.complete("join-token-abcdef", success=True)
    replay = guard.reserve("join-token-abcdef")

    assert reserved.accepted is True
    assert completed.reason == "join_token_completed"
    assert replay.accepted is False
    assert replay.reason == "join_token_replay_detected"
    assert replay.already_seen is True


def test_join_token_guard_safe_context_is_hash_only() -> None:
    guard = JoinTokenReplayGuard()
    token = "join-token-private-value"

    decision = guard.reserve(token)
    safe_context = decision.to_safe_context()

    assert safe_context["token_sha256"]
    assert safe_context["raw_join_token_redacted"] is True
    assert token not in str(safe_context)
    assert safe_context["claim_gate"]["live_spiffe_svid_claim_allowed"] is False
