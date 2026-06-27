#!/usr/bin/env python3
"""Audit x0tta6bl4_pulse external evidence gaps.

This command is read-only with respect to runtime state. It evaluates each
external evidence file against the proof-gate contract, then writes a separate
machine-readable gap audit. The audit records what must still be replaced by
real kernel, lab, review, or production approval evidence. It does not promote
any proof-gate claim boundary.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.external_evidence_gap_audit.v1"
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

NEXT_ACTIONS = {
    "kernel_attach": (
        "Run the read-only kernel attach collector on the real target interface after the "
        "x0tta6bl4_pulse XDP program and pulse_stats map are present; keep the result "
        "INCOMPLETE unless bpftool/ip output proves attach and a positive packet delta."
    ),
    "packet_capture": (
        "Keep the current sender and receiver PCAP evidence if the latest proof row stays VERIFIED."
    ),
    "baseline_timing_comparison": (
        "Keep the current baseline-vs-pulse timing comparison if the latest proof row stays VERIFIED."
    ),
    "dpi_lab": (
        "Replace the gap record with an authorized DPI-lab evidence file containing baseline "
        "detect-or-block output, pulse output, lab identity, artifact hashes, and a verified conclusion."
    ),
    "whitelist_lab": (
        "Replace the gap record with authorized provider or lab evidence for provider profile, "
        "third-party baseline capture, and verified whitelist-behavior result."
    ),
    "security_review": (
        "Replace the gap record with a completed security review covering pulse transport and "
        "showing zero open critical and high findings."
    ),
    "production_readiness": (
        "Replace the gap record only after all prior proof rows are referenced by an operator "
        "approval record with verified rollback and monitoring plans."
    ),
}


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


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_proof_gate(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_proof_gate_for_gap_audit", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def requirement_by_claim(proof) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}


def load_payload(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def record_audit(proof, requirement: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema": getattr(proof, "EVIDENCE_SCHEMA", "x0tta6bl4.ghost_pulse.claim_evidence.v1"),
        "claim_id": requirement["claim_id"],
        "status": "VERIFIED",
        "flags": {
            "simulated": False,
            "dry_run": False,
            "template": False,
        },
    }
    observed_flags = {
        "simulated": payload.get("simulated"),
        "dry_run": payload.get("dry_run"),
        "template": payload.get("template"),
    }
    claim_boundary = payload.get("claim_boundary")
    gap_record_markers = {
        "mode": payload.get("mode"),
        "missing_inputs_present": bool(payload.get("missing_inputs")),
        "failures_present": bool(payload.get("failures")),
        "claim_boundary_claim_verified_false": (
            isinstance(claim_boundary, dict) and claim_boundary.get("claim_verified") is False
        ),
    }
    observed = {
        "schema": payload.get("schema"),
        "claim_id": payload.get("claim_id"),
        "status": payload.get("status"),
        "observed_at_utc": payload.get("observed_at_utc"),
        "flags": observed_flags,
        "gap_record_markers": gap_record_markers,
    }

    failures: list[str] = []
    if observed["schema"] != expected["schema"]:
        failures.append("schema must match proof-gate evidence schema")
    if observed["claim_id"] != expected["claim_id"]:
        failures.append("claim_id must match requirement")
    if observed["status"] != expected["status"]:
        failures.append("status must be VERIFIED")
    if not isinstance(observed["observed_at_utc"], str) or not observed["observed_at_utc"]:
        failures.append("observed_at_utc must be present")
    for flag, expected_value in expected["flags"].items():
        if observed_flags.get(flag) is not expected_value:
            failures.append(f"{flag} must be false")
    if gap_record_markers["mode"] == "EXTERNAL_EVIDENCE_GAP_RECORD":
        failures.append("mode must not be EXTERNAL_EVIDENCE_GAP_RECORD")
    if gap_record_markers["missing_inputs_present"]:
        failures.append("missing_inputs must be absent or empty")
    if gap_record_markers["failures_present"]:
        failures.append("failures must be absent or empty")
    if gap_record_markers["claim_boundary_claim_verified_false"]:
        failures.append("claim_boundary.claim_verified must not be false")

    return {
        "status": "PASS" if not failures else "FAIL",
        "expected": expected,
        "observed": observed,
        "failures": failures,
    }


def measurement_audit(proof, requirement: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    measurements = payload.get("measurements", {})
    if not isinstance(measurements, dict):
        measurements = {}
    rows = []
    for key, expectation in requirement["measurements"].items():
        observed = measurements.get(key)
        rows.append(
            {
                "name": key,
                "expected": expectation,
                "observed": observed,
                "status": "PASS" if proof.measurement_matches(observed, expectation) else "FAIL",
            }
        )
    return rows


def command_audit(proof, requirement: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    required_templates = list(requirement.get("required_commands", []))
    measurements = payload.get("measurements", {})
    if not isinstance(measurements, dict):
        measurements = {}
    commands = payload.get("commands", [])
    if not isinstance(commands, list):
        commands = []

    required_commands = [
        proof.render_command_template(template, measurements)
        for template in required_templates
    ]
    observed_commands: list[list[str]] = []
    normalized_commands: list[dict[str, Any]] = []
    failed_commands: list[dict[str, Any]] = []
    commands_without_args: list[int] = []
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            commands_without_args.append(index)
            continue
        args = command.get("args")
        rendered_args: list[str] = []
        if isinstance(args, list) and args:
            rendered_args = [str(part) for part in args]
            observed_commands.append(rendered_args)
            normalized_commands.append({"args": rendered_args})
        else:
            commands_without_args.append(index)
        if command.get("exit_code") != 0:
            failed_commands.append(
                {
                    "index": index,
                    "args": rendered_args,
                    "exit_code": command.get("exit_code"),
                }
            )

    missing_commands: list[list[str]] = []
    if required_templates:
        missing_commands = proof.missing_required_commands(
            normalized_commands,
            required_templates,
            measurements,
        )

    if not required_templates:
        status = "NOT_REQUIRED"
    elif missing_commands or failed_commands or commands_without_args:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "required_commands": required_commands,
        "observed_commands": observed_commands,
        "missing_commands": missing_commands,
        "failed_commands": failed_commands,
        "commands_without_args": commands_without_args,
    }


def artifact_file_audit(root: Path, proof, payload: dict[str, Any]) -> dict[str, Any]:
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []

    rows: list[dict[str, Any]] = []
    malformed_artifact_indexes: list[int] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            malformed_artifact_indexes.append(index)
            continue
        path = artifact.get("path")
        expected_sha256 = artifact.get("sha256")
        path_errors: list[str] = []
        exists: bool | None = None
        actual_sha256: str | None = None
        sha256_matches = False
        if not isinstance(path, str) or not path:
            path_errors.append("artifact path is required")
        elif hasattr(proof, "artifact_path_errors"):
            path_errors.extend(proof.artifact_path_errors(root, path))

        if isinstance(path, str) and path and not path_errors:
            resolved = proof.resolve_path(root, path)
            exists = bool(resolved and resolved.exists())
            if exists:
                actual_sha256 = proof.sha256_file(resolved)
                sha256_matches = expected_sha256 == actual_sha256

        status = "PASS" if not path_errors and exists is True and sha256_matches else "FAIL"
        rows.append(
            {
                "index": index,
                "status": status,
                "path": path,
                "path_errors": path_errors,
                "exists": exists,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "sha256_matches": sha256_matches,
            }
        )

    status = "PASS"
    if not artifacts or malformed_artifact_indexes or any(row["status"] != "PASS" for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "artifacts": rows,
        "malformed_artifact_indexes": malformed_artifact_indexes,
    }


def artifact_role_audit(root: Path, proof, requirement: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    required_roles = list(requirement.get("required_artifact_roles", []))
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []

    observed_roles: list[str] = []
    artifacts_without_role: list[int] = []
    duplicate_roles: list[str] = []
    seen_roles: set[str] = set()
    required_path_by_role: dict[str, str] = {}
    required_role_by_path: dict[str, str] = {}
    reused_required_paths: list[dict[str, str]] = []
    path_scope_errors: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            artifacts_without_role.append(index)
            continue
        role = artifact.get("role")
        if isinstance(role, str) and role.strip():
            observed_roles.append(role)
            if role in seen_roles:
                duplicate_roles.append(role)
            seen_roles.add(role)
        else:
            artifacts_without_role.append(index)
            role = None
        path = artifact.get("path")
        if isinstance(path, str) and path:
            if hasattr(proof, "artifact_path_errors"):
                for error in proof.artifact_path_errors(root, path):
                    path_scope_errors.append({"artifact_index": index, "path": path, "error": error})
            if isinstance(role, str) and role in required_roles:
                required_path_by_role[role] = path
                previous_role = required_role_by_path.get(path)
                if previous_role and previous_role != role:
                    reused_required_paths.append(
                        {"path": path, "first_role": previous_role, "second_role": role}
                    )
                else:
                    required_role_by_path[path] = role

    missing_roles = [role for role in required_roles if role not in observed_roles]
    required_roles_without_path = [
        role
        for role in required_roles
        if role in observed_roles and role not in required_path_by_role
    ]
    if not required_roles:
        status = "NOT_REQUIRED"
    elif (
        missing_roles
        or artifacts_without_role
        or duplicate_roles
        or required_roles_without_path
        or reused_required_paths
        or path_scope_errors
    ):
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "required_roles": required_roles,
        "observed_roles": observed_roles,
        "missing_roles": missing_roles,
        "artifacts_without_role": artifacts_without_role,
        "duplicate_roles": sorted(set(duplicate_roles)),
        "required_roles_without_path": required_roles_without_path,
        "reused_required_paths": reused_required_paths,
        "path_scope_errors": path_scope_errors,
    }


def gap_record_role_audit(requirement: dict[str, Any], payload: dict[str, Any], roles: dict[str, Any]) -> dict[str, Any]:
    required_roles = list(requirement.get("required_artifact_roles", []))
    observed_roles = list(roles.get("observed_roles", [])) if isinstance(roles.get("observed_roles"), list) else []
    mode = payload.get("mode")
    observed_gap_role = payload.get("gap_artifact_role")
    is_gap_record = (
        mode == "EXTERNAL_EVIDENCE_GAP_RECORD"
        or observed_gap_role == GAP_ARTIFACT_ROLE
        or GAP_ARTIFACT_ROLE in observed_roles
    )
    declared_required_roles = sorted(set(observed_roles) & set(required_roles))
    failures: list[str] = []

    if not is_gap_record:
        status = "NOT_APPLICABLE"
    else:
        if observed_gap_role != GAP_ARTIFACT_ROLE:
            failures.append(f"gap_artifact_role must be {GAP_ARTIFACT_ROLE}")
        if GAP_ARTIFACT_ROLE not in observed_roles:
            failures.append(f"artifacts must include role {GAP_ARTIFACT_ROLE}")
        if GAP_ARTIFACT_ROLE in required_roles:
            failures.append("gap artifact role must not be a proof-gate required role")
        if declared_required_roles:
            failures.append("gap record must not declare proof-gate required artifact roles")
        status = "FAIL" if failures else "PASS"

    return {
        "status": status,
        "expected_gap_artifact_role": GAP_ARTIFACT_ROLE,
        "observed_gap_artifact_role": observed_gap_role,
        "observed_roles": observed_roles,
        "required_roles": required_roles,
        "declared_required_roles_on_gap_record": declared_required_roles,
        "failures": failures,
    }


def reference_audit(root: Path, proof, requirement: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    required_claims = list(requirement.get("required_references", []))
    references = payload.get("references", [])
    if not isinstance(references, list):
        references = []

    observed_claims: list[str] = []
    duplicate_claims: list[str] = []
    seen: set[str] = set()
    refs_by_claim: dict[str, dict[str, Any]] = {}
    for reference in references:
        if not isinstance(reference, dict):
            continue
        claim_id = reference.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            continue
        observed_claims.append(claim_id)
        if claim_id in seen:
            duplicate_claims.append(claim_id)
            continue
        seen.add(claim_id)
        refs_by_claim[claim_id] = reference

    requirements = requirement_by_claim(proof)
    current_status_by_claim: dict[str, str] = {}
    mismatched_claims: list[str] = []
    for claim_id in required_claims:
        required = requirements.get(claim_id)
        if not required:
            current_status_by_claim[claim_id] = "UNKNOWN_REQUIREMENT"
            mismatched_claims.append(claim_id)
            continue
        validation = proof.validate_external_evidence(root, required)
        current_status_by_claim[claim_id] = validation["status"]
        reference = refs_by_claim.get(claim_id)
        if not reference:
            continue
        for key in ("status", "evidence", "sha256"):
            if reference.get(key) != validation.get(key):
                mismatched_claims.append(claim_id)
                break

    missing_claims = [claim_id for claim_id in required_claims if claim_id not in refs_by_claim]
    unexpected_claims = sorted(set(observed_claims) - set(required_claims))
    unverified_claims = [
        claim_id
        for claim_id in required_claims
        if current_status_by_claim.get(claim_id) != "VERIFIED"
    ]
    if not required_claims:
        status = "NOT_REQUIRED"
    elif missing_claims or unexpected_claims or duplicate_claims or mismatched_claims or unverified_claims:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "required_claims": required_claims,
        "observed_claims": observed_claims,
        "missing_claims": missing_claims,
        "unexpected_claims": unexpected_claims,
        "duplicate_claims": duplicate_claims,
        "mismatched_claims": sorted(set(mismatched_claims)),
        "unverified_claims": unverified_claims,
        "current_status_by_claim": current_status_by_claim,
    }


def blocking_audit(
    validation: dict[str, Any],
    missing_inputs: list[Any],
    measurements: list[dict[str, Any]],
    record: dict[str, Any],
    commands: dict[str, Any],
    artifact_files: dict[str, Any],
    artifact_roles: dict[str, Any],
    gap_record_roles: dict[str, Any],
    references: dict[str, Any],
) -> dict[str, Any]:
    categories: dict[str, Any] = {}

    record_failures = record.get("failures", [])
    if isinstance(record_failures, list) and record_failures:
        categories["record"] = record_failures

    failed_measurements = [
        {
            "name": item.get("name"),
            "expected": item.get("expected"),
            "observed": item.get("observed"),
        }
        for item in measurements
        if isinstance(item, dict) and item.get("status") != "PASS"
    ]
    if failed_measurements:
        categories["measurements"] = failed_measurements

    command_blockers = {
        "missing_commands": commands.get("missing_commands", []),
        "failed_commands": commands.get("failed_commands", []),
        "commands_without_args": commands.get("commands_without_args", []),
    }
    if any(command_blockers.values()):
        categories["commands"] = command_blockers

    failed_artifact_files = [
        item
        for item in artifact_files.get("artifacts", [])
        if isinstance(item, dict) and item.get("status") != "PASS"
    ]
    malformed_artifacts = artifact_files.get("malformed_artifact_indexes", [])
    if failed_artifact_files or malformed_artifacts:
        categories["artifact_files"] = {
            "failed_artifacts": failed_artifact_files,
            "malformed_artifact_indexes": malformed_artifacts,
        }

    artifact_role_blockers = {
        key: artifact_roles.get(key, [])
        for key in (
            "missing_roles",
            "artifacts_without_role",
            "duplicate_roles",
            "required_roles_without_path",
            "reused_required_paths",
            "path_scope_errors",
        )
    }
    if any(artifact_role_blockers.values()):
        categories["artifact_roles"] = artifact_role_blockers

    gap_record_role_failures = gap_record_roles.get("failures", [])
    if isinstance(gap_record_role_failures, list) and gap_record_role_failures:
        categories["gap_record_roles"] = gap_record_role_failures

    reference_blockers = {
        key: references.get(key, [])
        for key in (
            "missing_claims",
            "unexpected_claims",
            "duplicate_claims",
            "mismatched_claims",
            "unverified_claims",
        )
    }
    if any(reference_blockers.values()):
        categories["references"] = reference_blockers

    if missing_inputs:
        categories["missing_inputs"] = missing_inputs

    proof_errors = validation.get("errors", [])
    if proof_errors:
        categories["proof_errors"] = proof_errors

    blocking_categories = sorted(categories)
    status = "CLEAR" if not blocking_categories else "BLOCKED"
    return {
        "status": status,
        "blocking_categories": blocking_categories,
        "categories": categories,
    }


def replacement_contract(proof, requirement: dict[str, Any]) -> dict[str, Any]:
    if hasattr(proof, "external_requirement_contract"):
        contract = proof.external_requirement_contract(requirement)
    else:
        contract = {
            "claim_id": requirement["claim_id"],
            "title": requirement["title"],
            "path": requirement["path"],
            "measurements": requirement["measurements"],
        }
    contract = dict(contract)
    claim_id = requirement["claim_id"]
    acceptance_commands = [
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--require-pass",
            "--json",
        ]
    ]
    if claim_id == "production_readiness":
        acceptance_commands.append(
            [
                "python3",
                "scripts/ops/verify_ghost_pulse_proof_gate.py",
                "--require-all-proven",
                "--json",
            ]
        )
    contract.update(
        {
            "evidence_schema": getattr(proof, "EVIDENCE_SCHEMA", "x0tta6bl4.ghost_pulse.claim_evidence.v1"),
            "required_status": "VERIFIED",
            "required_flags": {
                "simulated": False,
                "dry_run": False,
                "template": False,
            },
            "destination": requirement["path"],
            "acceptance_commands": acceptance_commands,
        }
    )
    return contract


def incoming_example_path(claim_id: str) -> str:
    return f"docs/verification/incoming/examples/{claim_id}.example.json"


def replacement_passport(rows: list[dict[str, Any]]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("replacement_required"):
            continue
        claim_id = row["claim_id"]
        candidate_path = f"docs/verification/incoming/{claim_id}.json"
        import_command = [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--candidate",
            candidate_path,
            "--require-ready",
            "--json",
        ]
        write_command = [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--candidate",
            candidate_path,
            "--write",
            "--json",
        ]
        claims.append(
            {
                "claim_id": claim_id,
                "title": row["title"],
                "destination": row["evidence"],
                "current_status": row["status"],
                "current_sha256": row["sha256"],
                "blocking_categories": row.get("blocking_audit", {}).get("blocking_categories", []),
                "replacement_contract": row["replacement_contract"],
                "candidate_path": candidate_path,
                "candidate_example_path": incoming_example_path(claim_id),
                "incoming_example_command": INCOMING_EXAMPLE_COMMAND,
                "read_only_import_command": import_command,
                "write_import_command": write_command,
                "acceptance_commands": row["replacement_contract"]["acceptance_commands"],
            }
        )
    return {
        "schema": REPLACEMENT_PASSPORT_SCHEMA,
        "status": REPLACEMENT_PASSPORT_ACTION_REQUIRED if claims else REPLACEMENT_PASSPORT_ALL_REPLACED,
        "claims": claims,
        "claim_boundary": {
            "note": "Replacement passport only; it never promotes proof-gate claims.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }


def row_for_requirement(root: Path, proof, requirement: dict[str, Any]) -> dict[str, Any]:
    validation = proof.validate_external_evidence(root, requirement)
    evidence_path = proof.resolve_path(root, requirement["path"])
    payload = load_payload(evidence_path)
    claim_id = requirement["claim_id"]
    measurements = measurement_audit(proof, requirement, payload)
    missing_inputs = payload.get("missing_inputs", [])
    if not isinstance(missing_inputs, list):
        missing_inputs = []
    record = record_audit(proof, requirement, payload)
    commands = command_audit(proof, requirement, payload)
    artifact_files = artifact_file_audit(root, proof, payload)
    artifact_roles = artifact_role_audit(root, proof, requirement, payload)
    gap_record_roles = gap_record_role_audit(requirement, payload, artifact_roles)
    references = reference_audit(root, proof, requirement, payload)
    return {
        "claim_id": claim_id,
        "title": requirement["title"],
        "status": validation["status"],
        "evidence": validation["evidence"],
        "sha256": validation["sha256"],
        "replacement_required": validation["status"] != "VERIFIED",
        "errors": validation["errors"],
        "required_measurements": requirement["measurements"],
        "record_audit": record,
        "measurement_audit": measurements,
        "command_audit": commands,
        "artifact_file_audit": artifact_files,
        "artifact_role_audit": artifact_roles,
        "gap_record_role_audit": gap_record_roles,
        "reference_audit": references,
        "blocking_audit": blocking_audit(
            validation,
            missing_inputs,
            measurements,
            record,
            commands,
            artifact_files,
            artifact_roles,
            gap_record_roles,
            references,
        ),
        "replacement_contract": replacement_contract(proof, requirement),
        "missing_inputs": missing_inputs,
        "next_action": NEXT_ACTIONS.get(claim_id, "Provide evidence that satisfies the proof-gate contract."),
    }


def build_report(root: Path = ROOT, claims: list[str] | None = None) -> dict[str, Any]:
    proof = load_proof_gate(root)
    requirements = requirement_by_claim(proof)
    selected_claims = claims or list(requirements)
    unknown = sorted(set(selected_claims) - set(requirements))
    rows = [
        row_for_requirement(root, proof, requirements[claim_id])
        for claim_id in selected_claims
        if claim_id in requirements
    ]
    failures = [f"unknown claim: {claim_id}" for claim_id in unknown]
    for row in rows:
        if row["status"] != "VERIFIED":
            failures.extend(f"{row['claim_id']}: {error}" for error in row["errors"])
    status = STATUS_ALL_VERIFIED if rows and not failures else STATUS_ACTION_REQUIRED
    report = {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "status": status,
        "selected_claims": selected_claims,
        "rows": rows,
        "failures": failures,
        "replacement_required": [row["claim_id"] for row in rows if row["replacement_required"]],
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
            "note": "Gap audit only; proof-gate claim boundaries are not upgraded by this report.",
        },
    }
    report["replacement_passport"] = replacement_passport(rows)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse External Evidence Gap Audit",
        "",
        f"Timestamp: `{report['timestamp_utc']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Claim Boundary",
        "",
    ]
    for key in sorted(report["claim_boundary"]):
        value = report["claim_boundary"][key]
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rows", "", "| Claim | Status | Replacement Required | Evidence |", "| --- | --- | --- | --- |"])
    for row in report["rows"]:
        lines.append(
            f"| {row['claim_id']} | `{row['status']}` | `{row['replacement_required']}` | `{row['evidence']}` |"
        )
    lines.extend(["", "## Next Actions", ""])
    for row in report["rows"]:
        if row["replacement_required"]:
            lines.append(f"- {row['claim_id']}: {row['next_action']}")
    if not report["replacement_required"]:
        lines.append("- None")
    lines.extend(["", "## Blocking Audit", ""])
    for row in report["rows"]:
        audit = row.get("blocking_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; blocking audit is missing")
            continue
        categories = ", ".join(audit.get("blocking_categories", [])) or "none"
        lines.append(f"- {row['claim_id']}: `{audit['status']}`; categories: `{categories}`")
    lines.extend(["", "## Evidence Records", ""])
    for row in report["rows"]:
        audit = row.get("record_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; record audit is missing")
            continue
        observed = audit.get("observed", {})
        gap_markers = observed.get("gap_record_markers", {}) if isinstance(observed, dict) else {}
        failures = "; ".join(audit.get("failures", [])) or "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; status: `{observed.get('status')}`; "
            f"mode: `{gap_markers.get('mode')}`; missing inputs present: "
            f"`{gap_markers.get('missing_inputs_present')}`; failures: `{failures}`"
        )
    lines.extend(["", "## Commands", ""])
    for row in report["rows"]:
        audit = row.get("command_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; command audit is missing")
            continue
        if audit["status"] == "NOT_REQUIRED":
            lines.append(f"- {row['claim_id']}: no exact command set required")
            continue
        missing = "; ".join(" ".join(command) for command in audit["missing_commands"]) or "none"
        failed = "; ".join(
            f"{' '.join(item.get('args', []))} -> {item.get('exit_code')}"
            for item in audit["failed_commands"]
            if isinstance(item, dict)
        ) or "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; missing commands: `{missing}`; "
            f"failed commands: `{failed}`"
        )
    lines.extend(["", "## Artifact Files", ""])
    for row in report["rows"]:
        audit = row.get("artifact_file_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; artifact file audit is missing")
            continue
        failed = [
            item
            for item in audit.get("artifacts", [])
            if isinstance(item, dict) and item.get("status") != "PASS"
        ]
        if not failed and not audit.get("malformed_artifact_indexes"):
            lines.append(f"- {row['claim_id']}: `{audit['status']}`; all artifact files match recorded hashes")
            continue
        failed_paths = "; ".join(
            f"{item.get('path')}: exists={item.get('exists')}, sha256_matches={item.get('sha256_matches')}"
            for item in failed
        ) or "none"
        malformed = ", ".join(str(index) for index in audit.get("malformed_artifact_indexes", [])) or "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; failed artifacts: `{failed_paths}`; "
            f"malformed artifact indexes: `{malformed}`"
        )
    lines.extend(["", "## Artifact Roles", ""])
    for row in report["rows"]:
        audit = row.get("artifact_role_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; artifact role audit is missing")
            continue
        if audit["status"] == "NOT_REQUIRED":
            lines.append(f"- {row['claim_id']}: no named artifact roles required")
            continue
        missing = ", ".join(audit["missing_roles"]) if audit["missing_roles"] else "none"
        observed = ", ".join(audit["observed_roles"]) if audit["observed_roles"] else "none"
        duplicate_roles = ", ".join(audit.get("duplicate_roles", [])) or "none"
        without_path = ", ".join(audit.get("required_roles_without_path", [])) or "none"
        reused_paths = "; ".join(
            f"{item.get('path')} ({item.get('first_role')} -> {item.get('second_role')})"
            for item in audit.get("reused_required_paths", [])
            if isinstance(item, dict)
        ) or "none"
        path_errors = "; ".join(
            f"{item.get('path')}: {item.get('error')}"
            for item in audit.get("path_scope_errors", [])
            if isinstance(item, dict)
        ) or "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; observed roles: `{observed}`; "
            f"missing roles: `{missing}`; duplicate roles: `{duplicate_roles}`; "
            f"required roles without path: `{without_path}`; reused required paths: `{reused_paths}`; "
            f"path scope errors: `{path_errors}`"
        )
    lines.extend(["", "## Gap Record Roles", ""])
    for row in report["rows"]:
        audit = row.get("gap_record_role_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; gap record role audit is missing")
            continue
        declared = ", ".join(audit.get("declared_required_roles_on_gap_record", [])) or "none"
        failures = "; ".join(audit.get("failures", [])) or "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; expected gap role: "
            f"`{audit.get('expected_gap_artifact_role')}`; observed gap role: "
            f"`{audit.get('observed_gap_artifact_role')}`; declared proof roles: "
            f"`{declared}`; failures: `{failures}`"
        )
    lines.extend(["", "## References", ""])
    for row in report["rows"]:
        audit = row.get("reference_audit")
        if not isinstance(audit, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; reference audit is missing")
            continue
        if audit["status"] == "NOT_REQUIRED":
            lines.append(f"- {row['claim_id']}: no prior-claim references required")
            continue
        missing = ", ".join(audit["missing_claims"]) if audit["missing_claims"] else "none"
        unverified = ", ".join(audit["unverified_claims"]) if audit["unverified_claims"] else "none"
        lines.append(
            f"- {row['claim_id']}: `{audit['status']}`; missing references: `{missing}`; "
            f"unverified referenced claims: `{unverified}`"
        )
    lines.extend(["", "## Replacement Contracts", ""])
    for row in report["rows"]:
        contract = row.get("replacement_contract")
        if not isinstance(contract, dict):
            lines.append(f"- {row['claim_id']}: `INVALID`; replacement contract is missing")
            continue
        commands = contract.get("acceptance_commands", [])
        first_command = " ".join(commands[0]) if commands and isinstance(commands[0], list) else "none"
        lines.append(
            f"- {row['claim_id']}: destination `{contract.get('destination')}`; "
            f"required status `{contract.get('required_status')}`; acceptance `{first_command}`"
        )
    passport = report.get("replacement_passport")
    lines.extend(["", "## Replacement Passport", ""])
    if not isinstance(passport, dict):
        lines.append("- `INVALID`; replacement_passport is missing")
    else:
        lines.append(f"- status: `{passport.get('status')}`")
        claims = passport.get("claims")
        if not claims:
            lines.append("- claims: none")
        elif not isinstance(claims, list):
            lines.append("- claims: `INVALID`")
        else:
            for claim in claims:
                if not isinstance(claim, dict):
                    lines.append("- `INVALID`; replacement_passport claim is malformed")
                    continue
                read_only = " ".join(claim.get("read_only_import_command", []))
                write = " ".join(claim.get("write_import_command", []))
                lines.append(
                    f"- {claim.get('claim_id')}: candidate `{claim.get('candidate_path')}`; "
                    f"example `{claim.get('candidate_example_path')}`; "
                    f"read-only import `{read_only}`; write import `{write}`"
                )
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-external-evidence-gap-audit-{stamp}"
    bundle_json = bundle_dir / "audit.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "audit_bundle_json": display_path(root, bundle_json),
        "audit_bundle_md": display_path(root, bundle_md),
        "audit_latest_json": display_path(root, output_json),
        "audit_latest_md": display_path(root, output_md),
    }
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--claim", action="append", help="Claim id to audit. Repeatable.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--require-all-verified", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = build_report(root=root, claims=args.claim)
    output_paths: dict[str, Path] = {}
    if not args.no_write:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        output_paths = write_report_outputs(root, report, output_json, output_md)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "bundle": display_path(root, output_paths["bundle_dir"]) if output_paths else None,
                    "output_json": display_path(root, output_paths["latest_json"]) if output_paths else None,
                    "output_md": display_path(root, output_paths["latest_md"]) if output_paths else None,
                    "replacement_required": report["replacement_required"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    if args.require_all_verified and report["status"] != STATUS_ALL_VERIFIED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
