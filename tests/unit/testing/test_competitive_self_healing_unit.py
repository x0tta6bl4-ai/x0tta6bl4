import random

from src.testing.competitive_self_healing import (
    default_profiles,
    default_scenarios,
    run_competitive_benchmark,
    simulate_failover_ms,
    simulate_packet_loss_pct,
)


def test_simulate_failover_is_positive_and_stable():
    profiles = default_profiles()
    scenarios = default_scenarios()
    rng_a = random.Random(12345)
    rng_b = random.Random(12345)

    v1 = simulate_failover_ms(profiles["x0tta6bl4-current"], scenarios[0], rng_a)
    v2 = simulate_failover_ms(profiles["x0tta6bl4-current"], scenarios[0], rng_b)

    assert v1 > 0.0
    assert v1 == v2


def test_simulate_packet_loss_is_non_negative():
    profiles = default_profiles()
    scenario = default_scenarios()[1]
    rng = random.Random(777)
    failover_ms = simulate_failover_ms(profiles["rajant-like"], scenario, rng)
    loss_pct = simulate_packet_loss_pct(profiles["rajant-like"], scenario, failover_ms, rng)

    assert failover_ms > 0.0
    assert loss_pct >= 0.0


def test_make_make_profile_beats_current_profile_on_p95_failover():
    profiles = default_profiles()
    scenarios = default_scenarios()

    report = run_competitive_benchmark(
        profiles=[
            profiles["x0tta6bl4-current"],
            profiles["x0tta6bl4-make-make-target"],
        ],
        scenarios=scenarios,
        iterations=120,
        seed=99,
    )

    by_name = {item.profile: item for item in report.profiles}
    assert by_name["x0tta6bl4-make-make-target"].overall_p95_failover_ms < by_name[
        "x0tta6bl4-current"
    ].overall_p95_failover_ms


def test_report_ranking_is_sorted_by_p95_failover():
    profiles = default_profiles()
    report = run_competitive_benchmark(
        profiles=[
            profiles["x0tta6bl4-current"],
            profiles["rajant-like"],
            profiles["istio-like-wan"],
        ],
        scenarios=default_scenarios(),
        iterations=80,
        seed=11,
    )

    # Rajant-like should rank ahead of current profile in this model.
    assert report.ranking_by_p95_failover.index("rajant-like") < report.ranking_by_p95_failover.index(
        "x0tta6bl4-current"
    )
