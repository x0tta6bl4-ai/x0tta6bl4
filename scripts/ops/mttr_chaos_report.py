#!/usr/bin/env python3
"""
MTTR Chaos Report Generator for x0tta6bl4.

Runs a suite of synthetic chaos scenarios through the MAPE-K healing loop,
measures Time-To-Detect (TTD) and Time-To-Recover (TTR) for each, and
produces a JSON + Markdown report.

Modes:
  CI mode (default):  Fast, fully synthetic — no cluster, no real network.
                      Uses mock detect/heal functions with configurable delays.
  Hardware mode:      MTTR_HW_MODE=1 — replaces mocks with live kubectl/helm
                      calls. Requires a running cluster.

SLO targets:
  TTD  < 30 s   (detect window in MAPE-K Monitor phase)
  TTR  < 300 s  (5 min recovery)
  MTTR < 300 s  (mean across all scenarios)

Usage:
  python3 scripts/ops/mttr_chaos_report.py
  python3 scripts/ops/mttr_chaos_report.py --output /tmp/mttr.json
  MTTR_HW_MODE=1 python3 scripts/ops/mttr_chaos_report.py
"""

import argparse
import datetime
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HW_MODE: bool = os.getenv("MTTR_HW_MODE", "0").strip() in {"1", "true", "yes"}
SLO_TTD_S: float = float(os.getenv("MTTR_SLO_TTD", "30"))
SLO_TTR_S: float = float(os.getenv("MTTR_SLO_TTR", "300"))
SLO_MTTR_S: float = float(os.getenv("MTTR_SLO_MTTR", "300"))
RANDOM_SEED: int = int(os.getenv("MTTR_SEED", "42"))

random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    description: str
    fault_type: str
    ttd_s: float          # time-to-detect
    ttr_s: float          # time-to-recover (from fault injection to healthy)
    healed: bool
    ttd_slo_pass: bool = field(init=False)
    ttr_slo_pass: bool = field(init=False)
    notes: str = ""

    def __post_init__(self) -> None:
        self.ttd_slo_pass = self.ttd_s <= SLO_TTD_S
        self.ttr_slo_pass = self.ttr_s <= SLO_TTR_S


@dataclass
class ChaosReport:
    schema_version: str = "1"
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    mode: str = field(default_factory=lambda: "hardware" if HW_MODE else "synthetic-ci")
    seed: int = RANDOM_SEED
    slo_ttd_s: float = SLO_TTD_S
    slo_ttr_s: float = SLO_TTR_S
    slo_mttr_s: float = SLO_MTTR_S
    scenarios: List[ScenarioResult] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)

    def compute_summary(self) -> None:
        n = len(self.scenarios)
        if n == 0:
            return
        healed = [s for s in self.scenarios if s.healed]
        ttds = [s.ttd_s for s in self.scenarios]
        ttrs = [s.ttr_s for s in healed]

        mttr = sum(ttrs) / len(ttrs) if ttrs else 0.0
        mttd = sum(ttds) / len(ttds) if ttds else 0.0

        self.summary = {
            "total_scenarios": n,
            "healed": len(healed),
            "failed_to_heal": n - len(healed),
            "heal_rate_pct": round(100.0 * len(healed) / n, 1),
            "mttd_s": round(mttd, 2),
            "mttr_s": round(mttr, 2),
            "mttr_slo_pass": mttr <= SLO_MTTR_S,
            "ttd_slo_pass_all": all(s.ttd_slo_pass for s in self.scenarios),
            "ttr_slo_pass_all": all(s.ttr_slo_pass for s in healed),
            "worst_ttr_s": round(max((s.ttr_s for s in healed), default=0), 2),
            "worst_ttd_s": round(max(ttds, default=0), 2),
        }


# ---------------------------------------------------------------------------
# Synthetic chaos engine (CI mode)
# ---------------------------------------------------------------------------
# Each scenario is defined as (name, description, fault_type, ttd_range, ttr_range)
# Ranges are (min_s, max_s) of realistic delays.

_CI_SCENARIOS: List[Tuple] = [
    (
        "api-pod-oom",
        "API pod exceeds memory limit, OOMKilled",
        "pod-kill",
        (2.0, 8.0),    # TTD: alert fires in 2–8s
        (15.0, 45.0),  # TTR: pod restarts in 15–45s
    ),
    (
        "db-connection-exhaustion",
        "PostgreSQL connection pool exhausted (max_connections hit)",
        "resource-exhaustion",
        (3.0, 12.0),
        (20.0, 60.0),
    ),
    (
        "redis-node-failure",
        "Redis primary node killed, sentinel failover",
        "pod-kill",
        (5.0, 15.0),
        (30.0, 90.0),
    ),
    (
        "network-partition-50pct",
        "50% packet loss injected between mesh nodes",
        "network-loss",
        (4.0, 10.0),
        (25.0, 70.0),
    ),
    (
        "pqc-handshake-timeout",
        "ML-KEM key exchange times out under CPU stress",
        "cpu-stress",
        (6.0, 18.0),
        (40.0, 120.0),
    ),
    (
        "mape-k-analyzer-crash",
        "MAPE-K Analyzer process segfaults, self-restart",
        "process-crash",
        (1.0, 5.0),
        (10.0, 30.0),
    ),
    (
        "helm-deploy-rollback",
        "Bad chart revision deployed, auto-rollback triggered",
        "deploy-failure",
        (8.0, 20.0),
        (60.0, 180.0),
    ),
    (
        "xdp-prog-evicted",
        "XDP program evicted from kernel (BPF map limit)",
        "kernel-eviction",
        (2.0, 6.0),
        (12.0, 35.0),
    ),
    (
        "ebpf-exporter-down",
        "Prometheus exporter crashes, metrics gap detected",
        "process-crash",
        (10.0, 30.0),
        (15.0, 40.0),
    ),
    (
        "disk-pressure-eviction",
        "Node disk pressure evicts lowest-priority pods",
        "disk-pressure",
        (15.0, 28.0),
        (90.0, 240.0),
    ),
]


def _run_synthetic(scenario_def: Tuple) -> ScenarioResult:
    """Simulate a chaos scenario with realistic but fast (10x compressed) delays."""
    name, desc, fault_type, ttd_range, ttr_range = scenario_def

    # Compress time: divide by 10 for CI speed, but keep relative variation
    compress = 0.1
    ttd = random.uniform(*ttd_range) * compress
    ttr = random.uniform(*ttr_range) * compress

    # 95% heal rate (1 scenario probabilistically fails to recover)
    healed = random.random() < 0.95
    if not healed:
        ttr = SLO_TTR_S * 2  # simulate breach

    # Simulate actual work
    t0 = time.perf_counter()
    time.sleep(ttd)
    time.sleep(ttr)
    elapsed = time.perf_counter() - t0

    return ScenarioResult(
        name=name,
        description=desc,
        fault_type=fault_type,
        ttd_s=round(ttd / compress, 2),   # report realistic seconds
        ttr_s=round(ttr / compress, 2),
        healed=healed,
        notes=f"synthetic-ci (seed={RANDOM_SEED}, elapsed_wall={elapsed:.2f}s)",
    )


# ---------------------------------------------------------------------------
# Hardware chaos engine placeholder (MTTR_HW_MODE=1)
# ---------------------------------------------------------------------------

def _run_hardware(scenario_def: Tuple) -> ScenarioResult:
    """Run real chaos via kubectl/chaos-mesh. Requires a live cluster."""
    import subprocess
    name, desc, fault_type, ttd_range, ttr_range = scenario_def

    print(f"  [HW] Injecting fault: {fault_type} → {name}")
    # The actual injection would call:
    #   kubectl apply -f infra/chaos/{name}.yaml
    # and poll for recovery. This stub measures real wall time.
    t_inject = time.time()

    # TTD: poll health endpoint until first failure detected
    t_detect = None
    deadline = t_inject + ttd_range[1] * 3
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "x0tta6bl4",
                 "--field-selector=status.phase!=Running",
                 "--no-headers"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                t_detect = time.time()
                break
        except Exception:
            pass
        time.sleep(1)

    if t_detect is None:
        return ScenarioResult(
            name=name, description=desc, fault_type=fault_type,
            ttd_s=99.0, ttr_s=99.0, healed=False,
            notes="fault not detected within window",
        )

    ttd = t_detect - t_inject

    # TTR: poll until all pods Running again
    t_recover = None
    deadline = t_detect + SLO_TTR_S * 2
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "x0tta6bl4",
                 "--field-selector=status.phase!=Running",
                 "--no-headers"],
                capture_output=True, text=True, timeout=5,
            )
            if not result.stdout.strip():
                t_recover = time.time()
                break
        except Exception:
            pass
        time.sleep(2)

    if t_recover is None:
        return ScenarioResult(
            name=name, description=desc, fault_type=fault_type,
            ttd_s=round(ttd, 2), ttr_s=SLO_TTR_S * 2,
            healed=False, notes="recovery not detected within SLO window",
        )

    return ScenarioResult(
        name=name, description=desc, fault_type=fault_type,
        ttd_s=round(ttd, 2),
        ttr_s=round(t_recover - t_inject, 2),
        healed=True,
        notes="hardware-chaos-mesh",
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render_markdown(report: ChaosReport) -> str:
    s = report.summary
    ts = report.timestamp
    mode = report.mode.upper()

    lines = [
        f"# x0tta6bl4 MTTR Chaos Report",
        f"",
        f"**Generated:** {ts}  ",
        f"**Mode:** {mode}  ",
        f"**Seed:** {report.seed}  ",
        f"",
        f"## SLO Targets",
        f"| SLO | Target | Result |",
        f"|-----|--------|--------|",
        f"| MTTR (mean recovery) | ≤ {report.slo_mttr_s:.0f}s | **{s.get('mttr_s', '?'):.1f}s** — {_status(s.get('mttr_slo_pass', False))} |",
        f"| TTD (mean detection) | ≤ {report.slo_ttd_s:.0f}s | **{s.get('mttd_s', '?'):.1f}s** — {_status(s.get('ttd_slo_pass_all', False))} |",
        f"| TTR (all scenarios) | ≤ {report.slo_ttr_s:.0f}s | worst={s.get('worst_ttr_s', '?'):.1f}s — {_status(s.get('ttr_slo_pass_all', False))} |",
        f"",
        f"## Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total scenarios | {s.get('total_scenarios', 0)} |",
        f"| Healed | {s.get('healed', 0)} |",
        f"| Failed to heal | {s.get('failed_to_heal', 0)} |",
        f"| Heal rate | {s.get('heal_rate_pct', 0):.1f}% |",
        f"| MTTD | {s.get('mttd_s', 0):.1f}s |",
        f"| MTTR | {s.get('mttr_s', 0):.1f}s |",
        f"",
        f"## Scenario Results",
        f"| Scenario | Fault Type | TTD (s) | TTD SLO | TTR (s) | TTR SLO | Healed |",
        f"|----------|-----------|---------|---------|---------|---------|--------|",
    ]

    for sc in report.scenarios:
        ttd_ok = _status(sc.ttd_slo_pass)
        ttr_ok = _status(sc.ttr_slo_pass) if sc.healed else "N/A"
        healed = "YES" if sc.healed else "NO"
        lines.append(
            f"| {sc.name} | {sc.fault_type} | {sc.ttd_s:.1f} | {ttd_ok} | "
            f"{sc.ttr_s:.1f} | {ttr_ok} | {healed} |"
        )

    overall = s.get("mttr_slo_pass", False) and s.get("ttr_slo_pass_all", False)
    lines += [
        f"",
        f"## Overall Gate: {'**PASS**' if overall else '**FAIL**'}",
        f"",
        f"> MTTR={s.get('mttr_s', 0):.1f}s (SLO ≤{report.slo_mttr_s:.0f}s) | "
        f"Heal rate={s.get('heal_rate_pct', 0):.1f}%",
        f">",
        f"> _Mode: {mode}. Hardware PPS validation requires a live Kubernetes cluster._",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MTTR chaos report generator")
    parser.add_argument("--output", default="/tmp/mttr-chaos-report.json",
                        help="Path for JSON output")
    parser.add_argument("--markdown", default="/tmp/mttr-chaos-report.md",
                        help="Path for Markdown output")
    parser.add_argument("--scenarios", nargs="*",
                        help="Run only named scenarios (default: all)")
    args = parser.parse_args(argv)

    run_fn: Callable = _run_hardware if HW_MODE else _run_synthetic
    scenarios = _CI_SCENARIOS
    if args.scenarios:
        scenarios = [s for s in _CI_SCENARIOS if s[0] in args.scenarios]
        if not scenarios:
            print(f"No matching scenarios for: {args.scenarios}", file=sys.stderr)
            return 1

    report = ChaosReport()

    print(f"x0tta6bl4 MTTR Chaos Report — mode={report.mode}")
    print(f"Running {len(scenarios)} scenario(s)…\n")

    for defn in scenarios:
        name = defn[0]
        print(f"  [{name}]", end=" ", flush=True)
        result = run_fn(defn)
        report.scenarios.append(result)
        status = "HEALED" if result.healed else "UNHEALED"
        print(f"TTD={result.ttd_s:.1f}s TTR={result.ttr_s:.1f}s [{status}]")

    report.compute_summary()
    s = report.summary

    print(f"\nSummary: healed={s['healed']}/{s['total_scenarios']} "
          f"MTTD={s['mttd_s']:.1f}s MTTR={s['mttr_s']:.1f}s "
          f"SLO={'PASS' if s['mttr_slo_pass'] else 'FAIL'}")

    # Write JSON
    with open(args.output, "w") as f:
        json.dump(asdict(report), f, indent=2)
    print(f"\nJSON  → {args.output}")

    # Write Markdown
    md = render_markdown(report)
    with open(args.markdown, "w") as f:
        f.write(md)
    print(f"MD    → {args.markdown}")

    # Exit code: 0=pass, 2=SLO breach (same convention as bench report)
    if not s.get("mttr_slo_pass", True) or not s.get("ttr_slo_pass_all", True):
        print("\nSLO BREACH — see report for details", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
