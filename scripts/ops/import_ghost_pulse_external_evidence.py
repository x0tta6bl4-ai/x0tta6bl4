#!/usr/bin/env python3
"""Import validated x0tta6bl4_pulse external evidence.

The default mode is read-only: validate a candidate evidence JSON against the
same proof-gate contract used for the target claim. Use --write to replace the
claim's latest evidence file, and only when validation reports READY_TO_IMPORT.
The importer never changes proof-gate code or claim boundaries directly.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
INCOMING_ROOT = Path("docs") / "verification" / "incoming"

SCHEMA = "x0tta6bl4.ghost_pulse.external_evidence_import.v1"
DECISION_READY = "READY_TO_IMPORT"
DECISION_REJECTED = "REJECTED"
DPI_LAB_CLAIM_ID = "dpi_lab"
DPI_PROXY_VALIDATOR = Path("scripts") / "ops" / "verify_external_dpi_proxy_reachability_evidence.py"
DPI_PROXY_CONTRACT = Path("docs") / "verification" / "EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
REPLACEMENT_CANDIDATES_REPORT = Path("docs") / "verification" / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
EXTERNAL_EVIDENCE_INTAKE_REPORT = Path("docs") / "verification" / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
REPLACEMENT_CANDIDATES_VERIFIER = Path("scripts") / "ops" / "verify_ghost_pulse_replacement_candidates.py"
EXTERNAL_EVIDENCE_INTAKE_VERIFIER = Path("scripts") / "ops" / "verify_ghost_pulse_external_evidence_intake.py"


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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
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


def expected_candidate_path(root: Path, claim_id: str) -> Path:
    return root / INCOMING_ROOT / f"{claim_id}.json"


def expected_candidate_display_path(claim_id: str) -> str:
    return str(INCOMING_ROOT / f"{claim_id}.json")


def incoming_root_path(root: Path) -> Path:
    return root / INCOMING_ROOT


def path_symlink_component(root: Path, rel_path: Path) -> str | None:
    current = root
    for part in rel_path.parts:
        current = current / part
        if current.is_symlink():
            return display_path(root, current)
    return None


def incoming_root_state(root: Path) -> dict[str, Any]:
    path = incoming_root_path(root)
    symlink_component = path_symlink_component(root, INCOMING_ROOT)
    return {
        "path": str(INCOMING_ROOT),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_symlink": path.is_symlink(),
        "has_symlink_component": symlink_component is not None,
        "symlink_component": symlink_component,
    }


def incoming_root_errors(root: Path) -> list[str]:
    state = incoming_root_state(root)
    if state["is_symlink"]:
        return [f"incoming evidence directory must not be a symlink: {state['path']}"]
    if state["has_symlink_component"]:
        return [
            "incoming evidence directory must not include symlink components: "
            f"{state['symlink_component']}"
        ]
    if state["exists"] and not state["is_dir"]:
        return [f"incoming evidence path is not a directory: {state['path']}"]
    return []


def candidate_path_errors(root: Path, claim_id: str, candidate_path: Path) -> list[str]:
    expected = expected_candidate_path(root, claim_id)
    errors = incoming_root_errors(root)
    if candidate_path.absolute() != expected.absolute():
        errors.append(
            "candidate evidence must be staged at "
            f"{expected_candidate_display_path(claim_id)}"
        )
    if candidate_path.is_symlink():
        errors.append(f"candidate evidence must not be a symlink: {display_path(root, candidate_path)}")
    return errors


def load_proof_gate(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_proof_gate_for_external_import", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_dpi_proxy_validator(root: Path):
    path = root / DPI_PROXY_VALIDATOR
    if not path.exists():
        path = ROOT / DPI_PROXY_VALIDATOR
    spec = importlib.util.spec_from_file_location("verify_external_dpi_proxy_for_external_import", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_replacement_candidates_verifier(root: Path):
    path = root / REPLACEMENT_CANDIDATES_VERIFIER
    if not path.exists():
        path = ROOT / REPLACEMENT_CANDIDATES_VERIFIER
    spec = importlib.util.spec_from_file_location(
        "verify_ghost_pulse_replacement_candidates_for_external_import_write",
        path,
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_external_evidence_intake_verifier(root: Path):
    path = root / EXTERNAL_EVIDENCE_INTAKE_VERIFIER
    if not path.exists():
        path = ROOT / EXTERNAL_EVIDENCE_INTAKE_VERIFIER
    spec = importlib.util.spec_from_file_location(
        "verify_ghost_pulse_external_evidence_intake_for_external_import_write",
        path,
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def dpi_proxy_contract_path(root: Path) -> Path:
    path = root / DPI_PROXY_CONTRACT
    return path if path.exists() else ROOT / DPI_PROXY_CONTRACT


def requirement_by_claim(proof) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}


def validate_candidate(root: Path, proof, requirement: dict[str, Any], candidate_path: Path) -> dict[str, Any]:
    candidate_requirement = dict(requirement)
    candidate_requirement["path"] = candidate_path if candidate_path.is_absolute() else display_path(root, candidate_path)
    return proof.validate_external_evidence(root, candidate_requirement)


def validate_dpi_proxy_candidate(root: Path, candidate_path: Path) -> dict[str, Any]:
    validator = load_dpi_proxy_validator(root)
    return validator.build_report(
        root=root,
        candidate=candidate_path,
        contract_path=dpi_proxy_contract_path(root),
    )


def requirement_contract(proof, requirement: dict[str, Any]) -> dict[str, Any]:
    if hasattr(proof, "external_requirement_contract"):
        return proof.external_requirement_contract(requirement)
    return {
        "claim_id": requirement["claim_id"],
        "title": requirement["title"],
        "path": requirement["path"],
        "measurements": requirement["measurements"],
    }


def render_evidence_markdown(payload: dict[str, Any], validation: dict[str, Any]) -> str:
    claim_id = payload.get("claim_id", validation.get("claim_id", "unknown"))
    lines = [
        f"# x0tta6bl4_pulse {claim_id} Imported External Evidence",
        "",
        f"Observed at: `{payload.get('observed_at_utc', '')}`",
        "",
        f"Validation status: `{validation['status']}`",
        "",
        "## Measurements",
        "",
    ]
    measurements = payload.get("measurements", {})
    if isinstance(measurements, dict) and measurements:
        for key in sorted(measurements):
            lines.append(f"- {key}: `{measurements[key]}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Validation Errors", ""])
    if validation["errors"]:
        lines.extend(f"- {error}" for error in validation["errors"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_input_errors(
    root: Path,
    candidate_path: Path,
    destination_path: Path,
    candidate_md: Path | None = None,
) -> list[str]:
    errors = incoming_root_errors(root)
    if not candidate_path.exists():
        errors.append(f"candidate evidence is missing: {display_path(root, candidate_path)}")
    elif not candidate_path.is_file():
        errors.append(f"candidate evidence is not a regular file: {display_path(root, candidate_path)}")
    elif candidate_path.is_symlink():
        errors.append(f"candidate evidence must not be a symlink: {display_path(root, candidate_path)}")
    if destination_path.exists() and not destination_path.is_file():
        errors.append(f"destination is not a regular file: {display_path(root, destination_path)}")
    if candidate_md is not None:
        if not candidate_md.exists():
            errors.append(f"candidate markdown is missing: {display_path(root, candidate_md)}")
        elif not candidate_md.is_file():
            errors.append(f"candidate markdown is not a regular file: {display_path(root, candidate_md)}")
    return errors


def external_dpi_intake_claim_gate(
    *,
    claim_id: str,
    decision: str,
    written: bool,
    failures: list[str],
    external_dpi_proxy_validation: dict[str, Any] | None,
    write_freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ready = decision == DECISION_READY
    dpi_ready = (
        isinstance(external_dpi_proxy_validation, dict)
        and external_dpi_proxy_validation.get("decision") == DECISION_READY
    )
    write_fresh = isinstance(write_freshness, dict) and write_freshness.get("fresh") is True
    return {
        "schema": "x0tta6bl4.external_dpi_intake.claim_gate.v1",
        "surface": f"ghost_pulse_external_import.{claim_id}",
        "claim_boundary": (
            "Ghost Pulse external evidence import preflight/copy metadata. "
            "READY_TO_IMPORT means the candidate passed import validation; "
            "written=true means the local latest evidence file was replaced. "
            "Neither state runs the proof gate or proves production readiness, "
            "durable censorship bypass, customer traffic, or anonymity."
        ),
        "local_import_preflight_claim_allowed": True,
        "candidate_ready_to_import_claim_allowed": ready,
        "external_dpi_proxy_validator_ready_claim_allowed": bool(dpi_ready),
        "local_latest_evidence_copy_claim_allowed": bool(written),
        "saved_replacement_preflight_current_claim_allowed": bool(
            isinstance(write_freshness, dict)
            and write_freshness.get("replacement_report_current") is True
        ),
        "saved_intake_report_current_claim_allowed": bool(
            isinstance(write_freshness, dict)
            and write_freshness.get("intake_report_current") is True
        ),
        "write_freshness_claim_allowed": bool(write_fresh),
        "validation_failures_present": bool(failures),
        "proof_gate_dpi_bypass_claim_allowed": False,
        "durable_censorship_bypass_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "anonymity_claim_allowed": False,
        "provider_health_claim_allowed": False,
        "payment_or_token_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }


def _row_by_claim(rows: Any, claim_id: str) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def expected_write_import_command(claim_id: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        claim_id,
        "--candidate",
        expected_candidate_display_path(claim_id),
        "--write",
        "--json",
    ]


def _safe_load_saved_report(root: Path, rel_path: Path) -> dict[str, Any]:
    path = root / rel_path
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def write_freshness_context(root: Path, claim_id: str, candidate_path: Path) -> dict[str, Any]:
    expected_candidate = expected_candidate_display_path(claim_id)
    candidate_sha = sha256_file(candidate_path)
    replacement_path = root / REPLACEMENT_CANDIDATES_REPORT
    intake_path = root / EXTERNAL_EVIDENCE_INTAKE_REPORT
    failures: list[str] = []

    replacement_failures: list[str]
    intake_failures: list[str]
    try:
        replacement = load_replacement_candidates_verifier(root)
        replacement_failures = replacement.verify_saved_report(replacement_path, root)
    except Exception as exc:
        replacement_failures = [f"replacement candidates report verification failed: {type(exc).__name__}"]
    try:
        intake = load_external_evidence_intake_verifier(root)
        intake_failures = intake.verify_saved_report(intake_path, root)
    except Exception as exc:
        intake_failures = [f"external evidence intake report verification failed: {type(exc).__name__}"]

    failures.extend(f"replacement preflight: {failure}" for failure in replacement_failures)
    failures.extend(f"external evidence intake: {failure}" for failure in intake_failures)

    replacement_report = _safe_load_saved_report(root, REPLACEMENT_CANDIDATES_REPORT)
    intake_report = _safe_load_saved_report(root, EXTERNAL_EVIDENCE_INTAKE_REPORT)
    replacement_row = _row_by_claim(replacement_report.get("rows"), claim_id)
    intake_task = _row_by_claim(intake_report.get("collection_tasks"), claim_id)

    if claim_id not in set(replacement_report.get("ready") or []):
        failures.append(f"replacement preflight: {claim_id} must be listed in ready")
    if claim_id not in set(intake_report.get("ready") or []):
        failures.append(f"external evidence intake: {claim_id} must be listed in ready")
    if replacement_row.get("candidate") != expected_candidate:
        failures.append(f"replacement preflight: {claim_id} candidate must be {expected_candidate}")
    if intake_task.get("candidate") != expected_candidate:
        failures.append(f"external evidence intake: {claim_id} candidate must be {expected_candidate}")
    if replacement_row.get("ready_to_import") is not True:
        failures.append(f"replacement preflight: {claim_id} row must be READY_TO_IMPORT")
    if intake_task.get("status") != DECISION_READY or intake_task.get("ready_to_import") is not True:
        failures.append(f"external evidence intake: {claim_id} task must be READY_TO_IMPORT")
    if not candidate_sha:
        failures.append(f"write freshness: {claim_id} candidate sha256 must be available")
    elif replacement_row.get("candidate_sha256") != candidate_sha:
        failures.append(f"replacement preflight: {claim_id} candidate sha256 must match current file")
    elif intake_task.get("candidate_sha256") != candidate_sha:
        failures.append(f"external evidence intake: {claim_id} candidate sha256 must match current file")

    expected_write = expected_write_import_command(claim_id)
    current_write_commands = intake_report.get("currently_ready_write_commands")
    if not isinstance(current_write_commands, list) or expected_write not in current_write_commands:
        failures.append(f"external evidence intake: {claim_id} write command must be currently ready")

    return {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_import.write_freshness.v1",
        "claim_id": claim_id,
        "replacement_report": display_path(root, replacement_path),
        "replacement_report_current": not replacement_failures,
        "intake_report": display_path(root, intake_path),
        "intake_report_current": not intake_failures,
        "expected_candidate": expected_candidate,
        "candidate_sha256": candidate_sha,
        "claim_ready_in_replacement_report": claim_id in set(replacement_report.get("ready") or []),
        "claim_ready_in_intake_report": claim_id in set(intake_report.get("ready") or []),
        "write_command_currently_ready": (
            isinstance(current_write_commands, list)
            and expected_write in current_write_commands
        ),
        "failures": failures,
        "fresh": not failures,
    }


def write_freshness_errors(report: dict[str, Any]) -> list[str]:
    freshness = report.get("write_freshness")
    if not isinstance(freshness, dict):
        return ["write freshness metadata is missing"]
    if freshness.get("fresh") is True:
        return []
    failures = freshness.get("failures")
    if isinstance(failures, list) and failures:
        return [str(failure) for failure in failures]
    return ["write freshness gate is not clear"]


def build_report(root: Path, claim_id: str, candidate: Path, *, write_requested: bool = False) -> dict[str, Any]:
    proof = load_proof_gate(root)
    requirements = requirement_by_claim(proof)
    observed_at = utc_now()
    candidate_path = candidate if candidate.is_absolute() else root / candidate
    incoming_state = incoming_root_state(root)
    failures: list[str] = []
    validation: dict[str, Any] | None = None
    destination: Path | None = None
    current_sha: str | None = None
    candidate_sha: str | None = None
    contract: dict[str, Any] | None = None
    destination_validation_before: dict[str, Any] | None = None
    external_dpi_proxy_validation: dict[str, Any] | None = None
    write_freshness: dict[str, Any] | None = None

    requirement = requirements.get(claim_id)
    if not requirement:
        failures.append(f"unknown claim: {claim_id}")
    else:
        candidate_errors = candidate_path_errors(root, claim_id, candidate_path)
        failures.extend(candidate_errors)
        if not candidate_errors:
            if not candidate_path.exists():
                failures.append(f"candidate evidence is missing: {display_path(root, candidate_path)}")
            elif not candidate_path.is_file():
                failures.append(f"candidate evidence is not a regular file: {display_path(root, candidate_path)}")
            else:
                candidate_sha = proof.sha256_file(candidate_path)

    if requirement and failures:
        destination = resolve_path(root, requirement["path"])
        contract = requirement_contract(proof, requirement)
        destination_validation_before = proof.validate_external_evidence(root, requirement)
    elif requirement:
        destination = resolve_path(root, requirement["path"])
        current_sha = proof.sha256_file(destination) if destination else None
        contract = requirement_contract(proof, requirement)
        destination_validation_before = proof.validate_external_evidence(root, requirement)
        validation = validate_candidate(root, proof, requirement, candidate_path)
        if validation["status"] != "VERIFIED":
            failures.extend(f"{claim_id}: {error}" for error in validation["errors"])
        if claim_id == DPI_LAB_CLAIM_ID:
            external_dpi_proxy_validation = validate_dpi_proxy_candidate(root, candidate_path)
            if external_dpi_proxy_validation["decision"] != DECISION_READY:
                dpi_failures = external_dpi_proxy_validation.get("failures") or [
                    f"decision must be {DECISION_READY}"
                ]
                failures.extend(
                    f"{claim_id}: external DPI/proxy validator: {failure}"
                    for failure in dpi_failures
                )

    if not failures and validation and validation["status"] == "VERIFIED" and write_requested:
        write_freshness = write_freshness_context(root, claim_id, candidate_path)
        if write_freshness.get("fresh") is not True:
            failures.extend(
                f"write freshness: {failure}"
                for failure in write_freshness.get("failures", [])
            )

    decision = DECISION_READY if not failures and validation and validation["status"] == "VERIFIED" else DECISION_REJECTED
    written = False
    return {
        "schema": SCHEMA,
        "timestamp_utc": observed_at,
        "decision": decision,
        "claim_id": claim_id,
        "candidate": display_path(root, candidate_path),
        "incoming_root": incoming_state,
        "candidate_exists": candidate_path.exists(),
        "candidate_is_file": candidate_path.is_file(),
        "candidate_is_symlink": candidate_path.is_symlink(),
        "candidate_sha256": candidate_sha,
        "destination": display_path(root, destination) if destination else None,
        "destination_sha256_before": current_sha,
        "destination_validation_before": destination_validation_before,
        "requirement_contract": contract,
        "write_requested": write_requested,
        "written": written,
        "failures": failures,
        "validation": validation,
        "external_dpi_proxy_validation": external_dpi_proxy_validation,
        "write_freshness": write_freshness,
        "claim_boundary": {
            "note": "Import validation/copy only; proof-gate claim boundaries are changed only by a later proof-gate run over real evidence.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
        "external_dpi_intake_claim_gate": external_dpi_intake_claim_gate(
            claim_id=claim_id,
            decision=decision,
            written=written,
            failures=failures,
            external_dpi_proxy_validation=external_dpi_proxy_validation,
            write_freshness=write_freshness,
        ),
    }


def write_import_outputs(
    root: Path,
    report: dict[str, Any],
    candidate_path: Path,
    destination_path: Path,
    candidate_md: Path | None = None,
) -> dict[str, Path]:
    if report.get("decision") != DECISION_READY:
        raise ValueError("report decision must be READY_TO_IMPORT before write")
    freshness_errors = write_freshness_errors(report)
    if freshness_errors:
        raise ValueError("write freshness gate is not clear: " + "; ".join(freshness_errors))
    errors = write_input_errors(root, candidate_path, destination_path, candidate_md)
    if errors:
        raise ValueError("; ".join(errors))

    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-external-evidence-import-{stamp}"
    bundle_report = bundle_dir / "import-report.json"
    bundle_candidate = bundle_dir / "candidate-evidence.json"
    bundle_previous = bundle_dir / "previous-latest.json"
    destination_md = destination_path.with_suffix(".md")

    bundle_dir.mkdir(parents=True, exist_ok=True)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.exists():
        shutil.copyfile(destination_path, bundle_previous)
    shutil.copyfile(candidate_path, bundle_candidate)
    shutil.copyfile(candidate_path, destination_path)

    if candidate_md and candidate_md.exists():
        shutil.copyfile(candidate_md, destination_md)
    else:
        payload = load_json(candidate_path)
        destination_md.write_text(render_evidence_markdown(payload, report["validation"]), encoding="utf-8")

    report["written"] = True
    report["external_dpi_intake_claim_gate"] = external_dpi_intake_claim_gate(
        claim_id=str(report.get("claim_id", "unknown")),
        decision=str(report.get("decision", DECISION_REJECTED)),
        written=True,
        failures=list(report.get("failures") or []),
        external_dpi_proxy_validation=report.get("external_dpi_proxy_validation"),
        write_freshness=report.get("write_freshness"),
    )
    proof = load_proof_gate(root)
    requirement = requirement_by_claim(proof).get(report["claim_id"])
    report["destination_sha256_after"] = proof.sha256_file(destination_path)
    report["destination_validation_after"] = (
        proof.validate_external_evidence(root, requirement)
        if requirement
        else None
    )
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "import_report": display_path(root, bundle_report),
        "candidate_evidence": display_path(root, bundle_candidate),
        "previous_latest": display_path(root, bundle_previous) if bundle_previous.exists() else None,
        "destination_json": display_path(root, destination_path),
        "destination_md": display_path(root, destination_md),
    }
    bundle_report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "bundle_dir": bundle_dir,
        "bundle_report": bundle_report,
        "bundle_candidate": bundle_candidate,
        "bundle_previous": bundle_previous,
        "destination_json": destination_path,
        "destination_md": destination_md,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--claim", required=True, help="Target claim id.")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate evidence JSON to import.")
    parser.add_argument("--candidate-md", type=Path, help="Optional candidate markdown summary to copy.")
    parser.add_argument("--write", action="store_true", help="Replace the latest evidence file if validation passes.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    candidate = args.candidate if args.candidate.is_absolute() else root / args.candidate
    report = build_report(root, args.claim, candidate, write_requested=args.write)
    if args.write and report["decision"] == DECISION_READY:
        destination = resolve_path(root, report["destination"])
        if not destination:
            report["decision"] = DECISION_REJECTED
            report["failures"].append("destination could not be resolved")
        else:
            candidate_md = None
            if args.candidate_md:
                candidate_md = args.candidate_md if args.candidate_md.is_absolute() else root / args.candidate_md
            write_errors = write_input_errors(root, candidate, destination, candidate_md)
            if write_errors:
                report["decision"] = DECISION_REJECTED
                report["failures"].extend(write_errors)
            else:
                write_import_outputs(root, report, candidate, destination, candidate_md)
    elif args.write:
        report["failures"].append("write requested but candidate is not READY_TO_IMPORT")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "decision": report["decision"],
                    "claim_id": report["claim_id"],
                    "candidate": report["candidate"],
                    "destination": report["destination"],
                    "written": report["written"],
                    "failures": report["failures"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    if args.require_ready and report["decision"] != DECISION_READY:
        return 1
    if args.write and not report["written"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
