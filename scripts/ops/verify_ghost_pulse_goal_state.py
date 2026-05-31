#!/usr/bin/env python3
"""Verify the active x0tta6bl4_pulse proof-goal state.

This checker is read-only by default. It verifies that packet_capture and
baseline_timing_comparison are proven, that the remaining external evidence
gaps are explicit in proof/intake/inventory reports, and that claim boundaries
are derived from proof rows instead of being promoted by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"

DEFAULT_PROOF = VERIFY_ROOT / "GHOST_PULSE_PROOF_GATE_LATEST.json"
DEFAULT_REPLACEMENT = VERIFY_ROOT / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
DEFAULT_INTAKE = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
DEFAULT_INVENTORY = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
DEFAULT_CHAIN = VERIFY_ROOT / "GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
DEFAULT_EXAMPLES_MANIFEST = VERIFY_ROOT / "incoming" / "examples" / "manifest.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_GOAL_STATE_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_GOAL_STATE_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.goal_state.v1"
DECISION_GAPS_RECORDED = "GHOST_PULSE_GOAL_STATE_GAPS_RECORDED_FAIL_CLOSED"
DECISION_ALL_PROVEN = "GHOST_PULSE_GOAL_STATE_ALL_CLAIMS_PROVEN"
DECISION_INVALID = "GHOST_PULSE_GOAL_STATE_INVALID"

PROOF_DECISION_INCOMPLETE = "GHOST_PULSE_PROOF_INCOMPLETE"
PROOF_DECISION_PROVEN = "GHOST_PULSE_ALL_CLAIMS_PROVEN"
REPLACEMENT_DECISION_NOT_READY = "REPLACEMENT_CANDIDATES_NOT_READY"
REPLACEMENT_DECISION_READY = "REPLACEMENT_CANDIDATES_READY"
INTAKE_DECISION_ACTION_REQUIRED = "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED"
INTAKE_DECISION_READY_NOT_WRITTEN = "EXTERNAL_EVIDENCE_INTAKE_READY_NOT_WRITTEN"
INVENTORY_STATUS_GAPS = "EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS"
INVENTORY_STATUS_ALL_VERIFIED = "EXTERNAL_EVIDENCE_INVENTORY_ALL_VERIFIED"
CHAIN_DECISION_VERIFIED = "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED"
EXAMPLES_STATUS = "EXAMPLE_ONLY_NOT_EVIDENCE"

EXPECTED_PROOF_ROW_CLAIMS = (
    "local_timing_replay",
    "false_claim_hygiene",
    "artifact_chain",
    "kernel_attach",
    "packet_capture",
    "baseline_timing_comparison",
    "dpi_lab",
    "whitelist_lab",
    "security_review",
    "production_readiness",
    "current_runtime_attached",
)
EXTERNAL_EVIDENCE_CLAIMS = (
    "kernel_attach",
    "packet_capture",
    "baseline_timing_comparison",
    "dpi_lab",
    "whitelist_lab",
    "security_review",
    "production_readiness",
)
STARTER_VERIFIED_CLAIMS = (
    "packet_capture",
    "baseline_timing_comparison",
)
CLOSURE_CLAIMS = (
    "kernel_attach",
    "dpi_lab",
    "whitelist_lab",
    "security_review",
    "production_readiness",
)
RUNTIME_CLAIMS = (
    "current_runtime_attached",
)
FALSE_REPORT_BOUNDARY_KEYS = (
    "stealth_verified",
    "whitelist_verified",
    "kernel_attach_verified",
    "production_ready",
)
STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "decision",
    "starter_verified_claims",
    "pending_external_evidence_claims",
    "pending_runtime_claims",
    "pending_external_evidence_details",
    "candidate_paths",
    "claim_boundary",
    "source_reports",
    "checks",
    "failures",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
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
    return {key: report.get(key) for key in STABLE_REPORT_KEYS}


def candidate_path(claim_id: str) -> str:
    return f"docs/verification/incoming/{claim_id}.json"


def expected_candidate_paths(claim_ids: list[str] | tuple[str, ...]) -> dict[str, str]:
    return {claim_id: candidate_path(claim_id) for claim_id in claim_ids}


def source_report(root: Path, path: Path, data: dict[str, Any] | None, load_error: str | None) -> dict[str, Any]:
    return {
        "path": display_path(root, path),
        "exists": path.exists(),
        "is_file": path.is_file() if path.exists() else False,
        "sha256": sha256_file(path),
        "schema": data.get("schema") if data else None,
        "status": data.get("status") if data else None,
        "decision": (
            data.get("decision")
            or data.get("inventory_status")
            or data.get("artifact_chain_status")
            if data
            else None
        ),
        "failures_count": len(data.get("failures") or []) if data else None,
        "load_error": load_error,
    }


def load_sources(root: Path, paths: dict[str, Path]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    data_by_name: dict[str, dict[str, Any]] = {}
    reports: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        load_error = None
        data: dict[str, Any] | None = None
        if path.exists() and path.is_file():
            try:
                data = load_json(path)
            except Exception as exc:
                load_error = str(exc)
                data = None
        elif not path.exists():
            load_error = "missing"
        else:
            load_error = "not a regular file"
        if data is not None:
            data_by_name[name] = data
        reports[name] = source_report(root, path, data, load_error)
    return data_by_name, reports


def proof_status_by_claim(proof: dict[str, Any], failures: list[str]) -> dict[str, str]:
    rows = proof.get("proof_rows")
    if not isinstance(rows, list):
        failures.append("proof.proof_rows must be a list")
        return {}
    observed_claims: list[str] = []
    statuses: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"proof.proof_rows[{index}] must be an object")
            continue
        claim_id = row.get("claim_id")
        status = row.get("status")
        if not isinstance(claim_id, str) or not claim_id:
            failures.append(f"proof.proof_rows[{index}].claim_id is required")
            continue
        observed_claims.append(claim_id)
        if status not in ("VERIFIED", "INVALID", "MISSING"):
            failures.append(f"proof.{claim_id}.status is unexpected: {status}")
            continue
        statuses[claim_id] = status
    if observed_claims != list(EXPECTED_PROOF_ROW_CLAIMS):
        failures.append("proof.proof_rows claim order does not match proof-goal contract")
    return statuses


def rows_by_claim(data: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows = data.get(key)
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_id = row.get("claim_id")
        if isinstance(claim_id, str) and claim_id:
            result[claim_id] = row
    return result


def expected_proof_boundary(statuses: dict[str, str]) -> dict[str, bool]:
    return {
        "current_runtime_attached": statuses.get("current_runtime_attached") == "VERIFIED",
        "kernel_attach_verified": statuses.get("kernel_attach") == "VERIFIED",
        "production_ready": all(statuses.get(claim_id) == "VERIFIED" for claim_id in EXPECTED_PROOF_ROW_CLAIMS),
        "stealth_verified": (
            statuses.get("packet_capture") == "VERIFIED"
            and statuses.get("baseline_timing_comparison") == "VERIFIED"
            and statuses.get("dpi_lab") == "VERIFIED"
        ),
        "whitelist_verified": statuses.get("whitelist_lab") == "VERIFIED",
    }


def false_report_boundary_failures(report_name: str, value: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(value, dict):
        return [f"{report_name}.claim_boundary must be an object"]
    for key in FALSE_REPORT_BOUNDARY_KEYS:
        if value.get(key) is not False:
            failures.append(f"{report_name}.claim_boundary.{key} must remain false")
    return failures


def list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    return list(value) if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def check_partition(report_name: str, ready: list[Any], not_ready: list[Any], pending: list[str]) -> list[str]:
    failures: list[str] = []
    combined = [item for item in ready + not_ready if isinstance(item, str)]
    if sorted(combined) != sorted(pending):
        failures.append(f"{report_name}.ready/not_ready must partition pending_external_evidence_claims")
    if len(combined) != len(set(combined)):
        failures.append(f"{report_name}.ready/not_ready contains duplicate claims")
    unexpected = [item for item in combined if item not in pending]
    if unexpected:
        failures.append(f"{report_name}.ready/not_ready contains unexpected claims: {', '.join(unexpected)}")
    return failures


def evidence_summary(root: Path, proof_row: dict[str, Any]) -> dict[str, Any]:
    evidence_value = proof_row.get("evidence")
    evidence_path = resolve_path(root, evidence_value) if isinstance(evidence_value, str) else None
    summary: dict[str, Any] = {
        "path": evidence_value if isinstance(evidence_value, str) else None,
        "proof_sha256": proof_row.get("sha256") if isinstance(proof_row.get("sha256"), str) else None,
        "exists": bool(evidence_path and evidence_path.exists()),
        "is_file": bool(evidence_path and evidence_path.is_file()),
        "actual_sha256": sha256_file(evidence_path) if evidence_path else None,
        "sha256_matches_proof": False,
        "load_error": None,
        "status": None,
        "failures_count": None,
        "claim_id": None,
        "collection_diagnostics": None,
        "object_preflight": None,
    }
    proof_sha = summary["proof_sha256"]
    actual_sha = summary["actual_sha256"]
    summary["sha256_matches_proof"] = bool(proof_sha and actual_sha and proof_sha == actual_sha)
    if not evidence_path or not evidence_path.exists() or not evidence_path.is_file():
        return summary
    try:
        current = load_json(evidence_path)
    except Exception as exc:
        summary["load_error"] = str(exc)
        return summary
    summary["status"] = current.get("status")
    summary["claim_id"] = current.get("claim_id")
    summary["failures_count"] = len(current.get("failures") or [])
    diagnostics = current.get("collection_diagnostics")
    if isinstance(diagnostics, dict):
        summary["collection_diagnostics"] = {
            "status": diagnostics.get("status"),
            "blockers": string_list(diagnostics.get("blockers")),
            "next_action": diagnostics.get("next_action"),
            "interface": diagnostics.get("interface"),
            "interface_seen": diagnostics.get("interface_seen"),
            "xdp_attached": diagnostics.get("xdp_attached"),
            "xdp_interfaces": string_list(diagnostics.get("xdp_interfaces")),
            "bpftool_permission_denied": diagnostics.get("bpftool_permission_denied"),
            "bpftool_privilege_mode": diagnostics.get("bpftool_privilege_mode"),
            "bpftool_net_contains_interface": diagnostics.get("bpftool_net_contains_interface"),
            "sudo_noninteractive_enabled": diagnostics.get("sudo_noninteractive_enabled"),
            "sudo_noninteractive_unavailable": diagnostics.get("sudo_noninteractive_unavailable"),
            "sudo_unavailable": diagnostics.get("sudo_unavailable"),
            "pulse_marker_visible": diagnostics.get("pulse_marker_visible"),
            "map_counter_delta_packets": diagnostics.get("map_counter_delta_packets"),
            "object_preflight_status": diagnostics.get("object_preflight_status"),
            "object_preflight_blockers": string_list(diagnostics.get("object_preflight_blockers")),
        }
    object_preflight = current.get("object_preflight")
    if isinstance(object_preflight, dict):
        source = object_preflight.get("source")
        bpf_object = object_preflight.get("object")
        source = source if isinstance(source, dict) else {}
        bpf_object = bpf_object if isinstance(bpf_object, dict) else {}
        summary["object_preflight"] = {
            "status": object_preflight.get("status"),
            "blockers": string_list(object_preflight.get("blockers")),
            "source_path": source.get("path"),
            "source_exists": source.get("exists"),
            "source_contains_xdp_section": source.get("contains_xdp_section"),
            "source_contains_pulse_stats": source.get("contains_pulse_stats"),
            "source_contains_pulse_function": source.get("contains_pulse_function"),
            "object_path": bpf_object.get("path"),
            "object_exists": bpf_object.get("exists"),
            "object_is_ebpf": bpf_object.get("is_ebpf"),
            "object_has_xdp_section": bpf_object.get("has_xdp_section"),
            "object_has_maps_section": bpf_object.get("has_maps_section"),
            "object_has_btf_section": bpf_object.get("has_btf_section"),
            "object_contains_pulse_stats": bpf_object.get("contains_pulse_stats"),
            "object_contains_pulse_function": bpf_object.get("contains_pulse_function"),
        }
    return summary


def build_pending_details(
    root: Path,
    pending: list[str],
    statuses: dict[str, str],
    proof: dict[str, Any],
    replacement: dict[str, Any],
    replacement_ready: list[Any],
    replacement_not_ready: list[Any],
    intake_ready: list[Any],
    intake_not_ready: list[Any],
    missing_paths: list[Any],
) -> list[dict[str, Any]]:
    proof_rows = rows_by_claim(proof, "proof_rows")
    replacement_rows = rows_by_claim(replacement, "rows")
    replacement_ready_claims = set(string_list(replacement_ready))
    replacement_not_ready_claims = set(string_list(replacement_not_ready))
    intake_ready_claims = set(string_list(intake_ready))
    intake_not_ready_claims = set(string_list(intake_not_ready))
    missing_path_set = set(string_list(missing_paths))

    details: list[dict[str, Any]] = []
    for claim_id in pending:
        expected_candidate = candidate_path(claim_id)
        candidate = root / expected_candidate
        proof_row = proof_rows.get(claim_id, {})
        replacement_row = replacement_rows.get(claim_id, {})
        proof_errors = string_list(proof_row.get("errors"))
        replacement_failures = string_list(replacement_row.get("failures"))
        candidate_exists = candidate.exists() and candidate.is_file()
        proof_status = statuses.get(claim_id)
        current_evidence = evidence_summary(root, proof_row)

        blocking_reasons: list[str] = []
        if proof_status != "VERIFIED":
            blocking_reasons.append("proof_status_not_verified")
        if proof_errors:
            blocking_reasons.append("proof_errors_present")
        if not candidate_exists:
            blocking_reasons.append("candidate_file_missing")
        if claim_id in replacement_not_ready_claims:
            blocking_reasons.append("replacement_not_ready")
        if claim_id in intake_not_ready_claims:
            blocking_reasons.append("intake_not_ready")
        if expected_candidate in missing_path_set:
            blocking_reasons.append("intake_missing_candidate_path")
        if current_evidence.get("status") not in (None, "VERIFIED"):
            blocking_reasons.append("current_evidence_not_verified")
        if current_evidence.get("proof_sha256") and not current_evidence.get("sha256_matches_proof"):
            blocking_reasons.append("current_evidence_sha256_mismatch")

        details.append(
            {
                "claim_id": claim_id,
                "candidate_path": expected_candidate,
                "candidate_exists": candidate.exists(),
                "candidate_is_file": candidate.is_file() if candidate.exists() else False,
                "candidate_sha256": sha256_file(candidate),
                "candidate_missing": not candidate_exists,
                "proof": {
                    "status": proof_status,
                    "errors_count": len(proof_errors),
                    "errors": proof_errors,
                },
                "replacement": {
                    "ready_to_import": claim_id in replacement_ready_claims,
                    "not_ready": claim_id in replacement_not_ready_claims,
                    "row_present": bool(replacement_row),
                    "import_decision": replacement_row.get("import_decision"),
                    "candidate_path": replacement_row.get("candidate"),
                    "candidate_exists": replacement_row.get("candidate_exists"),
                    "candidate_is_file": replacement_row.get("candidate_is_file"),
                    "candidate_sha256": replacement_row.get("candidate_sha256"),
                    "passport_current_status": replacement_row.get("passport_current_status"),
                    "passport_current_sha256": replacement_row.get("passport_current_sha256"),
                    "passport_blocking_categories": string_list(
                        replacement_row.get("passport_blocking_categories")
                    ),
                    "failures_count": len(replacement_failures),
                    "failures": replacement_failures,
                },
                "intake": {
                    "ready": claim_id in intake_ready_claims,
                    "not_ready": claim_id in intake_not_ready_claims,
                    "missing_candidate_path": expected_candidate in missing_path_set,
                },
                "current_evidence": current_evidence,
                "blocking_reasons": blocking_reasons,
            }
        )
    return details


def pending_details_failures(
    details: list[dict[str, Any]],
    pending: list[str],
    statuses: dict[str, str],
    replacement_ready: list[Any],
    replacement_not_ready: list[Any],
    intake_ready: list[Any],
    intake_not_ready: list[Any],
    missing_paths: list[Any],
) -> list[str]:
    failures: list[str] = []
    if [detail.get("claim_id") for detail in details] != pending:
        failures.append("pending_external_evidence_details must match pending claim order")
    replacement_ready_claims = set(string_list(replacement_ready))
    replacement_not_ready_claims = set(string_list(replacement_not_ready))
    intake_ready_claims = set(string_list(intake_ready))
    intake_not_ready_claims = set(string_list(intake_not_ready))
    missing_path_set = set(string_list(missing_paths))
    for detail in details:
        claim_id = detail.get("claim_id")
        if not isinstance(claim_id, str):
            failures.append("pending detail claim_id must be a string")
            continue
        expected_candidate = candidate_path(claim_id)
        if detail.get("candidate_path") != expected_candidate:
            failures.append(f"{claim_id}: pending detail candidate_path is inconsistent")
        proof_detail = detail.get("proof", {})
        if not isinstance(proof_detail, dict) or proof_detail.get("status") != statuses.get(claim_id):
            failures.append(f"{claim_id}: pending detail proof.status is inconsistent")
        replacement_detail = detail.get("replacement", {})
        if not isinstance(replacement_detail, dict):
            failures.append(f"{claim_id}: pending detail replacement must be an object")
        else:
            if replacement_detail.get("ready_to_import") != (claim_id in replacement_ready_claims):
                failures.append(f"{claim_id}: pending detail replacement.ready_to_import is inconsistent")
            if replacement_detail.get("not_ready") != (claim_id in replacement_not_ready_claims):
                failures.append(f"{claim_id}: pending detail replacement.not_ready is inconsistent")
            if replacement_detail.get("candidate_path") not in (None, expected_candidate):
                failures.append(f"{claim_id}: replacement row candidate path does not match expected intake path")
        intake_detail = detail.get("intake", {})
        if not isinstance(intake_detail, dict):
            failures.append(f"{claim_id}: pending detail intake must be an object")
        else:
            if intake_detail.get("ready") != (claim_id in intake_ready_claims):
                failures.append(f"{claim_id}: pending detail intake.ready is inconsistent")
            if intake_detail.get("not_ready") != (claim_id in intake_not_ready_claims):
                failures.append(f"{claim_id}: pending detail intake.not_ready is inconsistent")
            if intake_detail.get("missing_candidate_path") != (expected_candidate in missing_path_set):
                failures.append(f"{claim_id}: pending detail intake.missing_candidate_path is inconsistent")
        current = detail.get("current_evidence", {})
        if isinstance(current, dict):
            if current.get("proof_sha256") and not current.get("sha256_matches_proof"):
                failures.append(f"{claim_id}: current evidence sha256 does not match proof row")
        else:
            failures.append(f"{claim_id}: current_evidence must be an object")
        if statuses.get(claim_id) != "VERIFIED" and not detail.get("blocking_reasons"):
            failures.append(f"{claim_id}: pending detail must record at least one blocking reason")
    return failures


def build_report(
    root: Path = ROOT,
    *,
    proof_path: Path | None = None,
    replacement_path: Path | None = None,
    intake_path: Path | None = None,
    inventory_path: Path | None = None,
    chain_path: Path | None = None,
    examples_manifest_path: Path | None = None,
) -> dict[str, Any]:
    proof_path = proof_path or root / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    replacement_path = replacement_path or root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    intake_path = intake_path or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    inventory_path = inventory_path or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    chain_path = chain_path or root / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
    examples_manifest_path = examples_manifest_path or root / "docs/verification/incoming/examples/manifest.json"

    data, sources = load_sources(
        root,
        {
            "proof": proof_path,
            "replacement_candidates": replacement_path,
            "external_evidence_intake": intake_path,
            "external_evidence_inventory": inventory_path,
            "artifact_chain": chain_path,
            "incoming_examples_manifest": examples_manifest_path,
        },
    )
    failures: list[str] = []
    for name, source in sources.items():
        if source["load_error"]:
            failures.append(f"{name}: {source['load_error']}")

    proof = data.get("proof", {})
    proof_failures: list[str] = []
    statuses = proof_status_by_claim(proof, proof_failures)
    starter_verified = [
        claim_id
        for claim_id in STARTER_VERIFIED_CLAIMS
        if statuses.get(claim_id) == "VERIFIED"
    ]
    for claim_id in STARTER_VERIFIED_CLAIMS:
        if statuses.get(claim_id) != "VERIFIED":
            proof_failures.append(f"{claim_id}: starter claim must be VERIFIED")

    pending = [
        claim_id
        for claim_id in CLOSURE_CLAIMS
        if statuses.get(claim_id) != "VERIFIED"
    ]
    runtime_pending = [
        claim_id
        for claim_id in RUNTIME_CLAIMS
        if statuses.get(claim_id) != "VERIFIED"
    ]
    unexpected_unverified = [
        claim_id
        for claim_id in EXPECTED_PROOF_ROW_CLAIMS
        if statuses.get(claim_id) != "VERIFIED"
        and claim_id not in CLOSURE_CLAIMS
        and claim_id not in RUNTIME_CLAIMS
    ]
    for claim_id in unexpected_unverified:
        proof_failures.append(f"{claim_id}: non-closure claim must not be pending")
    expected_not_verified = pending + runtime_pending
    if proof.get("not_verified_yet") != expected_not_verified:
        proof_failures.append("proof.not_verified_yet must match pending external/runtime claims")
    expected_proof_decision = PROOF_DECISION_INCOMPLETE if expected_not_verified else PROOF_DECISION_PROVEN
    if proof.get("decision") != expected_proof_decision:
        proof_failures.append(f"proof.decision must be {expected_proof_decision}")
    if proof.get("claim_boundary") != expected_proof_boundary(statuses):
        proof_failures.append("proof.claim_boundary must match proof-row-derived state")
    failures.extend(proof_failures)

    replacement = data.get("replacement_candidates", {})
    replacement_failures: list[str] = []
    if replacement.get("schema") != "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1":
        replacement_failures.append("replacement_candidates.schema is unexpected")
    if replacement.get("status") != "PASS":
        replacement_failures.append("replacement_candidates.status must be PASS")
    if replacement.get("failures") not in ([], None):
        replacement_failures.append("replacement_candidates.failures must be empty")
    if replacement.get("replacement_required") != pending:
        replacement_failures.append("replacement_candidates.replacement_required must match pending claims")
    replacement_ready = list_value(replacement, "ready")
    replacement_not_ready = list_value(replacement, "not_ready")
    replacement_failures.extend(
        check_partition("replacement_candidates", replacement_ready, replacement_not_ready, pending)
    )
    expected_replacement_decision = (
        REPLACEMENT_DECISION_NOT_READY if replacement_not_ready else REPLACEMENT_DECISION_READY
    )
    if replacement.get("decision") != expected_replacement_decision:
        replacement_failures.append(f"replacement_candidates.decision must be {expected_replacement_decision}")
    plan = replacement.get("candidate_intake_plan", {})
    if not isinstance(plan, dict):
        replacement_failures.append("replacement_candidates.candidate_intake_plan must be an object")
    else:
        if plan.get("ready_claims") != replacement_ready:
            replacement_failures.append("candidate_intake_plan.ready_claims must match replacement ready list")
        if plan.get("not_ready_claims") != replacement_not_ready:
            replacement_failures.append("candidate_intake_plan.not_ready_claims must match replacement not_ready list")
    replacement_failures.extend(false_report_boundary_failures("replacement_candidates", replacement.get("claim_boundary")))
    failures.extend(replacement_failures)

    intake = data.get("external_evidence_intake", {})
    intake_failures: list[str] = []
    if intake.get("schema") != "x0tta6bl4.ghost_pulse.external_evidence_intake.v1":
        intake_failures.append("external_evidence_intake.schema is unexpected")
    if intake.get("status") != "PASS":
        intake_failures.append("external_evidence_intake.status must be PASS")
    if intake.get("failures") not in ([], None):
        intake_failures.append("external_evidence_intake.failures must be empty")
    if intake.get("replacement_required") != pending:
        intake_failures.append("external_evidence_intake.replacement_required must match pending claims")
    intake_ready = list_value(intake, "ready")
    intake_not_ready = list_value(intake, "not_ready")
    intake_failures.extend(check_partition("external_evidence_intake", intake_ready, intake_not_ready, pending))
    expected_intake_decision = (
        INTAKE_DECISION_ACTION_REQUIRED if intake_not_ready else INTAKE_DECISION_READY_NOT_WRITTEN
    )
    if intake.get("decision") != expected_intake_decision:
        intake_failures.append(f"external_evidence_intake.decision must be {expected_intake_decision}")
    missing_paths = list_value(intake, "missing_candidate_paths")
    expected_not_ready_paths = [candidate_path(claim_id) for claim_id in intake_not_ready]
    if len(missing_paths) != len(set(missing_paths)):
        intake_failures.append("external_evidence_intake.missing_candidate_paths contains duplicate paths")
    unexpected_missing_paths = [
        path
        for path in missing_paths
        if path not in expected_not_ready_paths
    ]
    if unexpected_missing_paths:
        intake_failures.append(
            "external_evidence_intake.missing_candidate_paths must be a subset of not_ready claim paths"
        )
    if intake.get("preflight_verification", {}).get("status") != "PASS":
        intake_failures.append("external_evidence_intake.preflight_verification.status must be PASS")
    examples = intake.get("incoming_examples_verification", {})
    if not isinstance(examples, dict) or examples.get("status") != "PASS":
        intake_failures.append("external_evidence_intake.incoming_examples_verification.status must be PASS")
    else:
        example_claims = [
            row.get("claim_id")
            for row in examples.get("examples", [])
            if isinstance(row, dict)
        ]
        if example_claims != list(EXTERNAL_EVIDENCE_CLAIMS):
            intake_failures.append("incoming examples must cover the proof-goal claim contract")
    intake_failures.extend(false_report_boundary_failures("external_evidence_intake", intake.get("claim_boundary")))
    failures.extend(intake_failures)

    inventory = data.get("external_evidence_inventory", {})
    inventory_failures: list[str] = []
    if inventory.get("schema") != "x0tta6bl4.ghost_pulse.external_evidence_inventory.v1":
        inventory_failures.append("external_evidence_inventory.schema is unexpected")
    if inventory.get("status") != "PASS":
        inventory_failures.append("external_evidence_inventory.status must be PASS")
    if inventory.get("failures") not in ([], None):
        inventory_failures.append("external_evidence_inventory.failures must be empty")
    expected_inventory_status = INVENTORY_STATUS_GAPS if pending else INVENTORY_STATUS_ALL_VERIFIED
    if inventory.get("inventory_status") != expected_inventory_status:
        inventory_failures.append(f"external_evidence_inventory.inventory_status must be {expected_inventory_status}")
    gap_audit = inventory.get("gap_audit", {})
    if isinstance(gap_audit, dict):
        if gap_audit.get("expected_replacement_required") != pending:
            inventory_failures.append("inventory gap_audit.expected_replacement_required must match pending claims")
        if gap_audit.get("replacement_required") != pending:
            inventory_failures.append("inventory gap_audit.replacement_required must match pending claims")
        if gap_audit.get("failures") not in ([], None):
            inventory_failures.append("inventory gap_audit.failures must be empty")
    else:
        inventory_failures.append("external_evidence_inventory.gap_audit must be an object")
    failures.extend(inventory_failures)

    chain = data.get("artifact_chain", {})
    chain_failures: list[str] = []
    if chain.get("schema") != "x0tta6bl4.ghost_pulse.artifact_chain.v1":
        chain_failures.append("artifact_chain.schema is unexpected")
    if chain.get("decision") != CHAIN_DECISION_VERIFIED:
        chain_failures.append(f"artifact_chain.decision must be {CHAIN_DECISION_VERIFIED}")
    if chain.get("failures") not in ([], None):
        chain_failures.append("artifact_chain.failures must be empty")
    failures.extend(chain_failures)

    manifest = data.get("incoming_examples_manifest", {})
    manifest_failures: list[str] = []
    if manifest.get("schema") != "x0tta6bl4.ghost_pulse.incoming_example_manifest.v1":
        manifest_failures.append("incoming_examples_manifest.schema is unexpected")
    if manifest.get("status") != EXAMPLES_STATUS:
        manifest_failures.append(f"incoming_examples_manifest.status must be {EXAMPLES_STATUS}")
    manifest_claims = [
        row.get("claim_id")
        for row in manifest.get("examples", [])
        if isinstance(row, dict)
    ]
    if manifest_claims != list(EXTERNAL_EVIDENCE_CLAIMS):
        manifest_failures.append("incoming_examples_manifest examples must match proof-goal claim contract")
    manifest_failures.extend(false_report_boundary_failures("incoming_examples_manifest", manifest.get("claim_boundary")))
    failures.extend(manifest_failures)

    pending_details = build_pending_details(
        root,
        pending,
        statuses,
        proof,
        replacement,
        replacement_ready,
        replacement_not_ready,
        intake_ready,
        intake_not_ready,
        missing_paths,
    )
    detail_failures = pending_details_failures(
        pending_details,
        pending,
        statuses,
        replacement_ready,
        replacement_not_ready,
        intake_ready,
        intake_not_ready,
        missing_paths,
    )
    failures.extend(detail_failures)

    pending_fail_closed = bool(pending or runtime_pending)
    decision = DECISION_INVALID if failures else (DECISION_GAPS_RECORDED if pending_fail_closed else DECISION_ALL_PROVEN)
    checks = {
        "proof_gate": {
            "status": "PASS" if not proof_failures else "FAIL",
            "starter_verified_claims": starter_verified,
            "pending_external_evidence_claims": pending,
            "pending_runtime_claims": runtime_pending,
            "failures": proof_failures,
        },
        "replacement_candidates": {
            "status": "PASS" if not replacement_failures else "FAIL",
            "ready": replacement_ready,
            "not_ready": replacement_not_ready,
            "failures": replacement_failures,
        },
        "external_evidence_intake": {
            "status": "PASS" if not intake_failures else "FAIL",
            "ready": intake_ready,
            "not_ready": intake_not_ready,
            "missing_candidate_paths": missing_paths,
            "failures": intake_failures,
        },
        "external_evidence_inventory": {
            "status": "PASS" if not inventory_failures else "FAIL",
            "failures": inventory_failures,
        },
        "artifact_chain": {
            "status": "PASS" if not chain_failures else "FAIL",
            "failures": chain_failures,
        },
        "incoming_examples_manifest": {
            "status": "PASS" if not manifest_failures else "FAIL",
            "failures": manifest_failures,
        },
        "pending_external_evidence_details": {
            "status": "PASS" if not detail_failures else "FAIL",
            "failures": detail_failures,
        },
    }
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "starter_verified_claims": starter_verified,
        "pending_external_evidence_claims": pending,
        "pending_runtime_claims": runtime_pending,
        "pending_external_evidence_details": pending_details,
        "candidate_paths": expected_candidate_paths(pending),
        "claim_boundary": proof.get("claim_boundary", {}),
        "source_reports": sources,
        "checks": checks,
        "failures": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Goal State",
        "",
        f"Status: `{report.get('status')}`",
        "",
        f"Decision: `{report.get('decision')}`",
        "",
        "## Starter Verified Claims",
    ]
    starters = report.get("starter_verified_claims", [])
    lines.append(f"- `{', '.join(starters) or 'none'}`")
    lines.extend(["", "## Pending External Evidence"])
    pending = report.get("pending_external_evidence_claims", [])
    details_by_claim = {
        detail.get("claim_id"): detail
        for detail in report.get("pending_external_evidence_details", [])
        if isinstance(detail, dict)
    }
    if pending:
        for claim_id in pending:
            path = report.get("candidate_paths", {}).get(claim_id)
            detail = details_by_claim.get(claim_id, {})
            proof = detail.get("proof", {}) if isinstance(detail, dict) else {}
            current = detail.get("current_evidence", {}) if isinstance(detail, dict) else {}
            blockers = detail.get("blocking_reasons", []) if isinstance(detail, dict) else []
            lines.append(
                f"- `{claim_id}` -> `{path}`; proof `{proof.get('status')}`; "
                f"errors `{proof.get('errors_count')}`; current `{current.get('status')}`; "
                f"blockers `{', '.join(blockers) or 'none'}`"
            )
            diagnostics = current.get("collection_diagnostics") if isinstance(current, dict) else None
            if isinstance(diagnostics, dict):
                lines.append(
                    f"  - diagnostics: status `{diagnostics.get('status')}`; "
                    f"xdp_attached `{diagnostics.get('xdp_attached')}`; "
                    f"bpftool_permission_denied `{diagnostics.get('bpftool_permission_denied')}`; "
                    f"map_counter_delta_packets `{diagnostics.get('map_counter_delta_packets')}`"
                )
            object_preflight = current.get("object_preflight") if isinstance(current, dict) else None
            if isinstance(object_preflight, dict):
                lines.append(
                    f"  - object preflight: status `{object_preflight.get('status')}`; "
                    f"object_is_ebpf `{object_preflight.get('object_is_ebpf')}`; "
                    f"has_xdp_section `{object_preflight.get('object_has_xdp_section')}`"
                )
    else:
        lines.append("- None")
    lines.extend(["", "## Pending Runtime Claims"])
    runtime_pending = report.get("pending_runtime_claims", [])
    if runtime_pending:
        for claim_id in runtime_pending:
            lines.append(f"- `{claim_id}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Claim Boundary"])
    boundary = report.get("claim_boundary", {})
    if isinstance(boundary, dict):
        for key in sorted(boundary):
            lines.append(f"- {key}: `{boundary[key]}`")
    lines.extend(["", "## Source Reports"])
    sources = report.get("source_reports", {})
    if isinstance(sources, dict):
        for name in sorted(sources):
            source = sources[name]
            if not isinstance(source, dict):
                continue
            lines.append(
                f"- {name}: `{source.get('path')}`; sha256 `{source.get('sha256')}`; "
                f"decision `{source.get('decision')}`"
            )
    lines.extend(["", "## Failures"])
    failures = report.get("failures", [])
    if failures:
        for failure in failures:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-goal-state-{stamp}"
    bundle_json = bundle_dir / "goal_state.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "goal_state_bundle_json": display_path(root, bundle_json),
        "goal_state_bundle_md": display_path(root, bundle_md),
        "goal_state_latest_json": display_path(root, output_json),
        "goal_state_latest_md": display_path(root, output_md),
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


def verify_saved_report(report_path: Path, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    if not report_path.exists():
        return [f"missing goal state report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"goal state report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load goal state report: {exc}"]
    if data.get("schema") != SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    expected = build_report(root)
    if stable_subset(data) != stable_subset(expected):
        failures.append("goal state stable fields do not match current proof/intake/inventory state")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("goal_state_latest_json"))
    latest_md = resolve_path(root, artifacts.get("goal_state_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("goal_state_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("goal_state_bundle_md"))
    if latest_json != report_path:
        failures.append("artifacts.goal_state_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("goal state latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("goal state latest markdown does not match bundle markdown")
    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("goal state latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("goal state bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="Saved goal state report to verify read-only.")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        failures = verify_saved_report(report_path, root)
        saved = load_json(report_path) if report_path.exists() and report_path.is_file() else {}
        result = {
            "status": "PASS" if not failures else "FAIL",
            "decision": saved.get("decision"),
            "report": display_path(root, report_path),
            "pending_external_evidence_claims": saved.get("pending_external_evidence_claims", []),
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse goal state report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse goal state report is current")
            print(f"report={result['report']}")
            print(f"decision={result['decision']}")
        if failures:
            return 1
        if args.require_complete and saved.get("decision") != DECISION_ALL_PROVEN:
            return 1
        return 0

    report = build_report(root)
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "PASS":
        print("FAIL: x0tta6bl4_pulse goal state is inconsistent")
        for failure in report["failures"]:
            print(f"- {failure}")
    else:
        print("PASS: x0tta6bl4_pulse goal state is machine-checkable")
        print(f"decision={report['decision']}")
        print(
            "pending_external_evidence_claims="
            f"{','.join(report['pending_external_evidence_claims']) or 'none'}"
        )

    if report["status"] != "PASS":
        return 1
    if args.require_complete and report["decision"] != DECISION_ALL_PROVEN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
