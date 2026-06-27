#!/usr/bin/env python3
"""Collect baseline-vs-pulse timing comparison evidence.

This collector runs bounded loopback probes only: one unshaped UDP baseline and
one experimental pulse transport run. It writes deterministic event digests and
marks the baseline_timing_comparison claim VERIFIED only when both local probes
deliver packets and produce comparable timing artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_BASELINE_COMPARISON_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_BASELINE_COMPARISON_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
CLAIM_ID = "baseline_timing_comparison"
STATUS_VERIFIED = "VERIFIED"
STATUS_INCOMPLETE = "INCOMPLETE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_cmd(root: Path, args: list[str], timeout: float = 20.0) -> dict[str, Any]:
    executable = args[0]
    if executable != sys.executable and not shutil.which(executable):
        return {
            "args": args,
            "available": False,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{executable} not found",
        }
    try:
        proc = subprocess.run(
            args,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "args": args,
            "available": True,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "available": True,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
        }


def load_local_collector():
    path = ROOT / "scripts" / "ops" / "collect_ghost_pulse_local_evidence.py"
    spec = importlib.util.spec_from_file_location("collect_ghost_pulse_local_evidence_for_baseline", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")


def artifact_record(root: Path, path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": display_path(root, path),
        "sha256": sha256_file(path),
    }


def comparable_sample_count(pulse_probe: dict[str, Any], baseline_probe: dict[str, Any]) -> int:
    pulse_gaps = pulse_probe.get("event_summary", {}).get("inter_packet_gap_ms", {}).get("count")
    baseline_gaps = baseline_probe.get("event_summary", {}).get("inter_packet_gap_ms", {}).get("count")
    if not isinstance(pulse_gaps, int) or not isinstance(baseline_gaps, int):
        return 0
    return min(pulse_gaps, baseline_gaps)


def render_markdown(report: dict[str, Any]) -> str:
    measurements = report["measurements"]
    comparison = report["comparison"]
    lines = [
        "# x0tta6bl4_pulse Baseline Timing Comparison Evidence",
        "",
        f"Observed at: `{report['observed_at_utc']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Scope",
        "",
        "- Local loopback timing comparison only.",
        "- Baseline is unshaped UDP; pulse is the experimental pulse transport.",
        "- No DPI, whitelist, kernel attach, or production-readiness claim.",
        "",
        "## Measurements",
        "",
        f"- Sample count: `{measurements['sample_count']}`",
        f"- Baseline digest: `{measurements['baseline_digest']}`",
        f"- Pulse digest: `{measurements['pulse_digest']}`",
        f"- Comparison passed: `{measurements['comparison_passed']}`",
        f"- Baseline mean gap ms: `{comparison['baseline_mean_gap_ms']}`",
        f"- Pulse mean gap ms: `{comparison['pulse_mean_gap_ms']}`",
        "",
        "## Failures",
        "",
    ]
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


async def collect_report(root: Path, packet_count: int, mode: str, seed: int) -> dict[str, Any]:
    observed_at = utc_now()
    stamp = datetime.fromisoformat(observed_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-baseline-comparison-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        run_cmd(root, ["uname", "-r"], 5.0),
        run_cmd(
            root,
            [
                sys.executable,
                "-m",
                "py_compile",
                "scripts/ops/collect_ghost_pulse_local_evidence.py",
                "src/network/transport/pulse_transport.py",
                "src/network/transport/udp_shaped.py",
            ],
            20.0,
        ),
    ]

    local = load_local_collector()
    baseline_probe = await local.run_baseline_probe(packet_count, seed + 1)
    pulse_probe = await local.run_local_probe(packet_count, mode, seed, None)

    baseline_events_path = bundle_dir / "baseline-events.jsonl"
    pulse_events_path = bundle_dir / "pulse-events.jsonl"
    comparison_path = bundle_dir / "comparison.json"
    write_jsonl(baseline_events_path, baseline_probe["packet_events"])
    write_jsonl(pulse_events_path, pulse_probe["packet_events"])

    sample_count = comparable_sample_count(pulse_probe, baseline_probe)
    baseline_digest = sha256_file(baseline_events_path)
    pulse_digest = sha256_file(pulse_events_path)
    pulse_replay = pulse_probe.get("transport_stats", {}).get("timing_plan_replay", {})
    baseline_gap = baseline_probe.get("event_summary", {}).get("inter_packet_gap_ms", {}).get("mean")
    pulse_gap = pulse_probe.get("event_summary", {}).get("inter_packet_gap_ms", {}).get("mean")
    comparison = {
        "baseline_status": baseline_probe.get("status"),
        "pulse_status": pulse_probe.get("status"),
        "baseline_packets_received": baseline_probe.get("packets_received"),
        "pulse_packets_received": pulse_probe.get("packets_received"),
        "baseline_mean_gap_ms": baseline_gap,
        "pulse_mean_gap_ms": pulse_gap,
        "pulse_timing_replay_status": pulse_replay.get("status"),
        "pulse_timing_replay_sha256": pulse_replay.get("sha256"),
    }

    failures: list[str] = []
    if baseline_probe.get("status") != "VERIFIED_LOCAL":
        failures.append(f"baseline probe status is {baseline_probe.get('status')}")
    if pulse_probe.get("status") != "VERIFIED_LOCAL":
        failures.append(f"pulse probe status is {pulse_probe.get('status')}")
    if sample_count <= 0:
        failures.append("no comparable inter-packet timing samples")
    if not baseline_digest:
        failures.append("baseline digest is missing")
    if not pulse_digest:
        failures.append("pulse digest is missing")
    if pulse_replay.get("status") != "LOCAL_SEED_REPLAYABLE":
        failures.append("pulse timing plan replay is not LOCAL_SEED_REPLAYABLE")
    for command in commands:
        if command.get("exit_code") != 0:
            failures.append(f"command failed: {' '.join(str(part) for part in command.get('args', []))}")

    comparison_passed = not failures
    measurements = {
        "sample_count": sample_count,
        "baseline_digest": baseline_digest,
        "pulse_digest": pulse_digest,
        "comparison_passed": comparison_passed,
    }
    comparison_path.write_text(
        json.dumps(
            {
                "measurements": measurements,
                "comparison": comparison,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    status = STATUS_VERIFIED if comparison_passed else STATUS_INCOMPLETE
    return {
        "schema": SCHEMA,
        "claim_id": CLAIM_ID,
        "status": status,
        "observed_at_utc": observed_at,
        "simulated": False,
        "dry_run": False,
        "template": False,
        "mode": "LOCAL_LOOPBACK_BASELINE_VS_PULSE",
        "commands": commands,
        "artifacts": [
            artifact_record(root, baseline_events_path, "baseline_events"),
            artifact_record(root, pulse_events_path, "pulse_events"),
            artifact_record(root, comparison_path, "timing_comparison"),
        ],
        "measurements": measurements,
        "comparison": comparison,
        "failures": failures,
        "bundle": display_path(root, bundle_dir),
        "claim_boundary": {
            "baseline_timing_comparison_verified": status == STATUS_VERIFIED,
            "note": "Local loopback timing comparison only; this is not DPI, whitelist, kernel attach, or production evidence.",
        },
    }


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    bundle_dir = root / report["bundle"]
    bundle_json = bundle_dir / "evidence.json"
    bundle_md = bundle_dir / "summary.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)
    bundle_json.write_text(rendered_json, encoding="utf-8")
    bundle_md.write_text(rendered_md, encoding="utf-8")
    output_json.write_text(rendered_json, encoding="utf-8")
    output_md.write_text(rendered_md, encoding="utf-8")
    return {
        "bundle_dir": bundle_dir,
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": output_json,
        "latest_md": output_md,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--packet-count", type=int, default=12)
    parser.add_argument("--mode", choices=("corporate", "whitelist"), default="corporate")
    parser.add_argument("--seed", type=int, default=20260522)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)
    if args.packet_count < 2:
        parser.error("--packet-count must be >= 2")
    if args.packet_count > 200:
        parser.error("--packet-count must be <= 200 for bounded local evidence")

    root = args.root.resolve()
    report = asyncio.run(collect_report(root, args.packet_count, args.mode, args.seed))
    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
    paths = write_report_outputs(root, report, output_json, output_md)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "bundle": report["bundle"],
                    "output_json": display_path(root, paths["latest_json"]),
                    "output_md": display_path(root, paths["latest_md"]),
                    "failures": report["failures"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    if args.require_verified and report["status"] != STATUS_VERIFIED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
