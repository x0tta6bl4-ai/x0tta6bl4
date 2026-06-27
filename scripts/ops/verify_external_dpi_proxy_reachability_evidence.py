#!/usr/bin/env python3
"""Validate bounded external DPI/proxy reachability evidence.

This command is read-only. It validates a concrete candidate artifact against
the repository contract in
docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json.

Passing this validator does not update the Ghost Pulse proof gate by itself.
It only means the candidate is structurally ready to be considered by a later
import path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = Path("docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json")
DEFAULT_CANDIDATE = Path("docs/verification/incoming/dpi_lab.json")
INCOMING_ROOT = Path("docs/verification/incoming")
INCOMING_ARTIFACT_ROOT = Path("docs/verification/incoming/artifacts")

SCHEMA = "x0tta6bl4.external_dpi_proxy_reachability_evidence_validator.v1"
EVIDENCE_SCHEMA_VERSION = "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1"
DECISION_READY = "READY_TO_IMPORT"
DECISION_REJECTED = "REJECTED"
PLACEHOLDER_MARKERS = (
    "REPLACE_WITH",
    "EXAMPLE_ONLY_NOT_EVIDENCE",
    "INCOMPLETE_EXAMPLE_NOT_EVIDENCE",
    "INCOMING_CANDIDATE_EXAMPLE_NOT_EVIDENCE",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_payload(payload: object) -> str:
    return sha256_text(canonical_json(payload))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_content_sha256(payload: dict[str, Any]) -> str | None:
    if not isinstance(dotted_get(payload, "artifact_identity"), dict):
        return None
    normalized = json.loads(canonical_json(payload))
    normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return sha256_payload(normalized)


def dotted_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def symlink_component(root: Path, rel_path: Path) -> str | None:
    current = root
    for part in rel_path.parts:
        current = current / part
        if current.is_symlink():
            return display_path(root, current)
    return None


def candidate_path_errors(root: Path, candidate_path: Path) -> list[str]:
    errors: list[str] = []
    incoming_component = symlink_component(root, INCOMING_ROOT)
    if incoming_component:
        errors.append(
            "incoming evidence directory must not include symlink components: "
            f"{incoming_component}"
        )
    incoming = root / INCOMING_ROOT
    if incoming.is_symlink():
        errors.append(f"incoming evidence directory must not be a symlink: {INCOMING_ROOT}")
    if incoming.exists() and not incoming.is_dir():
        errors.append(f"incoming evidence path is not a directory: {INCOMING_ROOT}")
    if not candidate_path.exists():
        errors.append(f"candidate evidence is missing: {display_path(root, candidate_path)}")
        return errors
    if candidate_path.is_symlink():
        errors.append(f"candidate evidence must not be a symlink: {display_path(root, candidate_path)}")
    if not candidate_path.is_file():
        errors.append(f"candidate evidence is not a regular file: {display_path(root, candidate_path)}")
    try:
        candidate_path.resolve().relative_to(incoming.resolve())
    except ValueError:
        errors.append(
            "candidate evidence must stay under "
            f"{INCOMING_ROOT}: {display_path(root, candidate_path)}"
        )
    return errors


def placeholder_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(placeholder_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(placeholder_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for marker in PLACEHOLDER_MARKERS:
            if marker in value:
                errors.append(f"{path} contains placeholder marker {marker}")
    return errors


def forbidden_raw_field_errors(
    value: Any,
    forbidden: set[str],
    path: str = "$",
) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden:
                errors.append(f"{child_path} is forbidden raw evidence field")
            errors.extend(forbidden_raw_field_errors(child, forbidden, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(forbidden_raw_field_errors(child, forbidden, f"{path}[{index}]"))
    return errors


def section_errors(contract: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_sections = contract.get("required_top_level_sections")
    if not isinstance(required_sections, list) or not required_sections:
        return ["contract.required_top_level_sections must be a non-empty list"]

    contracts = contract.get("required_sections")
    if not isinstance(contracts, dict):
        return ["contract.required_sections must be an object"]

    for section in required_sections:
        if section not in payload:
            errors.append(f"{section} section is required")
            continue
        if not isinstance(payload[section], dict):
            errors.append(f"{section} section must be an object")
            continue
        section_contract = contracts.get(section)
        if not isinstance(section_contract, dict):
            errors.append(f"contract for {section} must be an object")
            continue
        required_fields = section_contract.get("required_fields")
        if not isinstance(required_fields, list):
            errors.append(f"contract for {section}.required_fields must be a list")
            continue
        for field in required_fields:
            if field not in payload[section]:
                errors.append(f"{section}.{field} is required")

    return errors


def hash_field_errors(payload: dict[str, Any]) -> list[str]:
    paths = [
        "artifact_identity.operator_or_lab_hash",
        "artifact_identity.artifact_sha256",
        "authorization_scope.scope_id_hash",
        "environment.isp_or_lab_profile_hash",
        "raw_capture_redaction.redacted_capture_sha256",
    ]
    errors = [f"{path} must be a sha256 hex digest" for path in paths if not is_sha256(dotted_get(payload, path))]

    for index, value in enumerate(dotted_get(payload, "packet_flow_summary.capture_artifact_hashes") or []):
        if not is_sha256(value):
            errors.append(f"packet_flow_summary.capture_artifact_hashes[{index}] must be a sha256 hex digest")

    source_hashes = dotted_get(payload, "evidence_links.source_hashes")
    if not isinstance(source_hashes, list) or not source_hashes:
        errors.append("evidence_links.source_hashes must be a non-empty list")
    else:
        for index, item in enumerate(source_hashes):
            if isinstance(item, str):
                if not is_sha256(item):
                    errors.append(f"evidence_links.source_hashes[{index}] must be a sha256 hex digest")
            elif isinstance(item, dict):
                if not is_sha256(item.get("sha256")):
                    errors.append(f"evidence_links.source_hashes[{index}].sha256 must be a sha256 hex digest")
            else:
                errors.append(f"evidence_links.source_hashes[{index}] must be a string or object")

    return errors


def artifact_hash_errors(payload: dict[str, Any]) -> list[str]:
    actual = dotted_get(payload, "artifact_identity.artifact_sha256")
    expected = artifact_content_sha256(payload)
    if expected is not None and is_sha256(actual) and actual != expected:
        return [
            "artifact_identity.artifact_sha256 must match canonical artifact content "
            "with artifact_sha256 set to zeroes"
        ]
    return []


def source_hashes_by_path(payload: dict[str, Any]) -> dict[str, str]:
    source_hashes = dotted_get(payload, "evidence_links.source_hashes")
    if not isinstance(source_hashes, list):
        return {}

    hashes: dict[str, str] = {}
    for item in source_hashes:
        if isinstance(item, dict) and isinstance(item.get("path"), str) and is_sha256(item.get("sha256")):
            hashes[item["path"]] = item["sha256"]
    return hashes


def source_artifact_errors(root: Path, payload: dict[str, Any]) -> list[str]:
    source_artifacts = dotted_get(payload, "evidence_links.source_artifacts")
    if not isinstance(source_artifacts, list):
        return []

    errors: list[str] = []
    hashes = source_hashes_by_path(payload)
    root_resolved = root.resolve()
    for index, item in enumerate(source_artifacts):
        if not isinstance(item, dict):
            errors.append(f"evidence_links.source_artifacts[{index}] must be an object")
            continue
        path_text = item.get("path")
        if not isinstance(path_text, str) or not path_text:
            errors.append(f"evidence_links.source_artifacts[{index}].path must be a non-empty string")
            continue
        path = Path(path_text)
        if path.is_absolute():
            errors.append(f"evidence_links.source_artifacts[{index}].path must be repo-relative")
            continue
        artifact_path = root / path
        try:
            artifact_path.resolve().relative_to(root_resolved)
        except ValueError:
            errors.append(f"evidence_links.source_artifacts[{index}].path must stay under repository root")
            continue
        try:
            artifact_path.resolve().relative_to((root / INCOMING_ARTIFACT_ROOT).resolve())
        except ValueError:
            errors.append(
                f"evidence_links.source_artifacts[{index}].path must stay under {INCOMING_ARTIFACT_ROOT}"
            )
            continue
        symlink = symlink_component(root, path)
        if symlink:
            errors.append(
                f"evidence_links.source_artifacts[{index}].path must not include symlink components: {symlink}"
            )
            continue
        if artifact_path.is_symlink():
            errors.append(f"evidence_links.source_artifacts[{index}].path must not be a symlink")
            continue
        if not artifact_path.exists():
            errors.append(f"evidence_links.source_artifacts[{index}].path is missing: {path_text}")
            continue
        if not artifact_path.is_file():
            errors.append(f"evidence_links.source_artifacts[{index}].path is not a regular file: {path_text}")
            continue
        expected = hashes.get(path_text)
        if expected is None:
            errors.append(f"evidence_links.source_artifacts[{index}].path must have a matching source_hashes entry")
            continue
        actual = file_sha256(artifact_path)
        if actual != expected:
            errors.append(f"evidence_links.source_artifacts[{index}].sha256 does not match file bytes")
    return errors


def probe_matrix_errors(payload: dict[str, Any]) -> list[str]:
    matrix = dotted_get(payload, "probe_matrix")
    if not isinstance(matrix, dict):
        return ["probe_matrix section must be an object"]

    errors: list[str] = []
    pairs = matrix.get("probe_pairs")
    if not isinstance(pairs, list) or not pairs:
        errors.append("probe_matrix.probe_pairs must be a non-empty list")
        pairs = []

    attempt_count = matrix.get("attempt_count")
    success_count = matrix.get("success_count")
    if not isinstance(attempt_count, int) or isinstance(attempt_count, bool) or attempt_count <= 0:
        errors.append("probe_matrix.attempt_count must be a positive integer")
    if not isinstance(success_count, int) or isinstance(success_count, bool) or success_count <= 0:
        errors.append("probe_matrix.success_count must be a positive integer")
    if isinstance(attempt_count, int) and isinstance(success_count, int) and success_count > attempt_count:
        errors.append("probe_matrix.success_count must not exceed attempt_count")

    for key in ("failure_buckets", "control_probe_ids", "treatment_probe_ids"):
        value = matrix.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"probe_matrix.{key} must be a non-empty list")

    pair_required = {
        "pair_id",
        "transport",
        "proxy_or_fronting_mode",
        "target_category",
        "probe_target_hash",
        "control_result_bucket",
        "treatment_result_bucket",
        "attempts",
        "successes",
        "failure_buckets",
    }
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            errors.append(f"probe_matrix.probe_pairs[{index}] must be an object")
            continue
        missing = sorted(pair_required - set(pair))
        for field in missing:
            errors.append(f"probe_matrix.probe_pairs[{index}].{field} is required")
        if "probe_target_hash" in pair and not is_sha256(pair.get("probe_target_hash")):
            errors.append(f"probe_matrix.probe_pairs[{index}].probe_target_hash must be a sha256 hex digest")
        if not isinstance(pair.get("attempts"), int) or isinstance(pair.get("attempts"), bool) or pair.get("attempts", 0) <= 0:
            errors.append(f"probe_matrix.probe_pairs[{index}].attempts must be a positive integer")
        if not isinstance(pair.get("successes"), int) or isinstance(pair.get("successes"), bool):
            errors.append(f"probe_matrix.probe_pairs[{index}].successes must be an integer")
        if isinstance(pair.get("attempts"), int) and isinstance(pair.get("successes"), int):
            if pair["successes"] > pair["attempts"]:
                errors.append(f"probe_matrix.probe_pairs[{index}].successes must not exceed attempts")
        if not isinstance(pair.get("failure_buckets"), list) or not pair.get("failure_buckets"):
            errors.append(f"probe_matrix.probe_pairs[{index}].failure_buckets must be a non-empty list")

    return errors


def result_logic_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    result = dotted_get(payload, "result_summary")
    boundary_claims = dotted_get(payload, "claim_boundary.proof_claims")
    if not isinstance(result, dict):
        return ["result_summary section must be an object"]
    if not isinstance(boundary_claims, dict):
        return ["claim_boundary.proof_claims must be an object"]

    required_bools = {
        "external_dpi_tested",
        "baseline_blocked_or_detected",
        "treatment_reachability_observed",
        "reachability_observed",
        "dpi_bypass_confirmed",
        "bypass_confirmed",
        "dataplane_confirmed",
        "production_ready",
    }
    for key in required_bools:
        if not isinstance(result.get(key), bool):
            errors.append(f"result_summary.{key} must be a boolean")
        if key in boundary_claims and boundary_claims[key] != result.get(key):
            errors.append(f"claim_boundary.proof_claims.{key} must match result_summary.{key}")

    always_false = {
        "production_ready",
        "customer_traffic_confirmed",
        "durable_policy_confirmed",
        "anonymity_confirmed",
        "provider_health_confirmed",
        "payment_or_token_settlement_finality_confirmed",
    }
    for key in always_false:
        if result.get(key) is True or boundary_claims.get(key) is True:
            errors.append(f"{key} must remain false for this artifact family")

    if result.get("dpi_bypass_confirmed") is True:
        requirements = {
            "authorization_scope.authorization_present": True,
            "authorization_scope.consent_or_legal_basis_present": True,
            "methodology.external_dpi_or_blocking_middlebox_observed": True,
            "result_summary.external_dpi_tested": True,
            "result_summary.baseline_blocked_or_detected": True,
            "result_summary.treatment_reachability_observed": True,
            "result_summary.reachability_observed": True,
            "result_summary.bypass_confirmed": True,
            "result_summary.dataplane_confirmed": True,
            "raw_capture_redaction.redaction_performed": True,
            "raw_capture_redaction.forbidden_raw_fields_absent": True,
            "packet_flow_summary.packet_payloads_redacted": True,
            "repeatability_limits.not_generalizable_beyond_environment": True,
        }
        for path, expected in requirements.items():
            if dotted_get(payload, path) is not expected:
                errors.append(f"{path} must be {expected} when dpi_bypass_confirmed is true")
    else:
        errors.append("result_summary.dpi_bypass_confirmed must be true for DPI lab import readiness")

    if result.get("decision") != "bounded_external_dpi_bypass_observed":
        errors.append("result_summary.decision must be bounded_external_dpi_bypass_observed")

    not_proven = dotted_get(payload, "claim_boundary.not_proven")
    if not isinstance(not_proven, list):
        errors.append("claim_boundary.not_proven must be a list")
    else:
        text = " ".join(str(item).lower() for item in not_proven)
        for phrase in ("production readiness", "durable censorship bypass", "anonymity", "provider health", "customer traffic"):
            if phrase not in text:
                errors.append(f"claim_boundary.not_proven must include {phrase}")

    return errors


def readiness_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = payload.get("status")
    if status != "VERIFIED":
        errors.append("status must be VERIFIED")
    identity = dotted_get(payload, "artifact_identity")
    if isinstance(identity, dict):
        if identity.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
            errors.append(f"artifact_identity.schema_version must be {EVIDENCE_SCHEMA_VERSION}")
        if identity.get("collector_kind") == "example_only":
            errors.append("artifact_identity.collector_kind must not be example_only")
        if identity.get("claim_id") not in {"external_dpi_proxy_reachability", "dpi_lab"}:
            errors.append("artifact_identity.claim_id must be external_dpi_proxy_reachability or dpi_lab")
    else:
        errors.append("artifact_identity section must be an object")

    for path in (
        "evidence_links.source_artifacts",
        "evidence_links.artifact_roles",
        "packet_flow_summary.capture_artifact_hashes",
    ):
        value = dotted_get(payload, path)
        if not isinstance(value, list) or not value:
            errors.append(f"{path} must be a non-empty list")

    return errors


def validate_payload(contract: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(section_errors(contract, payload))
    errors.extend(placeholder_errors(payload))
    forbidden = set(contract.get("redaction_rules", {}).get("forbidden_raw_fields", []))
    errors.extend(forbidden_raw_field_errors(payload, forbidden))
    if payload.get("mode") == "EXTERNAL_EVIDENCE_GAP_RECORD" or payload.get("gap_artifact_role"):
        errors.append("candidate is a gap record, not external DPI/proxy evidence")
    errors.extend(hash_field_errors(payload))
    errors.extend(artifact_hash_errors(payload))
    errors.extend(probe_matrix_errors(payload))
    errors.extend(result_logic_errors(payload))
    errors.extend(readiness_errors(payload))
    return errors


def external_dpi_intake_claim_gate(
    *,
    decision: str,
    payload: dict[str, Any] | None,
    candidate_exists: bool,
    candidate_is_file: bool,
    candidate_is_symlink: bool,
    failures: list[str],
) -> dict[str, Any]:
    ready = decision == DECISION_READY
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": "external_dpi_proxy.validator",
        "claim_boundary": (
            "Read-only external DPI/proxy candidate validation. READY_TO_IMPORT "
            "means a bounded redacted candidate is structurally ready for the "
            "Ghost Pulse import preflight; it does not update latest evidence, "
            "run the proof gate, prove durable censorship bypass, prove customer "
            "traffic, or prove production readiness."
        ),
        "local_validator_run_claim_allowed": True,
        "candidate_file_observed_claim_allowed": bool(
            candidate_exists and candidate_is_file and not candidate_is_symlink
        ),
        "bounded_external_dpi_candidate_ready_to_import_claim_allowed": ready,
        "bounded_external_dpi_bypass_observation_claim_allowed": bool(
            ready and dotted_get(payload or {}, "result_summary.dpi_bypass_confirmed")
        ),
        "bounded_dataplane_probe_observation_claim_allowed": bool(
            ready and dotted_get(payload or {}, "result_summary.dataplane_confirmed")
        ),
        "validation_failures_present": bool(failures),
        "raw_capture_redacted_claim_allowed": bool(
            ready and dotted_get(payload or {}, "raw_capture_redaction.redaction_performed")
        ),
        "latest_evidence_updated_claim_allowed": False,
        "proof_gate_dpi_bypass_claim_allowed": False,
        "durable_censorship_bypass_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "anonymity_claim_allowed": False,
        "provider_health_claim_allowed": False,
        "payment_or_token_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }


def build_report(
    root: Path = ROOT,
    candidate: str | Path = DEFAULT_CANDIDATE,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    root = root.resolve()
    candidate_path = resolve_path(root, candidate)
    contract_file = resolve_path(root, contract_path)
    timestamp = utc_now()
    failures: list[str] = []
    payload: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None

    if not contract_file.exists():
        failures.append(f"contract is missing: {display_path(root, contract_file)}")
    elif not contract_file.is_file():
        failures.append(f"contract is not a regular file: {display_path(root, contract_file)}")
    else:
        try:
            contract = load_json(contract_file)
        except Exception as exc:
            failures.append(f"could not load contract JSON: {exc}")

    path_errors = candidate_path_errors(root, candidate_path)
    failures.extend(path_errors)
    if not path_errors:
        try:
            payload = load_json(candidate_path)
        except Exception as exc:
            failures.append(f"could not load candidate JSON: {exc}")

    if contract is not None and payload is not None:
        failures.extend(validate_payload(contract, payload))
        failures.extend(source_artifact_errors(root, payload))

    candidate_sha256 = None
    if candidate_path.exists() and candidate_path.is_file() and not candidate_path.is_symlink():
        candidate_sha256 = file_sha256(candidate_path)

    decision = DECISION_READY if not failures else DECISION_REJECTED
    candidate_exists = candidate_path.exists()
    candidate_is_file = candidate_path.is_file()
    candidate_is_symlink = candidate_path.is_symlink()
    return {
        "schema": SCHEMA,
        "timestamp_utc": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "candidate": display_path(root, candidate_path),
        "candidate_exists": candidate_exists,
        "candidate_is_file": candidate_is_file,
        "candidate_is_symlink": candidate_is_symlink,
        "candidate_sha256": candidate_sha256,
        "contract": display_path(root, contract_file),
        "failures": failures,
        "summary": {
            "ready_to_import": decision == DECISION_READY,
            "external_dpi_tested": bool(dotted_get(payload or {}, "result_summary.external_dpi_tested")),
            "dpi_bypass_confirmed": bool(dotted_get(payload or {}, "result_summary.dpi_bypass_confirmed")),
            "dataplane_confirmed": bool(dotted_get(payload or {}, "result_summary.dataplane_confirmed")),
            "production_ready": bool(dotted_get(payload or {}, "result_summary.production_ready")),
            "redaction_performed": bool(dotted_get(payload or {}, "raw_capture_redaction.redaction_performed")),
            "forbidden_raw_fields_absent": bool(
                dotted_get(payload or {}, "raw_capture_redaction.forbidden_raw_fields_absent")
            ),
        },
        "claim_boundary": {
            "note": "Read-only DPI/proxy artifact validation only; this does not import evidence or promote proof-gate claims.",
            "schema_only": False,
            "production_ready": False,
            "durable_censorship_bypass_confirmed": False,
            "customer_traffic_confirmed": False,
            "anonymity_confirmed": False,
            "provider_health_confirmed": False,
        },
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(
            decision=decision,
            payload=payload,
            candidate_exists=candidate_exists,
            candidate_is_file=candidate_is_file,
            candidate_is_symlink=candidate_is_symlink,
            failures=failures,
        ),
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"status={report['status']}",
        f"decision={report['decision']}",
        f"candidate={report['candidate']}",
    ]
    if report["failures"]:
        lines.append("failures:")
        lines.extend(f"- {failure}" for failure in report["failures"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidate", default=str(DEFAULT_CANDIDATE))
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(args.root, args.candidate, args.contract)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    if args.require_ready and report["decision"] != DECISION_READY:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
