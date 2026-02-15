#!/usr/bin/env python3
"""
Check benchmark results against baseline thresholds.

Blocks CI/CD if degradation exceeds threshold.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional


def load_json(filepath: Path) -> Dict:
    """Load JSON file"""
    with open(filepath, "r") as f:
        return json.load(f)


def compare_metrics(
    baseline: Dict, current: Dict, threshold: float = 0.10
) -> tuple[bool, list]:
    """Compare current metrics against baseline"""
    issues = []
    all_pass = True

    metrics_to_check = [
        "pqc_encrypt_latency_ms",
        "pqc_decrypt_latency_ms",
        "graphsage_inference_ms",
        "latency_p95_ms",
        "latency_p99_ms",
    ]

    for metric in metrics_to_check:
        baseline_val = baseline.get(metric)
        current_val = current.get(metric)

        if baseline_val is None or current_val is None:
            continue  # Skip if not available

        # Calculate degradation (positive = worse)
        degradation = (current_val - baseline_val) / baseline_val

        if degradation > threshold:
            all_pass = False
            issues.append(
                f"❌ {metric}: {degradation*100:.1f}% degradation "
                f"(baseline: {baseline_val:.2f}ms, current: {current_val:.2f}ms)"
            )
        elif degradation < -threshold:
            # Improvement (negative degradation)
            issues.append(
                f"✅ {metric}: {abs(degradation)*100:.1f}% improvement "
                f"(baseline: {baseline_val:.2f}ms, current: {current_val:.2f}ms)"
            )

    return all_pass, issues


def main():
    parser = argparse.ArgumentParser(
        description="Check benchmark results against baseline"
    )
    parser.add_argument(
        "--baseline", type=Path, required=True, help="Path to baseline JSON file"
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to current benchmark JSON file",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="Maximum allowed degradation (default: 0.10 = 10%%)",
    )

    args = parser.parse_args()

    # Load files
    try:
        baseline = load_json(args.baseline)
        current = load_json(args.current)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Compare
    all_pass, issues = compare_metrics(baseline, current, args.threshold)

    # Print results
    print("=" * 60)
    print("BENCHMARK THRESHOLD CHECK")
    print("=" * 60)
    print(f"Baseline: {args.baseline}")
    print(f"Current: {args.current}")
    print(f"Threshold: {args.threshold*100:.1f}%")
    print("=" * 60)

    if issues:
        for issue in issues:
            print(issue)
    else:
        print("✅ No significant changes detected")

    print("=" * 60)

    # Exit code
    if all_pass:
        print("✅ All metrics within threshold")
        sys.exit(0)
    else:
        print("❌ Degradation exceeds threshold - BLOCKING")
        sys.exit(1)


if __name__ == "__main__":
    main()
