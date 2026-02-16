#!/usr/bin/env python3
"""
Parse Stability Test Metrics
Дата: 2026-01-07
Версия: Enhanced
"""

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def parse_prometheus_metrics(metrics_file: Path) -> Dict[str, Any]:
    """Parse Prometheus metrics file."""
    metrics = {}

    try:
        with open(metrics_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse Prometheus format: metric_name{labels} value timestamp
                    if "{" in line:
                        parts = line.split("{", 1)
                        metric_name = parts[0]
                        rest = parts[1].split("}", 1)
                        value = float(rest[1].strip().split()[0])
                        metrics[metric_name] = value
                    else:
                        parts = line.split()
                        if len(parts) >= 2:
                            metric_name = parts[0]
                            value = float(parts[1])
                            metrics[metric_name] = value
    except Exception as e:
        print(f"⚠️ Error parsing {metrics_file}: {e}", file=sys.stderr)

    return metrics


def detect_anomalies(
    metrics: List[Dict[str, float]], metric_name: str
) -> List[Dict[str, Any]]:
    """Detect anomalies in metric values."""
    values = [m.get(metric_name, 0) for m in metrics if metric_name in m]

    if len(values) < 2:
        return []

    anomalies = []
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0

    for i, value in enumerate(values):
        if stdev > 0:
            z_score = abs((value - mean) / stdev)
            if z_score > 3:  # 3 sigma rule
                anomalies.append(
                    {
                        "index": i,
                        "value": value,
                        "z_score": z_score,
                        "timestamp": metrics[i].get("timestamp", "unknown"),
                    }
                )

    return anomalies


def analyze_memory_trend(metrics: List[Dict[str, float]]) -> Dict[str, Any]:
    """Analyze memory trend for leaks."""
    memory_values = [
        m.get("container_memory_usage_bytes", 0)
        for m in metrics
        if "container_memory_usage_bytes" in m
    ]

    if len(memory_values) < 2:
        return {"status": "insufficient_data"}

    # Calculate growth
    initial = memory_values[0]
    final = memory_values[-1]
    growth = final - initial
    growth_percent = (growth / initial * 100) if initial > 0 else 0

    # Linear regression check (simple)
    is_linear = True
    if len(memory_values) > 3:
        # Check if memory grows linearly (potential leak)
        diffs = [
            memory_values[i + 1] - memory_values[i]
            for i in range(len(memory_values) - 1)
        ]
        avg_diff = statistics.mean(diffs)
        for diff in diffs:
            if abs(diff - avg_diff) > avg_diff * 0.5:  # 50% variance
                is_linear = False
                break

    return {
        "initial": initial,
        "final": final,
        "growth": growth,
        "growth_percent": growth_percent,
        "is_linear_growth": is_linear,
        "status": "leak_detected" if is_linear and growth_percent > 10 else "stable",
    }


def generate_report(metrics_dir: Path, output_file: Path):
    """Generate analysis report."""
    metrics_files = sorted(metrics_dir.glob("*.json")) + sorted(
        metrics_dir.glob("metrics_*.txt")
    )

    if not metrics_files:
        print(f"⚠️ No metrics files found in {metrics_dir}")
        return

    all_metrics = []
    for file in metrics_files:
        if file.suffix == ".json":
            try:
                with open(file) as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data["timestamp"] = file.stem
                        all_metrics.append(data)
            except Exception as e:
                print(f"⚠️ Error reading {file}: {e}", file=sys.stderr)

    # Analyze
    memory_analysis = analyze_memory_trend(all_metrics)

    # Generate report
    with open(output_file, "w") as f:
        f.write("# Stability Test Metrics Analysis\n")
        f.write(f"**Дата:** {datetime.now().isoformat()}\n\n")

        f.write("## Memory Analysis\n\n")
        if memory_analysis.get("status") != "insufficient_data":
            f.write(f"- Initial: {memory_analysis.get('initial', 0):,.0f} bytes\n")
            f.write(f"- Final: {memory_analysis.get('final', 0):,.0f} bytes\n")
            f.write(
                f"- Growth: {memory_analysis.get('growth', 0):,.0f} bytes ({memory_analysis.get('growth_percent', 0):.2f}%)\n"
            )

            if memory_analysis.get("status") == "leak_detected":
                f.write(
                    f"- ⚠️ **Memory Leak Detected:** Linear growth pattern detected\n"
                )
            else:
                f.write(f"- ✅ **Memory Stable:** No significant growth detected\n")
        else:
            f.write("- ⚠️ Insufficient data for analysis\n")

        f.write("\n## Anomalies\n\n")
        anomalies = detect_anomalies(all_metrics, "container_cpu_usage_seconds_total")
        if anomalies:
            f.write(f"- ⚠️ {len(anomalies)} CPU anomalies detected\n")
        else:
            f.write("- ✅ No CPU anomalies detected\n")

    print(f"✅ Report generated: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Parse stability test metrics")
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="./stability_test_metrics",
        help="Directory containing metrics files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./STABILITY_METRICS_ANALYSIS.md",
        help="Output report file",
    )

    args = parser.parse_args()

    metrics_dir = Path(args.metrics_dir)
    output_file = Path(args.output)

    if not metrics_dir.exists():
        print(f"❌ Metrics directory not found: {metrics_dir}")
        sys.exit(1)

    generate_report(metrics_dir, output_file)


if __name__ == "__main__":
    main()
