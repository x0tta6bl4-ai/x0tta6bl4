#!/usr/bin/env python3
"""Run a repeated local profile matrix for x0tta6bl4_pulse.

The matrix compares the experimental pulse timing profiles against an unshaped
UDP loopback baseline across repeated runs. It is a local statistical
experiment only; it does not prove DPI evasion, third-party whitelist behavior,
kernel attach, or production readiness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import collect_ghost_pulse_local_evidence as pulse_evidence


ROOT = pulse_evidence.ROOT
VERIFY_ROOT = pulse_evidence.VERIFY_ROOT


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def summarize_numbers(values: list[float | int | None]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    return {
        "count": len(clean),
        "min": min(clean) if clean else None,
        "max": max(clean) if clean else None,
        "mean": statistics.fmean(clean) if clean else None,
        "stdev": statistics.pstdev(clean) if len(clean) > 1 else 0.0,
    }


def aggregate_mode(mode: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    success_rows = [
        row
        for row in rows
        if row["pulse_status"] == "VERIFIED_LOCAL"
        and row["baseline_status"] == "VERIFIED_LOCAL"
        and row["comparison_status"] == "VERIFIED_LOCAL_COMPARISON"
    ]
    return {
        "mode": mode,
        "runs": len(rows),
        "successful_runs": len(success_rows),
        "all_runs_successful": len(rows) == len(success_rows),
        "pulse_mean_gap_ms": summarize_numbers([row["pulse_mean_gap_ms"] for row in rows]),
        "sender_planned_mean_delay_ms": summarize_numbers(
            [row["sender_planned_mean_delay_ms"] for row in rows]
        ),
        "sender_actual_mean_gap_ms": summarize_numbers(
            [row["sender_actual_mean_gap_ms"] for row in rows]
        ),
        "baseline_mean_gap_ms": summarize_numbers([row["baseline_mean_gap_ms"] for row in rows]),
        "mean_gap_delta_ms": summarize_numbers([row["mean_gap_delta_ms"] for row in rows]),
        "mean_gap_ratio": summarize_numbers([row["mean_gap_ratio"] for row in rows]),
        "replayable_runs": sum(
            1
            for row in rows
            if row.get("timing_plan_replay_status") == "LOCAL_SEED_REPLAYABLE"
            and row.get("timing_plan_replay_sha256")
        ),
        "claim_boundary": (
            "Aggregate local timing comparison only; do not use as DPI, "
            "whitelist, kernel attach, or production evidence."
        ),
    }


async def run_matrix(args: argparse.Namespace) -> int:
    stamp = utc_stamp()
    bundle_dir = VERIFY_ROOT / f"ghost-pulse-profile-matrix-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    py_compile = pulse_evidence.run_cmd(
        [
            sys.executable,
            "-m",
            "py_compile",
            "scripts/ops/collect_ghost_pulse_local_evidence.py",
            "scripts/ops/run_ghost_pulse_profile_matrix.py",
            "src/network/transport/pulse_transport.py",
            "src/network/obfuscation/whitelist_mimicry.py",
            "src/network/mesh_node_complete.py",
        ],
        timeout=30,
    )
    shell_syntax = pulse_evidence.run_cmd(["bash", "-n", "scripts/ghost-core.sh"], timeout=10)
    static = pulse_evidence.static_artifact_evidence()
    kernel = pulse_evidence.kernel_read_only_evidence()

    rows: list[dict[str, Any]] = []
    for mode in args.modes:
        for repetition in range(args.repetitions):
            seed = args.seed + (1000 * len(rows))
            pulse_probe = await pulse_evidence.run_local_probe(
                packet_count=args.packet_count,
                mode=mode,
                seed=seed,
            )
            baseline_probe = await pulse_evidence.run_baseline_probe(
                packet_count=args.packet_count,
                seed=seed + 1,
            )
            comparison = pulse_evidence.build_timing_comparison(pulse_probe, baseline_probe)
            timing_plan = pulse_probe.get("transport_stats", {}).get("timing_plan_summary", {})
            replay = pulse_probe.get("transport_stats", {}).get("timing_plan_replay", {})
            rows.append(
                {
                    "mode": mode,
                    "repetition": repetition,
                    "seed": seed,
                    "pulse_status": pulse_probe["status"],
                    "baseline_status": baseline_probe["status"],
                    "comparison_status": comparison["status"],
                    "pulse_rng_seed": pulse_probe["transport_stats"].get("pulse_rng_seed"),
                    "pulse_received": pulse_probe["packets_received"],
                    "baseline_received": baseline_probe["packets_received"],
                    "timing_plan_replay_status": replay.get("status"),
                    "timing_plan_replay_seed": replay.get("seed"),
                    "timing_plan_replay_samples": replay.get("sample_count"),
                    "timing_plan_replay_sha256": replay.get("sha256"),
                    "pulse_mean_gap_ms": comparison["pulse_mean_gap_ms"],
                    "sender_planned_mean_delay_ms": comparison["sender_planned_mean_delay_ms"],
                    "sender_actual_mean_gap_ms": comparison["sender_actual_mean_gap_ms"],
                    "sender_relative_error_mean": comparison["sender_relative_error_mean"],
                    "baseline_mean_gap_ms": comparison["baseline_mean_gap_ms"],
                    "mean_gap_delta_ms": comparison["mean_gap_delta_ms"],
                    "mean_gap_ratio": comparison["mean_gap_ratio"],
                    "pulse_gap_stdev_ms": pulse_probe["event_summary"]["inter_packet_gap_ms"]["stdev"],
                    "baseline_gap_stdev_ms": baseline_probe["event_summary"]["inter_packet_gap_ms"]["stdev"],
                    "timing_plan_samples_recorded": timing_plan.get("samples_recorded"),
                }
            )

    aggregates = {
        mode: aggregate_mode(mode, [row for row in rows if row["mode"] == mode])
        for mode in args.modes
    }

    all_runs_successful = all(item["all_runs_successful"] for item in aggregates.values())
    static_pass = static["status"] == "STATIC_OBJECT_PRESENT"
    syntax_pass = py_compile.get("returncode") == 0 and shell_syntax.get("returncode") == 0
    decision = (
        "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED"
        if all_runs_successful and static_pass and syntax_pass
        else "PROFILE_MATRIX_INCOMPLETE"
    )

    evidence = {
        "schema": "x0tta6bl4.ghost_pulse.profile_matrix.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bundle": str(bundle_dir.relative_to(ROOT)),
        "decision": decision,
        "parameters": {
            "modes": args.modes,
            "repetitions": args.repetitions,
            "packet_count": args.packet_count,
            "seed": args.seed,
        },
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "production_ready": False,
            "kernel_attach_verified": False,
            "kernel_read_only_visible": kernel["status"] == "KERNEL_EVIDENCE_VISIBLE_READ_ONLY",
        },
        "gates": {
            "python_compile": {
                "status": pulse_evidence.gate_status(py_compile),
                "command": py_compile,
            },
            "ghost_core_shell_syntax": {
                "status": pulse_evidence.gate_status(shell_syntax),
                "command": shell_syntax,
            },
        },
        "static_artifacts": static,
        "kernel_read_only": kernel,
        "aggregates": aggregates,
        "runs": rows,
    }

    matrix_json = bundle_dir / "matrix.json"
    runs_jsonl = bundle_dir / "matrix-runs.jsonl"
    summary_md = bundle_dir / "summary.md"
    matrix_json.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    with runs_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    summary_md.write_text(render_summary(evidence), encoding="utf-8")

    latest_json = VERIFY_ROOT / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
    latest_md = VERIFY_ROOT / "GHOST_PULSE_PROFILE_MATRIX_LATEST.md"
    latest_json.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    latest_md.write_text(summary_md.read_text(encoding="utf-8"), encoding="utf-8")

    print(
        json.dumps(
            {
                "decision": decision,
                "bundle": str(bundle_dir.relative_to(ROOT)),
                "matrix": str(matrix_json.relative_to(ROOT)),
                "summary": str(summary_md.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if decision == "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED" else 1


def render_summary(evidence: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Profile Matrix",
        "",
        f"Timestamp: `{evidence['timestamp_utc']}`",
        "",
        f"Decision: `{evidence['decision']}`",
        "",
        "## What This Proves",
        "",
        "- Repeated local loopback timing runs completed for the selected profiles.",
        "- Each selected profile was compared with an unshaped UDP negative control.",
        "- Each row records a seed replay digest for deterministic sender-side timing fields.",
        "- Static eBPF artifacts and read-only kernel status were recorded.",
        "",
        "## What This Does Not Prove",
        "",
        "- No DPI bypass claim.",
        "- No VK/Yandex/Teams whitelist claim.",
        "- No production-readiness claim.",
        "- No kernel attach claim.",
        "",
        "## Aggregates",
        "",
        "| Mode | Runs | Successful | Replayable | Planned mean ms | Pulse mean gap ms | Baseline mean gap ms | Ratio mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, aggregate in evidence["aggregates"].items():
        lines.append(
            "| {mode} | {runs} | {successful_runs} | {replayable_runs} | {planned_gap} | {pulse_gap} | {baseline_gap} | {ratio} |".format(
                mode=mode,
                runs=aggregate["runs"],
                successful_runs=aggregate["successful_runs"],
                replayable_runs=aggregate["replayable_runs"],
                planned_gap=aggregate["sender_planned_mean_delay_ms"]["mean"],
                pulse_gap=aggregate["pulse_mean_gap_ms"]["mean"],
                baseline_gap=aggregate["baseline_mean_gap_ms"]["mean"],
                ratio=aggregate["mean_gap_ratio"]["mean"],
            )
        )
    lines.extend(
        [
            "",
            "## Kernel Read-Only Status",
            "",
            f"- Status: `{evidence['kernel_read_only']['status']}`",
            f"- pulse_stats map present: `{evidence['kernel_read_only']['pulse_map_present']}`",
            f"- pulse program visible: `{evidence['kernel_read_only']['pulse_prog_visible']}`",
            "",
            "Raw JSON: `matrix.json`",
            "Rows: `matrix-runs.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-count", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--modes", nargs="+", choices=("corporate", "whitelist"), default=["corporate", "whitelist"])
    parser.add_argument("--seed", type=int, default=20260522)
    args = parser.parse_args()
    if args.packet_count < 2:
        parser.error("--packet-count must be >= 2")
    if args.packet_count > 100:
        parser.error("--packet-count must be <= 100 for a bounded matrix run")
    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")
    if args.repetitions > 10:
        parser.error("--repetitions must be <= 10 for a bounded matrix run")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_matrix(parse_args())))
