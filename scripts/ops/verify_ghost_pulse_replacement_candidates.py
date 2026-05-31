#!/usr/bin/env python3
"""Verify x0tta6bl4_pulse replacement candidates from the gap-audit passport.

This checker is read-only. It loads the current external evidence gap audit,
verifies that the embedded replacement passport is current, then validates each
candidate path listed in that passport with the same importer used for actual
external evidence replacement. Missing or invalid candidates are reported as a
machine-readable NOT_READY state; they do not promote proof-gate claim
boundaries.
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
DEFAULT_AUDIT = ROOT / "docs" / "verification" / "GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
DEFAULT_REPORT_JSON = Path("docs") / "verification" / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
DEFAULT_REPORT_MD = Path("docs") / "verification" / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1"
DECISION_READY = "REPLACEMENT_CANDIDATES_READY"
DECISION_NOT_READY = "REPLACEMENT_CANDIDATES_NOT_READY"
DECISION_PASSPORT_INVALID = "REPLACEMENT_PASSPORT_INVALID"
STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "decision",
    "audit",
    "audit_sha256",
    "replacement_required",
    "ready",
    "not_ready",
    "missing_candidates",
    "non_file_candidates",
    "unsafe_candidates",
    "rows",
    "candidate_intake_plan",
    "failures",
    "gap_audit_failures",
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
        return json.load(f)


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


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


def load_gap_verifier(root: Path):
    return load_script(
        root,
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
        "verify_ghost_pulse_external_evidence_gap_audit_for_replacement_preflight",
    )


def load_importer(root: Path):
    return load_script(
        root,
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "import_ghost_pulse_external_evidence_for_replacement_preflight",
    )


def stable_import_report_summary(import_report: dict[str, Any]) -> dict[str, Any]:
    destination_before = import_report.get("destination_validation_before")
    validation = import_report.get("validation")
    external_dpi = import_report.get("external_dpi_proxy_validation")
    return {
        "schema": import_report.get("schema"),
        "decision": import_report.get("decision"),
        "claim_id": import_report.get("claim_id"),
        "candidate": import_report.get("candidate"),
        "incoming_root": import_report.get("incoming_root"),
        "candidate_exists": import_report.get("candidate_exists"),
        "candidate_is_file": import_report.get("candidate_is_file"),
        "candidate_is_symlink": import_report.get("candidate_is_symlink"),
        "candidate_sha256": import_report.get("candidate_sha256"),
        "destination": import_report.get("destination"),
        "destination_sha256_before": import_report.get("destination_sha256_before"),
        "destination_validation_before": (
            {
                "status": destination_before.get("status"),
                "errors": destination_before.get("errors", []),
                "sha256": destination_before.get("sha256"),
            }
            if isinstance(destination_before, dict)
            else None
        ),
        "requirement_contract": import_report.get("requirement_contract"),
        "write_requested": import_report.get("write_requested"),
        "written": import_report.get("written"),
        "failures": import_report.get("failures", []),
        "validation": (
            {
                "status": validation.get("status"),
                "errors": validation.get("errors", []),
                "sha256": validation.get("sha256"),
            }
            if isinstance(validation, dict)
            else None
        ),
        "external_dpi_proxy_validation": (
            {
                "status": external_dpi.get("status"),
                "decision": external_dpi.get("decision"),
                "failures": external_dpi.get("failures", []),
                "summary": external_dpi.get("summary", {}),
            }
            if isinstance(external_dpi, dict)
            else None
        ),
        "claim_boundary": import_report.get("claim_boundary"),
    }


def row_for_passport_claim(root: Path, importer, claim: dict[str, Any]) -> dict[str, Any]:
    claim_id = claim.get("claim_id")
    candidate_value = claim.get("candidate_path")
    candidate_path = resolve_path(root, candidate_value)
    if not isinstance(claim_id, str) or not claim_id:
        return {
            "claim_id": claim_id,
            "candidate": candidate_value,
            "candidate_exists": False,
            "candidate_is_file": False,
            "candidate_is_symlink": False,
            "ready_to_import": False,
            "import_decision": None,
            "failures": ["passport claim_id is missing or invalid"],
        }
    if not candidate_path:
        return {
            "claim_id": claim_id,
            "candidate": candidate_value,
            "candidate_exists": False,
            "candidate_is_file": False,
            "candidate_is_symlink": False,
            "ready_to_import": False,
            "import_decision": None,
            "failures": [f"{claim_id}: candidate_path is missing"],
        }

    import_report = importer.build_report(root, claim_id, candidate_path, write_requested=False)
    validation = import_report.get("validation")
    destination_before = import_report.get("destination_validation_before")
    ready = import_report.get("decision") == importer.DECISION_READY
    return {
        "claim_id": claim_id,
        "candidate": display_path(root, candidate_path),
        "incoming_root": import_report.get("incoming_root"),
        "candidate_exists": import_report.get("candidate_exists"),
        "candidate_is_file": import_report.get("candidate_is_file"),
        "candidate_is_symlink": import_report.get("candidate_is_symlink"),
        "candidate_sha256": import_report.get("candidate_sha256"),
        "passport_current_status": claim.get("current_status"),
        "passport_current_sha256": claim.get("current_sha256"),
        "passport_blocking_categories": claim.get("blocking_categories"),
        "destination": import_report.get("destination"),
        "destination_sha256_before": import_report.get("destination_sha256_before"),
        "destination_validation_before_status": (
            destination_before.get("status") if isinstance(destination_before, dict) else None
        ),
        "candidate_example_path": claim.get("candidate_example_path"),
        "incoming_example_command": claim.get("incoming_example_command"),
        "import_decision": import_report.get("decision"),
        "ready_to_import": ready,
        "validation_status": validation.get("status") if isinstance(validation, dict) else None,
        "validation_errors": validation.get("errors") if isinstance(validation, dict) else [],
        "failures": import_report.get("failures", []),
        "read_only_import_report": stable_import_report_summary(import_report),
        "read_only_import_command": claim.get("read_only_import_command"),
        "write_import_command": claim.get("write_import_command"),
        "acceptance_commands": claim.get("acceptance_commands"),
    }


def refresh_command_sequence() -> list[list[str]]:
    return [
        ["python3", "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py", "--json"],
        ["python3", "scripts/ops/verify_ghost_pulse_replacement_candidates.py", "--write-report", "--json"],
        ["python3", "scripts/ops/verify_ghost_pulse_external_evidence_intake.py", "--write-report", "--json"],
        ["python3", "scripts/ops/run_ghost_pulse_proof_gate.py", "--json"],
        ["python3", "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py", "--write-report", "--json"],
        ["python3", "scripts/ops/run_ghost_pulse_verification_suite.py"],
        ["python3", "scripts/ops/run_ghost_pulse_proof_gate.py", "--json"],
        ["python3", "scripts/ops/verify_ghost_pulse_artifact_chain.py", "--write-report", "--json"],
        ["python3", "scripts/ops/verify_ghost_pulse_goal_state.py", "--write-report", "--json"],
    ]


def candidate_intake_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready_claims = [row["claim_id"] for row in rows if row.get("ready_to_import") is True]
    not_ready_claims = [row["claim_id"] for row in rows if row.get("ready_to_import") is not True]
    missing_candidate_paths = [
        row["candidate"]
        for row in rows
        if row.get("candidate_exists") is False and isinstance(row.get("candidate"), str)
    ]
    non_file_candidate_paths = [
        row["candidate"]
        for row in rows
        if row.get("candidate_exists") is True
        and row.get("candidate_is_file") is not True
        and isinstance(row.get("candidate"), str)
    ]
    unsafe_candidate_paths = [
        row["candidate"]
        for row in rows
        if row.get("candidate_is_symlink") is True and isinstance(row.get("candidate"), str)
    ]
    read_only_commands = [
        row["read_only_import_command"]
        for row in rows
        if isinstance(row.get("read_only_import_command"), list)
    ]
    all_write_commands = [
        row["write_import_command"]
        for row in rows
        if isinstance(row.get("write_import_command"), list)
    ]
    ready_write_commands = [
        row["write_import_command"]
        for row in rows
        if row.get("ready_to_import") is True and isinstance(row.get("write_import_command"), list)
    ]
    return {
        "status": "READY_TO_IMPORT" if rows and not not_ready_claims else "ACTION_REQUIRED",
        "ready_claims": ready_claims,
        "not_ready_claims": not_ready_claims,
        "missing_candidate_paths": missing_candidate_paths,
        "non_file_candidate_paths": non_file_candidate_paths,
        "unsafe_candidate_paths": unsafe_candidate_paths,
        "read_only_preflight_commands": read_only_commands,
        "currently_ready_write_commands": ready_write_commands,
        "write_commands_after_ready": all_write_commands,
        "post_import_refresh_commands": refresh_command_sequence(),
        "claim_boundary": (
            "Intake plan only; run read-only preflight first, import only READY_TO_IMPORT candidates, "
            "then refresh proof/inventory/chain. This plan does not promote proof-gate claims."
        ),
    }


def build_report(root: Path = ROOT, audit_path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    audit_path = audit_path if audit_path.is_absolute() else root / audit_path
    failures: list[str] = []
    gap_failures: list[str] = []
    rows: list[dict[str, Any]] = []
    replacement_required: list[str] = []

    if not audit_path.exists():
        failures.append(f"missing gap audit: {display_path(root, audit_path)}")
        audit_data: dict[str, Any] = {}
    elif not audit_path.is_file():
        failures.append(f"gap audit is not a regular file: {display_path(root, audit_path)}")
        audit_data = {}
    else:
        audit_data = load_json(audit_path)
        verifier = load_gap_verifier(root)
        gap_failures = verifier.verify_audit(audit_path, root)
        failures.extend(f"gap audit: {failure}" for failure in gap_failures)

    passport = audit_data.get("replacement_passport", {}) if isinstance(audit_data, dict) else {}
    passport_claims = passport.get("claims", []) if isinstance(passport, dict) else []
    if isinstance(audit_data.get("replacement_required"), list):
        replacement_required = list(audit_data["replacement_required"])

    if not failures:
        if not isinstance(passport_claims, list):
            failures.append("replacement_passport.claims must be a list")
        else:
            importer = load_importer(root)
            for claim in passport_claims:
                if not isinstance(claim, dict):
                    rows.append(
                        {
                            "claim_id": None,
                            "candidate": None,
                            "candidate_exists": False,
                            "ready_to_import": False,
                            "import_decision": None,
                            "failures": ["replacement_passport claim must be an object"],
                        }
                    )
                    continue
                rows.append(row_for_passport_claim(root, importer, claim))

    ready_claims = [row["claim_id"] for row in rows if row.get("ready_to_import") is True]
    not_ready_claims = [row["claim_id"] for row in rows if row.get("ready_to_import") is not True]
    missing_candidates = [row["claim_id"] for row in rows if row.get("candidate_exists") is False]
    non_file_candidates = [
        row["claim_id"]
        for row in rows
        if row.get("candidate_exists") is True and row.get("candidate_is_file") is not True
    ]
    unsafe_candidates = [
        row["claim_id"]
        for row in rows
        if row.get("candidate_is_symlink") is True
        or (
            isinstance(row.get("incoming_root"), dict)
            and row["incoming_root"].get("is_symlink") is True
        )
        or (
            isinstance(row.get("incoming_root"), dict)
            and row["incoming_root"].get("has_symlink_component") is True
        )
    ]
    if failures:
        decision = DECISION_PASSPORT_INVALID
    elif not_ready_claims:
        decision = DECISION_NOT_READY
    else:
        decision = DECISION_READY

    return {
        "schema": SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "audit": display_path(root, audit_path),
        "audit_sha256": sha256_file(audit_path),
        "replacement_required": replacement_required,
        "ready": ready_claims,
        "not_ready": not_ready_claims,
        "missing_candidates": missing_candidates,
        "non_file_candidates": non_file_candidates,
        "unsafe_candidates": unsafe_candidates,
        "rows": rows,
        "candidate_intake_plan": candidate_intake_plan(rows),
        "failures": failures,
        "gap_audit_failures": gap_failures,
        "claim_boundary": {
            "note": "Replacement candidate preflight only; it never promotes proof-gate claims.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Replacement Candidate Preflight",
        "",
        f"Status: `{report.get('status')}`",
        "",
        f"Decision: `{report.get('decision')}`",
        "",
        f"Audit: `{report.get('audit')}`",
        "",
        f"Audit sha256: `{report.get('audit_sha256')}`",
        "",
        "## Claim Boundary",
        "",
    ]
    claim_boundary = report.get("claim_boundary", {})
    if isinstance(claim_boundary, dict):
        for key in sorted(claim_boundary):
            lines.append(f"- {key}: `{claim_boundary[key]}`")
    else:
        lines.append("- INVALID")

    lines.extend(["", "## Summary", ""])
    lines.append(f"- replacement_required: `{', '.join(report.get('replacement_required', [])) or 'none'}`")
    lines.append(f"- ready: `{', '.join(report.get('ready', [])) or 'none'}`")
    lines.append(f"- not_ready: `{', '.join(report.get('not_ready', [])) or 'none'}`")
    lines.append(f"- missing_candidates: `{', '.join(report.get('missing_candidates', [])) or 'none'}`")
    lines.append(f"- non_file_candidates: `{', '.join(report.get('non_file_candidates', [])) or 'none'}`")
    lines.append(f"- unsafe_candidates: `{', '.join(report.get('unsafe_candidates', [])) or 'none'}`")

    plan = report.get("candidate_intake_plan", {})
    lines.extend(["", "## Candidate Intake Plan", ""])
    if isinstance(plan, dict):
        lines.append(f"- status: `{plan.get('status')}`")
        lines.append(f"- ready_claims: `{', '.join(plan.get('ready_claims', [])) or 'none'}`")
        lines.append(f"- not_ready_claims: `{', '.join(plan.get('not_ready_claims', [])) or 'none'}`")
        lines.append(
            f"- missing_candidate_paths: `{', '.join(plan.get('missing_candidate_paths', [])) or 'none'}`"
        )
        lines.append(
            f"- currently_ready_write_commands: `{len(plan.get('currently_ready_write_commands', []))}`"
        )
        lines.append(f"- post_import_refresh_commands: `{len(plan.get('post_import_refresh_commands', []))}`")
    else:
        lines.append("- INVALID")

    lines.extend([
        "",
        "## Rows",
        "",
        "| Claim | Candidate | Exists | Is File | Symlink | Import Decision | Ready |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    rows = report.get("rows", [])
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                lines.append("| INVALID |  |  |  |  |  |  |")
                continue
            lines.append(
                "| "
                f"{row.get('claim_id')} | "
                f"`{row.get('candidate')}` | "
                f"`{row.get('candidate_exists')}` | "
                f"`{row.get('candidate_is_file')}` | "
                f"`{row.get('candidate_is_symlink')}` | "
                f"`{row.get('import_decision')}` | "
                f"`{row.get('ready_to_import')}` |"
            )
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    if "timestamp_utc" not in report:
        report["timestamp_utc"] = utc_now()
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-replacement-candidates-{stamp}"
    bundle_json = bundle_dir / "preflight.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "preflight_bundle_json": display_path(root, bundle_json),
        "preflight_bundle_md": display_path(root, bundle_md),
        "preflight_latest_json": display_path(root, output_json),
        "preflight_latest_md": display_path(root, output_md),
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
        return [f"missing replacement candidate report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"replacement candidate report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load replacement candidate report: {exc}"]

    if data.get("schema") != SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")

    audit_path = resolve_path(root, data.get("audit")) or DEFAULT_AUDIT
    expected = build_report(root, audit_path)
    if stable_subset(data) != stable_subset(expected):
        failures.append("replacement candidate stable fields do not match current passport/candidate state")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("preflight_latest_json"))
    latest_md = resolve_path(root, artifacts.get("preflight_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("preflight_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("preflight_bundle_md"))

    if latest_json != report_path:
        failures.append("artifacts.preflight_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("preflight latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("preflight latest markdown does not match bundle markdown")

    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("preflight latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("preflight bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--report", type=Path, help="Saved preflight report to verify read-only.")
    parser.add_argument("--write-report", action="store_true", help="Write latest and bundle preflight reports.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        failures = verify_saved_report(report_path, root)
        saved = load_json(report_path) if report_path.exists() else {}
        result = {
            "status": "PASS" if not failures else "FAIL",
            "decision": saved.get("decision"),
            "report": display_path(root, report_path),
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse replacement candidate report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse replacement candidate report is current")
            print(f"report={result['report']}")
            print(f"decision={result['decision']}")
        if failures:
            return 1
        if args.require_ready and saved.get("decision") != DECISION_READY:
            return 1
        return 0

    audit_path = args.audit if args.audit.is_absolute() else root / args.audit
    report = build_report(root, audit_path)
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "PASS":
        print("FAIL: x0tta6bl4_pulse replacement passport is invalid")
        for failure in report["failures"]:
            print(f"- {failure}")
    else:
        print(f"decision={report['decision']}")
        print(f"audit={report['audit']}")
        print(f"ready={','.join(report['ready']) if report['ready'] else 'none'}")
        print(f"not_ready={','.join(report['not_ready']) if report['not_ready'] else 'none'}")

    if report["status"] != "PASS":
        return 1
    if args.require_ready and report["decision"] != DECISION_READY:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
