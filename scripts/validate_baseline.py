#!/usr/bin/env python3
"""
Validate Baseline Metrics

Compares current metrics against baseline to ensure no regression.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent
DEFAULT_BASELINE_FILE = project_root / "baseline_metrics.json"
CURRENT_METRICS_ENV = "x0tta6bl4_CURRENT_METRICS_JSON"
REQUIRED_METRICS = (
    "success_rate_percent",
    "latency_p95_ms",
    "max_memory_mb",
)


def load_json_file(path: Path, label: str) -> dict[str, Any]:
    """Load a metrics JSON file."""
    if not path.exists():
        raise ValueError(f"{label} file not found: {path}")

    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} file is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{label} file must contain a JSON object")

    return payload


def load_baseline(path: Path = DEFAULT_BASELINE_FILE) -> dict[str, Any]:
    """Load baseline metrics."""
    return load_json_file(path, "baseline")


def extract_metrics(payload: dict[str, Any], label: str) -> dict[str, float]:
    """Return a validated metric summary from either a raw or wrapped payload."""
    metrics = payload.get("summary", payload)
    if not isinstance(metrics, dict):
        raise ValueError(f"{label} metrics must be an object or a summary object")

    normalized: dict[str, float] = {}
    for metric in REQUIRED_METRICS:
        value = metrics.get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} metric {metric!r} is required and must be numeric")
        normalized[metric] = float(value)

    return normalized


def validate_metrics(current_metrics, baseline):
    """Validate current metrics against baseline."""
    baseline_summary = extract_metrics(baseline, "baseline")
    current_summary = extract_metrics(current_metrics, "current")

    print("\n" + "=" * 60)
    print("📊 BASELINE VALIDATION")
    print("=" * 60 + "\n")

    checks = [
        (
            "Success Rate",
            current_summary["success_rate_percent"],
            baseline_summary["success_rate_percent"],
            ">=",
            "Success rate should not decrease",
        ),
        (
            "Latency P95",
            current_summary["latency_p95_ms"],
            baseline_summary["latency_p95_ms"] * 1.2,
            "<=",
            "Latency P95 should not increase by more than 20%",
        ),
        (
            "Memory",
            current_summary["max_memory_mb"],
            baseline_summary["max_memory_mb"] * 1.2,
            "<=",
            "Memory should not increase by more than 20%",
        ),
    ]

    all_passed = True

    for name, current, threshold, operator, description in checks:
        if operator == ">=":
            passed = current >= threshold
        elif operator == "<=":
            passed = current <= threshold
        else:
            passed = False

        status = "✅" if passed else "❌"
        print(f"{status} {name}: {current:.2f} (threshold: {threshold:.2f})")
        print(f"   {description}")

        if not passed:
            all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✅ BASELINE VALIDATION: PASSED")
        return True
    else:
        print("❌ BASELINE VALIDATION: FAILED")
        print("   Performance regression detected!")
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    current_from_env = os.environ.get(CURRENT_METRICS_ENV)
    parser = argparse.ArgumentParser(
        description="Compare current performance metrics against a saved baseline."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_FILE,
        help="baseline metrics JSON path",
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=Path(current_from_env) if current_from_env else None,
        help=f"current metrics JSON path; can also be set with {CURRENT_METRICS_ENV}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run baseline validation."""
    args = parse_args(argv)
    if args.current is None:
        print(
            "❌ Current metrics file is required. "
            f"Pass --current PATH or set {CURRENT_METRICS_ENV}."
        )
        return 2

    try:
        baseline = load_baseline(args.baseline)
        current = load_json_file(args.current, "current")
        passed = validate_metrics(current, baseline)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 2

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
