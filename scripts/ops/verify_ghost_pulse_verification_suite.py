#!/usr/bin/env python3
"""Verify a bounded x0tta6bl4_pulse verification suite report.

This checker validates the suite report and its file-level integrity metadata.
It does not run packet probes, attach kernel programs, mutate runtime services,
or promote stealth, whitelist, kernel attach, or production claims.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "docs" / "verification" / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
EXPECTED_SCHEMA = "x0tta6bl4.ghost_pulse.verification_suite.v1"
EXPECTED_DECISION = "GHOST_PULSE_VERIFICATION_SUITE_VERIFIED_STEALTH_NOT_VERIFIED"
EXPECTED_PASS_GATES = (
    "local_evidence_verifier",
    "profile_matrix_verifier",
    "seed_replay_verifier",
    "python_compile",
    "ghost_core_shell_syntax",
    "incoming_gap_candidates_verifier",
    "false_claim_scan",
    "artifact_integrity",
)
REQUIRED_ARTIFACT_INTEGRITY_CHECKS = (
    "local_latest_vs_bundle_json",
    "local_latest_vs_bundle_md",
    "matrix_latest_vs_bundle_json",
    "matrix_latest_vs_bundle_md",
)


def load_suite_runner():
    runner_path = ROOT / "scripts" / "ops" / "run_ghost_pulse_verification_suite.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_verification_suite", runner_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def resolve_artifact(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def compare_bytes(left: Path | None, right: Path | None) -> bool:
    if not left or not right or not left.exists() or not right.exists():
        return False
    return left.read_bytes() == right.read_bytes()


def render_expected_markdown(report: dict[str, Any]) -> str:
    return load_suite_runner().render_markdown(report)


def expected_false_claim_targets(root: Path) -> list[str]:
    module = load_suite_runner()
    return [display_path(root, path) for path in module.default_scan_targets(root)]


def expected_false_claim_target_policy() -> dict[str, Any]:
    return load_suite_runner().false_claim_target_policy()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expected_artifact_integrity_checks(root: Path, data: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    artifacts = data.get("artifacts", {})
    local_path = resolve_artifact(root, artifacts.get("local_evidence"))
    matrix_path = resolve_artifact(root, artifacts.get("profile_matrix"))
    failures: list[str] = []
    expected: dict[str, dict[str, str]] = {}

    if local_path and local_path.exists():
        try:
            local = load_json(local_path)
        except Exception as exc:
            failures.append(f"could not load local_evidence for artifact_integrity policy: {exc}")
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
                failures.append("local_evidence bundle path is missing for artifact_integrity policy")

    if matrix_path and matrix_path.exists():
        try:
            matrix = load_json(matrix_path)
        except Exception as exc:
            failures.append(f"could not load profile_matrix for artifact_integrity policy: {exc}")
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
                failures.append("profile_matrix bundle path is missing for artifact_integrity policy")

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


def duplicate_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def verify_suite(suite_path: Path, root: Path = ROOT) -> list[str]:
    data = load_json(suite_path)
    failures: list[str] = []

    if data.get("schema") != EXPECTED_SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    if data.get("decision") != EXPECTED_DECISION:
        failures.append(f"unexpected decision: {data.get('decision')}")
    if data.get("failures") not in ([], None):
        failures.append("suite failures must be empty")

    claim_boundary = data.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "production_ready", "kernel_attach_verified"):
        if claim_boundary.get(key) is not False:
            failures.append(f"claim_boundary.{key} must be false")

    gates = data.get("gates", {})
    for gate_name in EXPECTED_PASS_GATES:
        if gates.get(gate_name, {}).get("status") != "PASS":
            failures.append(f"{gate_name} status is not PASS")

    false_claim_gate = gates.get("false_claim_scan", {})
    if false_claim_gate.get("failures") not in ([], None):
        failures.append("false_claim_scan failures must be empty")
    if false_claim_gate.get("matches") not in ([], None):
        failures.append("false_claim_scan matches must be empty")
    if false_claim_gate.get("target_policy") != expected_false_claim_target_policy():
        failures.append("false_claim_scan target_policy does not match expected policy")
    scanned_target_items = false_claim_gate.get("targets_scanned", [])
    if not isinstance(scanned_target_items, list):
        failures.append("false_claim_scan targets_scanned must be a list")
        scanned_target_items = []
    valid_scanned_targets: list[str] = []
    for index, target in enumerate(scanned_target_items):
        if not isinstance(target, str) or not target:
            failures.append(f"false_claim_scan target {index} has invalid path")
            continue
        valid_scanned_targets.append(target)
    scanned_target_items = valid_scanned_targets
    scanned_targets = set(scanned_target_items)

    expected_target_items = expected_false_claim_targets(root)
    expected_targets = set(expected_target_items)

    target_record_items = false_claim_gate.get("target_records", [])
    if not isinstance(target_record_items, list):
        failures.append("false_claim_scan target_records must be a list")
        target_record_items = []
    target_record_paths: list[str] = []
    target_records: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(target_record_items):
        if not isinstance(item, dict):
            failures.append(f"false_claim_scan target record {index} must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            failures.append(f"false_claim_scan target record {index} has invalid path")
            continue
        target_record_paths.append(path)
        target_records.setdefault(path, item)
    record_targets = set(target_records)
    for target in duplicate_items(scanned_target_items):
        failures.append(f"false_claim_scan duplicate target: {target}")
    for target in duplicate_items(target_record_paths):
        failures.append(f"false_claim_scan duplicate target record: {target}")
    if scanned_target_items != expected_target_items:
        failures.append("false_claim_scan targets_scanned order does not match expected targets")
    if target_record_paths != scanned_target_items:
        failures.append("false_claim_scan target_records path order does not match targets_scanned")
    for target in sorted(expected_targets - scanned_targets):
        failures.append(f"false_claim_scan missing target: {target}")
    for target in sorted(scanned_targets - expected_targets):
        failures.append(f"false_claim_scan unexpected target: {target}")
    for target in sorted(scanned_targets - record_targets):
        failures.append(f"false_claim_scan target record is missing: {target}")
    for target in sorted(record_targets - scanned_targets):
        failures.append(f"false_claim_scan unexpected target record: {target}")

    for target in expected_targets:
        if target not in scanned_targets:
            continue
        record = target_records.get(target)
        if not record:
            continue
        path = resolve_artifact(root, target)
        if not path or not path.exists():
            failures.append(f"false_claim_scan target artifact is missing: {target}")
            continue
        if record.get("exists") is not True:
            failures.append(f"false_claim_scan target exists metadata is not true: {target}")
        if record.get("size_bytes") != path.stat().st_size:
            failures.append(f"false_claim_scan target size_bytes mismatch: {target}")
        if record.get("sha256") != sha256_file(path):
            failures.append(f"false_claim_scan target sha256 mismatch: {target}")
    for target in scanned_targets:
        path = resolve_artifact(root, target)
        if not path or not path.exists():
            failures.append(f"false_claim_scan target artifact is missing: {target}")

    artifact_gate = gates.get("artifact_integrity", {})
    if artifact_gate.get("failures") not in ([], None):
        failures.append("artifact_integrity failures must be empty")
    artifact_checks = artifact_gate.get("checks", {})
    if not isinstance(artifact_checks, dict):
        failures.append("artifact_integrity checks must be an object")
        artifact_checks = {}
    expected_artifact_checks, artifact_policy_failures = expected_artifact_integrity_checks(root, data)
    failures.extend(artifact_policy_failures)
    if artifact_gate.get("policy") != expected_artifact_integrity_policy(expected_artifact_checks):
        failures.append("artifact_integrity policy does not match expected policy")
    expected_check_names = set(REQUIRED_ARTIFACT_INTEGRITY_CHECKS)
    actual_check_names = set(artifact_checks)
    for check_name in sorted(expected_check_names - actual_check_names):
        failures.append(f"artifact_integrity missing check: {check_name}")
    for check_name in sorted(actual_check_names - expected_check_names):
        failures.append(f"artifact_integrity unexpected check: {check_name}")

    for check_name, check in artifact_checks.items():
        if not isinstance(check, dict):
            failures.append(f"artifact_integrity.{check_name} must be an object")
            continue
        expected_paths = expected_artifact_checks.get(check_name)
        if expected_paths:
            for side in ("left", "right"):
                record = check.get(side, {})
                if not isinstance(record, dict):
                    failures.append(f"artifact_integrity.{check_name}.{side} must be an object")
                    continue
                if record.get("path") != expected_paths[side]:
                    failures.append(f"artifact_integrity.{check_name}.{side} path mismatch")
        if check.get("match") is not True:
            failures.append(f"artifact_integrity.{check_name}.match is not true")
        for side in ("left", "right"):
            record = check.get(side, {})
            if not isinstance(record, dict):
                continue
            path = resolve_artifact(root, record.get("path"))
            if not path or not path.exists():
                failures.append(f"artifact_integrity.{check_name}.{side} artifact is missing")
                continue
            if record.get("exists") is not True:
                failures.append(f"artifact_integrity.{check_name}.{side} exists metadata is not true")
            if record.get("size_bytes") != path.stat().st_size:
                failures.append(f"artifact_integrity.{check_name}.{side} size_bytes mismatch")
            if record.get("sha256") != sha256_file(path):
                failures.append(f"artifact_integrity.{check_name}.{side} sha256 mismatch")

    artifacts = data.get("artifacts", {})
    local_path = resolve_artifact(root, artifacts.get("local_evidence"))
    matrix_path = resolve_artifact(root, artifacts.get("profile_matrix"))
    if not local_path or not local_path.exists():
        failures.append("local_evidence artifact is missing")
    elif artifacts.get("local_evidence_sha256") != sha256_file(local_path):
        failures.append("local_evidence_sha256 does not match local_evidence")
    if not matrix_path or not matrix_path.exists():
        failures.append("profile_matrix artifact is missing")
    elif artifacts.get("profile_matrix_sha256") != sha256_file(matrix_path):
        failures.append("profile_matrix_sha256 does not match profile_matrix")

    bundle = resolve_artifact(root, data.get("bundle"))
    bundle_json = resolve_artifact(root, artifacts.get("suite_bundle_json"))
    bundle_md = resolve_artifact(root, artifacts.get("suite_bundle_md"))
    latest_json = resolve_artifact(root, artifacts.get("suite_latest_json"))
    latest_md = resolve_artifact(root, artifacts.get("suite_latest_md"))
    if not bundle or not bundle.is_dir():
        failures.append("suite bundle directory is missing")
    if bundle and bundle_json and bundle_json.parent != bundle:
        failures.append("suite_bundle_json is not inside bundle directory")
    if bundle and bundle_md and bundle_md.parent != bundle:
        failures.append("suite_bundle_md is not inside bundle directory")
    for label, path in (
        ("suite_bundle_json", bundle_json),
        ("suite_bundle_md", bundle_md),
        ("suite_latest_json", latest_json),
        ("suite_latest_md", latest_md),
    ):
        if not path or not path.exists():
            failures.append(f"{label} artifact is missing")

    if not compare_bytes(latest_json, bundle_json):
        failures.append("suite_latest_json does not mirror suite_bundle_json")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("suite_latest_md does not mirror suite_bundle_md")
    if suite_path.resolve() == (latest_json.resolve() if latest_json else suite_path.resolve()):
        if not compare_bytes(suite_path, bundle_json):
            failures.append("validated latest suite does not match suite bundle json")

    try:
        expected_md = render_expected_markdown(data)
    except Exception as exc:
        failures.append(f"could not render expected suite markdown: {exc}")
    else:
        if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_md:
            failures.append("suite_bundle_md does not match rendered suite markdown")
        if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_md:
            failures.append("suite_latest_md does not match rendered suite markdown")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    suite_path = args.suite if args.suite.is_absolute() else root / args.suite
    if not suite_path.exists():
        print(f"FAIL: suite file not found: {display_path(root, suite_path)}", file=sys.stderr)
        return 2

    failures = verify_suite(suite_path, root)
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: x0tta6bl4_pulse verification suite report is internally consistent")
    print(f"suite={display_path(root, suite_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
