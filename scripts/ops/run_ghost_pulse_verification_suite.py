#!/usr/bin/env python3
"""Run the bounded x0tta6bl4_pulse verification suite.

The suite validates the latest local pulse evidence, profile matrix, and seed
replay artifacts. It is intentionally repo-local: it does not send packets,
attach eBPF programs, mutate routes, touch VPN/runtime services, or promote any
stealth, whitelist, kernel attach, or production claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_LOCAL = VERIFY_ROOT / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
DEFAULT_MATRIX = VERIFY_ROOT / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.md"

DECISION_PASS = "GHOST_PULSE_VERIFICATION_SUITE_VERIFIED_STEALTH_NOT_VERIFIED"
DECISION_FAIL = "GHOST_PULSE_VERIFICATION_SUITE_INCOMPLETE"
GATE_DISPLAY_ORDER = (
    "local_evidence_verifier",
    "profile_matrix_verifier",
    "seed_replay_verifier",
    "python_compile",
    "ghost_core_shell_syntax",
    "false_claim_scan",
    "artifact_integrity",
    "incoming_gap_candidates_verifier",
    "command_gates",
)
REQUIRED_ARTIFACT_INTEGRITY_CHECKS = (
    "local_latest_vs_bundle_json",
    "local_latest_vs_bundle_md",
    "matrix_latest_vs_bundle_json",
    "matrix_latest_vs_bundle_md",
)

KERNEL_ATTACH_VERIFIED_TRUE_PATTERN = re.compile(
    r"\bkernel_attach_verified\b[\"']?\s*[:=]\s*true\b",
    re.IGNORECASE,
)
KERNEL_ATTACH_PROOF_DERIVED_TARGETS = {
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md",
}

FALSE_CLAIM_PATTERNS = [
    re.compile(r"\bstealth_verified\b[\"']?\s*[:=]\s*true\b", re.IGNORECASE),
    re.compile(r"\bwhitelist_verified\b[\"']?\s*[:=]\s*true\b", re.IGNORECASE),
    re.compile(r"\bproduction_ready\b[\"']?\s*[:=]\s*true\b", re.IGNORECASE),
    KERNEL_ATTACH_VERIFIED_TRUE_PATTERN,
    re.compile(r"ADAPTATION COMPLETE|READY FOR PRODUCTION|unblockable", re.IGNORECASE),
    re.compile(r"невидим|неуязвим", re.IGNORECASE),
    re.compile(r"98\.4"),
]

FALSE_CLAIM_SCAN_REL_PATHS = (
    "src/network/transport/pulse_transport.py",
    "src/network/obfuscation/whitelist_mimicry.py",
    "scripts/ops/collect_ghost_pulse_local_evidence.py",
    "scripts/ops/run_ghost_pulse_profile_matrix.py",
    "scripts/ops/verify_ghost_pulse_local_evidence.py",
    "scripts/ops/verify_ghost_pulse_profile_matrix.py",
    "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    "scripts/ops/verify_ghost_pulse_rng_replay.py",
    "scripts/ops/verify_ghost_pulse_verification_suite.py",
    "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    "scripts/ops/collect_ghost_pulse_packet_capture_evidence.py",
    "scripts/ops/collect_ghost_pulse_baseline_comparison_evidence.py",
    "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    "scripts/ops/import_ghost_pulse_external_evidence.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    "scripts/ops/verify_ghost_pulse_external_evidence.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    "scripts/ops/verify_ghost_pulse_proof_gate.py",
    "scripts/ops/verify_ghost_pulse_goal_state.py",
    "scripts/ops/run_ghost_pulse_proof_gate.py",
    "scripts/ops/run_ghost_pulse_verification_suite.py",
    "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md",
    "docs/verification/ghost-core-pulse-claim-audit-2026-05-21.md",
    "docs/verification/gemini-ghost-core-vv-audit-2026-05-20.md",
    "docs/verification/ghost-pulse-local-evidence-runbook.md",
    "docs/verification/ghost-pulse-profile-matrix-runbook.md",
    "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json",
    "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.md",
    "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json",
    "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.md",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md",
    "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.json",
    "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.md",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_cmd(root: Path, args: list[str], timeout: float = 30.0) -> dict[str, Any]:
    executable = args[0]
    if executable != sys.executable and not shutil.which(executable):
        return {
            "args": args,
            "available": False,
            "returncode": None,
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
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "available": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
        }


def command_status(result: dict[str, Any]) -> str:
    if result.get("available") is False:
        return "TOOL_MISSING"
    return "PASS" if result.get("returncode") == 0 else "FAIL"


def file_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": display_path(root, path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path),
    }


def compare_files(root: Path, left: Path, right: Path) -> dict[str, Any]:
    left_record = file_record(root, left)
    right_record = file_record(root, right)
    return {
        "left": left_record,
        "right": right_record,
        "match": (
            left_record["exists"]
            and right_record["exists"]
            and left_record["sha256"] == right_record["sha256"]
        ),
    }


def artifact_integrity_check_paths(
    root: Path,
    local_path: Path,
    local: dict[str, Any],
    matrix_path: Path,
    matrix: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    failures: list[str] = []
    paths: dict[str, dict[str, str]] = {}

    local_bundle = local.get("bundle")
    matrix_bundle = matrix.get("bundle")
    if not local_bundle:
        failures.append("local bundle path is missing")
    if not matrix_bundle:
        failures.append("matrix bundle path is missing")

    if local_bundle:
        bundle_dir = root / local_bundle
        paths["local_latest_vs_bundle_json"] = {
            "left": display_path(root, local_path),
            "right": display_path(root, bundle_dir / "evidence.json"),
        }
        paths["local_latest_vs_bundle_md"] = {
            "left": display_path(root, local_path.with_suffix(".md")),
            "right": display_path(root, bundle_dir / "summary.md"),
        }
    if matrix_bundle:
        bundle_dir = root / matrix_bundle
        paths["matrix_latest_vs_bundle_json"] = {
            "left": display_path(root, matrix_path),
            "right": display_path(root, bundle_dir / "matrix.json"),
        }
        paths["matrix_latest_vs_bundle_md"] = {
            "left": display_path(root, matrix_path.with_suffix(".md")),
            "right": display_path(root, bundle_dir / "summary.md"),
        }

    return paths, failures


def artifact_integrity_policy(check_paths: dict[str, dict[str, str]]) -> dict[str, Any]:
    encoded_checks = [
        {
            "name": name,
            "left": check_paths[name]["left"],
            "right": check_paths[name]["right"],
        }
        for name in REQUIRED_ARTIFACT_INTEGRITY_CHECKS
        if name in check_paths
    ]
    encoded = json.dumps(encoded_checks, sort_keys=True, separators=(",", ":")) + "\n"
    return {
        "mode": "required_latest_bundle_path_pairs",
        "required": True,
        "check_count": len(encoded_checks),
        "sha256": sha256_text(encoded),
    }


def artifact_integrity_gate(
    root: Path,
    local_path: Path,
    local: dict[str, Any],
    matrix_path: Path,
    matrix: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    check_paths, failures = artifact_integrity_check_paths(
        root,
        local_path,
        local,
        matrix_path,
        matrix,
    )
    for name in REQUIRED_ARTIFACT_INTEGRITY_CHECKS:
        if name not in check_paths:
            continue
        pair = check_paths[name]
        checks[name] = compare_files(root, root / pair["left"], root / pair["right"])

    for name, check in checks.items():
        if not check.get("match"):
            failures.append(f"{name} hash mismatch or missing artifact")

    return {
        "status": "PASS" if not failures else "FAIL",
        "policy": artifact_integrity_policy(check_paths),
        "checks": checks,
        "failures": failures,
        "claim_boundary": "Artifact hash consistency only; this is not network, DPI, or production evidence.",
    }


def claim_boundary_failures(payload: dict[str, Any], label: str) -> list[str]:
    failures: list[str] = []
    claim_boundary = payload.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "production_ready", "kernel_attach_verified"):
        if claim_boundary.get(key) is not False:
            failures.append(f"{label}.claim_boundary.{key} must be false")
    return failures


def artifact_summary(local: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    local_probe = local.get("local_probe", {})
    local_stats = local_probe.get("transport_stats", {})
    local_replay = local_stats.get("timing_plan_replay", {})
    matrix_runs = matrix.get("runs", [])
    matrix_replayable = [
        row
        for row in matrix_runs
        if row.get("timing_plan_replay_status") == "LOCAL_SEED_REPLAYABLE"
        and row.get("timing_plan_replay_sha256")
    ]
    return {
        "local": {
            "decision": local.get("decision"),
            "mode": local_probe.get("mode"),
            "seed": local_probe.get("seed"),
            "pulse_rng_seed": local_stats.get("pulse_rng_seed"),
            "packets_received": local_probe.get("packets_received"),
            "replay_status": local_replay.get("status"),
            "replay_sample_count": local_replay.get("sample_count"),
            "replay_sha256": local_replay.get("sha256"),
        },
        "matrix": {
            "decision": matrix.get("decision"),
            "run_count": len(matrix_runs),
            "replayable_run_count": len(matrix_replayable),
            "modes": matrix.get("parameters", {}).get("modes"),
            "seed": matrix.get("parameters", {}).get("seed"),
            "rows": [
                {
                    "mode": row.get("mode"),
                    "repetition": row.get("repetition"),
                    "seed": row.get("seed"),
                    "pulse_rng_seed": row.get("pulse_rng_seed"),
                    "replay_status": row.get("timing_plan_replay_status"),
                    "replay_sha256": row.get("timing_plan_replay_sha256"),
                }
                for row in matrix_runs
            ],
        },
    }


def default_scan_targets(root: Path) -> list[Path]:
    return [root / rel_path for rel_path in FALSE_CLAIM_SCAN_REL_PATHS]


def false_claim_target_policy() -> dict[str, Any]:
    encoded_targets = "\n".join(FALSE_CLAIM_SCAN_REL_PATHS) + "\n"
    return {
        "mode": "required_static_rel_paths",
        "required": True,
        "target_count": len(FALSE_CLAIM_SCAN_REL_PATHS),
        "sha256": sha256_text(encoded_targets),
    }


def scan_false_claims(root: Path, targets: list[Path] | None = None) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    allowed_matches: list[dict[str, Any]] = []
    failures: list[str] = []
    target_paths = default_scan_targets(root) if targets is None else targets
    for path in target_paths:
        rel_path = display_path(root, path)
        if not path.exists():
            failures.append(f"false_claim_scan target is missing: {rel_path}")
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            failures.append(f"false_claim_scan target is not utf-8 text: {rel_path}")
            continue
        for line_no, line in enumerate(lines, start=1):
            if "re.compile(" in line:
                continue
            for pattern in FALSE_CLAIM_PATTERNS:
                if pattern.search(line):
                    match = {
                        "path": rel_path,
                        "line": line_no,
                        "pattern": pattern.pattern,
                        "text": line.strip(),
                    }
                    if (
                        pattern is KERNEL_ATTACH_VERIFIED_TRUE_PATTERN
                        and rel_path in KERNEL_ATTACH_PROOF_DERIVED_TARGETS
                    ):
                        allowed_matches.append(
                            {
                                **match,
                                "reason": (
                                    "kernel_attach_verified is proof-derived in inventory; "
                                    "inventory/proof verifiers validate the real evidence."
                                ),
                            }
                        )
                    else:
                        matches.append(match)
    return {
        "status": "PASS" if not matches and not failures else "FAIL",
        "failures": failures,
        "matches": matches,
        "allowed_matches": allowed_matches,
        "target_policy": false_claim_target_policy() if targets is None else {"mode": "custom_targets"},
        "targets_scanned": [display_path(root, path) for path in target_paths],
        "target_records": [file_record(root, path) for path in target_paths],
        "claim_boundary": "Static false-claim hygiene scan only; it is not DPI or production evidence.",
    }


CommandRunner = Callable[[Path, list[str], float], dict[str, Any]]


def build_report(
    *,
    root: Path = ROOT,
    local_path: Path | None = None,
    matrix_path: Path | None = None,
    command_runner: CommandRunner = run_cmd,
    run_command_gates: bool = True,
) -> dict[str, Any]:
    local_path = local_path or root / "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    matrix_path = matrix_path or root / "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
    local = load_json(local_path)
    matrix = load_json(matrix_path)

    failures = []
    failures.extend(claim_boundary_failures(local, "local"))
    failures.extend(claim_boundary_failures(matrix, "matrix"))

    if local.get("decision") != "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED":
        failures.append(f"unexpected local decision: {local.get('decision')}")
    if matrix.get("decision") != "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED":
        failures.append(f"unexpected matrix decision: {matrix.get('decision')}")

    gates: dict[str, Any] = {}
    if run_command_gates:
        command_specs = {
            "local_evidence_verifier": [
                sys.executable,
                "scripts/ops/verify_ghost_pulse_local_evidence.py",
                "--evidence",
                display_path(root, local_path),
            ],
            "profile_matrix_verifier": [
                sys.executable,
                "scripts/ops/verify_ghost_pulse_profile_matrix.py",
                "--evidence",
                display_path(root, matrix_path),
            ],
            "seed_replay_verifier": [
                sys.executable,
                "scripts/ops/verify_ghost_pulse_rng_replay.py",
                "--local-evidence",
                display_path(root, local_path),
                "--profile-matrix",
                display_path(root, matrix_path),
            ],
            "python_compile": [
                sys.executable,
                "-m",
                "py_compile",
                "src/network/transport/pulse_transport.py",
                "src/network/obfuscation/whitelist_mimicry.py",
                "scripts/ops/collect_ghost_pulse_local_evidence.py",
                "scripts/ops/run_ghost_pulse_profile_matrix.py",
                "scripts/ops/verify_ghost_pulse_local_evidence.py",
                "scripts/ops/verify_ghost_pulse_profile_matrix.py",
                "scripts/ops/verify_ghost_pulse_artifact_chain.py",
                "scripts/ops/verify_ghost_pulse_rng_replay.py",
                "scripts/ops/verify_ghost_pulse_verification_suite.py",
                "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
                "scripts/ops/collect_ghost_pulse_packet_capture_evidence.py",
                "scripts/ops/collect_ghost_pulse_baseline_comparison_evidence.py",
                "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
                "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
                "scripts/ops/import_ghost_pulse_external_evidence.py",
                "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
                "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
                "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
                "scripts/ops/verify_ghost_pulse_external_evidence.py",
                "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
                "scripts/ops/verify_ghost_pulse_proof_gate.py",
                "scripts/ops/verify_ghost_pulse_goal_state.py",
                "scripts/ops/run_ghost_pulse_proof_gate.py",
                "scripts/ops/run_ghost_pulse_verification_suite.py",
            ],
            "ghost_core_shell_syntax": ["bash", "-n", "scripts/ghost-core.sh"],
            "incoming_gap_candidates_verifier": [
                sys.executable,
                "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
                "--report",
                "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.json",
                "--require-fail-closed",
            ],
        }
        for gate_name, args in command_specs.items():
            result = command_runner(root, args, 45.0)
            gates[gate_name] = {"status": command_status(result), "command": result}
            if gates[gate_name]["status"] != "PASS":
                failures.append(f"{gate_name} did not pass")
    else:
        gates["command_gates"] = {
            "status": "SKIPPED",
            "claim_boundary": "Skipped command gates are not sufficient for a verified suite decision.",
        }
        failures.append("command gates were skipped")

    false_claim_scan = scan_false_claims(root)
    gates["false_claim_scan"] = false_claim_scan
    if false_claim_scan["status"] != "PASS":
        failures.append("false claim scan failed")
        failures.extend(false_claim_scan["failures"])

    artifact_integrity = artifact_integrity_gate(root, local_path, local, matrix_path, matrix)
    gates["artifact_integrity"] = artifact_integrity
    if artifact_integrity["status"] != "PASS":
        failures.extend(artifact_integrity["failures"])

    summary = artifact_summary(local, matrix)
    if summary["local"]["replay_status"] != "LOCAL_SEED_REPLAYABLE":
        failures.append("local replay status is not LOCAL_SEED_REPLAYABLE")
    if summary["matrix"]["replayable_run_count"] != summary["matrix"]["run_count"]:
        failures.append("not all matrix runs are seed replayable")

    decision = DECISION_PASS if not failures else DECISION_FAIL
    return {
        "schema": "x0tta6bl4.ghost_pulse.verification_suite.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "production_ready": False,
            "kernel_attach_verified": False,
            "kernel_read_only_visible": bool(
                local.get("claim_boundary", {}).get("kernel_read_only_visible")
                or matrix.get("claim_boundary", {}).get("kernel_read_only_visible")
            ),
        },
        "artifacts": {
            "local_evidence": display_path(root, local_path),
            "profile_matrix": display_path(root, matrix_path),
            "local_evidence_sha256": sha256_file(local_path),
            "profile_matrix_sha256": sha256_file(matrix_path),
        },
        "summary": summary,
        "gates": gates,
        "failures": failures,
        "claim_boundary_note": (
            "This suite verifies bounded local evidence consistency only. It does not prove "
            "DPI evasion, provider whitelist behavior, kernel attach, or production readiness."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Verification Suite",
        "",
        f"Timestamp: `{report['timestamp_utc']}`",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "## Suite Scope",
        "",
        "- Latest local evidence verifier.",
        "- Latest profile matrix verifier.",
        "- Seed replay verifier.",
        "- Static false-claim scan.",
        "- Latest-vs-bundle artifact hash consistency.",
        "- Fail-closed incoming gap candidate verifier.",
        "",
        "## What This Does Not Prove",
        "",
        "- No DPI bypass claim.",
        "- No VK/Yandex/Teams whitelist claim.",
        "- No production-readiness claim.",
        "- No kernel attach claim.",
        "",
        "## Summary",
        "",
        f"- Local seed: `{report['summary']['local']['seed']}`",
        f"- Local replay: `{report['summary']['local']['replay_status']}`",
        f"- Local replay sha256: `{report['summary']['local']['replay_sha256']}`",
        f"- Matrix runs: `{report['summary']['matrix']['run_count']}`",
        f"- Matrix replayable runs: `{report['summary']['matrix']['replayable_run_count']}`",
        f"- Local evidence sha256: `{report['artifacts']['local_evidence_sha256']}`",
        f"- Matrix sha256: `{report['artifacts']['profile_matrix_sha256']}`",
        "",
        "## Gates",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    gate_names = [
        gate_name
        for gate_name in GATE_DISPLAY_ORDER
        if gate_name in report["gates"]
    ]
    gate_names.extend(
        gate_name
        for gate_name in sorted(report["gates"])
        if gate_name not in gate_names
    )
    for gate_name in gate_names:
        gate = report["gates"][gate_name]
        lines.append(f"| {gate_name} | `{gate['status']}` |")

    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_report_outputs(
    root: Path,
    report: dict[str, Any],
    output_json: Path,
    output_md: Path,
) -> dict[str, Path]:
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-verification-suite-{stamp}"
    bundle_json = bundle_dir / "suite.json"
    bundle_md = bundle_dir / "summary.md"

    report["bundle"] = display_path(root, bundle_dir)
    report.setdefault("artifacts", {}).update(
        {
            "suite_bundle_json": display_path(root, bundle_json),
            "suite_bundle_md": display_path(root, bundle_md),
            "suite_latest_json": display_path(root, output_json),
            "suite_latest_md": display_path(root, output_md),
        }
    )

    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

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
    parser.add_argument("--local-evidence", type=Path)
    parser.add_argument("--profile-matrix", type=Path)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--skip-command-gates", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    local_path = args.local_evidence
    matrix_path = args.profile_matrix
    if local_path and not local_path.is_absolute():
        local_path = root / local_path
    if matrix_path and not matrix_path.is_absolute():
        matrix_path = root / matrix_path

    report = build_report(
        root=root,
        local_path=local_path,
        matrix_path=matrix_path,
        run_command_gates=not args.skip_command_gates,
    )

    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
    output_paths = write_report_outputs(root, report, output_json, output_md)

    print(
        json.dumps(
            {
                "decision": report["decision"],
                "bundle": display_path(root, output_paths["bundle_dir"]),
                "output_json": display_path(root, output_paths["latest_json"]),
                "output_md": display_path(root, output_paths["latest_md"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["decision"] == DECISION_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
