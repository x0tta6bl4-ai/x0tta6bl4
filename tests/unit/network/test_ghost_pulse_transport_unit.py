from src.network.transport import GhostPulseTransport


def _planned_samples(mode: str, seed: int, count: int) -> list[dict]:
    transport = GhostPulseTransport(b"k" * 32, mode=mode, pulse_seed=seed)
    for _ in range(count):
        transport.plan_next_delay()
    return transport.get_stats()["timing_plan_samples"]


def test_ghost_pulse_transport_encrypts_and_unwraps_payload():
    transport = GhostPulseTransport(b"k" * 32, mode="corporate", pulse_seed=123)

    packet = transport.wrap_packet(b"mesh-heartbeat")

    assert transport.unwrap_packet(packet) == b"mesh-heartbeat"
    stats = transport.get_stats()
    assert stats["packets_processed"] == 1
    assert stats["evidence_status"] == "EXPERIMENTAL_LOCAL_TIMING_PROFILE"
    assert stats["stealth_mode"] == "NOT_VERIFIED"
    assert stats["timing_plan_replay"]["claim_boundary"] == stats["claim_boundary"]


def test_ghost_pulse_transport_replay_digest_matches_seed_and_mode():
    first = GhostPulseTransport.timing_plan_replay_digest(
        _planned_samples(mode="corporate", seed=424242, count=6)
    )
    second = GhostPulseTransport.timing_plan_replay_digest(
        _planned_samples(mode="corporate", seed=424242, count=6)
    )
    different_seed = GhostPulseTransport.timing_plan_replay_digest(
        _planned_samples(mode="corporate", seed=424243, count=6)
    )
    different_mode = GhostPulseTransport.timing_plan_replay_digest(
        _planned_samples(mode="whitelist", seed=424242, count=6)
    )

    assert first == second
    assert first != different_seed
    assert first != different_mode
