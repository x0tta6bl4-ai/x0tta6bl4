#!/usr/bin/env python3
"""Import validated x0tta6bl4_pulse external evidence.

The default mode is read-only: validate a candidate evidence JSON against the
same proof-gate contract used for the target claim. Use --write to replace the
claim's latest evidence file, and only when validation reports READY_TO_IMPORT.
The importer never changes proof-gate code or claim boundaries directly.
"""

from __future__ import annotations

import argparse
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


def requirement_by_claim(proof) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}


def validate_candidate(root: Path, proof, requirement: dict[str, Any], candidate_path: Path) -> dict[str, Any]:
    candidate_requirement = dict(requirement)
    candidate_requirement["path"] = candidate_path if candidate_path.is_absolute() else display_path(root, candidate_path)
    return proof.validate_external_evidence(root, candidate_requirement)


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

    decision = DECISION_READY if not failures and validation and validation["status"] == "VERIFIED" else DECISION_REJECTED
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
        "written": False,
        "failures": failures,
        "validation": validation,
        "claim_boundary": {
            "note": "Import validation/copy only; proof-gate claim boundaries are changed only by a later proof-gate run over real evidence.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }


def write_import_outputs(
    root: Path,
    report: dict[str, Any],
    candidate_path: Path,
    destination_path: Path,
    candidate_md: Path | None = None,
) -> dict[str, Path]:
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
