#!/usr/bin/env python3
"""
Compare Current Metrics Against Baseline

Compares current production metrics against locked baseline to detect regressions.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

project_root = Path(__file__).parent.parent


def load_baseline() -> Dict[str, Any]:
    """Load baseline metrics."""
    baseline_file = project_root / "baseline_metrics.json"

    if not baseline_file.exists():
        print("❌ Baseline file not found. Run performance baseline first.")
        sys.exit(1)

    with open(baseline_file) as f:
        return json.load(f)


def load_current_metrics(metrics_file: Path) -> Dict[str, Any]:
    """Load current metrics from file."""
    if not metrics_file.exists():
        print(f"❌ Metrics file not found: {metrics_file}")
        sys.exit(1)

    with open(metrics_file) as f:
        data = json.load(f)
        # If it's a list, get the latest
        if isinstance(data, list):
            return data[-1] if data else {}
        return data


def compare_metrics(
    baseline: Dict[str, Any], current: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare current metrics against baseline."""
    baseline_summary = baseline.get("summary", {})

    comparisons = []
    regressions = []

    # Success Rate
    baseline_sr = baseline_summary.get("success_rate_percent", 100.0)
    current_sr = current.get("performance", {}).get("success_rate_percent", 100.0)
    sr_diff = current_sr - baseline_sr
    sr_regression = sr_diff < -1.0  # More than 1% decrease

    comparisons.append(
        {
            "metric": "Success Rate",
            "baseline": baseline_sr,
            "current": current_sr,
            "diff": sr_diff,
            "regression": sr_regression,
        }
    )

    if sr_regression:
        regressions.append(f"Success rate decreased by {abs(sr_diff):.2f}%")

    # Latency P95
    baseline_latency = baseline_summary.get("latency_p95_ms", 0.0)
    current_latency = current.get("performance", {}).get("latency_p95", 0.0)
    latency_diff = current_latency - baseline_latency
    latency_regression = latency_diff > baseline_latency * 0.2  # More than 20% increase

    comparisons.append(
        {
            "metric": "Latency P95",
            "baseline": baseline_latency,
            "current": current_latency,
            "diff": latency_diff,
            "regression": latency_regression,
        }
    )

    if latency_regression:
        regressions.append(
            f"Latency P95 increased by {latency_diff:.2f}ms ({latency_diff/baseline_latency*100:.1f}%)"
        )

    # Memory
    baseline_memory = baseline_summary.get("max_memory_mb", 0.0)
    current_memory = current.get("resources", {}).get("memory_mb", 0.0)
    memory_diff = current_memory - baseline_memory
    memory_regression = memory_diff > baseline_memory * 0.2  # More than 20% increase

    comparisons.append(
        {
            "metric": "Memory",
            "baseline": baseline_memory,
            "current": current_memory,
            "diff": memory_diff,
            "regression": memory_regression,
        }
    )

    if memory_regression:
        regressions.append(
            f"Memory increased by {memory_diff:.2f}MB ({memory_diff/baseline_memory*100:.1f}%)"
        )

    return {
        "comparisons": comparisons,
        "regressions": regressions,
        "has_regression": len(regressions) > 0,
    }


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Compare metrics against baseline")
    parser.add_argument("--metrics", type=str, help="Path to current metrics file")

    args = parser.parse_args()

    baseline = load_baseline()

    if args.metrics:
        current_file = Path(args.metrics)
    else:
        # Find latest metrics file
        metrics_files = sorted(project_root.glob("metrics_*.json"), reverse=True)
        if not metrics_files:
            print("❌ No metrics files found. Run metrics_collector first.")
            sys.exit(1)
        current_file = metrics_files[0]
        print(f"Using latest metrics file: {current_file.name}")

    current = load_current_metrics(current_file)

    print("\n" + "=" * 60)
    print("📊 BASELINE COMPARISON")
    print("=" * 60 + "\n")

    result = compare_metrics(baseline, current)

    for comp in result["comparisons"]:
        status = "❌" if comp["regression"] else "✅"
        print(f"{status} {comp['metric']}:")
        print(f"   Baseline: {comp['baseline']:.2f}")
        print(f"   Current:  {comp['current']:.2f}")
        print(f"   Diff:     {comp['diff']:+.2f}")
        print()

    if result["has_regression"]:
        print("=" * 60)
        print("⚠️  PERFORMANCE REGRESSION DETECTED")
        print("=" * 60)
        for regression in result["regressions"]:
            print(f"  • {regression}")
        print()
        print("Recommendation: Review recent changes or consider rollback.")
        sys.exit(1)
    else:
        print("=" * 60)
        print("✅ NO REGRESSION DETECTED")
        print("=" * 60)
        print("All metrics are within acceptable range.")
        sys.exit(0)


if __name__ == "__main__":
    main()
