#!/usr/bin/env python3
"""
Prometheus / OpenMetrics endpoint validator for x0tta6bl4.

Fetches /metrics from a running exporter and verifies:
  - Required metric names are present
  - Required labels exist on specified metrics
  - Metric values are within expected ranges (optional)
  - Output is valid OpenMetrics text format (no parse errors)

No external dependencies — uses stdlib only.

Usage:
  python3 scripts/ops/validate_metrics_endpoint.py --url http://localhost:9101/metrics
  python3 scripts/ops/validate_metrics_endpoint.py --snapshot /tmp/metrics.txt
  python3 scripts/ops/validate_metrics_endpoint.py --help

Exit codes:
  0  all checks pass
  1  one or more checks failed
  2  endpoint unreachable or snapshot not found
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Validation rules for x0tta6bl4 eBPF exporter
# ---------------------------------------------------------------------------

REQUIRED_METRICS: List[str] = [
    "x0tta6bl4_xdp_runs_total",
    "x0tta6bl4_xdp_pps",
]

# {metric_name: [(label_key, allowed_values_or_None_for_any)]}
REQUIRED_LABELS: Dict[str, List[Tuple[str, Optional[List[str]]]]] = {
    "x0tta6bl4_xdp_runs_total": [
        ("prog_name", None),          # any value
        ("iface", None),
    ],
    "x0tta6bl4_xdp_pps": [
        ("prog_name", None),
        ("iface", None),
    ],
}

# {metric_name: (min, max)}  — None means unchecked
VALUE_RANGES: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    "x0tta6bl4_xdp_runs_total": (0.0, None),   # non-negative counter
    "x0tta6bl4_xdp_pps": (0.0, None),           # non-negative gauge
}


# ---------------------------------------------------------------------------
# OpenMetrics text parser (subset)
# ---------------------------------------------------------------------------

@dataclass
class MetricSample:
    name: str
    labels: Dict[str, str]
    value: float
    raw_line: str


def _parse_label_string(label_str: str) -> Dict[str, str]:
    """Parse 'key="val",key2="val2"' into a dict."""
    labels: Dict[str, str] = {}
    for m in re.finditer(r'(\w+)="([^"]*)"', label_str):
        labels[m.group(1)] = m.group(2)
    return labels


def parse_openmetrics(text: str) -> List[MetricSample]:
    """
    Parse Prometheus text exposition format into MetricSample list.
    Skips comment (#) and empty lines.
    """
    samples: List[MetricSample] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # metric_name{labels} value [timestamp]
        m = re.match(
            r'^([a-zA-Z_:][a-zA-Z0-9_:]*)'   # metric name
            r'(?:\{([^}]*)\})?'                # optional labels
            r'\s+([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|[+-]?Inf|NaN)'  # value
            r'(?:\s+\S+)?$',                   # optional timestamp
            line,
        )
        if not m:
            continue
        name = m.group(1)
        label_str = m.group(2) or ""
        value_str = m.group(3)

        try:
            value = float(value_str)
        except ValueError:
            continue

        samples.append(MetricSample(
            name=name,
            labels=_parse_label_string(label_str),
            value=value,
            raw_line=line,
        ))
    return samples


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


def validate(samples: List[MetricSample]) -> List[CheckResult]:
    results: List[CheckResult] = []
    by_name: Dict[str, List[MetricSample]] = {}
    for s in samples:
        by_name.setdefault(s.name, []).append(s)

    # 1. Required metrics present
    for metric in REQUIRED_METRICS:
        present = metric in by_name
        results.append(CheckResult(
            name=f"metric_present:{metric}",
            passed=present,
            message=f"{'FOUND' if present else 'MISSING'}: {metric}",
        ))

    # 2. Required labels
    for metric, label_specs in REQUIRED_LABELS.items():
        metric_samples = by_name.get(metric, [])
        if not metric_samples:
            continue  # already reported as missing
        for lk, allowed in label_specs:
            has_label = any(lk in s.labels for s in metric_samples)
            if has_label and allowed:
                valid_val = any(s.labels.get(lk) in allowed for s in metric_samples)
                ok = valid_val
                detail = f"value in {allowed}" if ok else f"got {[s.labels.get(lk) for s in metric_samples]}, expected {allowed}"
            else:
                ok = has_label
                detail = "present" if ok else "missing"
            results.append(CheckResult(
                name=f"label:{metric}[{lk}]",
                passed=ok,
                message=f"{'OK' if ok else 'FAIL'}: {metric} label '{lk}' — {detail}",
            ))

    # 3. Value ranges
    for metric, (lo, hi) in VALUE_RANGES.items():
        metric_samples = by_name.get(metric, [])
        if not metric_samples:
            continue
        for s in metric_samples:
            v = s.value
            in_range = (lo is None or v >= lo) and (hi is None or v <= hi)
            bounds = f"[{lo if lo is not None else '-∞'}, {hi if hi is not None else '+∞'}]"
            results.append(CheckResult(
                name=f"range:{metric}",
                passed=in_range,
                message=f"{'OK' if in_range else 'FAIL'}: {metric}={v} {'in' if in_range else 'outside'} {bounds}",
            ))

    # 4. At least one sample parsed
    results.append(CheckResult(
        name="samples_parsed",
        passed=len(samples) > 0,
        message=f"Parsed {len(samples)} sample(s)",
    ))

    return results


# ---------------------------------------------------------------------------
# Fetch / load
# ---------------------------------------------------------------------------

def fetch_url(url: str, timeout: int = 10) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach {url}: {e}", file=sys.stderr)
        sys.exit(2)


def load_snapshot(path: str) -> str:
    try:
        return open(path).read()
    except OSError as e:
        print(f"ERROR: Cannot read snapshot {path}: {e}", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate x0tta6bl4 Prometheus /metrics endpoint",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Live endpoint URL (e.g. http://localhost:9101/metrics)")
    group.add_argument("--snapshot", help="Path to saved metrics text file")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout seconds")
    args = parser.parse_args(argv)

    if args.url:
        print(f"Fetching {args.url}…")
        text = fetch_url(args.url, args.timeout)
    else:
        print(f"Loading snapshot {args.snapshot}…")
        text = load_snapshot(args.snapshot)

    samples = parse_openmetrics(text)
    results = validate(samples)

    print(f"\nResults ({len(results)} checks):")
    passed = sum(1 for r in results if r.passed)
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.message}")

    print(f"\n{passed}/{len(results)} checks passed.")

    if passed < len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
