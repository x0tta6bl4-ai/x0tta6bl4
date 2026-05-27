#!/usr/bin/env python3
"""Verify x0tta6bl4_pulse external evidence inventory completeness.

This checker is read-only. It verifies that every external evidence file
required by the proof gate exists, has a latest markdown companion, and matches
the current proof-gate row for the same claim. INVALID rows are acceptable only
when they are explicit evidence records, not missing files, and the current gap
audit covers them with replacement contracts.
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
DEFAULT_PROOF = ROOT / "docs" / "verification" / "GHOST_PULSE_PROOF_GATE_LATEST.json"
DEFAULT_GAP_AUDIT = ROOT / "docs" / "verification" / "GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
DEFAULT_REPORT_JSON = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
DEFAULT_REPORT_MD = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md"

STATUS_ALL_VERIFIED = "EXTERNAL_EVIDENCE_INVENTORY_ALL_VERIFIED"
STATUS_COMPLETE_WITH_GAPS = "EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS"
STATUS_INCOMPLETE = "EXTERNAL_EVIDENCE_INVENTORY_INCOMPLETE"
STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "inventory_status",
    "proof",
    "rows",
    "failures",
    "verified",
    "invalid",
    "missing",
    "gap_audit",
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


def compare_bytes(left: Path | None, right: Path | None) -> bool:
    if not left or not right or not left.exists() or not right.exists():
        return False
    if not left.is_file() or not right.is_file():
        return False
    return left.read_bytes() == right.read_bytes()


def stable_subset(report: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in STABLE_REPORT_KEYS}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_proof_runner(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    return load_module("run_ghost_pulse_proof_gate_for_external_inventory", path)


def load_proof_verifier(root: Path):
    path = root / "scripts" / "ops" / "verify_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "verify_ghost_pulse_proof_gate.py"
    return load_module("verify_ghost_pulse_proof_gate_for_external_inventory", path)


def load_gap_audit_verifier(root: Path):
    path = root / "scripts" / "ops" / "verify_ghost_pulse_external_evidence_gap_audit.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "verify_ghost_pulse_external_evidence_gap_audit.py"
    return load_module("verify_ghost_pulse_external_evidence_gap_audit_for_external_inventory", path)


def row_by_claim(proof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in proof.get("proof_rows", []):
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str):
            rows[row["claim_id"]] = row
    return rows


def gap_rows_by_claim(gap_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in gap_audit.get("rows", []):
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str):
            rows[row["claim_id"]] = row
    return rows


def requirement_map(proof_runner) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in proof_runner.EXTERNAL_REQUIREMENTS}


def build_row(root: Path, proof_runner, proof_rows: dict[str, dict[str, Any]], requirement: dict[str, Any]) -> dict[str, Any]:
    claim_id = requirement["claim_id"]
    validation = proof_runner.validate_external_evidence(root, requirement)
    proof_row = proof_rows.get(claim_id, {})
    evidence_path = resolve_path(root, requirement["path"])
    md_path = evidence_path.with_suffix(".md") if evidence_path else None
    row_failures: list[str] = []

    if not proof_row:
        row_failures.append("proof row is missing")
    if validation["status"] == "MISSING":
        row_failures.append("required external evidence JSON is missing")
    if not md_path or not md_path.exists():
        row_failures.append("required external evidence markdown is missing")
    for key in ("status", "evidence", "sha256"):
        if proof_row and proof_row.get(key) != validation.get(key):
            row_failures.append(f"proof row {key} does not match current evidence validation")
    if proof_row and proof_row.get("errors") != validation.get("errors"):
        row_failures.append("proof row errors do not match current evidence validation")

    return {
        "claim_id": claim_id,
        "title": requirement["title"],
        "json": requirement["path"],
        "json_exists": bool(evidence_path and evidence_path.exists()),
        "markdown": display_path(root, md_path) if md_path else None,
        "markdown_exists": bool(md_path and md_path.exists()),
        "proof_status": proof_row.get("status"),
        "validation_status": validation["status"],
        "proof_errors": proof_row.get("errors", []),
        "validation_errors": validation["errors"],
        "sha256": validation["sha256"],
        "failures": row_failures,
    }


def build_report(
    root: Path = ROOT,
    proof_path: Path = DEFAULT_PROOF,
    *,
    gap_audit_path: Path = DEFAULT_GAP_AUDIT,
    check_proof_consistency: bool = True,
    check_gap_audit_consistency: bool = True,
) -> dict[str, Any]:
    proof_runner = load_proof_runner(root)
    failures: list[str] = []
    if not proof_path.exists():
        return {
            "status": "FAIL",
            "inventory_status": STATUS_INCOMPLETE,
            "proof": display_path(root, proof_path),
            "rows": [],
            "failures": [f"missing proof report: {display_path(root, proof_path)}"],
            "claim_boundary": {
                "note": "External evidence inventory only; this report does not promote proof-gate claims.",
            },
        }

    proof = load_json(proof_path)
    if check_proof_consistency:
        proof_verifier = load_proof_verifier(root)
        proof_failures = proof_verifier.verify_proof(proof_path, root)
        failures.extend(f"proof verifier: {failure}" for failure in proof_failures)

    if hasattr(proof_runner, "external_requirement_contract"):
        expected_required = [
            proof_runner.external_requirement_contract(item)
            for item in proof_runner.EXTERNAL_REQUIREMENTS
        ]
    else:
        expected_required = [
            {
                "claim_id": item["claim_id"],
                "title": item["title"],
                "path": item["path"],
                "measurements": item["measurements"],
            }
            for item in proof_runner.EXTERNAL_REQUIREMENTS
        ]
    if proof.get("required_external_evidence") != expected_required:
        failures.append("proof required_external_evidence does not match proof-gate contract")

    proof_rows = row_by_claim(proof)
    rows = [
        build_row(root, proof_runner, proof_rows, requirement)
        for requirement in proof_runner.EXTERNAL_REQUIREMENTS
    ]
    for row in rows:
        failures.extend(f"{row['claim_id']}: {failure}" for failure in row["failures"])

    gap_audit_summary: dict[str, Any] = {
        "path": display_path(root, gap_audit_path),
        "status": "NOT_CHECKED",
        "replacement_required": [],
        "expected_replacement_required": [
            row["claim_id"]
            for row in rows
            if row["validation_status"] != "VERIFIED"
        ],
        "covered_replacement_required": [],
        "missing_replacement_rows": [],
        "contract_mismatches": [],
        "failures": [],
    }
    if check_gap_audit_consistency:
        if not gap_audit_path.exists():
            message = f"missing gap audit report: {display_path(root, gap_audit_path)}"
            failures.append(message)
            gap_audit_summary["status"] = "MISSING"
            gap_audit_summary["failures"] = [message]
        else:
            gap_verifier = load_gap_audit_verifier(root)
            gap_failures = gap_verifier.verify_audit(gap_audit_path, root)
            failures.extend(f"gap audit verifier: {failure}" for failure in gap_failures)
            gap_audit = load_json(gap_audit_path)
            observed_replacement = gap_audit.get("replacement_required", [])
            if not isinstance(observed_replacement, list):
                observed_replacement = []
            gap_audit_summary["replacement_required"] = observed_replacement
            if observed_replacement != gap_audit_summary["expected_replacement_required"]:
                failures.append("gap audit replacement_required does not match external inventory gaps")
            gap_rows = gap_rows_by_claim(gap_audit)
            for row in rows:
                claim_id = row["claim_id"]
                gap_row = gap_rows.get(claim_id)
                if row["validation_status"] == "VERIFIED":
                    continue
                if not gap_row:
                    gap_audit_summary["missing_replacement_rows"].append(claim_id)
                    continue
                contract = gap_row.get("replacement_contract")
                if (
                    isinstance(contract, dict)
                    and contract.get("destination") == row["json"]
                    and contract.get("required_status") == "VERIFIED"
                ):
                    gap_audit_summary["covered_replacement_required"].append(claim_id)
                else:
                    gap_audit_summary["contract_mismatches"].append(claim_id)
            for claim_id in gap_audit_summary["missing_replacement_rows"]:
                failures.append(f"{claim_id}: gap audit replacement row is missing")
            for claim_id in gap_audit_summary["contract_mismatches"]:
                failures.append(f"{claim_id}: gap audit replacement_contract does not match inventory row")
            gap_audit_summary["failures"] = gap_failures
            gap_audit_summary["status"] = "PASS" if (
                not gap_failures
                and not gap_audit_summary["missing_replacement_rows"]
                and not gap_audit_summary["contract_mismatches"]
                and observed_replacement == gap_audit_summary["expected_replacement_required"]
            ) else "FAIL"

    duplicate_claims = [
        claim_id
        for claim_id in proof_rows
        if sum(1 for row in proof.get("proof_rows", []) if isinstance(row, dict) and row.get("claim_id") == claim_id) > 1
    ]
    for claim_id in sorted(set(duplicate_claims)):
        failures.append(f"duplicate proof row: {claim_id}")

    all_verified = rows and all(row["validation_status"] == "VERIFIED" for row in rows)
    no_missing = all(row["validation_status"] != "MISSING" for row in rows)
    if failures:
        inventory_status = STATUS_INCOMPLETE
    elif all_verified:
        inventory_status = STATUS_ALL_VERIFIED
    elif no_missing:
        inventory_status = STATUS_COMPLETE_WITH_GAPS
    else:
        inventory_status = STATUS_INCOMPLETE

    return {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_inventory.v1",
        "status": "PASS" if not failures else "FAIL",
        "inventory_status": inventory_status,
        "proof": display_path(root, proof_path),
        "rows": rows,
        "failures": failures,
        "verified": [row["claim_id"] for row in rows if row["validation_status"] == "VERIFIED"],
        "invalid": [row["claim_id"] for row in rows if row["validation_status"] == "INVALID"],
        "missing": [row["claim_id"] for row in rows if row["validation_status"] == "MISSING"],
        "gap_audit": gap_audit_summary,
        "claim_boundary": {
            "note": "External evidence inventory only; this report does not promote proof-gate claims.",
            "proof_claim_boundary": proof.get("claim_boundary", {}),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse External Evidence Inventory",
        "",
        f"Status: `{report.get('status')}`",
        "",
        f"Inventory status: `{report.get('inventory_status')}`",
        "",
        f"Proof: `{report.get('proof')}`",
        "",
        "## Claim Boundary",
        "",
    ]
    claim_boundary = report.get("claim_boundary", {})
    proof_claim_boundary = (
        claim_boundary.get("proof_claim_boundary", {})
        if isinstance(claim_boundary, dict)
        else {}
    )
    if isinstance(proof_claim_boundary, dict):
        for key in sorted(proof_claim_boundary):
            lines.append(f"- {key}: `{proof_claim_boundary[key]}`")
    else:
        lines.append("- INVALID")

    lines.extend(["", "## Summary", ""])
    lines.append(f"- verified: `{', '.join(report.get('verified', [])) or 'none'}`")
    lines.append(f"- invalid: `{', '.join(report.get('invalid', [])) or 'none'}`")
    lines.append(f"- missing: `{', '.join(report.get('missing', [])) or 'none'}`")

    gap_audit = report.get("gap_audit", {})
    if isinstance(gap_audit, dict):
        lines.extend(["", "## Gap Audit", ""])
        lines.append(f"- status: `{gap_audit.get('status')}`")
        lines.append(
            "- replacement_required: "
            f"`{', '.join(gap_audit.get('replacement_required', [])) or 'none'}`"
        )
        lines.append(
            "- expected_replacement_required: "
            f"`{', '.join(gap_audit.get('expected_replacement_required', [])) or 'none'}`"
        )

    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Claim | JSON | Markdown | Proof Status | Validation Status | SHA256 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    rows = report.get("rows", [])
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                lines.append("| INVALID |  |  |  |  |  |")
                continue
            lines.append(
                "| "
                f"{row.get('claim_id')} | "
                f"`{row.get('json')}` | "
                f"`{row.get('markdown')}` | "
                f"`{row.get('proof_status')}` | "
                f"`{row.get('validation_status')}` | "
                f"`{row.get('sha256')}` |"
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
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-external-evidence-inventory-{stamp}"
    bundle_json = bundle_dir / "inventory.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "inventory_bundle_json": display_path(root, bundle_json),
        "inventory_bundle_md": display_path(root, bundle_md),
        "inventory_latest_json": display_path(root, output_json),
        "inventory_latest_md": display_path(root, output_md),
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


def verify_saved_report(
    report_path: Path,
    root: Path = ROOT,
    *,
    check_proof_consistency: bool = True,
    check_gap_audit_consistency: bool = True,
) -> list[str]:
    failures: list[str] = []
    if not report_path.exists():
        return [f"missing external evidence inventory report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"external evidence inventory report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load external evidence inventory report: {exc}"]

    if data.get("schema") != "x0tta6bl4.ghost_pulse.external_evidence_inventory.v1":
        failures.append(f"unexpected schema: {data.get('schema')}")

    proof_path = resolve_path(root, data.get("proof")) or DEFAULT_PROOF
    gap_audit = data.get("gap_audit", {})
    gap_path = (
        resolve_path(root, gap_audit.get("path"))
        if isinstance(gap_audit, dict)
        else DEFAULT_GAP_AUDIT
    )
    expected = build_report(
        root,
        proof_path,
        gap_audit_path=gap_path or DEFAULT_GAP_AUDIT,
        check_proof_consistency=check_proof_consistency,
        check_gap_audit_consistency=check_gap_audit_consistency,
    )
    if stable_subset(data) != stable_subset(expected):
        failures.append("external evidence inventory stable fields do not match current proof/gap state")

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("inventory_latest_json"))
    latest_md = resolve_path(root, artifacts.get("inventory_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("inventory_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("inventory_bundle_md"))

    if latest_json != report_path:
        failures.append("artifacts.inventory_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("inventory latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("inventory latest markdown does not match bundle markdown")

    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("inventory latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("inventory bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    parser.add_argument("--gap-audit", type=Path, default=DEFAULT_GAP_AUDIT)
    parser.add_argument("--report", type=Path, help="Saved inventory report to verify read-only.")
    parser.add_argument("--write-report", action="store_true", help="Write latest and bundle inventory reports.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument(
        "--skip-proof-consistency",
        action="store_true",
        help="Skip proof self-verifier recursion while still comparing inventory rows to the saved proof.",
    )
    parser.add_argument("--skip-gap-audit-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-all-verified", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        failures = verify_saved_report(
            report_path,
            root,
            check_proof_consistency=not args.skip_proof_consistency,
            check_gap_audit_consistency=not args.skip_gap_audit_check,
        )
        try:
            saved = load_json(report_path) if report_path.exists() and report_path.is_file() else {}
        except Exception:
            saved = {}
        result = {
            "status": "PASS" if not failures else "FAIL",
            "inventory_status": saved.get("inventory_status"),
            "report": display_path(root, report_path),
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse external evidence inventory report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse external evidence inventory report is current")
            print(f"report={result['report']}")
            print(f"inventory_status={result['inventory_status']}")
        if failures:
            return 1
        if args.require_all_verified and saved.get("inventory_status") != STATUS_ALL_VERIFIED:
            return 1
        return 0

    proof_path = args.proof if args.proof.is_absolute() else root / args.proof
    gap_audit_path = args.gap_audit if args.gap_audit.is_absolute() else root / args.gap_audit
    report = build_report(
        root=root,
        proof_path=proof_path,
        gap_audit_path=gap_audit_path,
        check_gap_audit_consistency=not args.skip_gap_audit_check,
    )
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "PASS":
        print("PASS: x0tta6bl4_pulse external evidence inventory files are present and consistent")
        print(f"inventory_status={report['inventory_status']}")
        print(f"proof={report['proof']}")
    else:
        print("FAIL: x0tta6bl4_pulse external evidence inventory is incomplete")
        for failure in report["failures"]:
            print(f"- {failure}")
    if report["status"] != "PASS":
        return 1
    if args.require_all_verified and report["inventory_status"] != STATUS_ALL_VERIFIED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
