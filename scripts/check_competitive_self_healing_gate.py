#!/usr/bin/env python3
"""
CI performance gate for competitive self-healing benchmark.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.testing.competitive_self_healing import (  # noqa: E402
    default_profiles,
    default_scenarios,
    run_competitive_benchmark,
    save_report,
)


def _load_thresholds(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Threshold file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_map(report_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    profiles = report_dict.get("profiles", [])
    return {item["profile"]: item for item in profiles}


def _check_gates(report_dict: Dict[str, Any], thresholds: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    profiles = _profile_map(report_dict)

    for profile_name, limits in thresholds.get("profiles", {}).items():
        if profile_name not in profiles:
            failures.append(f"Missing profile in report: {profile_name}")
            continue
        profile = profiles[profile_name]
        max_p95_failover_ms = limits.get("max_p95_failover_ms")
        max_p95_packet_loss_pct = limits.get("max_p95_packet_loss_pct")
        if max_p95_failover_ms is not None and profile["overall_p95_failover_ms"] > max_p95_failover_ms:
            failures.append(
                f"{profile_name}: p95 failover {profile['overall_p95_failover_ms']:.2f}ms "
                f"> limit {max_p95_failover_ms:.2f}ms"
            )
        if max_p95_packet_loss_pct is not None and profile["overall_p95_packet_loss_pct"] > max_p95_packet_loss_pct:
            failures.append(
                f"{profile_name}: p95 packet loss {profile['overall_p95_packet_loss_pct']:.3f}% "
                f"> limit {max_p95_packet_loss_pct:.3f}%"
            )

    relative_cfg = thresholds.get("relative", {})
    current = profiles.get("x0tta6bl4-current")
    target = profiles.get("x0tta6bl4-make-make-target")
    rajant = profiles.get("rajant-like")
    if current and target:
        min_improvement_pct = float(relative_cfg.get("min_target_improvement_vs_current_pct", 0.0))
        improvement_pct = (
            ((current["overall_p95_failover_ms"] - target["overall_p95_failover_ms"]) / current["overall_p95_failover_ms"]) * 100.0
            if current["overall_p95_failover_ms"] > 0
            else 0.0
        )
        if improvement_pct < min_improvement_pct:
            failures.append(
                f"x0tta6bl4 target improvement {improvement_pct:.2f}% "
                f"< required {min_improvement_pct:.2f}%"
            )

    if current and rajant:
        max_ratio = relative_cfg.get("max_current_to_rajant_p95_failover_ratio")
        if max_ratio is not None and rajant["overall_p95_failover_ms"] > 0:
            ratio = current["overall_p95_failover_ms"] / rajant["overall_p95_failover_ms"]
            if ratio > float(max_ratio):
                failures.append(
                    f"x0tta6bl4-current to rajant p95 ratio {ratio:.2f} > limit {float(max_ratio):.2f}"
                )

    expected_prefix = thresholds.get("ranking", {}).get("expected_order_prefix", [])
    ranking = report_dict.get("ranking_by_p95_failover", [])
    if expected_prefix:
        if ranking[: len(expected_prefix)] != expected_prefix:
            failures.append(
                "ranking prefix mismatch: "
                f"expected {expected_prefix}, got {ranking[:len(expected_prefix)]}"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run competitive self-healing CI gate")
    parser.add_argument(
        "--thresholds",
        default="benchmarks/baseline/competitive_self_healing_gate.json",
        help="Path to threshold config JSON",
    )
    parser.add_argument("--iterations", type=int, default=120, help="Iterations per scenario/profile")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic benchmark seed")
    parser.add_argument("--output-dir", default="benchmarks/results", help="Where to save benchmark artifacts")
    args = parser.parse_args()

    thresholds_path = (REPO_ROOT / args.thresholds).resolve() if not Path(args.thresholds).is_absolute() else Path(args.thresholds)
    thresholds = _load_thresholds(thresholds_path)

    report = run_competitive_benchmark(
        profiles=list(default_profiles().values()),
        scenarios=default_scenarios(),
        iterations=args.iterations,
        seed=args.seed,
    )
    paths = save_report(report, output_dir=Path(args.output_dir))
    report_dict = asdict(report)

    failures = _check_gates(report_dict, thresholds)

    print("Competitive self-healing benchmark gate")
    print(f"- thresholds: {thresholds_path}")
    print(f"- report_json: {paths['json']}")
    print(f"- report_md: {paths['markdown']}")
    print("- ranking:", " > ".join(report.ranking_by_p95_failover))
    for profile in report.profiles:
        print(
            f"  {profile.profile}: p95_failover={profile.overall_p95_failover_ms:.2f}ms, "
            f"p95_loss={profile.overall_p95_packet_loss_pct:.3f}%"
        )

    if failures:
        print("Gate status: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("Gate status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
