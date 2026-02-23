"""
Competitive self-healing benchmark runner.

Compares x0tta6bl4 profiles against competitor-like baselines under the same
failure scenarios to produce reproducible MTTR/failover/loss deltas.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

# Ensure repository root is importable when script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.testing.competitive_self_healing import (
    default_profiles,
    default_scenarios,
    run_competitive_benchmark,
    save_report,
)


def _parse_profiles(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run competitive self-healing benchmark")
    parser.add_argument("--iterations", type=int, default=250, help="Samples per scenario/profile")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--profiles",
        default="x0tta6bl4-current,x0tta6bl4-make-make-target,rajant-like,istio-like-wan",
        help="Comma-separated profile IDs",
    )
    parser.add_argument("--output-dir", default="benchmarks/results", help="Output directory")
    args = parser.parse_args()

    profiles_map = default_profiles()
    requested_profiles = _parse_profiles(args.profiles)
    unknown = [name for name in requested_profiles if name not in profiles_map]
    if unknown:
        raise SystemExit(f"Unknown profile(s): {', '.join(unknown)}")

    profiles = [profiles_map[name] for name in requested_profiles]
    report = run_competitive_benchmark(
        profiles=profiles,
        scenarios=default_scenarios(),
        iterations=args.iterations,
        seed=args.seed,
    )
    paths = save_report(report, output_dir=Path(args.output_dir))

    print("Competitive benchmark completed.")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print("Ranking by p95 failover:")
    for idx, profile in enumerate(report.ranking_by_p95_failover, start=1):
        print(f"  {idx}. {profile}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
