#!/usr/bin/env python3
"""Run a bounded non-mock measured-attestation verifier smoke.

This script is for local operators with access to a real SGX verifier command
and real attestation material. It writes only hashes, sizes, verifier
provenance, and claim gates. Raw report data, quote, signature, file paths, and
operator identifiers are not written to the artifact.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.security.tee_attestation import TEEAttestation, TEEValidator


SCHEMA = "x0tta6bl4.measured_attestation_verifier_smoke.v1"
CLAIM_GATE_SCHEMA = "x0tta6bl4.measured_attestation_verifier_smoke.claim_gate.v1"
READY_DECISION = "MEASURED_ATTESTATION_VERIFIER_SMOKE_READY"
BLOCKED_DECISION = "MEASURED_ATTESTATION_VERIFIER_SMOKE_BLOCKED"
DEFAULT_OUTPUT = Path("docs/verification/incoming/measured_attestation_verifier_smoke.json")
CLAIM_BOUNDARY = (
    "Bounded local measured-attestation verifier smoke only. It proves a "
    "configured non-mock verifier accepted one supplied attestation sample and "
    "returned redacted provenance. It does not prove production trust finality, "
    "fleet-wide hardware coverage, live customer traffic, payment settlement, "
    "PQC identity finality, or production readiness."
)
CLAIM_GATE_BOUNDARY = (
    "Measured-attestation verifier-smoke claim gate. A ready artifact can prove "
    "only that one local non-mock verifier accepted one supplied attestation "
    "sample with redacted provenance. It does not prove production trust "
    "finality, fleet-wide hardware coverage, dataplane delivery, customer "
    "traffic, settlement finality, production SLOs, or production readiness."
)


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def artifact_content_sha256(payload: object) -> str:
    normalized = json.loads(canonical_json(payload))
    if isinstance(normalized, dict) and isinstance(normalized.get("artifact_identity"), dict):
        normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return sha256_text(canonical_json(normalized))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--provider", choices=["sgx"], default="sgx")
    parser.add_argument("--report-data-file", type=Path, required=True)
    parser.add_argument("--quote-file", type=Path, required=True)
    parser.add_argument("--signature-file", type=Path, required=True)
    parser.add_argument("--sgx-verifier-command")
    parser.add_argument("--operator-or-lab-id", required=True)
    parser.add_argument("--authorization-scope-id", required=True)
    parser.add_argument("--environment-bucket", required=True)
    parser.add_argument("--hardware-profile-bucket", required=True)
    parser.add_argument("--policy-context", required=True)
    parser.add_argument(
        "--allow-local-verifier-run",
        action="store_true",
        help="Required. Confirms the operator is authorized to run the local verifier.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def read_bytes(path: Path, *, label: str) -> bytes:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"{label} file does not exist: {path}")
    value = path.read_bytes()
    if not value:
        raise SystemExit(f"{label} file is empty: {path}")
    return value


def redacted_blob_summary(value: bytes) -> dict[str, Any]:
    return {
        "present": bool(value),
        "size_bytes": len(value),
        "sha256": sha256_bytes(value),
        "raw_value_redacted": True,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_local_verifier_run:
        raise SystemExit("--allow-local-verifier-run is required")

    root = args.root.resolve()
    report_data = read_bytes(
        resolve_path(root, args.report_data_file),
        label="report_data",
    )
    quote = read_bytes(resolve_path(root, args.quote_file), label="quote")
    signature = read_bytes(resolve_path(root, args.signature_file), label="signature")

    validator = TEEValidator(
        allow_mock=False,
        sgx_verifier_command=args.sgx_verifier_command,
    )
    attestation = TEEAttestation(
        provider=args.provider,
        report_data=report_data,
        quote=quote,
        signature=signature,
    )
    result = validator.verify_report_with_context(attestation)
    provenance = dict(result.verifier_provenance or {})
    non_mock_provider = args.provider != "mock"
    ready = (
        bool(result.verified)
        and non_mock_provider
        and result.verifier_backend not in {"mock_local_allowlist", "mock_disabled"}
        and bool(result.production_verifier_claim_allowed)
        and bool(provenance)
    )
    claim_gate_blockers: list[str] = []
    if not result.verified:
        claim_gate_blockers.append("attestation_not_verified")
    if not non_mock_provider:
        claim_gate_blockers.append("provider_is_mock")
    if result.verifier_backend in {"mock_local_allowlist", "mock_disabled"}:
        claim_gate_blockers.append("verifier_backend_is_mock")
    if not result.production_verifier_claim_allowed:
        claim_gate_blockers.append("production_verifier_claim_not_allowed")
    if not provenance:
        claim_gate_blockers.append("verifier_provenance_missing")

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "decision": READY_DECISION if ready else BLOCKED_DECISION,
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "captured_at_utc": utc_now_text(),
        "provider": args.provider,
        "artifact_identity": {
            "claim_id": "measured_attestation_verifier_smoke",
            "operator_or_lab_hash": sha256_text(args.operator_or_lab_id),
            "authorization_scope_hash": sha256_text(args.authorization_scope_id),
            "environment_bucket": args.environment_bucket,
            "hardware_profile_bucket": args.hardware_profile_bucket,
            "policy_context_hash": sha256_text(args.policy_context),
            "artifact_sha256": "0" * 64,
        },
        "input_redaction": {
            "raw_attestation_material_retained": False,
            "raw_file_paths_redacted": True,
            "report_data": redacted_blob_summary(report_data),
            "quote": redacted_blob_summary(quote),
            "signature": redacted_blob_summary(signature),
        },
        "verifier": {
            "backend": result.verifier_backend,
            "verified": bool(result.verified),
            "reason": result.reason,
            "production_verifier_claim_allowed": bool(
                result.production_verifier_claim_allowed
            ),
            "provenance": provenance,
            "command_configured": bool(validator.sgx_verifier_command),
        },
        "measurements": {
            "non_mock_provider": non_mock_provider,
            "hardware_quote_present": bool(quote),
            "signature_present": bool(signature),
            "attestation_verified": bool(result.verified),
            "verifier_provenance_recorded": bool(provenance),
            "production_verifier_claim_allowed": bool(
                result.production_verifier_claim_allowed
            ),
            "production_trust_finality": False,
            "production_ready": False,
        },
        "result_summary": {
            "production_attestation_verifier_smoke_ready": ready,
            "confidence_bucket": (
                "bounded-single-verifier-run"
                if ready
                else "insufficient-for-production-attestation-claim"
            ),
            "production_trust_finality": False,
            "production_ready": False,
        },
        "claim_boundary": {
            "summary": CLAIM_BOUNDARY,
            "not_proven": [
                "production trust finality",
                "fleet-wide hardware coverage",
                "live customer traffic",
                "payment or token settlement finality",
                "PQC identity finality",
                "production readiness",
            ],
            "proof_claims": {
                "non_mock_attestation_verified": bool(result.verified)
                and non_mock_provider,
                "verifier_provenance_recorded": bool(provenance),
                "production_attestation_verifier_claim_allowed": bool(
                    result.production_verifier_claim_allowed
                ),
                "production_trust_finality": False,
                "production_ready": False,
            },
            "upgrade_rule": (
                "Only this bounded verifier-smoke claim can become true here; "
                "production trust finality requires a separate reviewed evidence gate."
            ),
        },
        "claim_gate": {
            "schema": CLAIM_GATE_SCHEMA,
            "measured_attestation_verifier_smoke_claim_allowed": ready,
            "non_mock_attestation_verified": bool(result.verified) and non_mock_provider,
            "verifier_provenance_recorded": bool(provenance),
            "production_attestation_verifier_claim_allowed": bool(
                result.production_verifier_claim_allowed
            ),
            "production_trust_finality_claim_allowed": False,
            "fleet_hardware_coverage_claim_allowed": False,
            "pqc_identity_finality_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "settlement_finality_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "blockers": claim_gate_blockers,
            "claim_boundary": CLAIM_GATE_BOUNDARY,
            "redacted": True,
        },
        "safe_local_input_rule": (
            "Do not paste report data, quote, signature, verifier command, operator "
            "ID, authorization scope, or policy context into chat. Keep them in local "
            "files and pass paths to this script."
        ),
    }
    payload["artifact_identity"]["artifact_sha256"] = artifact_content_sha256(payload)
    return payload


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_report(args)
    output = resolve_path(args.root.resolve(), args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["decision"])
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
