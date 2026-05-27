#!/usr/bin/env python3
"""Verify fail-closed incoming gap candidates for x0tta6bl4_pulse.

This checker is read-only. It validates that unresolved external evidence
claims have incoming gap candidate files under docs/verification/incoming, and
that the normal importer rejects those files. A passing report records an
intentional fail-closed state; it does not import evidence or promote proof
claims.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_PROOF = VERIFY_ROOT / "GHOST_PULSE_PROOF_GATE_LATEST.json"
DEFAULT_REPLACEMENT = VERIFY_ROOT / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
DEFAULT_INTAKE = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.incoming_gap_candidate_verification.v1"
EVIDENCE_SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
GAP_MODE = "EXTERNAL_EVIDENCE_GAP_RECORD"
DECISION_FAIL_CLOSED = "INCOMING_GAP_CANDIDATES_FAIL_CLOSED"
DECISION_NOT_REQUIRED = "INCOMING_GAP_CANDIDATES_NOT_REQUIRED"
DECISION_INVALID = "INCOMING_GAP_CANDIDATES_INVALID"
EXPECTED_FALSE_BOUNDARY = {
    "stealth_verified": False,
    "whitelist_verified": False,
    "kernel_attach_verified": False,
    "production_ready": False,
}
STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "decision",
    "proof",
    "replacement",
    "replacement_sha256",
    "intake",
    "intake_sha256",
    "expected_gap_claims",
    "unexpected_gap_claims",
    "rows",
    "checks",
    "failures",
    "claim_boundary",
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
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def sha256_file(path: Path | None) -> str | None:
    if not path or not path.exists() or not path.is_file():
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


def load_script(root: Path, rel_path: str, module_name: str):
    path = root / rel_path
    if not path.exists():
        path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_scaffold(root: Path):
    return load_script(
        root,
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        "scaffold_ghost_pulse_external_evidence_gaps_for_incoming_gap_verifier",
    )


def load_importer(root: Path):
    return load_script(
        root,
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "import_ghost_pulse_external_evidence_for_incoming_gap_verifier",
    )


def candidate_path(claim_id: str) -> str:
    return f"docs/verification/incoming/{claim_id}.json"


def source_record(root: Path, path: Path) -> dict[str, Any]:
    load_error = None
    data: dict[str, Any] = {}
    if not path.exists():
        load_error = "missing"
    elif not path.is_file():
        load_error = "not a regular file"
    else:
        try:
            data = load_json(path)
        except Exception as exc:
            load_error = str(exc)
    return {
        "path": display_path(root, path),
        "exists": path.exists(),
        "is_file": path.is_file() if path.exists() else False,
        "sha256": sha256_file(path),
        "schema": data.get("schema") if data else None,
        "status": data.get("status") if data else None,
        "decision": data.get("decision") if data else None,
        "load_error": load_error,
        "data": data,
    }


def proof_status_by_claim(proof: dict[str, Any]) -> dict[str, str]:
    rows = proof.get("proof_rows")
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_id = row.get("claim_id")
        status = row.get("status")
        if isinstance(claim_id, str) and isinstance(status, str):
            result[claim_id] = status
    return result


def string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def stable_import_report_summary(import_report: dict[str, Any]) -> dict[str, Any]:
    validation = import_report.get("validation")
    validation = validation if isinstance(validation, dict) else {}
    return {
        "schema": import_report.get("schema"),
        "decision": import_report.get("decision"),
        "claim_id": import_report.get("claim_id"),
        "candidate": import_report.get("candidate"),
        "candidate_exists": import_report.get("candidate_exists"),
        "candidate_is_file": import_report.get("candidate_is_file"),
        "candidate_is_symlink": import_report.get("candidate_is_symlink"),
        "candidate_sha256": import_report.get("candidate_sha256"),
        "write_requested": import_report.get("write_requested"),
        "written": import_report.get("written"),
        "validation_status": validation.get("status"),
        "validation_errors": validation.get("errors", []),
        "failures": import_report.get("failures", []),
        "claim_boundary": import_report.get("claim_boundary"),
    }


def boundary_false_failures(label: str, boundary: Any) -> list[str]:
    if not isinstance(boundary, dict):
        return [f"{label}.claim_boundary must be an object"]
    failures: list[str] = []
    for key, expected in EXPECTED_FALSE_BOUNDARY.items():
        if boundary.get(key) is not expected:
            failures.append(f"{label}.claim_boundary.{key} must be false")
    return failures


def validate_gap_payload(
    payload: dict[str, Any],
    claim_id: str,
    scaffold,
) -> list[str]:
    failures: list[str] = []
    spec = scaffold.CLAIM_GAPS[claim_id]
    if payload.get("schema") != EVIDENCE_SCHEMA:
        failures.append(f"{claim_id}: candidate schema is unexpected")
    if payload.get("claim_id") != claim_id:
        failures.append(f"{claim_id}: candidate claim_id mismatch")
    if payload.get("status") != scaffold.STATUS_INCOMPLETE:
        failures.append(f"{claim_id}: gap candidate status must be {scaffold.STATUS_INCOMPLETE}")
    if payload.get("simulated") is not False:
        failures.append(f"{claim_id}: gap candidate simulated must be false")
    if payload.get("dry_run") is not False:
        failures.append(f"{claim_id}: gap candidate dry_run must be false")
    if payload.get("template") is not False:
        failures.append(f"{claim_id}: gap candidate template must be false")
    if payload.get("mode") != GAP_MODE:
        failures.append(f"{claim_id}: gap candidate mode must be {GAP_MODE}")
    if payload.get("gap_artifact_role") != scaffold.GAP_ARTIFACT_ROLE:
        failures.append(f"{claim_id}: gap_artifact_role mismatch")
    if payload.get("required_artifact_roles") != spec.get("required_artifact_roles", []):
        failures.append(f"{claim_id}: required_artifact_roles mismatch")
    if payload.get("missing_inputs") != spec.get("missing_inputs", []):
        failures.append(f"{claim_id}: missing_inputs mismatch")
    if not payload.get("failures"):
        failures.append(f"{claim_id}: gap candidate failures must explain missing evidence")
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict) or boundary.get("claim_verified") is not False:
        failures.append(f"{claim_id}: claim_boundary.claim_verified must be false")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append(f"{claim_id}: gap candidate must include a gap-record artifact")
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                failures.append(f"{claim_id}: artifacts[{index}] must be an object")
                continue
            if artifact.get("role") != scaffold.GAP_ARTIFACT_ROLE:
                failures.append(f"{claim_id}: artifacts[{index}].role must be {scaffold.GAP_ARTIFACT_ROLE}")
            artifact_path = artifact.get("path")
            if not isinstance(artifact_path, str) or not artifact_path:
                failures.append(f"{claim_id}: artifacts[{index}].path is required")
            if not isinstance(artifact.get("sha256"), str) or len(artifact["sha256"]) != 64:
                failures.append(f"{claim_id}: artifacts[{index}].sha256 must be a sha256 hex string")
    return failures


def validate_import_rejection(
    claim_id: str,
    import_report: dict[str, Any],
    importer,
) -> list[str]:
    failures: list[str] = []
    import_failures = string_list(import_report.get("failures"))
    if import_report.get("decision") != importer.DECISION_REJECTED:
        failures.append(f"{claim_id}: importer must reject the incoming gap candidate")
    if import_report.get("written") is not False:
        failures.append(f"{claim_id}: importer must not write a gap candidate")
    if not any("status must be VERIFIED" in failure for failure in import_failures):
        failures.append(f"{claim_id}: importer rejection must include status-not-VERIFIED")
    if not any(f"mode must not be {GAP_MODE}" in failure for failure in import_failures):
        failures.append(f"{claim_id}: importer rejection must include gap-mode rejection")
    failures.extend(boundary_false_failures(f"{claim_id}.importer", import_report.get("claim_boundary")))
    return failures


def candidate_row(root: Path, claim_id: str, scaffold, importer) -> dict[str, Any]:
    rel_candidate = candidate_path(claim_id)
    path = root / rel_candidate
    failures: list[str] = []
    payload: dict[str, Any] = {}
    if not path.exists():
        failures.append(f"{claim_id}: incoming gap candidate is missing: {rel_candidate}")
    elif not path.is_file():
        failures.append(f"{claim_id}: incoming gap candidate is not a regular file: {rel_candidate}")
    elif path.is_symlink():
        failures.append(f"{claim_id}: incoming gap candidate must not be a symlink: {rel_candidate}")
    else:
        try:
            payload = load_json(path)
        except Exception as exc:
            failures.append(f"{claim_id}: incoming gap candidate could not be loaded: {exc}")
        else:
            failures.extend(validate_gap_payload(payload, claim_id, scaffold))

    import_report = importer.build_report(root, claim_id, path, write_requested=False)
    failures.extend(validate_import_rejection(claim_id, import_report, importer))

    return {
        "claim_id": claim_id,
        "candidate": rel_candidate,
        "candidate_exists": path.exists(),
        "candidate_is_file": path.is_file() if path.exists() else False,
        "candidate_is_symlink": path.is_symlink() if path.exists() else False,
        "candidate_sha256": sha256_file(path),
        "payload_status": payload.get("status"),
        "payload_mode": payload.get("mode"),
        "payload_template": payload.get("template"),
        "payload_claim_verified": (
            payload.get("claim_boundary", {}).get("claim_verified")
            if isinstance(payload.get("claim_boundary"), dict)
            else None
        ),
        "expected_import_decision": importer.DECISION_REJECTED,
        "import_decision": import_report.get("decision"),
        "import_failures": string_list(import_report.get("failures")),
        "read_only_import_report": stable_import_report_summary(import_report),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def unexpected_gap_claims(root: Path, supported_claims: list[str], expected_claims: list[str]) -> list[str]:
    unexpected: list[str] = []
    expected = set(expected_claims)
    for claim_id in supported_claims:
        if claim_id in expected:
            continue
        path = root / candidate_path(claim_id)
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = load_json(path)
        except Exception:
            continue
        if payload.get("mode") == GAP_MODE:
            unexpected.append(claim_id)
    return unexpected


def build_report(
    root: Path = ROOT,
    *,
    proof_path: Path | None = None,
    replacement_path: Path | None = None,
    intake_path: Path | None = None,
) -> dict[str, Any]:
    proof_path = proof_path or root / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    replacement_path = replacement_path or root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    intake_path = intake_path or root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    proof_source = source_record(root, proof_path)
    replacement_source = source_record(root, replacement_path)
    intake_source = source_record(root, intake_path)
    proof = proof_source.pop("data")
    replacement = replacement_source.pop("data")
    intake = intake_source.pop("data")

    scaffold = load_scaffold(root)
    importer = load_importer(root)
    supported_claims = list(scaffold.CLAIM_GAPS)
    statuses = proof_status_by_claim(proof)
    not_verified = string_list(proof.get("not_verified_yet"))
    expected_gap_claims = [
        claim_id
        for claim_id in supported_claims
        if claim_id in not_verified or statuses.get(claim_id) != "VERIFIED"
    ]

    failures: list[str] = []
    for name, source in (
        ("proof", proof_source),
        ("replacement", replacement_source),
        ("intake", intake_source),
    ):
        if source.get("load_error"):
            failures.append(f"{name}: {source['load_error']}")

    if proof.get("schema") != "x0tta6bl4.ghost_pulse.proof_gate.v1":
        failures.append("proof.schema is unexpected")
    if not isinstance(proof.get("proof_rows"), list):
        failures.append("proof.proof_rows must be a list")
    if proof.get("not_verified_yet") is not None and not isinstance(proof.get("not_verified_yet"), list):
        failures.append("proof.not_verified_yet must be a list")

    replacement_not_ready = string_list(replacement.get("not_ready"))
    replacement_ready = string_list(replacement.get("ready"))
    intake_not_ready = string_list(intake.get("not_ready"))
    intake_ready = string_list(intake.get("ready"))
    if replacement and replacement.get("schema") != "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1":
        failures.append("replacement.schema is unexpected")
    if intake and intake.get("schema") != "x0tta6bl4.ghost_pulse.external_evidence_intake.v1":
        failures.append("intake.schema is unexpected")
    if sorted(claim for claim in replacement_not_ready if claim in supported_claims) != sorted(expected_gap_claims):
        failures.append("replacement.not_ready supported claims must match expected incoming gap claims")
    if sorted(claim for claim in intake_not_ready if claim in supported_claims) != sorted(expected_gap_claims):
        failures.append("intake.not_ready supported claims must match expected incoming gap claims")
    unexpected_ready = sorted(
        claim for claim in replacement_ready + intake_ready if claim in expected_gap_claims
    )
    if unexpected_ready:
        failures.append(f"expected gap claims must not be ready: {', '.join(unexpected_ready)}")
    failures.extend(boundary_false_failures("replacement", replacement.get("claim_boundary")))
    failures.extend(boundary_false_failures("intake", intake.get("claim_boundary")))

    rows = [candidate_row(root, claim_id, scaffold, importer) for claim_id in expected_gap_claims]
    row_failures = [
        failure
        for row in rows
        for failure in row.get("failures", [])
    ]
    failures.extend(row_failures)

    stale_gap_claims = unexpected_gap_claims(root, supported_claims, expected_gap_claims)
    if stale_gap_claims:
        failures.append(
            "incoming gap candidates are stale for verified/non-pending claims: "
            f"{', '.join(stale_gap_claims)}"
        )

    if failures:
        decision = DECISION_INVALID
    elif expected_gap_claims:
        decision = DECISION_FAIL_CLOSED
    else:
        decision = DECISION_NOT_REQUIRED

    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "proof": proof_source["path"],
        "proof_sha256": proof_source["sha256"],
        "replacement": replacement_source["path"],
        "replacement_sha256": replacement_source["sha256"],
        "intake": intake_source["path"],
        "intake_sha256": intake_source["sha256"],
        "expected_gap_claims": expected_gap_claims,
        "unexpected_gap_claims": stale_gap_claims,
        "rows": rows,
        "checks": {
            "proof_pending_gap_claims": {
                "status": "PASS" if not failures else "FAIL",
                "supported_claims": supported_claims,
                "expected_gap_claims": expected_gap_claims,
            },
            "importer_rejects_gap_candidates": {
                "status": "PASS" if not row_failures else "FAIL",
                "row_count": len(rows),
            },
        },
        "failures": failures,
        "claim_boundary": {
            "note": "Incoming gap candidate verification only; rejected candidates do not prove external claims.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Incoming Gap Candidates",
        "",
        f"Timestamp: `{report.get('timestamp_utc')}`",
        "",
        f"Status: `{report.get('status')}`",
        "",
        f"Decision: `{report.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- expected_gap_claims: `{', '.join(report.get('expected_gap_claims', [])) or 'none'}`",
        f"- unexpected_gap_claims: `{', '.join(report.get('unexpected_gap_claims', [])) or 'none'}`",
        f"- rows: `{len(report.get('rows', []))}`",
        "",
        "## Rows",
        "",
        "| Claim | Candidate | Payload Status | Mode | Import Decision | Row Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.get("rows", []):
        if not isinstance(row, dict):
            lines.append("| INVALID |  |  |  |  |  |")
            continue
        lines.append(
            "| "
            f"{row.get('claim_id')} | "
            f"`{row.get('candidate')}` | "
            f"`{row.get('payload_status')}` | "
            f"`{row.get('payload_mode')}` | "
            f"`{row.get('import_decision')}` | "
            f"`{row.get('status')}` |"
        )
    lines.extend(["", "## Claim Boundary", ""])
    boundary = report.get("claim_boundary", {})
    if isinstance(boundary, dict):
        for key in sorted(boundary):
            lines.append(f"- {key}: `{boundary[key]}`")
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
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-incoming-gap-candidates-{stamp}"
    bundle_json = bundle_dir / "gap_candidates.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "incoming_gap_candidates_bundle_json": display_path(root, bundle_json),
        "incoming_gap_candidates_bundle_md": display_path(root, bundle_md),
        "incoming_gap_candidates_latest_json": display_path(root, output_json),
        "incoming_gap_candidates_latest_md": display_path(root, output_md),
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
        return [f"missing incoming gap candidate report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"incoming gap candidate report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load incoming gap candidate report: {exc}"]

    if data.get("schema") != SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    proof_path = resolve_path(root, data.get("proof")) or DEFAULT_PROOF
    replacement_path = resolve_path(root, data.get("replacement")) or DEFAULT_REPLACEMENT
    intake_path = resolve_path(root, data.get("intake")) or DEFAULT_INTAKE
    expected = build_report(
        root,
        proof_path=proof_path,
        replacement_path=replacement_path,
        intake_path=intake_path,
    )
    if stable_subset(data) != stable_subset(expected):
        failures.append("incoming gap candidate stable fields do not match current proof/intake state")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("incoming_gap_candidates_latest_json"))
    latest_md = resolve_path(root, artifacts.get("incoming_gap_candidates_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("incoming_gap_candidates_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("incoming_gap_candidates_bundle_md"))
    if latest_json != report_path:
        failures.append("artifacts.incoming_gap_candidates_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("incoming gap candidate latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("incoming gap candidate latest markdown does not match bundle markdown")
    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("incoming gap candidate latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("incoming gap candidate bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    parser.add_argument("--replacement", type=Path, default=DEFAULT_REPLACEMENT)
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--report", type=Path, help="Saved incoming gap candidate report to verify read-only.")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-fail-closed", action="store_true")
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
            "expected_gap_claims": saved.get("expected_gap_claims", []),
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse incoming gap candidate report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse incoming gap candidate report is current")
            print(f"report={result['report']}")
            print(f"decision={result['decision']}")
        if failures:
            return 1
        if args.require_fail_closed and saved.get("decision") != DECISION_FAIL_CLOSED:
            return 1
        return 0

    proof_path = args.proof if args.proof.is_absolute() else root / args.proof
    replacement_path = args.replacement if args.replacement.is_absolute() else root / args.replacement
    intake_path = args.intake if args.intake.is_absolute() else root / args.intake
    report = build_report(root, proof_path=proof_path, replacement_path=replacement_path, intake_path=intake_path)
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "PASS":
        print("FAIL: x0tta6bl4_pulse incoming gap candidates are inconsistent")
        for failure in report["failures"]:
            print(f"- {failure}")
    else:
        print("PASS: x0tta6bl4_pulse incoming gap candidates are fail-closed")
        print(f"decision={report['decision']}")
        print(f"expected_gap_claims={','.join(report['expected_gap_claims']) or 'none'}")

    if report["status"] != "PASS":
        return 1
    if args.require_fail_closed and report["decision"] != DECISION_FAIL_CLOSED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
