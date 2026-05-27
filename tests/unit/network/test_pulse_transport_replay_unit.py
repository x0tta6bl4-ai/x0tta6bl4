import os

from src.network.transport.pulse_transport import PulseUDPTransport


def _planned_samples(mode: str, seed: int, count: int) -> list[dict]:
    previous_mode = os.environ.get("PULSE_MODE")
    os.environ["PULSE_MODE"] = mode
    try:
        transport = PulseUDPTransport(
            local_host="127.0.0.1",
            local_port=0,
            traffic_profile="GHOST_PULSE",
            obfuscation="none",
            pulse_seed=seed,
        )
        samples = []
        for index in range(1, count + 1):
            plan = transport.plan_next_delay()
            samples.append(
                {
                    "index": index,
                    "mode": transport.mode,
                    "profile_label": plan["profile_label"],
                    "next_profile_label": plan["next_profile_label"],
                    "mode_shift_roll": plan["mode_shift_roll"],
                    "mode_shifted": plan["mode_shifted"],
                    "planned_delay_ms": plan["planned_delay"] * 1000.0,
                }
            )
        return samples
    finally:
        if previous_mode is None:
            os.environ.pop("PULSE_MODE", None)
        else:
            os.environ["PULSE_MODE"] = previous_mode


def test_replay_digest_is_stable_for_same_seed_and_mode():
    for mode in ("corporate", "whitelist"):
        first = PulseUDPTransport.timing_plan_replay_digest(
            _planned_samples(mode=mode, seed=424242, count=8)
        )
        second = PulseUDPTransport.timing_plan_replay_digest(
            _planned_samples(mode=mode, seed=424242, count=8)
        )
        different_seed = PulseUDPTransport.timing_plan_replay_digest(
            _planned_samples(mode=mode, seed=424243, count=8)
        )

        assert first == second
        assert first != different_seed


def test_replay_digest_is_sensitive_to_mode():
    corporate = PulseUDPTransport.timing_plan_replay_digest(
        _planned_samples(mode="corporate", seed=515151, count=8)
    )
    whitelist = PulseUDPTransport.timing_plan_replay_digest(
        _planned_samples(mode="whitelist", seed=515151, count=8)
    )

    assert corporate != whitelist


def test_replay_digest_ignores_runtime_only_timing_fields():
    samples = _planned_samples(mode="corporate", seed=616161, count=4)
    enriched = [
        {
            **sample,
            "actual_gap_ms": 999.0,
            "payload_size_bytes": 1400,
            "relative_error": 1.0,
            "wait_time_ms": 888.0,
        }
        for sample in samples
    ]

    assert PulseUDPTransport.timing_plan_replay_digest(samples) == (
        PulseUDPTransport.timing_plan_replay_digest(enriched)
    )
