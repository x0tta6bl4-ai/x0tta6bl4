#!/usr/bin/env python3
"""Build a safe local handoff for measured-attestation verifier smoke runs.

This command is read-only. It validates operator-provided local file metadata
and prints the exact local commands needed to produce and validate a bounded
measured-attestation verifier-smoke artifact. It never runs the verifier,
reads raw attestation material into the output, writes artifacts, or promotes
production trust finality or production readiness claims by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "x0tta6bl4.measured_attestation_verifier_handoff.v1"
DECISION_READY = "MEASURED_ATTESTATION_VERIFIER_HANDOFF_READY"
DECISION_BLOCKED = "MEASURED_ATTESTATION_VERIFIER_HANDOFF_BLOCKED_ON_OPERATOR"
CLAIM_BOUNDARY = (
    "Read-only operator handoff for bounded measured-attestation verifier "
    "smoke. It can prove local inputs and command surface are ready to run, "
    "but it does not run the verifier, validate an artifact, prove production "
    "trust finality, fleet hardware coverage, PQC identity finality, customer "
    "traffic, settlement finality, production SLOs, or production readiness."
)
SMOKE_COMMAND = (
    'python3 scripts/ops/verify_measured_attestation_verifier_smoke.py --root . '
    '--provider "${X0T_MEASURED_ATTESTATION_PROVIDER:-sgx}" '
    '--report-data-file "$X0T_MEASURED_ATTESTATION_REPORT_DATA_FILE" '
    '--quote-file "$X0T_MEASURED_ATTESTATION_QUOTE_FILE" '
    '--signature-file "$X0T_MEASURED_ATTESTATION_SIGNATURE_FILE" '
    '--verifier-command "${X0T_MEASURED_ATTESTATION_VERIFIER_COMMAND:-$X0T_MEASURED_ATTESTATION_SGX_VERIFIER_COMMAND}" '
    '--operator-or-lab-id "$X0T_MEASURED_ATTESTATION_OPERATOR_OR_LAB_ID" '
    '--authorization-scope-id "$X0T_MEASURED_ATTESTATION_AUTHORIZATION_SCOPE_ID" '
    '--environment-bucket "$X0T_MEASURED_ATTESTATION_ENVIRONMENT_BUCKET" '
    '--hardware-profile-bucket "$X0T_MEASURED_ATTESTATION_HARDWARE_PROFILE_BUCKET" '
    '--policy-context "$X0T_MEASURED_ATTESTATION_POLICY_CONTEXT" '
    "--allow-local-verifier-run --json"
)
VALIDATE_COMMAND = (
    "python3 scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py "
    "--candidate docs/verification/incoming/measured_attestation_verifier_smoke.json "
    "--require-ready --json"
)
PROOF_GATE_COMMAND = (
    "python3 scripts/ops/run_cross_plane_proof_gate.py "
    "--claim measured_attestation_verifier_smoke --json "
    "--output-json .tmp/validation-shards/cross-plane-proof-gate-current.json"
)
ENV_VARS = (
    "X0T_MEASURED_ATTESTATION_PROVIDER",
    "X0T_MEASURED_ATTESTATION_REPORT_DATA_FILE",
    "X0T_MEASURED_ATTESTATION_QUOTE_FILE",
    "X0T_MEASURED_ATTESTATION_SIGNATURE_FILE",
    "X0T_MEASURED_ATTESTATION_VERIFIER_COMMAND",
    "X0T_MEASURED_ATTESTATION_SGX_VERIFIER_COMMAND",
    "X0T_MEASURED_ATTESTATION_OPERATOR_OR_LAB_ID",
    "X0T_MEASURED_ATTESTATION_AUTHORIZATION_SCOPE_ID",
    "X0T_MEASURED_ATTESTATION_ENVIRONMENT_BUCKET",
    "X0T_MEASURED_ATTESTATION_HARDWARE_PROFILE_BUCKET",
    "X0T_MEASURED_ATTESTATION_POLICY_CONTEXT",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--provider",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_PROVIDER", "sgx"),
    )
    parser.add_argument(
        "--report-data-file",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_REPORT_DATA_FILE", ""),
    )
    parser.add_argument(
        "--quote-file",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_QUOTE_FILE", ""),
    )
    parser.add_argument(
        "--signature-file",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_SIGNATURE_FILE", ""),
    )
    parser.add_argument(
        "--verifier-command",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_VERIFIER_COMMAND", ""),
    )
    parser.add_argument(
        "--sgx-verifier-command",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_SGX_VERIFIER_COMMAND", ""),
    )
    parser.add_argument(
        "--operator-or-lab-id",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_OPERATOR_OR_LAB_ID", ""),
    )
    parser.add_argument(
        "--authorization-scope-id",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_AUTHORIZATION_SCOPE_ID", ""),
    )
    parser.add_argument(
        "--environment-bucket",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_ENVIRONMENT_BUCKET", ""),
    )
    parser.add_argument(
        "--hardware-profile-bucket",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_HARDWARE_PROFILE_BUCKET", ""),
    )
    parser.add_argument(
        "--policy-context",
        default=os.environ.get("X0T_MEASURED_ATTESTATION_POLICY_CONTEXT", ""),
    )
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _file_summary(root: Path, value: str, *, label: str) -> tuple[dict[str, Any], list[str]]:
    text = str(value or "").strip()
    summary = {
        "label": label,
        "path_present": bool(text),
        "path_hash": sha256_text(text) if text else None,
        "raw_path_redacted": True,
        "exists": False,
        "is_file": False,
        "is_symlink": False,
        "size_bytes": 0,
        "non_empty": False,
    }
    blockers: list[str] = []
    if not text:
        blockers.append(f"{label}_file_required")
        return summary, blockers

    path = _resolve_path(root, text)
    summary["exists"] = path.exists()
    summary["is_file"] = path.is_file()
    summary["is_symlink"] = path.is_symlink()
    if path.exists() and path.is_file():
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        summary["size_bytes"] = int(size)
        summary["non_empty"] = size > 0

    if summary["is_symlink"]:
        blockers.append(f"{label}_file_must_not_be_symlink")
    if not summary["exists"]:
        blockers.append(f"{label}_file_missing")
    elif not summary["is_file"]:
        blockers.append(f"{label}_file_not_regular")
    elif not summary["non_empty"]:
        blockers.append(f"{label}_file_empty")
    return summary, blockers


def _command_summary(
    command: str,
    *,
    blocker_prefix: str = "sgx_verifier_command",
) -> tuple[dict[str, Any], list[str]]:
    text = str(command or "").strip()
    summary = {
        "command_present": bool(text),
        "command_hash": sha256_text(text) if text else None,
        "raw_command_redacted": True,
        "argv0_present": False,
        "argv0_found": False,
    }
    blockers: list[str] = []
    if not text:
        blockers.append(f"{blocker_prefix}_required")
        return summary, blockers
    try:
        tokens = shlex.split(text)
    except ValueError:
        blockers.append(f"{blocker_prefix}_unparseable")
        return summary, blockers
    argv0 = tokens[0] if tokens else ""
    summary["argv0_present"] = bool(argv0)
    if not argv0:
        blockers.append(f"{blocker_prefix}_unparseable")
        return summary, blockers
    path = Path(argv0)
    found = path.exists() if path.is_absolute() else shutil.which(argv0) is not None
    summary["argv0_found"] = bool(found)
    if not found:
        blockers.append(f"{blocker_prefix}_not_found")
    return summary, blockers


def _effective_provider(value: str) -> str:
    normalized = str(value or "sgx").strip().lower()
    return normalized or "sgx"


def _effective_verifier_command(
    *,
    provider: str,
    verifier_command: str = "",
    sgx_verifier_command: str = "",
) -> str:
    if str(verifier_command or "").strip():
        return str(verifier_command)
    if _effective_provider(provider) == "sgx":
        return str(sgx_verifier_command or "")
    return ""


def _python_command_entrypoint(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    if len(tokens) >= 2 and tokens[0].startswith("python") and tokens[1].endswith(".py"):
        return tokens[1]
    return ""


def operator_command_checks(root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for action_id, command in (
        ("run_measured_attestation_verifier_smoke", SMOKE_COMMAND),
        ("verify_measured_attestation_verifier_smoke_artifact", VALIDATE_COMMAND),
        ("run_cross_plane_proof_gate", PROOF_GATE_COMMAND),
    ):
        entrypoint = _python_command_entrypoint(command)
        checks.append(
            {
                "action_id": action_id,
                "command": command,
                "expected_entrypoint": entrypoint,
                "entrypoint_exists": bool(entrypoint and (root / entrypoint).is_file()),
                "raw_operator_inputs_embedded": False,
            }
        )
    return checks


def build_report(
    root: Path,
    *,
    provider: str = "sgx",
    report_data_file: str = "",
    quote_file: str = "",
    signature_file: str = "",
    verifier_command: str = "",
    sgx_verifier_command: str = "",
    operator_or_lab_id: str = "",
    authorization_scope_id: str = "",
    environment_bucket: str = "",
    hardware_profile_bucket: str = "",
    policy_context: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    blockers: list[str] = []
    report_summary, report_blockers = _file_summary(
        root,
        report_data_file,
        label="report_data",
    )
    quote_summary, quote_blockers = _file_summary(root, quote_file, label="quote")
    signature_summary, signature_blockers = _file_summary(
        root,
        signature_file,
        label="signature",
    )
    effective_provider = _effective_provider(provider)
    supported_provider = effective_provider in {"sgx", "sev", "nitro"}
    command_blocker_prefix = f"{effective_provider}_verifier_command"
    effective_command = _effective_verifier_command(
        provider=effective_provider,
        verifier_command=verifier_command,
        sgx_verifier_command=sgx_verifier_command,
    )
    command_summary, command_blockers = _command_summary(
        effective_command,
        blocker_prefix=command_blocker_prefix,
    )
    blockers.extend(report_blockers)
    blockers.extend(quote_blockers)
    blockers.extend(signature_blockers)
    blockers.extend(command_blockers)
    if not supported_provider:
        blockers.append("provider_unsupported")

    private_fields = {
        "operator_or_lab_id": operator_or_lab_id,
        "authorization_scope_id": authorization_scope_id,
        "policy_context": policy_context,
    }
    for name, value in private_fields.items():
        if not str(value or "").strip():
            blockers.append(f"{name}_required")
    if not str(environment_bucket or "").strip():
        blockers.append("environment_bucket_required")
    if not str(hardware_profile_bucket or "").strip():
        blockers.append("hardware_profile_bucket_required")

    command_checks = operator_command_checks(root)
    if not all(check.get("entrypoint_exists") is True for check in command_checks):
        blockers.append("operator_command_surface_not_ready")

    ready = not blockers
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "decision": DECISION_READY if ready else DECISION_BLOCKED,
        "ready_for_operator_run": ready,
        "mutates_runtime": False,
        "runs_verifier": False,
        "reads_attestation_material_into_output": False,
        "writes_artifacts": False,
        "raw_inputs_redacted": True,
        "inputs": {
            "provider": {
                "value": effective_provider,
                "supported": supported_provider,
                "raw_value_redacted": True,
            },
            "report_data": report_summary,
            "quote": quote_summary,
            "signature": signature_summary,
            "verifier_command": command_summary,
            "sgx_verifier_command": command_summary,
            "operator_or_lab_hash": (
                sha256_text(operator_or_lab_id) if operator_or_lab_id else None
            ),
            "authorization_scope_hash": (
                sha256_text(authorization_scope_id)
                if authorization_scope_id
                else None
            ),
            "environment_bucket_present": bool(environment_bucket),
            "hardware_profile_bucket_present": bool(hardware_profile_bucket),
            "policy_context_hash": sha256_text(policy_context) if policy_context else None,
        },
        "claim_flags": {
            "measured_attestation_verifier_smoke_claimed": False,
            "production_attestation_verifier_claimed": False,
            "production_trust_finality_claimed": False,
            "fleet_hardware_coverage_claimed": False,
            "pqc_identity_finality_claimed": False,
            "traffic_delivery_claimed": False,
            "customer_traffic_claimed": False,
            "settlement_finality_claimed": False,
            "production_slo_claimed": False,
            "production_readiness_claimed": False,
        },
        "blockers": blockers,
        "operator_env_vars": list(ENV_VARS),
        "operator_commands": [
            {
                "id": "run_measured_attestation_verifier_smoke",
                "status": "READY" if ready else "OPERATOR_INPUT_REQUIRED",
                "command": SMOKE_COMMAND,
                "runs_verifier": True,
                "writes_artifact": True,
            },
            {
                "id": "verify_measured_attestation_verifier_smoke_artifact",
                "status": "READY" if ready else "WAITING_FOR_SMOKE_ARTIFACT",
                "command": VALIDATE_COMMAND,
                "runs_verifier": False,
            },
            {
                "id": "run_cross_plane_proof_gate",
                "status": "READY" if ready else "WAITING_FOR_VALIDATED_ARTIFACT",
                "command": PROOF_GATE_COMMAND,
                "runs_verifier": False,
            },
        ],
        "operator_command_checks": command_checks,
        "safe_local_input_steps": [
            "Keep report data, quote, signature, verifier command, operator ID, authorization scope, and policy context local.",
            "Set X0T_MEASURED_ATTESTATION_* env vars locally; Do not paste private values into chat.",
            "Run this handoff with --require-ready before running the verifier smoke.",
            "Run the listed smoke, validator, and proof-gate commands only in an authorized environment.",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        report_data_file=args.report_data_file,
        quote_file=args.quote_file,
        signature_file=args.signature_file,
        sgx_verifier_command=args.sgx_verifier_command,
        provider=args.provider,
        verifier_command=args.verifier_command,
        operator_or_lab_id=args.operator_or_lab_id,
        authorization_scope_id=args.authorization_scope_id,
        environment_bucket=args.environment_bucket,
        hardware_profile_bucket=args.hardware_profile_bucket,
        policy_context=args.policy_context,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ready_for_operator_run={report['ready_for_operator_run']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report["ready_for_operator_run"] or not args.require_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
