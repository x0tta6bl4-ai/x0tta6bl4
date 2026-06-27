#!/usr/bin/env python3
"""Replay x0tta6bl4_pulse seed timing plans from bounded evidence artifacts.

This verifier checks deterministic sender-side timing plan fields only. It does
not validate wall-clock delivery gaps, DPI behavior, provider whitelists, kernel
attach state, or production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL = ROOT / "docs" / "verification" / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
DEFAULT_MATRIX = ROOT / "docs" / "verification" / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def replay_timing_plan(mode: str, seed: int, sample_count: int) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.network.transport.pulse_transport import PulseUDPTransport

    previous_mode = os.environ.get("PULSE_MODE")
    os.environ["PULSE_MODE"] = mode
    try:
        transport = PulseUDPTransport(
            local_host="127.0.0.1",
            local_port=0,
            traffic_profile="GHOST_PULSE",
            obfuscation="none",
            pulse_seed=seed,
        )
        samples: list[dict[str, Any]] = []
        for index in range(1, sample_count + 1):
            plan = transport.plan_next_delay()
            samples.append(
                {
                    "index": index,
                    "mode": transport.mode,
                    "profile_label": plan["profile_label"],
                    "next_profile_label": plan["next_profile_label"],
                    "mode_shift_roll": plan["mode_shift_roll"],
                    "mode_shifted": plan["mode_shifted"],
                    "planned_delay_ms": plan["planned_delay"] * 1000.0,
                }
            )
        return {
            "sample_count": len(samples),
            "sha256": PulseUDPTransport.timing_plan_replay_digest(samples),
            "projection": PulseUDPTransport.timing_plan_replay_projection(samples),
        }
    finally:
        if previous_mode is None:
            os.environ.pop("PULSE_MODE", None)
        else:
            os.environ["PULSE_MODE"] = previous_mode


def verify_local(path: Path) -> list[str]:
    data = load_json(path)
    failures: list[str] = []

    local_probe = data.get("local_probe", {})
    stats = local_probe.get("transport_stats", {})
    replay = stats.get("timing_plan_replay", {})
    samples = stats.get("timing_plan_samples", [])

    mode = local_probe.get("mode")
    seed = local_probe.get("seed")
    sample_count = replay.get("sample_count")
    if mode not in ("corporate", "whitelist"):
        failures.append(f"local mode is not replayable: {mode}")
    if not isinstance(seed, int):
        failures.append("local seed is missing or not an integer")
    if not isinstance(sample_count, int) or sample_count < 1:
        failures.append("local timing_plan_replay.sample_count is missing")
    if replay.get("status") != "LOCAL_SEED_REPLAYABLE":
        failures.append("local timing_plan_replay.status is not LOCAL_SEED_REPLAYABLE")
    if replay.get("seed") != seed:
        failures.append("local timing_plan_replay.seed does not match local seed")
    if len(samples) != sample_count:
        failures.append("local timing_plan_samples length does not match replay sample_count")

    if not failures:
        expected = replay_timing_plan(mode=mode, seed=seed, sample_count=sample_count)
        if replay.get("sha256") != expected["sha256"]:
            failures.append("local replay sha256 does not match seed replay")

    return [f"{display_path(path)}: {failure}" for failure in failures]


def verify_matrix(path: Path) -> list[str]:
    data = load_json(path)
    failures: list[str] = []

    for idx, row in enumerate(data.get("runs", [])):
        mode = row.get("mode")
        seed = row.get("seed")
        sample_count = row.get("timing_plan_replay_samples")
        if mode not in ("corporate", "whitelist"):
            failures.append(f"run {idx}: mode is not replayable: {mode}")
            continue
        if not isinstance(seed, int):
            failures.append(f"run {idx}: seed is missing or not an integer")
            continue
        if row.get("pulse_rng_seed") != seed:
            failures.append(f"run {idx}: pulse_rng_seed does not match seed")
        if row.get("timing_plan_replay_seed") != seed:
            failures.append(f"run {idx}: timing_plan_replay_seed does not match seed")
        if row.get("timing_plan_replay_status") != "LOCAL_SEED_REPLAYABLE":
            failures.append(f"run {idx}: timing_plan_replay_status is not LOCAL_SEED_REPLAYABLE")
        if not isinstance(sample_count, int) or sample_count < 1:
            failures.append(f"run {idx}: timing_plan_replay_samples is missing")
            continue

        expected = replay_timing_plan(mode=mode, seed=seed, sample_count=sample_count)
        if row.get("timing_plan_replay_sha256") != expected["sha256"]:
            failures.append(f"run {idx}: replay sha256 does not match seed replay")

    if not data.get("runs"):
        failures.append("matrix runs are missing")

    return [f"{display_path(path)}: {failure}" for failure in failures]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-evidence", type=Path, default=DEFAULT_LOCAL)
    parser.add_argument("--profile-matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    local_path = args.local_evidence if args.local_evidence.is_absolute() else ROOT / args.local_evidence
    matrix_path = args.profile_matrix if args.profile_matrix.is_absolute() else ROOT / args.profile_matrix

    if not args.skip_local:
        if not local_path.exists():
            failures.append(f"local evidence file not found: {local_path}")
        else:
            failures.extend(verify_local(local_path))

    if not args.skip_matrix:
        if not matrix_path.exists():
            failures.append(f"profile matrix file not found: {matrix_path}")
        else:
            failures.extend(verify_matrix(matrix_path))

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    checked = []
    if not args.skip_local:
        checked.append(display_path(local_path))
    if not args.skip_matrix:
        checked.append(display_path(matrix_path))
    print("PASS: x0tta6bl4_pulse seed replay digests match evidence artifacts")
    print("checked=" + ", ".join(checked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
