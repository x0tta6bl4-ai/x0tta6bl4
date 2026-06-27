#!/usr/bin/env python3
"""Verify the latest x0tta6bl4_pulse profile matrix evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = ROOT / "docs" / "verification" / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()

    evidence_path = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    if not evidence_path.exists():
        print(f"FAIL: evidence file not found: {evidence_path}", file=sys.stderr)
        return 2

    data = load_json(evidence_path)
    failures: list[str] = []

    if data.get("schema") != "x0tta6bl4.ghost_pulse.profile_matrix.v1":
        failures.append("unexpected schema")

    if data.get("decision") != "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED":
        failures.append(f"unexpected decision: {data.get('decision')}")

    claim_boundary = data.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "production_ready", "kernel_attach_verified"):
        if claim_boundary.get(key) is not False:
            failures.append(f"claim_boundary.{key} must be false")

    gates = data.get("gates", {})
    for gate_name in ("python_compile", "ghost_core_shell_syntax"):
        if gates.get(gate_name, {}).get("status") != "PASS":
            failures.append(f"{gate_name} did not pass")

    static_object = data.get("static_artifacts", {}).get("object", {})
    if static_object.get("is_elf") is not True:
        failures.append("x0tta6bl4_pulse object is not an ELF artifact")

    aggregates = data.get("aggregates", {})
    if not aggregates:
        failures.append("aggregates are missing")
    for mode, aggregate in aggregates.items():
        if aggregate.get("all_runs_successful") is not True:
            failures.append(f"{mode} aggregate does not have all runs successful")
        if aggregate.get("successful_runs") != aggregate.get("runs"):
            failures.append(f"{mode} successful_runs does not match runs")
        if aggregate.get("replayable_runs") != aggregate.get("runs"):
            failures.append(f"{mode} replayable_runs does not match runs")
        if aggregate.get("mean_gap_ratio", {}).get("mean") is None:
            failures.append(f"{mode} mean_gap_ratio is missing")
        if aggregate.get("sender_planned_mean_delay_ms", {}).get("mean") is None:
            failures.append(f"{mode} sender_planned_mean_delay_ms is missing")

    runs = data.get("runs", [])
    expected_runs = data.get("parameters", {}).get("repetitions", 0) * len(data.get("parameters", {}).get("modes", []))
    if len(runs) != expected_runs:
        failures.append(f"run count mismatch: got {len(runs)}, expected {expected_runs}")
    for idx, row in enumerate(runs):
        if row.get("pulse_status") != "VERIFIED_LOCAL":
            failures.append(f"run {idx} pulse_status is not VERIFIED_LOCAL")
        if row.get("baseline_status") != "VERIFIED_LOCAL":
            failures.append(f"run {idx} baseline_status is not VERIFIED_LOCAL")
        if row.get("comparison_status") != "VERIFIED_LOCAL_COMPARISON":
            failures.append(f"run {idx} comparison_status is not VERIFIED_LOCAL_COMPARISON")
        if row.get("pulse_rng_seed") != row.get("seed"):
            failures.append(f"run {idx} pulse_rng_seed does not match seed")
        if row.get("timing_plan_replay_status") != "LOCAL_SEED_REPLAYABLE":
            failures.append(f"run {idx} timing_plan_replay_status is not LOCAL_SEED_REPLAYABLE")
        if row.get("timing_plan_replay_seed") != row.get("seed"):
            failures.append(f"run {idx} timing_plan_replay_seed does not match seed")
        if not row.get("timing_plan_replay_sha256"):
            failures.append(f"run {idx} timing_plan_replay_sha256 is missing")
        if row.get("sender_planned_mean_delay_ms") is None:
            failures.append(f"run {idx} sender_planned_mean_delay_ms is missing")
        if row.get("timing_plan_samples_recorded", 0) < row.get("pulse_received", 0):
            failures.append(f"run {idx} timing plan samples do not cover pulse packets")
        if row.get("timing_plan_replay_samples") != row.get("timing_plan_samples_recorded"):
            failures.append(f"run {idx} timing_plan_replay_samples does not match samples recorded")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: local x0tta6bl4_pulse profile matrix is bounded and internally consistent")
    print(f"evidence={evidence_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
