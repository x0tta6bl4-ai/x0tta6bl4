#!/usr/bin/env python3
"""Verify the latest x0tta6bl4_pulse local evidence bundle.

This gate intentionally passes only the local experiment boundary. It fails if
the bundle claims stealth, whitelist, production, or kernel attach evidence that
was not explicitly collected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = ROOT / "docs" / "verification" / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"


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

    if data.get("schema") != "x0tta6bl4.ghost_pulse.local_evidence.v1":
        failures.append("unexpected schema")

    if data.get("decision") != "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED":
        failures.append(f"unexpected decision: {data.get('decision')}")

    claim_boundary = data.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "production_ready"):
        if claim_boundary.get(key) is not False:
            failures.append(f"claim_boundary.{key} must be false")
    if claim_boundary.get("kernel_attach_verified") is not False:
        failures.append("claim_boundary.kernel_attach_verified must be false")

    local_probe = data.get("local_probe", {})
    if local_probe.get("status") != "VERIFIED_LOCAL":
        failures.append("local_probe.status is not VERIFIED_LOCAL")

    transport_stats = local_probe.get("transport_stats", {})
    if transport_stats.get("evidence_status") != "EXPERIMENTAL_LOCAL_TIMING_PROFILE":
        failures.append("transport evidence_status is not experimental/local")
    if transport_stats.get("stealth_mode") != "NOT_VERIFIED":
        failures.append("transport stealth_mode must remain NOT_VERIFIED")
    if transport_stats.get("pulse_rng_seed") != local_probe.get("seed"):
        failures.append("transport pulse_rng_seed does not match local_probe.seed")
    timing_plan = transport_stats.get("timing_plan_summary", {})
    if not timing_plan:
        failures.append("timing_plan_summary is missing")
    elif timing_plan.get("samples_recorded", 0) < local_probe.get("packets_received", 0):
        failures.append("timing_plan_summary samples do not cover received packet count")
    timing_samples = transport_stats.get("timing_plan_samples", [])
    if not timing_samples:
        failures.append("timing_plan_samples is missing")
    elif len(timing_samples) < local_probe.get("packets_received", 0):
        failures.append("timing_plan_samples does not cover received packet count")
    if not transport_stats.get("timing_plan_samples_tail"):
        failures.append("timing_plan_samples_tail is missing")
    elif timing_samples and transport_stats["timing_plan_samples_tail"] != timing_samples[-10:]:
        failures.append("timing_plan_samples_tail does not match the full sample tail")

    replay = transport_stats.get("timing_plan_replay", {})
    if replay.get("status") != "LOCAL_SEED_REPLAYABLE":
        failures.append("timing_plan_replay.status is not LOCAL_SEED_REPLAYABLE")
    if replay.get("seed") != local_probe.get("seed"):
        failures.append("timing_plan_replay.seed does not match local_probe.seed")
    if replay.get("sample_count") != timing_plan.get("samples_recorded"):
        failures.append("timing_plan_replay.sample_count does not match timing_plan_summary.samples_recorded")
    if not replay.get("sha256"):
        failures.append("timing_plan_replay.sha256 is missing")
    elif timing_samples:
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from src.network.transport.pulse_transport import PulseUDPTransport

            if replay["sha256"] != PulseUDPTransport.timing_plan_replay_digest(timing_samples):
                failures.append("timing_plan_replay.sha256 does not match timing_plan_samples")
        except Exception as exc:  # pragma: no cover - surfaced as verifier failure
            failures.append(f"could not recompute timing_plan_replay.sha256: {exc}")

    baseline_probe = data.get("baseline_probe")
    comparison = data.get("timing_comparison", {})
    if baseline_probe:
        if baseline_probe.get("status") != "VERIFIED_LOCAL":
            failures.append("baseline_probe.status is not VERIFIED_LOCAL")
        if comparison.get("status") != "VERIFIED_LOCAL_COMPARISON":
            failures.append("timing comparison is not VERIFIED_LOCAL_COMPARISON")
        if comparison.get("mean_gap_delta_ms") is None:
            failures.append("timing comparison has no mean_gap_delta_ms")
        if comparison.get("mean_gap_ratio") is None:
            failures.append("timing comparison has no mean_gap_ratio")
        if comparison.get("sender_planned_mean_delay_ms") is None:
            failures.append("timing comparison has no sender_planned_mean_delay_ms")
    elif comparison.get("status") not in (None, "NOT_REQUESTED"):
        failures.append(f"unexpected comparison status without baseline: {comparison.get('status')}")

    static_object = data.get("static_artifacts", {}).get("object", {})
    if static_object.get("is_elf") is not True:
        failures.append("x0tta6bl4_pulse object is not an ELF artifact")

    gates = data.get("gates", {})
    for gate_name in ("python_compile", "ghost_core_shell_syntax"):
        if gates.get(gate_name, {}).get("status") != "PASS":
            failures.append(f"{gate_name} did not pass")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: local x0tta6bl4_pulse evidence is bounded and internally consistent")
    print(f"evidence={evidence_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
