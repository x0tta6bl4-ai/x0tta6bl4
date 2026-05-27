#!/usr/bin/env python3
"""Verify the latest x0tta6bl4_pulse artifact chain.

This command is read-only. It runs the bounded local evidence, profile matrix,
seed replay, suite report, and replacement-candidate report verifiers, then
checks that the suite report points at the latest local/profile artifacts and
records their current hashes. It does not run packet probes, attach kernel
programs, mutate routes, or touch runtime services.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
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
DEFAULT_SUITE = VERIFY_ROOT / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
DEFAULT_INVENTORY = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
DEFAULT_INTAKE = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md"
REQUIRED_ARTIFACT_INTEGRITY_CHECKS = (
    "local_latest_vs_bundle_json",
    "local_latest_vs_bundle_md",
    "matrix_latest_vs_bundle_json",
    "matrix_latest_vs_bundle_md",
)
CHAIN_INPUT_ARTIFACT_KEYS = (
    "local_evidence",
    "local_evidence_sha256",
    "profile_matrix",
    "profile_matrix_sha256",
    "verification_suite",
    "verification_suite_sha256",
    "external_evidence_inventory",
    "external_evidence_inventory_sha256",
    "external_evidence_intake",
    "external_evidence_intake_sha256",
    "replacement_candidates",
    "replacement_candidates_sha256",
    "suite_bundle",
    "suite_bundle_json",
    "suite_bundle_md",
    "suite_latest_json",
    "suite_latest_md",
)
STABLE_REPORT_KEYS = (
    "schema",
    "decision",
    "artifacts",
    "gates",
    "failures",
    "claim_boundary",
    "claim_boundary_note",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


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


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def compare_bytes(left: Path | None, right: Path | None) -> bool:
    if not left or not right or not left.exists() or not right.exists():
        return False
    if not left.is_file() or not right.is_file():
        return False
    return left.read_bytes() == right.read_bytes()


def stable_subset(report: dict[str, Any]) -> dict[str, Any]:
    subset = {key: report.get(key) for key in STABLE_REPORT_KEYS}
    artifacts = subset.get("artifacts")
    if isinstance(artifacts, dict):
        subset["artifacts"] = {
            key: artifacts.get(key)
            for key in CHAIN_INPUT_ARTIFACT_KEYS
            if key in artifacts
        }
    return subset


def run_cmd(root: Path, args: list[str], timeout: float = 45.0) -> dict[str, Any]:
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


def load_suite_runner():
    runner_path = ROOT / "scripts" / "ops" / "run_ghost_pulse_verification_suite.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_verification_suite", runner_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_false_claim_targets(root: Path) -> list[str]:
    module = load_suite_runner()
    return [display_path(root, path) for path in module.default_scan_targets(root)]


def expected_false_claim_target_policy() -> dict[str, Any]:
    return load_suite_runner().false_claim_target_policy()


def duplicate_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def false_claim_scan_failures(root: Path, suite: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    gate = suite.get("gates", {}).get("false_claim_scan", {})
    if gate.get("status") != "PASS":
        failures.append("suite false_claim_scan status is not PASS")
    if gate.get("failures") not in ([], None):
        failures.append("suite false_claim_scan failures must be empty")
    if gate.get("matches") not in ([], None):
        failures.append("suite false_claim_scan matches must be empty")
    if gate.get("target_policy") != expected_false_claim_target_policy():
        failures.append("suite false_claim_scan target_policy does not match expected policy")

    scanned_items = gate.get("targets_scanned", [])
    if not isinstance(scanned_items, list):
        failures.append("suite false_claim_scan targets_scanned must be a list")
        scanned_items = []
    valid_scanned: list[str] = []
    for index, target in enumerate(scanned_items):
        if not isinstance(target, str) or not target:
            failures.append(f"suite false_claim_scan target {index} has invalid path")
            continue
        valid_scanned.append(target)

    record_items = gate.get("target_records", [])
    if not isinstance(record_items, list):
        failures.append("suite false_claim_scan target_records must be a list")
        record_items = []
    record_paths: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(record_items):
        if not isinstance(item, dict):
            failures.append(f"suite false_claim_scan target record {index} must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            failures.append(f"suite false_claim_scan target record {index} has invalid path")
            continue
        record_paths.append(path)
        records.setdefault(path, item)

    expected_targets = expected_false_claim_targets(root)
    scanned_set = set(valid_scanned)
    expected_set = set(expected_targets)
    record_set = set(records)
    for target in duplicate_items(valid_scanned):
        failures.append(f"suite false_claim_scan duplicate target: {target}")
    for target in duplicate_items(record_paths):
        failures.append(f"suite false_claim_scan duplicate target record: {target}")
    if valid_scanned != expected_targets:
        failures.append("suite false_claim_scan targets_scanned order does not match expected targets")
    if record_paths != valid_scanned:
        failures.append("suite false_claim_scan target_records path order does not match targets_scanned")
    for target in sorted(expected_set - scanned_set):
        failures.append(f"suite false_claim_scan missing target: {target}")
    for target in sorted(scanned_set - expected_set):
        failures.append(f"suite false_claim_scan unexpected target: {target}")
    for target in sorted(scanned_set - record_set):
        failures.append(f"suite false_claim_scan target record is missing: {target}")
    for target in sorted(record_set - scanned_set):
        failures.append(f"suite false_claim_scan unexpected target record: {target}")

    for target in expected_targets:
        if target not in scanned_set:
            continue
        record = records.get(target)
        if not record:
            continue
        path = resolve_path(root, target)
        if not path or not path.exists():
            failures.append(f"suite false_claim_scan target artifact is missing: {target}")
            continue
        if record.get("exists") is not True:
            failures.append(f"suite false_claim_scan target exists metadata is not true: {target}")
        if record.get("size_bytes") != path.stat().st_size:
            failures.append(f"suite false_claim_scan target size_bytes mismatch: {target}")
        if record.get("sha256") != sha256_file(path):
            failures.append(f"suite false_claim_scan target sha256 mismatch: {target}")

    return failures


def expected_artifact_integrity_checks(root: Path, suite: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    artifacts = suite.get("artifacts", {})
    local_path = resolve_path(root, artifacts.get("local_evidence"))
    matrix_path = resolve_path(root, artifacts.get("profile_matrix"))
    failures: list[str] = []
    expected: dict[str, dict[str, str]] = {}

    if local_path and local_path.exists():
        try:
            local = load_json(local_path)
        except Exception as exc:
            failures.append(f"could not load local_evidence for suite artifact_integrity policy: {exc}")
        else:
            local_bundle = local.get("bundle")
            if local_bundle:
                expected["local_latest_vs_bundle_json"] = {
                    "left": display_path(root, local_path),
                    "right": display_path(root, root / local_bundle / "evidence.json"),
                }
                expected["local_latest_vs_bundle_md"] = {
                    "left": display_path(root, local_path.with_suffix(".md")),
                    "right": display_path(root, root / local_bundle / "summary.md"),
                }
            else:
                failures.append("suite local_evidence bundle path is missing for artifact_integrity policy")

    if matrix_path and matrix_path.exists():
        try:
            matrix = load_json(matrix_path)
        except Exception as exc:
            failures.append(f"could not load profile_matrix for suite artifact_integrity policy: {exc}")
        else:
            matrix_bundle = matrix.get("bundle")
            if matrix_bundle:
                expected["matrix_latest_vs_bundle_json"] = {
                    "left": display_path(root, matrix_path),
                    "right": display_path(root, root / matrix_bundle / "matrix.json"),
                }
                expected["matrix_latest_vs_bundle_md"] = {
                    "left": display_path(root, matrix_path.with_suffix(".md")),
                    "right": display_path(root, root / matrix_bundle / "summary.md"),
                }
            else:
                failures.append("suite profile_matrix bundle path is missing for artifact_integrity policy")

    return expected, failures


def expected_artifact_integrity_policy(check_paths: dict[str, dict[str, str]]) -> dict[str, Any]:
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


def artifact_integrity_failures(root: Path, suite: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    gate = suite.get("gates", {}).get("artifact_integrity", {})
    if gate.get("status") != "PASS":
        failures.append("suite artifact_integrity status is not PASS")
    if gate.get("failures") not in ([], None):
        failures.append("suite artifact_integrity failures must be empty")
    checks = gate.get("checks", {})
    if not isinstance(checks, dict):
        failures.append("suite artifact_integrity checks must be an object")
        checks = {}
    expected_checks, policy_failures = expected_artifact_integrity_checks(root, suite)
    failures.extend(policy_failures)
    if gate.get("policy") != expected_artifact_integrity_policy(expected_checks):
        failures.append("suite artifact_integrity policy does not match expected policy")
    expected_check_names = set(REQUIRED_ARTIFACT_INTEGRITY_CHECKS)
    actual_check_names = set(checks)
    for check_name in sorted(expected_check_names - actual_check_names):
        failures.append(f"suite artifact_integrity missing check: {check_name}")
    for check_name in sorted(actual_check_names - expected_check_names):
        failures.append(f"suite artifact_integrity unexpected check: {check_name}")

    for check_name, check in checks.items():
        if not isinstance(check, dict):
            failures.append(f"suite artifact_integrity.{check_name} must be an object")
            continue
        expected_paths = expected_checks.get(check_name)
        if expected_paths:
            for side in ("left", "right"):
                record = check.get(side, {})
                if not isinstance(record, dict):
                    failures.append(f"suite artifact_integrity.{check_name}.{side} must be an object")
                    continue
                if record.get("path") != expected_paths[side]:
                    failures.append(f"suite artifact_integrity.{check_name}.{side} path mismatch")
        if check.get("match") is not True:
            failures.append(f"suite artifact_integrity.{check_name}.match is not true")
        for side in ("left", "right"):
            record = check.get(side, {})
            if not isinstance(record, dict):
                continue
            path = resolve_path(root, record.get("path"))
            if not path or not path.exists():
                failures.append(f"suite artifact_integrity.{check_name}.{side} artifact is missing")
                continue
            if record.get("exists") is not True:
                failures.append(
                    f"suite artifact_integrity.{check_name}.{side} exists metadata is not true"
                )
            if record.get("size_bytes") != path.stat().st_size:
                failures.append(f"suite artifact_integrity.{check_name}.{side} size_bytes mismatch")
            if record.get("sha256") != sha256_file(path):
                failures.append(f"suite artifact_integrity.{check_name}.{side} sha256 mismatch")
    return failures


CommandRunner = Callable[[Path, list[str], float], dict[str, Any]]


def build_report(
    *,
    root: Path = ROOT,
    local_path: Path | None = None,
    matrix_path: Path | None = None,
    suite_path: Path | None = None,
    external_evidence_inventory_path: Path | None = None,
    external_evidence_intake_path: Path | None = None,
    replacement_candidates_path: Path | None = None,
    command_runner: CommandRunner = run_cmd,
) -> dict[str, Any]:
    local_path = local_path or root / "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    matrix_path = matrix_path or root / "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
    suite_path = suite_path or root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    external_evidence_inventory_path = (
        external_evidence_inventory_path
        or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    )
    external_evidence_intake_path = (
        external_evidence_intake_path
        or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    )
    replacement_candidates_path = (
        replacement_candidates_path
        or root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    )

    failures: list[str] = []
    gates: dict[str, Any] = {}
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
        "suite_self_verifier": [
            sys.executable,
            "scripts/ops/verify_ghost_pulse_verification_suite.py",
            "--suite",
            display_path(root, suite_path),
        ],
        "external_evidence_inventory_verifier": [
            sys.executable,
            "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
            "--report",
            display_path(root, external_evidence_inventory_path),
            "--skip-proof-consistency",
        ],
        "external_evidence_intake_verifier": [
            sys.executable,
            "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
            "--report",
            display_path(root, external_evidence_intake_path),
        ],
        "replacement_candidates_verifier": [
            sys.executable,
            "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
            "--report",
            display_path(root, replacement_candidates_path),
        ],
    }
    for gate_name, args in command_specs.items():
        result = command_runner(root, args, 45.0)
        gates[gate_name] = {"status": command_status(result), "command": result}
        if gates[gate_name]["status"] != "PASS":
            failures.append(f"{gate_name} did not pass")

    local_exists = local_path.exists()
    matrix_exists = matrix_path.exists()
    suite_exists = suite_path.exists()
    external_evidence_inventory_exists = external_evidence_inventory_path.exists()
    external_evidence_intake_exists = external_evidence_intake_path.exists()
    replacement_candidates_exists = replacement_candidates_path.exists()
    if not local_exists:
        failures.append("local evidence latest artifact is missing")
    if not matrix_exists:
        failures.append("profile matrix latest artifact is missing")
    if not suite_exists:
        failures.append("verification suite latest artifact is missing")
    if not external_evidence_inventory_exists:
        failures.append("external evidence inventory latest artifact is missing")
    if not external_evidence_intake_exists:
        failures.append("external evidence intake latest artifact is missing")
    if not replacement_candidates_exists:
        failures.append("replacement candidates latest artifact is missing")

    suite: dict[str, Any] = load_json(suite_path) if suite_exists else {}
    suite_artifacts = suite.get("artifacts", {})
    suite_local = resolve_path(root, suite_artifacts.get("local_evidence"))
    suite_matrix = resolve_path(root, suite_artifacts.get("profile_matrix"))
    suite_bundle = resolve_path(root, suite.get("bundle"))
    suite_bundle_json = resolve_path(root, suite_artifacts.get("suite_bundle_json"))
    suite_bundle_md = resolve_path(root, suite_artifacts.get("suite_bundle_md"))
    suite_latest_json = resolve_path(root, suite_artifacts.get("suite_latest_json"))
    suite_latest_md = resolve_path(root, suite_artifacts.get("suite_latest_md"))

    if suite_local != local_path:
        failures.append("suite local_evidence pointer does not match selected local latest")
    if suite_matrix != matrix_path:
        failures.append("suite profile_matrix pointer does not match selected profile matrix latest")
    if local_exists and suite_artifacts.get("local_evidence_sha256") != sha256_file(local_path):
        failures.append("suite local_evidence_sha256 does not match selected local latest")
    if matrix_exists and suite_artifacts.get("profile_matrix_sha256") != sha256_file(matrix_path):
        failures.append("suite profile_matrix_sha256 does not match selected profile matrix latest")

    if not suite_bundle or not suite_bundle.is_dir():
        failures.append("suite bundle directory is missing")
    if suite_bundle and suite_bundle_json and suite_bundle_json.parent != suite_bundle:
        failures.append("suite_bundle_json is not inside suite bundle directory")
    if suite_bundle and suite_bundle_md and suite_bundle_md.parent != suite_bundle:
        failures.append("suite_bundle_md is not inside suite bundle directory")
    for label, path in (
        ("suite_bundle_json", suite_bundle_json),
        ("suite_bundle_md", suite_bundle_md),
        ("suite_latest_json", suite_latest_json),
        ("suite_latest_md", suite_latest_md),
    ):
        if not path or not path.exists():
            failures.append(f"{label} artifact is missing")

    if suite_bundle_json and suite_bundle_json.exists() and suite_path.read_bytes() != suite_bundle_json.read_bytes():
        failures.append("suite latest json does not match suite bundle json")
    if suite_latest_json and suite_bundle_json and suite_latest_json.exists() and suite_bundle_json.exists():
        if suite_latest_json.read_bytes() != suite_bundle_json.read_bytes():
            failures.append("suite latest json does not match suite bundle json")
    if suite_latest_md and suite_bundle_md and suite_latest_md.exists() and suite_bundle_md.exists():
        if suite_latest_md.read_bytes() != suite_bundle_md.read_bytes():
            failures.append("suite latest markdown does not match suite bundle markdown")

    claim_boundary = suite.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "production_ready", "kernel_attach_verified"):
        if claim_boundary.get(key) is not False:
            failures.append(f"suite claim_boundary.{key} must be false")
    failures.extend(false_claim_scan_failures(root, suite))
    failures.extend(artifact_integrity_failures(root, suite))

    return {
        "schema": "x0tta6bl4.ghost_pulse.artifact_chain.v1",
        "decision": "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED" if not failures else "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE",
        "artifacts": {
            "local_evidence": display_path(root, local_path),
            "local_evidence_sha256": sha256_file(local_path),
            "profile_matrix": display_path(root, matrix_path),
            "profile_matrix_sha256": sha256_file(matrix_path),
            "verification_suite": display_path(root, suite_path),
            "verification_suite_sha256": sha256_file(suite_path),
            "external_evidence_inventory": display_path(root, external_evidence_inventory_path),
            "external_evidence_inventory_sha256": sha256_file(external_evidence_inventory_path),
            "external_evidence_intake": display_path(root, external_evidence_intake_path),
            "external_evidence_intake_sha256": sha256_file(external_evidence_intake_path),
            "replacement_candidates": display_path(root, replacement_candidates_path),
            "replacement_candidates_sha256": sha256_file(replacement_candidates_path),
            "suite_bundle": display_path(root, suite_bundle) if suite_bundle else None,
            "suite_bundle_json": display_path(root, suite_bundle_json) if suite_bundle_json else None,
            "suite_bundle_md": display_path(root, suite_bundle_md) if suite_bundle_md else None,
            "suite_latest_json": display_path(root, suite_latest_json) if suite_latest_json else None,
            "suite_latest_md": display_path(root, suite_latest_md) if suite_latest_md else None,
        },
        "gates": gates,
        "failures": failures,
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "production_ready": False,
            "kernel_attach_verified": False,
            "kernel_read_only_visible": bool(claim_boundary.get("kernel_read_only_visible")),
        },
        "claim_boundary_note": (
            "Artifact-chain verification is read-only consistency evidence. It does not prove "
            "DPI evasion, whitelist behavior, kernel attach, or production readiness."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Artifact Chain",
        "",
        f"Decision: `{report.get('decision')}`",
        "",
        "## Claim Boundary",
        "",
    ]
    claim_boundary = report.get("claim_boundary", {})
    if isinstance(claim_boundary, dict):
        for key in sorted(claim_boundary):
            lines.append(f"- {key}: `{claim_boundary[key]}`")
    else:
        lines.append("- INVALID")

    lines.extend(["", "## Artifacts", ""])
    artifacts = report.get("artifacts", {})
    if isinstance(artifacts, dict):
        for key in sorted(artifacts):
            lines.append(f"- {key}: `{artifacts[key]}`")
    else:
        lines.append("- INVALID")

    lines.extend(["", "## Gates", ""])
    gates = report.get("gates", {})
    if isinstance(gates, dict):
        for key in sorted(gates):
            gate = gates[key]
            status = gate.get("status") if isinstance(gate, dict) else "INVALID"
            lines.append(f"- {key}: `{status}`")
    else:
        lines.append("- INVALID")

    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    if "timestamp_utc" not in report:
        report["timestamp_utc"] = utc_now()
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-artifact-chain-{stamp}"
    bundle_json = bundle_dir / "chain.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    artifacts = report.setdefault("artifacts", {})
    if isinstance(artifacts, dict):
        artifacts.update(
            {
                "chain_bundle_json": display_path(root, bundle_json),
                "chain_bundle_md": display_path(root, bundle_md),
                "chain_latest_json": display_path(root, output_json),
                "chain_latest_md": display_path(root, output_md),
            }
        )

    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(bundle_json, rendered_json)
    atomic_write_text(bundle_md, rendered_md)
    atomic_write_text(output_json, rendered_json)
    atomic_write_text(output_md, rendered_md)
    return {
        "bundle_dir": bundle_dir,
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": output_json,
        "latest_md": output_md,
    }


def verify_saved_report(
    report_path: Path,
    root: Path = ROOT,
    *,
    command_runner: CommandRunner = run_cmd,
) -> list[str]:
    failures: list[str] = []
    if not report_path.exists():
        return [f"missing artifact-chain report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"artifact-chain report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load artifact-chain report: {exc}"]

    if data.get("schema") != "x0tta6bl4.ghost_pulse.artifact_chain.v1":
        failures.append(f"unexpected schema: {data.get('schema')}")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}

    expected = build_report(
        root=root,
        local_path=(
            resolve_path(root, artifacts.get("local_evidence"))
            or root / "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
        ),
        matrix_path=(
            resolve_path(root, artifacts.get("profile_matrix"))
            or root / "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
        ),
        suite_path=(
            resolve_path(root, artifacts.get("verification_suite"))
            or root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
        ),
        external_evidence_inventory_path=(
            resolve_path(root, artifacts.get("external_evidence_inventory"))
            or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
        ),
        external_evidence_intake_path=(
            resolve_path(root, artifacts.get("external_evidence_intake"))
            or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
        ),
        replacement_candidates_path=(
            resolve_path(root, artifacts.get("replacement_candidates"))
            or root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
        ),
        command_runner=command_runner,
    )
    if stable_subset(data) != stable_subset(expected):
        failures.append("artifact-chain stable fields do not match current artifact state")

    latest_json = resolve_path(root, artifacts.get("chain_latest_json"))
    latest_md = resolve_path(root, artifacts.get("chain_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("chain_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("chain_bundle_md"))

    if latest_json != report_path:
        failures.append("artifacts.chain_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("artifact-chain latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("artifact-chain latest markdown does not match bundle markdown")

    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("artifact-chain latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("artifact-chain bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--local-evidence", type=Path)
    parser.add_argument("--profile-matrix", type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--external-evidence-inventory", type=Path)
    parser.add_argument("--external-evidence-intake", type=Path)
    parser.add_argument("--replacement-candidates", type=Path)
    parser.add_argument("--report", type=Path, help="Saved artifact-chain report to verify read-only.")
    parser.add_argument("--write-report", action="store_true", help="Write latest and bundle artifact-chain reports.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        failures = verify_saved_report(report_path, root)
        try:
            saved = load_json(report_path) if report_path.exists() and report_path.is_file() else {}
        except Exception:
            saved = {}
        result = {
            "status": "PASS" if not failures else "FAIL",
            "decision": saved.get("decision"),
            "report": display_path(root, report_path),
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse artifact-chain report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse artifact-chain report is current")
            print(f"report={result['report']}")
            print(f"decision={result['decision']}")
        return 0 if not failures else 1

    local_arg = args.local_evidence or root / "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    matrix_arg = args.profile_matrix or root / "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
    suite_arg = args.suite or root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    inventory_arg = (
        args.external_evidence_inventory
        or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    )
    intake_arg = (
        args.external_evidence_intake
        or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    )
    replacement_arg = (
        args.replacement_candidates
        or root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    )
    local_path = local_arg if local_arg.is_absolute() else root / local_arg
    matrix_path = matrix_arg if matrix_arg.is_absolute() else root / matrix_arg
    suite_path = suite_arg if suite_arg.is_absolute() else root / suite_arg
    inventory_path = inventory_arg if inventory_arg.is_absolute() else root / inventory_arg
    intake_path = intake_arg if intake_arg.is_absolute() else root / intake_arg
    replacement_path = replacement_arg if replacement_arg.is_absolute() else root / replacement_arg
    report = build_report(
        root=root,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        external_evidence_inventory_path=inventory_path,
        external_evidence_intake_path=intake_path,
        replacement_candidates_path=replacement_path,
    )
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["failures"]:
        print("FAIL")
        for failure in report["failures"]:
            print(f"- {failure}")
    else:
        print("PASS: x0tta6bl4_pulse artifact chain is internally consistent")
        print(f"suite={display_path(root, suite_path)}")

    return 0 if report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
