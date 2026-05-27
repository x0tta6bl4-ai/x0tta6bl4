#!/usr/bin/env python3
"""Verify the x0tta6bl4_pulse external evidence gap audit.

This checker is read-only. It confirms that the latest gap-audit report matches
the current proof-gate external evidence contract and that its latest/bundle
artifacts are byte-for-byte mirrored. A valid audit may still report
EXTERNAL_EVIDENCE_ACTION_REQUIRED; that is the expected fail-closed state until
real external evidence replaces the gap records.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / "docs" / "verification" / "GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"

EXPECTED_SCHEMA = "x0tta6bl4.ghost_pulse.external_evidence_gap_audit.v1"
STATUS_ALL_VERIFIED = "ALL_EXTERNAL_EVIDENCE_VERIFIED"
STATUS_ACTION_REQUIRED = "EXTERNAL_EVIDENCE_ACTION_REQUIRED"
GAP_ARTIFACT_ROLE = "evidence_gap_record"
REPLACEMENT_PASSPORT_SCHEMA = "x0tta6bl4.ghost_pulse.external_evidence_replacement_passport.v1"
REPLACEMENT_PASSPORT_ACTION_REQUIRED = "REPLACEMENT_ACTION_REQUIRED"
REPLACEMENT_PASSPORT_ALL_REPLACED = "ALL_REPLACEMENTS_IMPORTED"
INCOMING_EXAMPLE_COMMAND = [
    "python3",
    "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    "--examples-only",
]

STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "selected_claims",
    "rows",
    "failures",
    "replacement_required",
    "replacement_passport",
    "claim_boundary",
)


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


def load_audit_runner(root: Path):
    path = root / "scripts" / "ops" / "audit_ghost_pulse_external_evidence_gaps.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "audit_ghost_pulse_external_evidence_gaps.py"
    spec = importlib.util.spec_from_file_location("audit_ghost_pulse_external_evidence_gaps_for_verify", path)
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


def validate_replacement_contract(
    claim_id: str,
    row: dict[str, Any],
    expected_contract: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    contract = row.get("replacement_contract")
    if not isinstance(contract, dict):
        return [f"{claim_id}: replacement_contract must be an object"]

    if contract.get("claim_id") != claim_id:
        failures.append(f"{claim_id}: replacement_contract.claim_id must match row claim_id")
    if contract.get("destination") != row.get("evidence"):
        failures.append(f"{claim_id}: replacement_contract.destination must match row evidence")
    if contract.get("path") != row.get("evidence"):
        failures.append(f"{claim_id}: replacement_contract.path must match row evidence")
    if contract.get("evidence_schema") != "x0tta6bl4.ghost_pulse.claim_evidence.v1":
        failures.append(f"{claim_id}: replacement_contract.evidence_schema is invalid")
    if contract.get("required_status") != "VERIFIED":
        failures.append(f"{claim_id}: replacement_contract.required_status must be VERIFIED")

    flags = contract.get("required_flags")
    if not isinstance(flags, dict):
        failures.append(f"{claim_id}: replacement_contract.required_flags must be an object")
    else:
        for flag in ("simulated", "dry_run", "template"):
            if flags.get(flag) is not False:
                failures.append(f"{claim_id}: replacement_contract.required_flags.{flag} must be false")

    if not isinstance(contract.get("measurements"), dict) or not contract["measurements"]:
        failures.append(f"{claim_id}: replacement_contract.measurements must be a non-empty object")

    commands = contract.get("acceptance_commands")
    if not isinstance(commands, list) or not commands:
        failures.append(f"{claim_id}: replacement_contract.acceptance_commands must be a non-empty list")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
                failures.append(f"{claim_id}: replacement_contract.acceptance_commands[{index}] must be string list")
    if expected_contract is not None and contract != expected_contract:
        failures.append(f"{claim_id}: replacement_contract does not match proof-gate contract")
    return failures


def expected_import_command(claim_id: str, candidate_path: str, write: bool = False) -> list[str]:
    command = [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        claim_id,
        "--candidate",
        candidate_path,
    ]
    if write:
        command.append("--write")
    else:
        command.append("--require-ready")
    command.append("--json")
    return command


def expected_incoming_example_path(claim_id: str) -> str:
    return f"docs/verification/incoming/examples/{claim_id}.example.json"


def validate_replacement_passport(
    data: dict[str, Any],
    rows: list[Any],
    replacement_required: list[Any],
) -> list[str]:
    failures: list[str] = []
    passport = data.get("replacement_passport")
    if not isinstance(passport, dict):
        return ["replacement_passport must be an object"]

    if passport.get("schema") != REPLACEMENT_PASSPORT_SCHEMA:
        failures.append("replacement_passport.schema is invalid")
    expected_status = (
        REPLACEMENT_PASSPORT_ACTION_REQUIRED
        if replacement_required
        else REPLACEMENT_PASSPORT_ALL_REPLACED
    )
    if passport.get("status") != expected_status:
        failures.append("replacement_passport.status does not match replacement_required")

    boundary = passport.get("claim_boundary")
    if not isinstance(boundary, dict):
        failures.append("replacement_passport.claim_boundary must be an object")
    else:
        for key in ("stealth_verified", "whitelist_verified", "kernel_attach_verified", "production_ready"):
            if boundary.get(key) is not False:
                failures.append(f"replacement_passport.claim_boundary.{key} must be false")

    passport_claims = passport.get("claims")
    if not isinstance(passport_claims, list):
        failures.append("replacement_passport.claims must be a list")
        passport_claims = []

    passport_claim_ids: list[str] = []
    passport_by_claim: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(passport_claims):
        if not isinstance(claim, dict):
            failures.append(f"replacement_passport.claims[{index}] must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            failures.append(f"replacement_passport.claims[{index}].claim_id is required")
            continue
        passport_claim_ids.append(claim_id)
        if claim_id in passport_by_claim:
            failures.append(f"replacement_passport contains duplicate claim: {claim_id}")
        passport_by_claim[claim_id] = claim

    if passport_claim_ids != replacement_required:
        failures.append("replacement_passport.claims does not match replacement_required")

    row_by_claim = {
        row["claim_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }
    for claim_id in passport_claim_ids:
        if claim_id not in replacement_required:
            failures.append(f"replacement_passport contains unexpected claim: {claim_id}")
    for claim_id in replacement_required:
        row = row_by_claim.get(claim_id)
        claim = passport_by_claim.get(claim_id)
        if not row:
            failures.append(f"{claim_id}: replacement_passport references missing row")
            continue
        if not claim:
            failures.append(f"{claim_id}: replacement_passport claim is missing")
            continue

        expected_candidate = f"docs/verification/incoming/{claim_id}.json"
        expected_read_only = expected_import_command(claim_id, expected_candidate)
        expected_write = expected_import_command(claim_id, expected_candidate, write=True)
        expected_blockers = row.get("blocking_audit", {}).get("blocking_categories", [])
        contract = row.get("replacement_contract")
        expected_acceptance = contract.get("acceptance_commands") if isinstance(contract, dict) else None
        checks = {
            "title": row.get("title"),
            "destination": row.get("evidence"),
            "current_status": row.get("status"),
            "current_sha256": row.get("sha256"),
            "blocking_categories": expected_blockers,
            "replacement_contract": contract,
            "candidate_path": expected_candidate,
            "candidate_example_path": expected_incoming_example_path(claim_id),
            "incoming_example_command": INCOMING_EXAMPLE_COMMAND,
            "read_only_import_command": expected_read_only,
            "write_import_command": expected_write,
            "acceptance_commands": expected_acceptance,
        }
        for key, expected_value in checks.items():
            if claim.get(key) != expected_value:
                failures.append(f"{claim_id}: replacement_passport.{key} does not match audit row")

    return failures


def verify_audit(audit_path: Path, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    if not audit_path.exists():
        return [f"missing audit report: {display_path(root, audit_path)}"]

    try:
        data = load_json(audit_path)
    except Exception as exc:
        return [f"could not load audit JSON: {exc}"]

    if data.get("schema") != EXPECTED_SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    if data.get("status") not in (STATUS_ALL_VERIFIED, STATUS_ACTION_REQUIRED):
        failures.append(f"unexpected status: {data.get('status')}")

    runner = load_audit_runner(root)
    expected = runner.build_report(root=root, claims=data.get("selected_claims"))
    expected_contracts = {
        row["claim_id"]: row.get("replacement_contract")
        for row in expected.get("rows", [])
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }

    claim_boundary = data.get("claim_boundary", {})
    for key in ("stealth_verified", "whitelist_verified", "kernel_attach_verified", "production_ready"):
        if claim_boundary.get(key) is not False:
            failures.append(f"claim_boundary.{key} must be false")

    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        failures.append("rows must be a non-empty list")
        rows = []
    replacement_required = data.get("replacement_required")
    if not isinstance(replacement_required, list):
        failures.append("replacement_required must be a list")
        replacement_required = []
    replacement_set = set(replacement_required)
    expected_replacement: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"rows[{index}] must be an object")
            continue
        claim_id = row.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            failures.append(f"rows[{index}].claim_id is required")
            continue
        row_status = row.get("status")
        row_replacement = row.get("replacement_required")
        if row_status == "VERIFIED" and row_replacement is not False:
            failures.append(f"{claim_id}: VERIFIED row must not require replacement")
        if row_status != "VERIFIED":
            expected_replacement.append(claim_id)
            if row_replacement is not True:
                failures.append(f"{claim_id}: non-VERIFIED row must require replacement")
            if not row.get("errors"):
                failures.append(f"{claim_id}: non-VERIFIED row must include errors")
        blocking_rows = row.get("blocking_audit")
        if not isinstance(blocking_rows, dict):
            failures.append(f"{claim_id}: blocking_audit must be an object")
        else:
            blocking_status = blocking_rows.get("status")
            if blocking_status not in ("CLEAR", "BLOCKED"):
                failures.append(f"{claim_id}: blocking_audit status is invalid")
            blocking_categories = blocking_rows.get("blocking_categories")
            if not isinstance(blocking_categories, list):
                failures.append(f"{claim_id}: blocking_audit.blocking_categories must be a list")
                blocking_categories = []
            if not isinstance(blocking_rows.get("categories"), dict):
                failures.append(f"{claim_id}: blocking_audit.categories must be an object")
            if row_status == "VERIFIED":
                if blocking_status != "CLEAR":
                    failures.append(f"{claim_id}: VERIFIED row blocking_audit must be CLEAR")
                if blocking_categories:
                    failures.append(f"{claim_id}: VERIFIED row must not list blocking categories")
            elif blocking_status != "BLOCKED":
                failures.append(f"{claim_id}: non-VERIFIED row blocking_audit must be BLOCKED")
            elif not blocking_categories:
                failures.append(f"{claim_id}: non-VERIFIED row must list blocking categories")
        record_rows = row.get("record_audit")
        if not isinstance(record_rows, dict):
            failures.append(f"{claim_id}: record_audit must be an object")
        else:
            if record_rows.get("status") not in ("PASS", "FAIL"):
                failures.append(f"{claim_id}: record_audit status is invalid")
            if not isinstance(record_rows.get("expected"), dict):
                failures.append(f"{claim_id}: record_audit.expected must be an object")
            observed = record_rows.get("observed")
            if not isinstance(observed, dict):
                failures.append(f"{claim_id}: record_audit.observed must be an object")
            else:
                if not isinstance(observed.get("flags"), dict):
                    failures.append(f"{claim_id}: record_audit.observed.flags must be an object")
                if not isinstance(observed.get("gap_record_markers"), dict):
                    failures.append(f"{claim_id}: record_audit.observed.gap_record_markers must be an object")
            if not isinstance(record_rows.get("failures"), list):
                failures.append(f"{claim_id}: record_audit.failures must be a list")
        measurement_rows = row.get("measurement_audit")
        if not isinstance(measurement_rows, list) or not measurement_rows:
            failures.append(f"{claim_id}: measurement_audit must be a non-empty list")
        else:
            for measurement in measurement_rows:
                if not isinstance(measurement, dict):
                    failures.append(f"{claim_id}: measurement_audit item must be an object")
                    continue
                if measurement.get("status") not in ("PASS", "FAIL"):
                    failures.append(f"{claim_id}: measurement_audit status must be PASS or FAIL")
        command_rows = row.get("command_audit")
        if not isinstance(command_rows, dict):
            failures.append(f"{claim_id}: command_audit must be an object")
        else:
            if command_rows.get("status") not in ("PASS", "FAIL", "NOT_REQUIRED"):
                failures.append(f"{claim_id}: command_audit status is invalid")
            for key in (
                "required_commands",
                "observed_commands",
                "missing_commands",
                "failed_commands",
                "commands_without_args",
            ):
                if not isinstance(command_rows.get(key), list):
                    failures.append(f"{claim_id}: command_audit.{key} must be a list")
        artifact_file_rows = row.get("artifact_file_audit")
        if not isinstance(artifact_file_rows, dict):
            failures.append(f"{claim_id}: artifact_file_audit must be an object")
        else:
            if artifact_file_rows.get("status") not in ("PASS", "FAIL"):
                failures.append(f"{claim_id}: artifact_file_audit status is invalid")
            if not isinstance(artifact_file_rows.get("artifacts"), list):
                failures.append(f"{claim_id}: artifact_file_audit.artifacts must be a list")
            if not isinstance(artifact_file_rows.get("malformed_artifact_indexes"), list):
                failures.append(f"{claim_id}: artifact_file_audit.malformed_artifact_indexes must be a list")
        role_audit = row.get("artifact_role_audit")
        if not isinstance(role_audit, dict):
            failures.append(f"{claim_id}: artifact_role_audit must be an object")
        else:
            if role_audit.get("status") not in ("PASS", "FAIL", "NOT_REQUIRED"):
                failures.append(f"{claim_id}: artifact_role_audit status is invalid")
            for key in (
                "required_roles",
                "observed_roles",
                "missing_roles",
                "artifacts_without_role",
                "duplicate_roles",
                "required_roles_without_path",
                "reused_required_paths",
                "path_scope_errors",
            ):
                if not isinstance(role_audit.get(key), list):
                    failures.append(f"{claim_id}: artifact_role_audit.{key} must be a list")
        gap_role_audit = row.get("gap_record_role_audit")
        if not isinstance(gap_role_audit, dict):
            failures.append(f"{claim_id}: gap_record_role_audit must be an object")
        else:
            if gap_role_audit.get("status") not in ("PASS", "FAIL", "NOT_APPLICABLE"):
                failures.append(f"{claim_id}: gap_record_role_audit status is invalid")
            if gap_role_audit.get("expected_gap_artifact_role") != GAP_ARTIFACT_ROLE:
                failures.append(f"{claim_id}: gap_record_role_audit.expected_gap_artifact_role is invalid")
            for key in (
                "observed_roles",
                "required_roles",
                "declared_required_roles_on_gap_record",
                "failures",
            ):
                if not isinstance(gap_role_audit.get(key), list):
                    failures.append(f"{claim_id}: gap_record_role_audit.{key} must be a list")
            observed_gap_role = gap_role_audit.get("observed_gap_artifact_role")
            if observed_gap_role is not None and not isinstance(observed_gap_role, str):
                failures.append(f"{claim_id}: gap_record_role_audit.observed_gap_artifact_role must be string or null")
            if gap_role_audit.get("status") == "FAIL" and not gap_role_audit.get("failures"):
                failures.append(f"{claim_id}: failed gap_record_role_audit must include failures")
            if gap_role_audit.get("status") == "PASS" and gap_role_audit.get("failures"):
                failures.append(f"{claim_id}: passing gap_record_role_audit must not include failures")
        reference_audit = row.get("reference_audit")
        if not isinstance(reference_audit, dict):
            failures.append(f"{claim_id}: reference_audit must be an object")
        else:
            if reference_audit.get("status") not in ("PASS", "FAIL", "NOT_REQUIRED"):
                failures.append(f"{claim_id}: reference_audit status is invalid")
            for key in (
                "required_claims",
                "observed_claims",
                "missing_claims",
                "unexpected_claims",
                "duplicate_claims",
                "mismatched_claims",
                "unverified_claims",
            ):
                if not isinstance(reference_audit.get(key), list):
                    failures.append(f"{claim_id}: reference_audit.{key} must be a list")
            if not isinstance(reference_audit.get("current_status_by_claim"), dict):
                failures.append(f"{claim_id}: reference_audit.current_status_by_claim must be an object")
        failures.extend(validate_replacement_contract(claim_id, row, expected_contracts.get(claim_id)))

    if replacement_required != expected_replacement:
        failures.append("replacement_required does not match non-VERIFIED rows")
    if len(replacement_required) != len(replacement_set):
        failures.append("replacement_required contains duplicate claims")
    failures.extend(validate_replacement_passport(data, rows, replacement_required))
    if data.get("status") == STATUS_ALL_VERIFIED and replacement_required:
        failures.append("ALL_EXTERNAL_EVIDENCE_VERIFIED must not have replacement_required rows")
    if data.get("status") == STATUS_ACTION_REQUIRED and not replacement_required:
        failures.append("EXTERNAL_EVIDENCE_ACTION_REQUIRED must list replacement_required rows")

    if stable_subset(data) != stable_subset(expected):
        failures.append("audit stable fields do not match current external evidence state")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("audit_latest_json"))
    latest_md = resolve_path(root, artifacts.get("audit_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("audit_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("audit_bundle_md"))

    if latest_json != audit_path:
        failures.append("artifacts.audit_latest_json does not point at the checked audit report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("audit latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("audit latest markdown does not match bundle markdown")

    expected_markdown = runner.render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("audit latest markdown does not match rendered audit report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("audit bundle markdown does not match rendered audit report")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-all-verified", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    audit_path = args.audit if args.audit.is_absolute() else root / args.audit
    failures = verify_audit(audit_path, root)
    data = load_json(audit_path) if audit_path.exists() else {}
    result = {
        "status": "PASS" if not failures else "FAIL",
        "audit": display_path(root, audit_path),
        "audit_status": data.get("status"),
        "replacement_required": data.get("replacement_required", []),
        "failures": failures,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif failures:
        print(f"FAIL: x0tta6bl4_pulse external evidence gap audit is inconsistent")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("PASS: x0tta6bl4_pulse external evidence gap audit is internally consistent")
        print(f"audit={display_path(root, audit_path)}")
        print(f"audit_status={result['audit_status']}")
    if failures:
        return 1
    if args.require_all_verified and data.get("status") != STATUS_ALL_VERIFIED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
