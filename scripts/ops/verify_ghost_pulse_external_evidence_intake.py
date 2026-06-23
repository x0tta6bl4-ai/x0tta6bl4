#!/usr/bin/env python3
"""Verify x0tta6bl4_pulse external evidence intake readiness.

The default mode is read-only. It verifies the saved replacement-candidate
preflight report, records which incoming evidence files are missing or ready,
and preserves the exact post-import refresh commands. It never imports evidence
or promotes proof-gate claim boundaries.
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
DEFAULT_PREFLIGHT = VERIFY_ROOT / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
DEFAULT_EXAMPLES_MANIFEST = Path("docs") / "verification" / "incoming" / "examples" / "manifest.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.external_evidence_intake.v1"
INCOMING_EXAMPLE_MANIFEST_SCHEMA = "x0tta6bl4.ghost_pulse.incoming_example_manifest.v1"
INCOMING_EXAMPLE_STATUS = "EXAMPLE_ONLY_NOT_EVIDENCE"
INCOMING_EXAMPLE_MODE = "INCOMING_CANDIDATE_EXAMPLE_NOT_EVIDENCE"
COLLECTION_TASK_STATUS = "WAITING_FOR_REAL_EXTERNAL_EVIDENCE"
COLLECTION_TASK_READY = "READY_TO_IMPORT"
COLLECTION_TASK_MISSING = "MISSING_CANDIDATE"
COLLECTION_TASK_NON_FILE = "CANDIDATE_NOT_FILE"
COLLECTION_TASK_UNSAFE = "UNSAFE_CANDIDATE_PATH"
COLLECTION_TASK_REJECTED = "CANDIDATE_REJECTED"
COLLECTION_TASK_ACTION_REQUIRED = "ACTION_REQUIRED"
DECISION_ACTION_REQUIRED = "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED"
DECISION_READY_NOT_WRITTEN = "EXTERNAL_EVIDENCE_INTAKE_READY_NOT_WRITTEN"
DECISION_PREFLIGHT_INVALID = "EXTERNAL_EVIDENCE_INTAKE_PREFLIGHT_INVALID"
STABLE_REPORT_KEYS = (
    "schema",
    "status",
    "decision",
    "preflight",
    "preflight_sha256",
    "preflight_verification",
    "incoming_examples_manifest",
    "incoming_examples_manifest_sha256",
    "incoming_examples_verification",
    "replacement_required",
    "ready",
    "not_ready",
    "missing_candidate_paths",
    "non_file_candidate_paths",
    "unsafe_candidate_paths",
    "read_only_preflight_commands",
    "currently_ready_write_commands",
    "write_commands_after_ready",
    "post_import_refresh_commands",
    "collection_tasks",
    "collection_tasks_verification",
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


def load_replacement_verifier(root: Path):
    path = root / "scripts/ops/verify_ghost_pulse_replacement_candidates.py"
    if not path.exists():
        path = ROOT / "scripts/ops/verify_ghost_pulse_replacement_candidates.py"
    spec = importlib.util.spec_from_file_location(
        "verify_ghost_pulse_replacement_candidates_for_intake",
        path,
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalized_plan(preflight: dict[str, Any]) -> dict[str, Any]:
    plan = preflight.get("candidate_intake_plan")
    return plan if isinstance(plan, dict) else {}


def verify_claim_boundary_false(value: Any, failures: list[str], prefix: str) -> None:
    if not isinstance(value, dict):
        failures.append(f"{prefix} claim_boundary must be an object")
        return
    for key in ("stealth_verified", "whitelist_verified", "kernel_attach_verified", "production_ready"):
        if value.get(key) is not False:
            failures.append(f"{prefix} claim_boundary.{key} must be false")


def expected_read_only_import_command(claim_id: str, candidate: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        claim_id,
        "--candidate",
        candidate,
        "--require-ready",
        "--json",
    ]


def expected_write_import_command(claim_id: str, candidate: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        claim_id,
        "--candidate",
        candidate,
        "--write",
        "--json",
    ]


def expected_acceptance_commands(claim_id: str) -> list[list[str]]:
    commands = [
        [
            "python3",
            "scripts/ops/verify_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--require-pass",
            "--json",
        ]
    ]
    if claim_id == "production_readiness":
        commands.append(
            [
                "python3",
                "scripts/ops/verify_ghost_pulse_proof_gate.py",
                "--require-all-proven",
                "--json",
            ]
        )
    return commands


def verify_incoming_examples_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    failures: list[str] = []
    examples: list[dict[str, Any]] = []
    collection_tasks: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    payloads_by_claim: dict[str, dict[str, Any]] = {}

    if not manifest_path.exists():
        failures.append(f"missing incoming examples manifest: {display_path(root, manifest_path)}")
    elif not manifest_path.is_file():
        failures.append(f"incoming examples manifest is not a regular file: {display_path(root, manifest_path)}")
    elif manifest_path.is_symlink():
        failures.append(f"incoming examples manifest must not be a symlink: {display_path(root, manifest_path)}")
    else:
        try:
            manifest = load_json(manifest_path)
        except Exception as exc:
            failures.append(f"could not load incoming examples manifest: {exc}")

    if manifest:
        if manifest.get("schema") != INCOMING_EXAMPLE_MANIFEST_SCHEMA:
            failures.append(f"incoming examples manifest schema is unexpected: {manifest.get('schema')}")
        if manifest.get("status") != INCOMING_EXAMPLE_STATUS:
            failures.append(f"incoming examples manifest status must be {INCOMING_EXAMPLE_STATUS}")
        verify_claim_boundary_false(manifest.get("claim_boundary"), failures, "incoming examples manifest")
        intake_gate = manifest.get("intake_gate")
        if not isinstance(intake_gate, dict):
            failures.append("incoming examples manifest intake_gate must be an object")
        else:
            if intake_gate.get("expected_current_decision_with_examples_only") != DECISION_ACTION_REQUIRED:
                failures.append("incoming examples manifest intake_gate expected decision is not fail-closed")
            commands = intake_gate.get("post_import_refresh_commands")
            if not isinstance(commands, list) or not commands:
                failures.append("incoming examples manifest intake_gate post_import_refresh_commands must be non-empty")
            elif [
                "python3",
                "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
                "--write-report",
                "--json",
            ] not in commands:
                failures.append("incoming examples manifest refresh commands must include intake report refresh")

        rows = manifest.get("examples")
        if not isinstance(rows, list) or not rows:
            failures.append("incoming examples manifest examples must be a non-empty list")
            rows = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                failures.append(f"incoming examples manifest row {index} must be an object")
                continue
            claim_id = row.get("claim_id")
            example_value = row.get("example")
            candidate_value = row.get("candidate")
            if not isinstance(claim_id, str) or not claim_id:
                failures.append(f"incoming examples manifest row {index} has invalid claim_id")
                continue
            expected_candidate = f"docs/verification/incoming/{claim_id}.json"
            expected_example = f"docs/verification/incoming/examples/{claim_id}.example.json"
            if candidate_value != expected_candidate:
                failures.append(f"{claim_id}: incoming example candidate path must be {expected_candidate}")
            if example_value != expected_example:
                failures.append(f"{claim_id}: incoming example path must be {expected_example}")
            example_path = resolve_path(root, example_value)
            if not example_path or not example_path.exists():
                failures.append(f"{claim_id}: incoming example file is missing")
                continue
            if not example_path.is_file():
                failures.append(f"{claim_id}: incoming example is not a regular file")
                continue
            if example_path.is_symlink():
                failures.append(f"{claim_id}: incoming example must not be a symlink")
                continue
            if row.get("sha256") != sha256_file(example_path):
                failures.append(f"{claim_id}: incoming example sha256 mismatch")
            try:
                payload = load_json(example_path)
            except Exception as exc:
                failures.append(f"{claim_id}: incoming example could not be loaded: {exc}")
                continue
            if payload.get("schema") != "x0tta6bl4.ghost_pulse.claim_evidence.v1":
                failures.append(f"{claim_id}: incoming example schema is unexpected")
            if payload.get("claim_id") != claim_id:
                failures.append(f"{claim_id}: incoming example claim_id mismatch")
            if payload.get("status") == "VERIFIED":
                failures.append(f"{claim_id}: incoming example must not be VERIFIED")
            if payload.get("template") is not True:
                failures.append(f"{claim_id}: incoming example template must be true")
            if payload.get("simulated") is not False:
                failures.append(f"{claim_id}: incoming example simulated must be false")
            if payload.get("dry_run") is not False:
                failures.append(f"{claim_id}: incoming example dry_run must be false")
            if payload.get("mode") != INCOMING_EXAMPLE_MODE:
                failures.append(f"{claim_id}: incoming example mode must be {INCOMING_EXAMPLE_MODE}")
            if payload.get("candidate_destination") != expected_candidate:
                failures.append(f"{claim_id}: incoming example candidate_destination mismatch")
            if not payload.get("failures"):
                failures.append(f"{claim_id}: incoming example failures must explain rejection")
            payloads_by_claim[claim_id] = payload
            examples.append(
                {
                    "claim_id": claim_id,
                    "example": display_path(root, example_path),
                    "candidate": candidate_value,
                    "sha256": sha256_file(example_path),
                    "status": payload.get("status"),
                    "template": payload.get("template"),
                    "mode": payload.get("mode"),
                }
            )
        tasks = manifest.get("collection_tasks")
        if not isinstance(tasks, list) or not tasks:
            failures.append("incoming examples manifest collection_tasks must be a non-empty list")
            tasks = []
        if [
            task.get("claim_id")
            for task in tasks
            if isinstance(task, dict)
        ] != [
            row.get("claim_id")
            for row in rows
            if isinstance(row, dict)
        ]:
            failures.append("incoming examples manifest collection_tasks must match example claim order")
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                failures.append(f"incoming examples manifest collection task {index} must be an object")
                continue
            claim_id = task.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id:
                failures.append(f"incoming examples manifest collection task {index} has invalid claim_id")
                continue
            expected_candidate = f"docs/verification/incoming/{claim_id}.json"
            expected_example = f"docs/verification/incoming/examples/{claim_id}.example.json"
            if task.get("status") != COLLECTION_TASK_STATUS:
                failures.append(f"{claim_id}: collection task status must be {COLLECTION_TASK_STATUS}")
            if task.get("candidate") != expected_candidate:
                failures.append(f"{claim_id}: collection task candidate path must be {expected_candidate}")
            if task.get("example") != expected_example:
                failures.append(f"{claim_id}: collection task example path must be {expected_example}")
            if task.get("artifact_root") != f"docs/verification/incoming/artifacts/{claim_id}":
                failures.append(f"{claim_id}: collection task artifact_root mismatch")
            if task.get("read_only_import_command") != expected_read_only_import_command(claim_id, expected_candidate):
                failures.append(f"{claim_id}: collection task read_only_import_command mismatch")
            if task.get("write_import_command") != expected_write_import_command(claim_id, expected_candidate):
                failures.append(f"{claim_id}: collection task write_import_command mismatch")
            if task.get("acceptance_commands") != expected_acceptance_commands(claim_id):
                failures.append(f"{claim_id}: collection task acceptance_commands mismatch")
            payload = payloads_by_claim.get(claim_id, {})
            contract = payload.get("requirement_contract") if isinstance(payload, dict) else {}
            if not isinstance(contract, dict):
                contract = {}
            if task.get("required_measurements") != contract.get("measurements", {}):
                failures.append(f"{claim_id}: collection task required_measurements mismatch")
            if task.get("required_artifact_roles") != contract.get("required_artifact_roles", []):
                failures.append(f"{claim_id}: collection task required_artifact_roles mismatch")
            if task.get("required_commands") != contract.get("required_commands", []):
                failures.append(f"{claim_id}: collection task required_commands mismatch")
            if task.get("required_references") != contract.get("required_references", []):
                failures.append(f"{claim_id}: collection task required_references mismatch")
            collection_tasks.append(
                {
                    "claim_id": claim_id,
                    "title": task.get("title"),
                    "status": task.get("status"),
                    "candidate": task.get("candidate"),
                    "example": task.get("example"),
                    "artifact_root": task.get("artifact_root"),
                    "required_artifact_roles": task.get("required_artifact_roles", []),
                    "required_measurements": task.get("required_measurements", {}),
                    "required_commands": task.get("required_commands", []),
                    "required_references": task.get("required_references", []),
                    "read_only_import_command": task.get("read_only_import_command"),
                    "write_import_command": task.get("write_import_command"),
                    "acceptance_commands": task.get("acceptance_commands"),
                }
            )

    return {
        "status": "PASS" if not failures else "FAIL",
        "manifest": display_path(root, manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "example_count": len(examples),
        "examples": examples,
        "collection_task_count": len(collection_tasks),
        "collection_tasks": collection_tasks,
        "failures": failures,
    }


def row_by_claim(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_id = row.get("claim_id")
        if isinstance(claim_id, str):
            result[claim_id] = row
    return result


def manifest_task_by_claim(examples_verification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return row_by_claim(examples_verification.get("collection_tasks"))


def collection_status_from_row(row: dict[str, Any]) -> str:
    if not row:
        return COLLECTION_TASK_ACTION_REQUIRED
    incoming_root = row.get("incoming_root")
    if row.get("ready_to_import") is True:
        return COLLECTION_TASK_READY
    if row.get("candidate_exists") is False:
        return COLLECTION_TASK_MISSING
    if row.get("candidate_is_file") is not True:
        return COLLECTION_TASK_NON_FILE
    if row.get("candidate_is_symlink") is True:
        return COLLECTION_TASK_UNSAFE
    if isinstance(incoming_root, dict) and (
        incoming_root.get("is_symlink") is True
        or incoming_root.get("has_symlink_component") is True
    ):
        return COLLECTION_TASK_UNSAFE
    return COLLECTION_TASK_REJECTED


def collection_blocking_reasons(status: str, row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if status == COLLECTION_TASK_MISSING:
        reasons.append("candidate_file_missing")
    elif status == COLLECTION_TASK_NON_FILE:
        reasons.append("candidate_path_not_regular_file")
    elif status == COLLECTION_TASK_UNSAFE:
        reasons.append("candidate_path_unsafe")
    elif status == COLLECTION_TASK_REJECTED:
        reasons.append("candidate_validation_failed")
    elif status == COLLECTION_TASK_ACTION_REQUIRED:
        reasons.append("preflight_row_missing")
    if row.get("failures"):
        reasons.append("preflight_failures_present")
    return reasons


def build_collection_tasks(
    replacement_required: list[str],
    preflight: dict[str, Any],
    examples_verification: dict[str, Any],
) -> list[dict[str, Any]]:
    preflight_rows = row_by_claim(preflight.get("rows"))
    manifest_tasks = manifest_task_by_claim(examples_verification)
    tasks: list[dict[str, Any]] = []
    for claim_id in replacement_required:
        row = preflight_rows.get(claim_id, {})
        manifest_task = manifest_tasks.get(claim_id, {})
        candidate = row.get("candidate") or manifest_task.get("candidate") or f"docs/verification/incoming/{claim_id}.json"
        status = collection_status_from_row(row)
        tasks.append(
            {
                "claim_id": claim_id,
                "status": status,
                "candidate": candidate,
                "candidate_exists": row.get("candidate_exists"),
                "candidate_is_file": row.get("candidate_is_file"),
                "candidate_is_symlink": row.get("candidate_is_symlink"),
                "candidate_sha256": row.get("candidate_sha256"),
                "example": manifest_task.get("example") or row.get("candidate_example_path"),
                "title": manifest_task.get("title"),
                "artifact_root": manifest_task.get("artifact_root"),
                "required_artifact_roles": manifest_task.get("required_artifact_roles", []),
                "required_measurements": manifest_task.get("required_measurements", {}),
                "required_commands": manifest_task.get("required_commands", []),
                "required_references": manifest_task.get("required_references", []),
                "read_only_import_command": row.get("read_only_import_command")
                or manifest_task.get("read_only_import_command"),
                "write_import_command": row.get("write_import_command")
                or manifest_task.get("write_import_command"),
                "acceptance_commands": row.get("acceptance_commands")
                or manifest_task.get("acceptance_commands"),
                "ready_to_import": row.get("ready_to_import") is True,
                "import_decision": row.get("import_decision"),
                "validation_status": row.get("validation_status"),
                "failures": row.get("failures", []),
                "blocking_reasons": collection_blocking_reasons(status, row),
            }
        )
    return tasks


def verify_collection_tasks(
    tasks: list[dict[str, Any]],
    replacement_required: list[str],
    ready: list[str],
    not_ready: list[str],
) -> list[str]:
    failures: list[str] = []
    if [task.get("claim_id") for task in tasks] != replacement_required:
        failures.append("collection_tasks must match replacement_required claim order")
    ready_set = set(ready)
    not_ready_set = set(not_ready)
    for task in tasks:
        claim_id = task.get("claim_id")
        if not isinstance(claim_id, str):
            failures.append("collection task claim_id must be a string")
            continue
        expected_candidate = f"docs/verification/incoming/{claim_id}.json"
        if task.get("candidate") != expected_candidate:
            failures.append(f"{claim_id}: collection task candidate path is inconsistent")
        if task.get("read_only_import_command") != expected_read_only_import_command(claim_id, expected_candidate):
            failures.append(f"{claim_id}: collection task read_only_import_command is inconsistent")
        if task.get("write_import_command") != expected_write_import_command(claim_id, expected_candidate):
            failures.append(f"{claim_id}: collection task write_import_command is inconsistent")
        if task.get("acceptance_commands") != expected_acceptance_commands(claim_id):
            failures.append(f"{claim_id}: collection task acceptance_commands is inconsistent")
        if claim_id in ready_set and task.get("status") != COLLECTION_TASK_READY:
            failures.append(f"{claim_id}: ready claim must have READY_TO_IMPORT collection task")
        if claim_id in not_ready_set and task.get("status") == COLLECTION_TASK_READY:
            failures.append(f"{claim_id}: not_ready claim must not have READY_TO_IMPORT collection task")
        if claim_id in not_ready_set and not task.get("blocking_reasons"):
            failures.append(f"{claim_id}: not_ready collection task must record blocking reasons")
    return failures


def build_report(
    root: Path = ROOT,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    examples_manifest_path: Path = DEFAULT_EXAMPLES_MANIFEST,
) -> dict[str, Any]:
    preflight_path = preflight_path if preflight_path.is_absolute() else root / preflight_path
    examples_manifest_path = (
        examples_manifest_path
        if examples_manifest_path.is_absolute()
        else root / examples_manifest_path
    )
    failures: list[str] = []
    preflight: dict[str, Any] = {}
    verifier = load_replacement_verifier(root)
    examples_verification = verify_incoming_examples_manifest(root, examples_manifest_path)
    failures.extend(
        f"incoming examples: {failure}"
        for failure in examples_verification.get("failures", [])
    )

    if not preflight_path.exists():
        failures.append(f"missing replacement preflight: {display_path(root, preflight_path)}")
    elif not preflight_path.is_file():
        failures.append(f"replacement preflight is not a regular file: {display_path(root, preflight_path)}")
    else:
        try:
            preflight = load_json(preflight_path)
        except Exception as exc:
            failures.append(f"could not load replacement preflight: {exc}")
        else:
            preflight_failures = verifier.verify_saved_report(preflight_path, root)
            failures.extend(f"replacement preflight: {failure}" for failure in preflight_failures)

    plan = normalized_plan(preflight)
    if preflight and not plan:
        failures.append("replacement preflight is missing candidate_intake_plan")

    ready = list(preflight.get("ready", [])) if isinstance(preflight.get("ready"), list) else []
    not_ready = list(preflight.get("not_ready", [])) if isinstance(preflight.get("not_ready"), list) else []
    replacement_required = (
        list(preflight.get("replacement_required", []))
        if isinstance(preflight.get("replacement_required"), list)
        else []
    )
    if preflight and plan:
        if plan.get("ready_claims") != ready:
            failures.append("candidate_intake_plan.ready_claims does not match preflight ready list")
        if plan.get("not_ready_claims") != not_ready:
            failures.append("candidate_intake_plan.not_ready_claims does not match preflight not_ready list")

    collection_tasks = build_collection_tasks(replacement_required, preflight, examples_verification)
    collection_task_failures = verify_collection_tasks(
        collection_tasks,
        replacement_required,
        [item for item in ready if isinstance(item, str)],
        [item for item in not_ready if isinstance(item, str)],
    )
    failures.extend(collection_task_failures)

    if failures:
        decision = DECISION_PREFLIGHT_INVALID
    elif ready and not not_ready:
        decision = DECISION_READY_NOT_WRITTEN
    else:
        decision = DECISION_ACTION_REQUIRED

    return {
        "schema": SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "timestamp_utc": utc_now(),
        "preflight": display_path(root, preflight_path),
        "preflight_sha256": sha256_file(preflight_path),
        "preflight_verification": {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
        },
        "incoming_examples_manifest": display_path(root, examples_manifest_path),
        "incoming_examples_manifest_sha256": sha256_file(examples_manifest_path),
        "incoming_examples_verification": examples_verification,
        "replacement_required": replacement_required,
        "ready": ready,
        "not_ready": not_ready,
        "missing_candidate_paths": list(plan.get("missing_candidate_paths", [])),
        "non_file_candidate_paths": list(plan.get("non_file_candidate_paths", [])),
        "unsafe_candidate_paths": list(plan.get("unsafe_candidate_paths", [])),
        "read_only_preflight_commands": list(plan.get("read_only_preflight_commands", [])),
        "currently_ready_write_commands": list(plan.get("currently_ready_write_commands", [])),
        "write_commands_after_ready": list(plan.get("write_commands_after_ready", [])),
        "post_import_refresh_commands": list(plan.get("post_import_refresh_commands", [])),
        "collection_tasks": collection_tasks,
        "collection_tasks_verification": {
            "status": "PASS" if not collection_task_failures else "FAIL",
            "failures": collection_task_failures,
        },
        "failures": failures,
        "claim_boundary": {
            "note": "External evidence intake readiness only; this report does not import evidence or promote proof-gate claims.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse External Evidence Intake",
        "",
        f"Timestamp: `{report.get('timestamp_utc')}`",
        "",
        f"Status: `{report.get('status')}`",
        "",
        f"Decision: `{report.get('decision')}`",
        "",
        f"Preflight: `{report.get('preflight')}`",
        "",
        "## Summary",
        "",
        f"- replacement_required: `{', '.join(report.get('replacement_required', [])) or 'none'}`",
        f"- ready: `{', '.join(report.get('ready', [])) or 'none'}`",
        f"- not_ready: `{', '.join(report.get('not_ready', [])) or 'none'}`",
        f"- missing_candidate_paths: `{', '.join(report.get('missing_candidate_paths', [])) or 'none'}`",
        f"- currently_ready_write_commands: `{len(report.get('currently_ready_write_commands', []))}`",
        f"- post_import_refresh_commands: `{len(report.get('post_import_refresh_commands', []))}`",
        f"- incoming_examples_status: `{report.get('incoming_examples_verification', {}).get('status')}`",
        f"- incoming_examples_count: `{report.get('incoming_examples_verification', {}).get('example_count')}`",
        f"- collection_tasks: `{len(report.get('collection_tasks', []))}`",
        "",
        "## Collection Tasks",
        "",
    ]
    tasks = report.get("collection_tasks", [])
    if tasks:
        for task in tasks:
            lines.append(
                f"- `{task.get('claim_id')}`: status `{task.get('status')}`, "
                f"candidate `{task.get('candidate')}`, blockers "
                f"`{', '.join(task.get('blocking_reasons', [])) or 'none'}`"
            )
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Claim Boundary",
        "",
    ])
    claim_boundary = report.get("claim_boundary", {})
    if isinstance(claim_boundary, dict):
        for key in sorted(claim_boundary):
            lines.append(f"- {key}: `{claim_boundary[key]}`")
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
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-external-evidence-intake-{stamp}"
    bundle_json = bundle_dir / "intake.json"
    bundle_md = bundle_dir / "summary.md"
    report["bundle"] = display_path(root, bundle_dir)
    report["artifacts"] = {
        "intake_bundle_json": display_path(root, bundle_json),
        "intake_bundle_md": display_path(root, bundle_md),
        "intake_latest_json": display_path(root, output_json),
        "intake_latest_md": display_path(root, output_md),
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
        return [f"missing external evidence intake report: {display_path(root, report_path)}"]
    if not report_path.is_file():
        return [f"external evidence intake report is not a regular file: {display_path(root, report_path)}"]
    try:
        data = load_json(report_path)
    except Exception as exc:
        return [f"could not load external evidence intake report: {exc}"]

    if data.get("schema") != SCHEMA:
        failures.append(f"unexpected schema: {data.get('schema')}")
    preflight_path = resolve_path(root, data.get("preflight")) or DEFAULT_PREFLIGHT
    examples_manifest_path = resolve_path(root, data.get("incoming_examples_manifest")) or DEFAULT_EXAMPLES_MANIFEST
    expected = build_report(root, preflight_path, examples_manifest_path)
    if stable_subset(data) != stable_subset(expected):
        failures.append(
            "external evidence intake stable fields do not match current replacement preflight/incoming examples state"
        )

    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    latest_json = resolve_path(root, artifacts.get("intake_latest_json"))
    latest_md = resolve_path(root, artifacts.get("intake_latest_md"))
    bundle_json = resolve_path(root, artifacts.get("intake_bundle_json"))
    bundle_md = resolve_path(root, artifacts.get("intake_bundle_md"))

    if latest_json != report_path:
        failures.append("artifacts.intake_latest_json does not point at the checked report")
    if not compare_bytes(latest_json, bundle_json):
        failures.append("intake latest JSON does not match bundle JSON")
    if not compare_bytes(latest_md, bundle_md):
        failures.append("intake latest markdown does not match bundle markdown")

    expected_markdown = render_markdown(data)
    if latest_md and latest_md.exists() and latest_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("intake latest markdown does not match rendered report")
    if bundle_md and bundle_md.exists() and bundle_md.read_text(encoding="utf-8") != expected_markdown:
        failures.append("intake bundle markdown does not match rendered report")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--report", type=Path, help="Saved intake report to verify read-only.")
    parser.add_argument("--write-report", action="store_true", help="Write latest and bundle intake reports.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-all-ready", action="store_true")
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
            "failures": failures,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif failures:
            print("FAIL: x0tta6bl4_pulse external evidence intake report is stale")
            for failure in failures:
                print(f"- {failure}")
        else:
            print("PASS: x0tta6bl4_pulse external evidence intake report is current")
            print(f"report={result['report']}")
            print(f"decision={result['decision']}")
        if failures:
            return 1
        if args.require_all_ready and saved.get("decision") != DECISION_READY_NOT_WRITTEN:
            return 1
        return 0

    preflight_path = args.preflight if args.preflight.is_absolute() else root / args.preflight
    report = build_report(root, preflight_path)
    if args.write_report:
        output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
        output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
        write_report_outputs(root, report, output_json, output_md)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "PASS":
        print("FAIL: x0tta6bl4_pulse external evidence intake preflight is invalid")
        for failure in report["failures"]:
            print(f"- {failure}")
    else:
        print(f"decision={report['decision']}")
        print(f"preflight={report['preflight']}")
        print(f"ready={','.join(report['ready']) if report['ready'] else 'none'}")
        print(f"not_ready={','.join(report['not_ready']) if report['not_ready'] else 'none'}")

    if report["status"] != "PASS":
        return 1
    if args.require_all_ready and report["decision"] != DECISION_READY_NOT_WRITTEN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
