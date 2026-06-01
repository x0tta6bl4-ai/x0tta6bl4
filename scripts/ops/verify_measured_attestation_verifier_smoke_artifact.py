#!/usr/bin/env python3
"""Validate a bounded measured-attestation verifier-smoke artifact.

This command is read-only. It validates the JSON produced by
verify_measured_attestation_verifier_smoke.py before a future evidence gate or
operator workflow treats it as import-ready context. Passing this validator does
not prove production trust finality.
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
DEFAULT_CANDIDATE = Path("docs/verification/incoming/measured_attestation_verifier_smoke.json")
INCOMING_ROOT = Path("docs/verification/incoming")
SCHEMA = "x0tta6bl4.measured_attestation_verifier_smoke_validator.v1"
ARTIFACT_SCHEMA = "x0tta6bl4.measured_attestation_verifier_smoke.v1"
CLAIM_GATE_SCHEMA = "x0tta6bl4.measured_attestation_verifier_smoke.claim_gate.v1"
DECISION_READY = "READY_TO_IMPORT"
DECISION_REJECTED = "REJECTED"
READY_DECISION = "MEASURED_ATTESTATION_VERIFIER_SMOKE_READY"
PLACEHOLDER_MARKERS = (
    "REPLACE_WITH",
    "EXAMPLE_ONLY_NOT_EVIDENCE",
    "INCOMPLETE_EXAMPLE_NOT_EVIDENCE",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def dotted_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def artifact_content_sha256(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload.get("artifact_identity"), dict):
        return None
    normalized = json.loads(canonical_json(payload))
    normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return sha256_text(canonical_json(normalized))


def path_errors(root: Path, candidate: Path) -> list[str]:
    errors: list[str] = []
    incoming = root / INCOMING_ROOT
    if incoming.exists() and incoming.is_symlink():
        errors.append(f"incoming directory must not be a symlink: {INCOMING_ROOT}")
    if not candidate.exists():
        errors.append(f"candidate artifact is missing: {display_path(root, candidate)}")
        return errors
    if candidate.is_symlink():
        errors.append(f"candidate artifact must not be a symlink: {display_path(root, candidate)}")
    if not candidate.is_file():
        errors.append(f"candidate artifact is not a regular file: {display_path(root, candidate)}")
    try:
        candidate.resolve().relative_to(incoming.resolve())
    except ValueError:
        errors.append(
            "candidate artifact must stay under "
            f"{INCOMING_ROOT}: {display_path(root, candidate)}"
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


def schema_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != ARTIFACT_SCHEMA:
        errors.append(f"schema must be {ARTIFACT_SCHEMA}")
    if payload.get("decision") != READY_DECISION:
        errors.append(f"decision must be {READY_DECISION}")
    if payload.get("ready") is not True:
        errors.append("ready must be true")
    if payload.get("provider") == "mock":
        errors.append("provider must be non-mock")
    return errors


def hash_errors(payload: dict[str, Any]) -> list[str]:
    paths = [
        "artifact_identity.operator_or_lab_hash",
        "artifact_identity.authorization_scope_hash",
        "artifact_identity.policy_context_hash",
        "artifact_identity.artifact_sha256",
        "input_redaction.report_data.sha256",
        "input_redaction.quote.sha256",
        "input_redaction.signature.sha256",
    ]
    errors = [f"{path} must be a sha256 hex digest" for path in paths if not is_sha256(dotted_get(payload, path))]
    actual = dotted_get(payload, "artifact_identity.artifact_sha256")
    expected = artifact_content_sha256(payload)
    if expected is not None and is_sha256(actual) and actual != expected:
        errors.append(
            "artifact_identity.artifact_sha256 must match canonical artifact "
            "content with artifact_sha256 set to zeroes"
        )
    return errors


def redaction_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if dotted_get(payload, "input_redaction.raw_attestation_material_retained") is not False:
        errors.append("input_redaction.raw_attestation_material_retained must be false")
    if dotted_get(payload, "input_redaction.raw_file_paths_redacted") is not True:
        errors.append("input_redaction.raw_file_paths_redacted must be true")
    for name in ("report_data", "quote", "signature"):
        if dotted_get(payload, f"input_redaction.{name}.raw_value_redacted") is not True:
            errors.append(f"input_redaction.{name}.raw_value_redacted must be true")
        if not dotted_get(payload, f"input_redaction.{name}.present"):
            errors.append(f"input_redaction.{name}.present must be true")
    return errors


def verifier_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if dotted_get(payload, "verifier.verified") is not True:
        errors.append("verifier.verified must be true")
    if dotted_get(payload, "verifier.command_configured") is not True:
        errors.append("verifier.command_configured must be true")
    if dotted_get(payload, "verifier.backend") in {None, "", "mock_local_allowlist", "mock_disabled"}:
        errors.append("verifier.backend must be a non-mock verifier backend")
    if dotted_get(payload, "verifier.production_verifier_claim_allowed") is not True:
        errors.append("verifier.production_verifier_claim_allowed must be true")
    provenance = dotted_get(payload, "verifier.provenance")
    if not isinstance(provenance, dict) or not provenance:
        errors.append("verifier.provenance must be a non-empty object")
    elif provenance.get("raw_attestation_redacted") is not True:
        errors.append("verifier.provenance.raw_attestation_redacted must be true")
    return errors


def claim_boundary_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("goal_can_be_marked_complete") is not False:
        errors.append("goal_can_be_marked_complete must be false")
    false_paths = [
        "measurements.production_trust_finality",
        "measurements.production_ready",
        "result_summary.production_trust_finality",
        "result_summary.production_ready",
        "claim_boundary.proof_claims.production_trust_finality",
        "claim_boundary.proof_claims.production_ready",
    ]
    for path in false_paths:
        if dotted_get(payload, path) is not False:
            errors.append(f"{path} must be false")
    true_paths = [
        "measurements.non_mock_provider",
        "measurements.hardware_quote_present",
        "measurements.signature_present",
        "measurements.attestation_verified",
        "measurements.verifier_provenance_recorded",
        "measurements.production_verifier_claim_allowed",
        "result_summary.production_attestation_verifier_smoke_ready",
        "claim_boundary.proof_claims.non_mock_attestation_verified",
        "claim_boundary.proof_claims.verifier_provenance_recorded",
        "claim_boundary.proof_claims.production_attestation_verifier_claim_allowed",
    ]
    for path in true_paths:
        if dotted_get(payload, path) is not True:
            errors.append(f"{path} must be true")
    not_proven = dotted_get(payload, "claim_boundary.not_proven")
    if not isinstance(not_proven, list) or "production readiness" not in not_proven:
        errors.append("claim_boundary.not_proven must include production readiness")
    claim_gate = payload.get("claim_gate")
    if not isinstance(claim_gate, dict) or not claim_gate:
        errors.append("claim_gate must be a non-empty object")
        return errors
    if dotted_get(payload, "claim_gate.schema") != CLAIM_GATE_SCHEMA:
        errors.append(f"claim_gate.schema must be {CLAIM_GATE_SCHEMA}")
    gate_true_paths = [
        "claim_gate.measured_attestation_verifier_smoke_claim_allowed",
        "claim_gate.non_mock_attestation_verified",
        "claim_gate.verifier_provenance_recorded",
        "claim_gate.production_attestation_verifier_claim_allowed",
    ]
    for path in gate_true_paths:
        if dotted_get(payload, path) is not True:
            errors.append(f"{path} must be true")
    gate_false_paths = [
        "claim_gate.production_trust_finality_claim_allowed",
        "claim_gate.fleet_hardware_coverage_claim_allowed",
        "claim_gate.pqc_identity_finality_claim_allowed",
        "claim_gate.traffic_delivery_claim_allowed",
        "claim_gate.customer_traffic_claim_allowed",
        "claim_gate.settlement_finality_claim_allowed",
        "claim_gate.production_slo_claim_allowed",
        "claim_gate.production_readiness_claim_allowed",
    ]
    for path in gate_false_paths:
        if dotted_get(payload, path) is not False:
            errors.append(f"{path} must be false")
    if dotted_get(payload, "claim_gate.redacted") is not True:
        errors.append("claim_gate.redacted must be true")
    if not dotted_get(payload, "claim_gate.claim_boundary"):
        errors.append("claim_gate.claim_boundary must be present")
    if dotted_get(payload, "claim_gate.blockers") != []:
        errors.append("claim_gate.blockers must be an empty list for READY artifacts")
    return errors


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(placeholder_errors(payload))
    errors.extend(schema_errors(payload))
    errors.extend(hash_errors(payload))
    errors.extend(redaction_errors(payload))
    errors.extend(verifier_errors(payload))
    errors.extend(claim_boundary_errors(payload))
    return errors


def build_report(
    root: Path,
    candidate: Path = DEFAULT_CANDIDATE,
    *,
    require_ready: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    candidate_path = resolve_path(root, candidate)
    failures = path_errors(root, candidate_path)
    payload: dict[str, Any] | None = None
    candidate_sha256: str | None = None
    if not failures:
        try:
            raw = candidate_path.read_bytes()
            candidate_sha256 = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                failures.append("candidate artifact JSON root must be an object")
                payload = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"candidate artifact is not valid JSON: {exc}")
    if payload is not None:
        failures.extend(validate(payload))

    ready = not failures
    if require_ready and not ready and "require-ready requested" not in failures:
        failures.append("require-ready requested but artifact is not ready")
    return {
        "schema": SCHEMA,
        "decision": DECISION_READY if ready else DECISION_REJECTED,
        "ready": ready,
        "timestamp_utc": utc_now(),
        "candidate": display_path(root, candidate_path),
        "candidate_sha256": candidate_sha256,
        "artifact_schema": payload.get("schema") if isinstance(payload, dict) else None,
        "artifact_ready": payload.get("ready") if isinstance(payload, dict) else None,
        "failures": failures,
        "claim_boundary": (
            "Validator readiness means the local verifier-smoke artifact is "
            "structurally bounded and redacted. It does not prove production "
            "trust finality or production readiness."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        args.candidate,
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["decision"])
        for failure in report["failures"]:
            print(f"- {failure}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
