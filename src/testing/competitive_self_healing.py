"""
Competitive self-healing benchmark for MaaS positioning.

This module uses profile-driven simulation to compare failover behavior between
x0tta6bl4 and competitor-like architectures under identical failure scenarios.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class Profile:
    name: str
    routing_style: str
    base_failover_ms: float
    jitter_ms: float
    packet_loss_base_pct: float
    distributed_weight: float
    multi_radio_factor: float
    control_plane_penalty_ms: float
    seed_offset: int = 0


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    failure_type: str
    node_count: int
    concurrent_failures: int
    interference_level: float
    complexity_factor: float
    seed_offset: int = 0


@dataclass
class ScenarioSummary:
    scenario_id: str
    mean_failover_ms: float
    p95_failover_ms: float
    p99_failover_ms: float
    mean_packet_loss_pct: float
    p95_packet_loss_pct: float


@dataclass
class ProfileSummary:
    profile: str
    routing_style: str
    scenarios: List[ScenarioSummary]
    overall_mean_failover_ms: float
    overall_p95_failover_ms: float
    overall_mean_packet_loss_pct: float
    overall_p95_packet_loss_pct: float


@dataclass
class CompetitiveBenchmarkReport:
    generated_at_utc: str
    iterations_per_scenario: int
    seed: int
    profiles: List[ProfileSummary]
    ranking_by_p95_failover: List[str]
    notes: List[str]


def default_profiles() -> Dict[str, Profile]:
    """Reference profiles for comparative simulation."""
    return {
        "x0tta6bl4-current": Profile(
            name="x0tta6bl4-current",
            routing_style="pqc-mesh-distributed",
            base_failover_ms=18.0,
            jitter_ms=4.5,
            packet_loss_base_pct=0.22,
            distributed_weight=0.75,
            multi_radio_factor=1.3,
            control_plane_penalty_ms=1.8,
            seed_offset=10,
        ),
        "x0tta6bl4-make-make-target": Profile(
            name="x0tta6bl4-make-make-target",
            routing_style="prewarmed-multipath",
            base_failover_ms=5.5,
            jitter_ms=1.8,
            packet_loss_base_pct=0.08,
            distributed_weight=0.92,
            multi_radio_factor=1.8,
            control_plane_penalty_ms=0.9,
            seed_offset=20,
        ),
        "rajant-like": Profile(
            name="rajant-like",
            routing_style="hardware-multi-radio",
            base_failover_ms=0.9,
            jitter_ms=0.35,
            packet_loss_base_pct=0.03,
            distributed_weight=0.94,
            multi_radio_factor=4.0,
            control_plane_penalty_ms=0.2,
            seed_offset=30,
        ),
        "istio-like-wan": Profile(
            name="istio-like-wan",
            routing_style="centralized-sidecar-control",
            base_failover_ms=85.0,
            jitter_ms=20.0,
            packet_loss_base_pct=0.9,
            distributed_weight=0.38,
            multi_radio_factor=1.0,
            control_plane_penalty_ms=35.0,
            seed_offset=40,
        ),
    }


def default_scenarios() -> List[Scenario]:
    """Failure scenarios tuned for WAN/edge mesh behavior."""
    return [
        Scenario(
            scenario_id="single_link_cut_100_nodes",
            failure_type="link_cut",
            node_count=100,
            concurrent_failures=1,
            interference_level=0.20,
            complexity_factor=4.0,
            seed_offset=101,
        ),
        Scenario(
            scenario_id="dual_link_cut_300_nodes",
            failure_type="multi_link_cut",
            node_count=300,
            concurrent_failures=2,
            interference_level=0.35,
            complexity_factor=8.5,
            seed_offset=102,
        ),
        Scenario(
            scenario_id="edge_node_crash_500_nodes",
            failure_type="node_crash",
            node_count=500,
            concurrent_failures=1,
            interference_level=0.25,
            complexity_factor=10.0,
            seed_offset=103,
        ),
        Scenario(
            scenario_id="interference_spike_1000_nodes",
            failure_type="interference_spike",
            node_count=1000,
            concurrent_failures=4,
            interference_level=0.90,
            complexity_factor=18.0,
            seed_offset=104,
        ),
    ]


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if percentile <= 0:
        return float(sorted_values[0])
    if percentile >= 100:
        return float(sorted_values[-1])
    idx = int(round((len(sorted_values) - 1) * (percentile / 100.0)))
    idx = max(0, min(idx, len(sorted_values) - 1))
    return float(sorted_values[idx])


def simulate_failover_ms(profile: Profile, scenario: Scenario, rng: random.Random) -> float:
    """Profile-driven failover simulation (synthetic, reproducible)."""
    topology_pressure = max(0.0, (scenario.node_count - 100) / 900.0)
    concurrency_pressure = scenario.concurrent_failures / max(1.0, scenario.node_count / 60.0)
    interference_penalty = scenario.interference_level * (12.0 / max(1.0, profile.multi_radio_factor))
    distributed_discount = profile.distributed_weight * 8.0
    control_penalty = profile.control_plane_penalty_ms * (1.0 + topology_pressure)
    concurrency_penalty = (concurrency_pressure * 25.0) / max(1.0, profile.multi_radio_factor)
    jitter = rng.gauss(0.0, profile.jitter_ms)

    value = (
        profile.base_failover_ms
        + scenario.complexity_factor
        + interference_penalty
        + control_penalty
        + concurrency_penalty
        - distributed_discount
        + jitter
    )
    return max(0.1, value)


def simulate_packet_loss_pct(
    profile: Profile,
    scenario: Scenario,
    failover_ms: float,
    rng: random.Random,
) -> float:
    """Synthetic packet-loss during failover window."""
    loss = (
        profile.packet_loss_base_pct
        + (failover_ms / 1000.0) * 0.35
        + scenario.interference_level * 0.40
        + (scenario.concurrent_failures * 0.03)
        - (profile.distributed_weight * 0.15)
        + rng.uniform(-0.03, 0.03)
    )
    return max(0.01, loss)


def run_profile_benchmark(
    profile: Profile,
    scenarios: Iterable[Scenario],
    iterations: int,
    seed: int,
) -> ProfileSummary:
    scenario_summaries: List[ScenarioSummary] = []
    all_failover: List[float] = []
    all_loss: List[float] = []

    for scenario in scenarios:
        failover_samples: List[float] = []
        loss_samples: List[float] = []

        for i in range(iterations):
            sample_seed = seed + profile.seed_offset + (scenario.seed_offset * 1000) + i
            rng = random.Random(sample_seed)
            failover_ms = simulate_failover_ms(profile, scenario, rng)
            loss_pct = simulate_packet_loss_pct(profile, scenario, failover_ms, rng)
            failover_samples.append(failover_ms)
            loss_samples.append(loss_pct)

        failover_samples.sort()
        loss_samples.sort()
        scenario_summaries.append(
            ScenarioSummary(
                scenario_id=scenario.scenario_id,
                mean_failover_ms=statistics.mean(failover_samples),
                p95_failover_ms=_percentile(failover_samples, 95),
                p99_failover_ms=_percentile(failover_samples, 99),
                mean_packet_loss_pct=statistics.mean(loss_samples),
                p95_packet_loss_pct=_percentile(loss_samples, 95),
            )
        )
        all_failover.extend(failover_samples)
        all_loss.extend(loss_samples)

    all_failover.sort()
    all_loss.sort()
    return ProfileSummary(
        profile=profile.name,
        routing_style=profile.routing_style,
        scenarios=scenario_summaries,
        overall_mean_failover_ms=statistics.mean(all_failover) if all_failover else 0.0,
        overall_p95_failover_ms=_percentile(all_failover, 95),
        overall_mean_packet_loss_pct=statistics.mean(all_loss) if all_loss else 0.0,
        overall_p95_packet_loss_pct=_percentile(all_loss, 95),
    )


def run_competitive_benchmark(
    *,
    profiles: Sequence[Profile],
    scenarios: Sequence[Scenario],
    iterations: int = 200,
    seed: int = 42,
) -> CompetitiveBenchmarkReport:
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    if not profiles:
        raise ValueError("profiles must not be empty")
    if not scenarios:
        raise ValueError("scenarios must not be empty")

    summaries = [run_profile_benchmark(p, scenarios, iterations, seed) for p in profiles]
    ranking = [
        x.profile
        for x in sorted(
            summaries,
            key=lambda item: (item.overall_p95_failover_ms, item.overall_p95_packet_loss_pct),
        )
    ]
    notes = [
        "This benchmark is profile-driven simulation, not direct hardware measurement.",
        "Use identical scenario seeds for fair relative comparison between profiles.",
    ]
    return CompetitiveBenchmarkReport(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        iterations_per_scenario=iterations,
        seed=seed,
        profiles=summaries,
        ranking_by_p95_failover=ranking,
        notes=notes,
    )


def _report_to_dict(report: CompetitiveBenchmarkReport) -> Dict[str, object]:
    return asdict(report)


def _report_to_markdown(report: CompetitiveBenchmarkReport) -> str:
    lines = [
        "# Competitive Self-Healing Benchmark",
        "",
        f"- Generated (UTC): `{report.generated_at_utc}`",
        f"- Iterations per scenario: `{report.iterations_per_scenario}`",
        f"- Seed: `{report.seed}`",
        "",
        "## Ranking by p95 failover",
    ]
    for idx, name in enumerate(report.ranking_by_p95_failover, start=1):
        lines.append(f"{idx}. `{name}`")

    lines.extend(
        [
            "",
            "## Profile summary",
            "",
            "| Profile | p95 failover (ms) | Mean failover (ms) | p95 packet loss (%) |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in report.profiles:
        lines.append(
            f"| {item.profile} | {item.overall_p95_failover_ms:.2f} | "
            f"{item.overall_mean_failover_ms:.2f} | {item.overall_p95_packet_loss_pct:.3f} |"
        )

    lines.extend(["", "## Notes"])
    for note in report.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def save_report(
    report: CompetitiveBenchmarkReport,
    output_dir: Path = Path("benchmarks/results"),
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"competitive_self_healing_{ts}.json"
    md_path = output_dir / f"competitive_self_healing_{ts}.md"
    json_path.write_text(json.dumps(_report_to_dict(report), indent=2), encoding="utf-8")
    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
