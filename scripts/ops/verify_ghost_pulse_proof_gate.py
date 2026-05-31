#!/usr/bin/env python3
"""Verify the x0tta6bl4_pulse proof gate report.

This checker is read-only. It verifies that the latest proof-gate report matches
the current suite and external evidence files, that latest/bundle copies match,
and that claim boundaries are derived from proof rows instead of being promoted
by hand.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROOF = ROOT / "docs" / "verification" / "GHOST_PULSE_PROOF_GATE_LATEST.json"

EXPECTED_SCHEMA = "x0tta6bl4.ghost_pulse.proof_gate.v1"
DECISION_PROVEN = "GHOST_PULSE_ALL_CLAIMS_PROVEN"
DECISION_INCOMPLETE = "GHOST_PULSE_PROOF_INCOMPLETE"

STABLE_REPORT_KEYS = (
    "schema",
    "decision",
    "suite",
    "suite_sha256",
    "replacement_candidates",
    "proof_rows",
    "failures",
    "not_verified_yet",
    "required_external_evidence",
    "claim_boundary",
    "claim_boundary_note",
)
REPLACEMENT_CANDIDATE_BOUNDARY_KEYS = (
    "stealth_verified",
    "whitelist_verified",
    "kernel_attach_verified",
    "production_ready",
)
REPLACEMENT_CANDIDATE_DECISIONS = {
    "REPLACEMENT_CANDIDATES_READY",
    "REPLACEMENT_CANDIDATES_NOT_READY",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_proof_runner(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_proof_gate_for_verify", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def compare_bytes(left: Path | None, right: Path | None) -> bool:
    if not left or not right or not left.exists() or not right.exists():
        return False
    return left.read_bytes() == right.read_bytes()


def stable_subset(report: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in STABLE_REPORT_KEYS}


def status_by_claim(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        row["claim_id"]: row.get("status")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }


def expected_claim_boundary(rows: list[dict[str, Any]]) -> dict[str, bool]:
    statuses = status_by_claim(rows)
    all_verified = rows and all(row.get("status") == "VERIFIED" for row in rows if isinstance(row, dict))
    production_ready = all_verified and statuses.get("production_readiness") == "VERIFIED"
    return {
        "current_runtime_attached": statuses.get("current_runtime_attached") == "VERIFIED",
        "kernel_attach_verified": statuses.get("kernel_attach") == "VERIFIED",
        "production_ready": production_ready,
        "stealth_verified": (
            statuses.get("dpi_lab") == "VERIFIED"
            and statuses.get("packet_capture") == "VERIFIED"
            and statuses.get("baseline_timing_comparison") == "VERIFIED"
        ),
        "whitelist_verified": statuses.get("whitelist_lab") == "VERIFIED",
    }


def expected_decision(rows: list[dict[str, Any]]) -> str:
    return DECISION_PROVEN if expected_claim_boundary(rows)["production_ready"] else DECISION_INCOMPLETE


def validate_replacement_candidates(
    root: Path,
    runner,
    value: Any,
    *,
    check_current_state: bool,
) -> list[str]:
    failures: list[str] = []
    if not isinstance(value, dict):
        return ["replacement_candidates must be an object"]

    report_path = resolve_path(root, value.get("report"))
    if not report_path:
        failures.append("replacement_candidates.report is required")
    elif not report_path.exists():
        failures.append(f"replacement_candidates report is missing: {value.get('report')}")
    elif value.get("sha256") != runner.sha256_file(report_path):
        failures.append("replacement_candidates.sha256 does not match report artifact")

    if value.get("status") != "PASS":
        failures.append("replacement_candidates verifier status must be PASS")
    if value.get("decision") not in REPLACEMENT_CANDIDATE_DECISIONS:
        failures.append(f"replacement_candidates decision is unexpected: {value.get('decision')}")

    claim_boundary = value.get("claim_boundary")
    if not isinstance(claim_boundary, dict):
        failures.append("replacement_candidates.claim_boundary must be an object")
    else:
        for key in REPLACEMENT_CANDIDATE_BOUNDARY_KEYS:
            if claim_boundary.get(key) is not False:
                failures.append(f"replacement_candidates.claim_boundary.{key} must remain false")

    if check_current_state and report_path:
        expected = runner.default_replacement_candidate_preflight(root, report_path)
        if value != expected:
            failures.append("replacement_candidates does not match current saved preflight report")
        if expected.get("status") != "PASS":
            failures.append("replacement_candidates saved preflight verifier is not PASS")

    return failures


def verify_proof(
    proof_path: Path,
    root: Path = ROOT,
    *,
    check_current_state: bool = True,
    check_artifacts: bool = True,
) -> list[str]:
    failures: list[str] = []
    if not proof_path.exists():
        return [f"missing proof report: {display_path(root, proof_path)}"]

    try:
        data = load_json(proof_path)
    except Exception as exc:
        return [f"could not load proof JSON: {exc}"]

    runner = load_proof_runner(root)
    if data.get("schema") != EXPECTED_SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    if data.get("decision") not in (DECISION_PROVEN, DECISION_INCOMPLETE):
        failures.append(f"unexpected decision: {data.get('decision')}")

    rows = data.get("proof_rows")
    if not isinstance(rows, list) or not rows:
        failures.append("proof_rows must be a non-empty list")
        rows = []
    row_claims: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"proof_rows[{index}] must be an object")
            continue
        claim_id = row.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            failures.append(f"proof_rows[{index}].claim_id is required")
            continue
        row_claims.append(claim_id)
        if row.get("status") not in ("VERIFIED", "INVALID", "MISSING"):
            failures.append(f"{claim_id}: unexpected row status {row.get('status')}")
        errors = row.get("errors")
        if row.get("status") == "VERIFIED" and errors not in ([], None):
            failures.append(f"{claim_id}: VERIFIED row must not have errors")
        if row.get("status") != "VERIFIED" and not errors:
            failures.append(f"{claim_id}: non-VERIFIED row must include errors")
        evidence = resolve_path(root, row.get("evidence"))
        if evidence and evidence.exists():
            if row.get("sha256") != runner.sha256_file(evidence):
                failures.append(f"{claim_id}: evidence sha256 mismatch")

    if len(row_claims) != len(set(row_claims)):
        failures.append("proof_rows contains duplicate claim ids")

    not_verified = data.get("not_verified_yet")
    expected_not_verified = [
        row["claim_id"]
        for row in rows
        if isinstance(row, dict) and row.get("status") != "VERIFIED" and isinstance(row.get("claim_id"), str)
    ]
    if not_verified != expected_not_verified:
        failures.append("not_verified_yet does not match non-VERIFIED proof rows")

    claim_boundary = data.get("claim_boundary", {})
    if claim_boundary != expected_claim_boundary(rows):
        failures.append("claim_boundary does not match proof-row-derived boundary")
    if data.get("decision") != expected_decision(rows):
        failures.append("decision does not match proof-row-derived production readiness")

    required = data.get("required_external_evidence")
    if hasattr(runner, "external_requirement_contract"):
        expected_required = [runner.external_requirement_contract(item) for item in runner.EXTERNAL_REQUIREMENTS]
    else:
        expected_required = [
            {
                "claim_id": item["claim_id"],
                "title": item["title"],
                "path": item["path"],
                "measurements": item["measurements"],
            }
            for item in runner.EXTERNAL_REQUIREMENTS
        ]
    if required != expected_required:
        failures.append("required_external_evidence does not match proof-gate contract")

    suite_path = resolve_path(root, data.get("suite"))
    if not suite_path or not suite_path.exists():
        failures.append("suite artifact is missing")
    elif data.get("suite_sha256") != runner.sha256_file(suite_path):
        failures.append("suite_sha256 does not match suite artifact")

    if check_current_state and suite_path and suite_path.exists():
        expected = runner.build_report(root=root, suite_path=suite_path)
        if stable_subset(data) != stable_subset(expected):
            failures.append("proof stable fields do not match current suite/external evidence state")

    failures.extend(
        validate_replacement_candidates(
            root,
            runner,
            data.get("replacement_candidates"),
            check_current_state=check_current_state,
        )
    )

    if check_artifacts:
        artifacts = data.get("artifacts", {})
        if not isinstance(artifacts, dict):
            failures.append("artifacts must be an object")
            artifacts = {}
        latest_json = resolve_path(root, artifacts.get("proof_latest_json"))
        latest_md = resolve_path(root, artifacts.get("proof_latest_md"))
        bundle_json = resolve_path(root, artifacts.get("proof_bundle_json"))
        bundle_md = resolve_path(root, artifacts.get("proof_bundle_md"))
        if latest_json != proof_path:
            failures.append("artifacts.proof_latest_json does not point at the checked proof report")
        if not compare_bytes(latest_json, bundle_json):
            failures.append("proof latest JSON does not match bundle JSON")
        if not compare_bytes(latest_md, bundle_md):
            failures.append("proof latest markdown does not match bundle markdown")
        expected_markdown = runner.render_markdown(data)
        if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
            failures.append("proof latest markdown does not match rendered proof report")
        if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
            failures.append("proof bundle markdown does not match rendered proof report")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-all-proven", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    proof_path = args.proof if args.proof.is_absolute() else root / args.proof
    failures = verify_proof(proof_path, root)
    data = load_json(proof_path) if proof_path.exists() else {}
    result = {
        "status": "PASS" if not failures else "FAIL",
        "proof": display_path(root, proof_path),
        "decision": data.get("decision"),
        "not_verified_yet": data.get("not_verified_yet", []),
        "claim_boundary": data.get("claim_boundary", {}),
        "replacement_candidates": data.get("replacement_candidates", {}),
        "failures": failures,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif failures:
        print("FAIL: x0tta6bl4_pulse proof gate is inconsistent")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("PASS: x0tta6bl4_pulse proof gate is internally consistent")
        print(f"proof={display_path(root, proof_path)}")
        print(f"decision={result['decision']}")

    if failures:
        return 1
    if args.require_all_proven and data.get("decision") != DECISION_PROVEN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
