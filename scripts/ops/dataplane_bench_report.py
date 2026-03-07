#!/usr/bin/env python3
"""
x0tta6bl4 dataplane benchmark report generator.

Parses the output of `go test -bench=. -benchmem` and produces:
  - A timestamped JSON report (machine-readable, stored in docs/benchmarks/)
  - A Markdown summary (human-readable, used in PR comments and changelog)

Usage
-----
  # Run benchmarks and feed output to this script:
  go test -bench=. -benchmem -benchtime=5s -count=5 ./ebpf/prod/ \
    | python3 scripts/ops/dataplane_bench_report.py --out docs/benchmarks/

  # Or pass a file:
  python3 scripts/ops/dataplane_bench_report.py \
    --input /tmp/bench-current.txt \
    --baseline /tmp/bench-baseline.txt \
    --out docs/benchmarks/

Modes
-----
  VETH_MODE=1    CI mode — Go-level benchmarks only, no root required
  PKTGEN_MODE=1  Hardware mode — runs ebpf/prod/benchmark-pps.sh (needs root)

Exit codes
----------
  0  All gates PASS (or no regressions detected)
  1  Error in script
  2  Benchmark regression >threshold detected
  3  Hardware gate not met (PKTGEN_MODE only)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REGRESSION_THRESHOLD = 0.10   # 10% — fail PR gate
DECISIONS_PER_SEC_MIN = 5_000_000   # Go-level target
HARDWARE_PPS_TARGET = 1_000_000     # Hardware target (pktgen, not enforced here)

# Benchmark names we specifically track for the summary KPIs
KPI_BENCHMARKS = {
    "BenchmarkXDPDecisionSimulator":       "xdp_decisions_per_sec",
    "BenchmarkPolicyRender":               "policy_render_ns_op",
    "BenchmarkPolicyRenderToFile":         "policy_render_file_ns_op",
    "BenchmarkKernelVersionParse":         "kernel_parse_ns_op",
}

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_BENCH_LINE = re.compile(
    r'^(Benchmark\S+)\s+(\d+)\s+([\d.]+)\s+ns/op'
    r'(?:\s+([\d.]+)\s+B/op)?'
    r'(?:\s+(\d+)\s+allocs/op)?'
    r'(.*)?$'
)
_EXTRA_METRIC = re.compile(r'([\d.]+)\s+([\w/]+)')


def _parse_bench_output(text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for line in text.splitlines():
        m = _BENCH_LINE.match(line.strip())
        if not m:
            continue
        name = m.group(1)
        ns_op = float(m.group(3))
        extra: Dict[str, Any] = {}
        for em in _EXTRA_METRIC.finditer(m.group(6) or ""):
            key = em.group(2).replace("/", "_per_")
            extra[key] = float(em.group(1))
        results.append({
            "benchmark": name,
            "iterations": int(m.group(2)),
            "ns_op": ns_op,
            "ops_per_sec": round(1e9 / ns_op, 0) if ns_op > 0 else 0,
            "b_op": float(m.group(4) or 0),
            "allocs_op": int(m.group(5) or 0),
            **extra,
        })
    return results


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------

def _detect_regressions(
    baseline: List[Dict[str, Any]],
    current: List[Dict[str, Any]],
    threshold: float = REGRESSION_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Return benchmarks where ns/op increased by more than threshold."""
    base_map = {b["benchmark"]: b["ns_op"] for b in baseline}
    regressions = []
    for bench in current:
        name = bench["benchmark"]
        base_ns = base_map.get(name)
        if base_ns is None or base_ns == 0:
            continue
        delta = (bench["ns_op"] - base_ns) / base_ns
        if delta > threshold:
            regressions.append({
                "benchmark": name,
                "base_ns_op": base_ns,
                "current_ns_op": bench["ns_op"],
                "delta_pct": round(delta * 100, 1),
            })
    return regressions


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------

def _build_summary(benchmarks: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Find the canonical (non-Parallel) XDPDecisionSimulator result
    xdp_decisions = 0.0
    for b in benchmarks:
        if "XDPDecisionSimulator" in b["benchmark"] and "Parallel" not in b["benchmark"]:
            xdp_decisions = b.get("decisions_per_sec", b.get("ops_per_sec", 0))
            break

    policy_ns_op = next(
        (b["ns_op"] for b in benchmarks
         if b["benchmark"].startswith("BenchmarkPolicyRender-")), 0.0
    )

    go_gate_pass = xdp_decisions >= DECISIONS_PER_SEC_MIN

    return {
        "xdp_decision_simulator_decisions_per_sec": xdp_decisions,
        "xdp_decision_simulator_mps": round(xdp_decisions / 1e6, 2),
        "policy_render_ns_op": policy_ns_op,
        "go_decision_gate": "PASS" if go_gate_pass else "BELOW_TARGET",
        "go_decision_target": DECISIONS_PER_SEC_MIN,
        "hardware_pps_target": HARDWARE_PPS_TARGET,
        "hardware_pps_note": (
            "Hardware PPS gate requires root+pktgen via "
            "ebpf/prod/benchmark-pps.sh — not run in CI."
        ),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _build_report(
    benchmarks: List[Dict[str, Any]],
    commit: str,
    branch: str,
    regressions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": "1",
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit[:12],
        "branch": branch,
        "package": "x0tta6bl4/ebpf/prod",
        "benchmarks": benchmarks,
        "summary": _build_summary(benchmarks),
        "regressions": regressions or [],
        "regression_threshold_pct": REGRESSION_THRESHOLD * 100,
    }


def _build_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    regressions = report.get("regressions", [])
    status = "PASS" if not regressions else "REGRESSION"
    icon = "✅" if status == "PASS" else "⚠️"

    lines = [
        f"# {icon} x0tta6bl4 Go Dataplane Benchmark",
        f"",
        f"**Commit:** `{report['commit']}` | **Branch:** `{report['branch']}`  ",
        f"**Timestamp:** {report['timestamp']}",
        f"",
        f"## KPIs",
        f"",
        f"| Metric | Value | Target | Gate |",
        f"|--------|-------|--------|------|",
        f"| XDP decisions/sec (Go) | **{s['xdp_decision_simulator_mps']:.1f} M/s** "
        f"| {s['go_decision_target']/1e6:.0f} M/s | {s['go_decision_gate']} |",
        f"| Policy render | **{s['policy_render_ns_op']:.0f} ns/op** | — | — |",
        f"| Hardware PPS | _CI-blocked_ | {s['hardware_pps_target']:,} | hardware gate |",
        f"",
        f"## All Benchmarks",
        f"",
        f"| Benchmark | ns/op | ops/sec | B/op | allocs/op |",
        f"|-----------|-------|---------|------|-----------|",
    ]
    for b in report["benchmarks"]:
        if "Parallel" not in b["benchmark"]:
            name = b["benchmark"].replace("Benchmark", "")
            lines.append(
                f"| {name} | {b['ns_op']:.1f} | {b['ops_per_sec']:,.0f} "
                f"| {b['b_op']:.0f} | {b['allocs_op']} |"
            )

    if regressions:
        lines += [
            f"",
            f"## ⚠️ Regressions Detected",
            f"",
            f"| Benchmark | Baseline ns/op | Current ns/op | Delta |",
            f"|-----------|----------------|---------------|-------|",
        ]
        for r in regressions:
            lines.append(
                f"| {r['benchmark']} | {r['base_ns_op']:.1f} "
                f"| {r['current_ns_op']:.1f} | +{r['delta_pct']:.1f}% |"
            )

    lines += [
        f"",
        f"---",
        f"_Hardware PPS gate: {s['hardware_pps_note']}_",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hardware pktgen mode
# ---------------------------------------------------------------------------

def _run_hardware_bench(iface: str, duration: int) -> Dict[str, Any]:
    """Run ebpf/prod/benchmark-pps.sh in PKTGEN_MODE=1 (requires root)."""
    script = Path(__file__).parents[2] / "ebpf/prod/benchmark-pps.sh"
    if not script.exists():
        return {"error": f"{script} not found"}
    env = os.environ.copy()
    env.update({"RUN_BENCH": "1", "IFACE": iface, "DURATION": str(duration)})
    result = subprocess.run(
        ["bash", str(script)], env=env, capture_output=True, text=True
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="x0tta6bl4 dataplane benchmark reporter")
    p.add_argument("--input", "-i", default="-",
                   help="Path to go test -bench output (default: stdin)")
    p.add_argument("--baseline", "-b", default=None,
                   help="Path to baseline benchmark output for regression comparison")
    p.add_argument("--out", "-o", default=None,
                   help="Output directory for JSON + Markdown reports")
    p.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local"),
                   help="Git commit SHA")
    p.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "local"),
                   help="Branch name")
    p.add_argument("--threshold", type=float, default=REGRESSION_THRESHOLD,
                   help="Regression threshold (default 0.10 = 10%%)")
    p.add_argument("--hardware", action="store_true",
                   help="Also run hardware pktgen benchmark (requires root)")
    p.add_argument("--iface", default="eth0",
                   help="Network interface for hardware benchmark")
    p.add_argument("--duration", type=int, default=10,
                   help="Duration (s) for hardware benchmark")
    p.add_argument("--quiet", "-q", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    # Read benchmark output
    if args.input == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text()

    benchmarks = _parse_bench_output(text)
    if not benchmarks:
        print("ERROR: No benchmark results found in input.", file=sys.stderr)
        return 1

    # Regression comparison
    regressions: List[Dict[str, Any]] = []
    if args.baseline:
        baseline_text = Path(args.baseline).read_text()
        baseline_benchmarks = _parse_bench_output(baseline_text)
        regressions = _detect_regressions(baseline_benchmarks, benchmarks, args.threshold)

    # Hardware mode
    hw_result: Optional[Dict[str, Any]] = None
    if args.hardware:
        if os.getuid() != 0:
            print("WARNING: --hardware requires root; skipping.", file=sys.stderr)
        else:
            hw_result = _run_hardware_bench(args.iface, args.duration)

    report = _build_report(benchmarks, args.commit, args.branch, regressions)
    if hw_result:
        report["hardware_benchmark"] = hw_result

    markdown = _build_markdown(report)

    # Output
    if not args.quiet:
        print(markdown)

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = report["timestamp"].replace(":", "").replace("-", "")
        json_path = out_dir / f"dataplane_bench_{ts}.json"
        md_path = out_dir / f"dataplane_bench_{ts}.md"
        latest_json = out_dir / "dataplane_bench_LATEST.json"
        latest_md = out_dir / "dataplane_bench_LATEST.md"

        json_path.write_text(json.dumps(report, indent=2))
        md_path.write_text(markdown)
        latest_json.write_text(json.dumps(report, indent=2))
        latest_md.write_text(markdown)

        if not args.quiet:
            print(f"\nReports written to {out_dir}/", file=sys.stderr)

    if regressions:
        print(
            f"\nREGRESSION: {len(regressions)} benchmark(s) regressed "
            f">{args.threshold*100:.0f}%",
            file=sys.stderr,
        )
        return 2

    summary = report["summary"]
    if summary["go_decision_gate"] != "PASS":
        print(
            f"\nWARNING: XDP decisions/sec "
            f"({summary['xdp_decision_simulator_decisions_per_sec']:,.0f}) "
            f"below target ({summary['go_decision_target']:,})",
            file=sys.stderr,
        )
        # Advisory only — don't fail; hardware gate is separate

    return 0


if __name__ == "__main__":
    sys.exit(main())
