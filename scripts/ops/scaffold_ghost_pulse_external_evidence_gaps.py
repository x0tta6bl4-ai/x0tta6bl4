#!/usr/bin/env python3
"""Write fail-closed external evidence gap records for x0tta6bl4_pulse.

The records produced here are not templates and not simulated success. They are
machine-readable statements that required external evidence is absent on this
machine. The proof gate must continue to reject the affected claim until a real
authorized lab/review/approval artifact replaces the gap record.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
STATUS_INCOMPLETE = "INCOMPLETE"
GAP_ARTIFACT_ROLE = "evidence_gap_record"
INCOMING_EXAMPLE_MANIFEST_SCHEMA = "x0tta6bl4.ghost_pulse.incoming_example_manifest.v1"
INCOMING_EXAMPLE_MODE = "INCOMING_CANDIDATE_EXAMPLE_NOT_EVIDENCE"
INCOMING_EXAMPLE_STATUS = "EXAMPLE_ONLY_NOT_EVIDENCE"
INCOMING_EXAMPLE_DIR = Path("docs") / "verification" / "incoming" / "examples"
INCOMING_GAP_CANDIDATE_SCHEMA = "x0tta6bl4.ghost_pulse.incoming_gap_candidates.v1"
COLLECTION_TASK_STATUS = "WAITING_FOR_REAL_EXTERNAL_EVIDENCE"
INTAKE_GATE_COMMANDS = {
    "write_report": [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--write-report",
        "--json",
    ],
    "read_only": [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--json",
    ],
    "require_all_ready": [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--require-all-ready",
        "--json",
    ],
}
POST_IMPORT_REFRESH_COMMANDS = [
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

CLAIM_GAPS: dict[str, dict[str, Any]] = {
    "dpi_lab": {
        "title": "Authorized DPI lab result",
        "latest_json": "GHOST_PULSE_DPI_LAB_LATEST.json",
        "latest_md": "GHOST_PULSE_DPI_LAB_LATEST.md",
        "missing_inputs": [
            "authorized lab identity and scope",
            "baseline detected-or-blocked result",
            "pulse result record",
            "lab conclusion for DPI bypass behavior",
        ],
        "measurements": {
            "authorized_lab": False,
            "baseline_detected_or_blocked": False,
            "pulse_result_recorded": False,
            "dpi_bypass_verified": False,
        },
        "required_artifact_roles": [
            "lab_scope",
            "baseline_result",
            "pulse_result",
            "lab_conclusion",
        ],
    },
    "whitelist_lab": {
        "title": "Authorized whitelist-behavior lab result",
        "latest_json": "GHOST_PULSE_WHITELIST_LAB_LATEST.json",
        "latest_md": "GHOST_PULSE_WHITELIST_LAB_LATEST.md",
        "missing_inputs": [
            "authorized provider or lab identity",
            "provider traffic-management profile",
            "third-party baseline capture",
            "whitelist behavior conclusion",
        ],
        "measurements": {
            "authorized_provider_or_lab": False,
            "provider_profile": "",
            "third_party_baseline_captured": False,
            "whitelist_behavior_verified": False,
        },
        "required_artifact_roles": [
            "provider_or_lab_authorization",
            "provider_profile",
            "third_party_baseline_capture",
            "whitelist_conclusion",
        ],
    },
    "security_review": {
        "title": "Security review with no open high-severity findings",
        "latest_json": "GHOST_PULSE_SECURITY_REVIEW_LATEST.json",
        "latest_md": "GHOST_PULSE_SECURITY_REVIEW_LATEST.md",
        "missing_inputs": [
            "reviewer identity",
            "review scope covering pulse transport",
            "critical finding count from completed review",
            "high finding count from completed review",
        ],
        "measurements": {
            "reviewer": "",
            "scope_includes_pulse_transport": False,
            "open_critical_findings": None,
            "open_high_findings": None,
        },
        "required_artifact_roles": [
            "reviewer_identity",
            "review_scope",
            "findings_report",
        ],
    },
    "production_readiness": {
        "title": "Production readiness approval and rollback evidence",
        "latest_json": "GHOST_PULSE_PRODUCTION_READINESS_LATEST.json",
        "latest_md": "GHOST_PULSE_PRODUCTION_READINESS_LATEST.md",
        "missing_inputs": [
            "production readiness approval",
            "verified rollback plan",
            "verified monitoring plan",
            "operator approval record",
            "references to all prior proof rows",
        ],
        "measurements": {
            "production_ready": False,
            "rollback_plan_verified": False,
            "monitoring_plan_verified": False,
            "operator_approval_recorded": False,
            "all_prior_claims_referenced": False,
        },
        "required_artifact_roles": [
            "operator_approval",
            "rollback_plan",
            "monitoring_plan",
            "prior_claim_references",
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
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


def load_proof_gate(root: Path):
    path = root / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    if not path.exists():
        path = ROOT / "scripts" / "ops" / "run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location(
        "run_ghost_pulse_proof_gate_for_external_gap_scaffold",
        path,
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def incoming_example_path(claim_id: str) -> str:
    return str(INCOMING_EXAMPLE_DIR / f"{claim_id}.example.json")


def placeholder_measurement(expectation: Any) -> Any:
    if expectation is True or expectation == "bool_true":
        return "REPLACE_WITH_TRUE"
    if expectation == "positive_int":
        return "REPLACE_WITH_POSITIVE_INTEGER"
    if expectation == "sha256":
        return "REPLACE_WITH_SHA256"
    if expectation == "nonempty":
        return "REPLACE_WITH_NONEMPTY_VALUE"
    if expectation == 0:
        return "REPLACE_WITH_ZERO"
    return f"REPLACE_WITH_{expectation}"


def placeholder_command(template: list[str]) -> list[str]:
    return [
        "REPLACE_WITH_INTERFACE" if part == "<interface>" else str(part)
        for part in template
    ]


def acceptance_commands_for_claim(claim_id: str) -> list[list[str]]:
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


def build_incoming_example(proof, requirement: dict[str, Any]) -> dict[str, Any]:
    claim_id = requirement["claim_id"]
    required_roles = list(requirement.get("required_artifact_roles", []))
    required_commands = list(requirement.get("required_commands", []))
    commands = [
        {
            "args": placeholder_command(template),
            "exit_code": "REPLACE_WITH_ZERO_EXIT_CODE",
        }
        for template in required_commands
    ]
    if not commands:
        commands = [
            {
                "args": ["REPLACE_WITH_REAL_COLLECTION_OR_REVIEW_COMMAND"],
                "exit_code": "REPLACE_WITH_ZERO_EXIT_CODE",
            }
        ]
    json_artifact_roles = set(requirement.get("json_artifact_payload_links", {}))
    json_artifact_roles.update(requirement.get("json_artifact_object_field_links", {}))

    payload = {
        "schema": getattr(proof, "EVIDENCE_SCHEMA", SCHEMA),
        "claim_id": claim_id,
        "title": requirement["title"],
        "status": STATUS_INCOMPLETE,
        "observed_at_utc": "REPLACE_WITH_REAL_OBSERVATION_TIME_UTC",
        "simulated": False,
        "dry_run": False,
        "template": True,
        "mode": INCOMING_EXAMPLE_MODE,
        "commands": commands,
        "artifacts": [
            {
                "role": role,
                "path": (
                    f"docs/verification/incoming/artifacts/{claim_id}/{role}.REPLACE_WITH_REAL_JSON_FILE"
                    if role in json_artifact_roles
                    else f"docs/verification/incoming/artifacts/{claim_id}/{role}.REPLACE_WITH_REAL_FILE"
                ),
                "sha256": "REPLACE_WITH_ARTIFACT_SHA256",
            }
            for role in required_roles
        ],
        "measurements": {
            key: placeholder_measurement(expectation)
            for key, expectation in requirement["measurements"].items()
        },
        "requirement_contract": (
            proof.external_requirement_contract(requirement)
            if hasattr(proof, "external_requirement_contract")
            else {
                "claim_id": claim_id,
                "title": requirement["title"],
                "path": requirement["path"],
                "measurements": requirement["measurements"],
            }
        ),
        "candidate_destination": f"docs/verification/incoming/{claim_id}.json",
        "import_command": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--candidate",
            f"docs/verification/incoming/{claim_id}.json",
            "--require-ready",
            "--json",
        ],
        "acceptance_commands": acceptance_commands_for_claim(claim_id),
        "missing_inputs": [
            "replace this example with real external evidence before import",
            "set template to false only after every placeholder is replaced",
        ],
        "failures": [
            "incoming example is not evidence and must be rejected by proof gate",
        ],
        "claim_boundary": {
            "note": "Example only; this file must not promote proof-gate claims.",
        },
    }
    required_references = requirement.get("required_references")
    if isinstance(required_references, list):
        payload["references"] = [
            {
                "claim_id": claim,
                "status": "REPLACE_WITH_CURRENT_PROOF_STATUS",
                "evidence": "REPLACE_WITH_CURRENT_EVIDENCE_PATH",
                "sha256": "REPLACE_WITH_CURRENT_EVIDENCE_SHA256",
            }
            for claim in required_references
        ]
    for payload_key in requirement.get("json_artifact_payload_links", {}).values():
        payload.setdefault(
            payload_key,
            {
                "example_placeholder": f"REPLACE_WITH_REAL_{payload_key.upper()}",
            },
        )
    for payload_keys in requirement.get("json_artifact_object_field_links", {}).values():
        for payload_key in payload_keys:
            payload.setdefault(
                payload_key,
                {
                    "example_placeholder": f"REPLACE_WITH_REAL_{payload_key.upper()}",
                },
            )
    return payload


def incoming_collection_task(requirement: dict[str, Any]) -> dict[str, Any]:
    claim_id = requirement["claim_id"]
    candidate = f"docs/verification/incoming/{claim_id}.json"
    return {
        "claim_id": claim_id,
        "title": requirement["title"],
        "status": COLLECTION_TASK_STATUS,
        "candidate": candidate,
        "example": incoming_example_path(claim_id),
        "artifact_root": f"docs/verification/incoming/artifacts/{claim_id}",
        "required_artifact_roles": list(requirement.get("required_artifact_roles", [])),
        "required_measurements": dict(requirement.get("measurements", {})),
        "required_commands": list(requirement.get("required_commands", [])),
        "required_references": list(requirement.get("required_references", [])),
        "read_only_import_command": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--candidate",
            candidate,
            "--require-ready",
            "--json",
        ],
        "write_import_command": [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            claim_id,
            "--candidate",
            candidate,
            "--write",
            "--json",
        ],
        "acceptance_commands": acceptance_commands_for_claim(claim_id),
        "claim_boundary": (
            "Collection task only; it records required real evidence and does not "
            "promote proof-gate claims."
        ),
    }


def render_incoming_examples_readme(manifest: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Incoming External Evidence Examples",
        "",
        f"Status: `{manifest['status']}`",
        "",
        "These files are examples only. They are not replacement candidates and must not be copied unchanged into the proof gate.",
        "",
        "Use the real candidate path from each row, then run the read-only import command before using `--write`.",
        "",
        "## Intake Gate",
        "",
        "After staging real candidate files, run the intake gate before importing anything.",
        "",
        "```bash",
        " ".join(manifest["intake_gate"]["write_report_command"]),
        " ".join(manifest["intake_gate"]["require_all_ready_command"]),
        "```",
        "",
        "Expected current result with only examples present: `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`.",
        "",
        "After importing real ready candidates, refresh dependent reports in this order:",
        "",
        "```bash",
        *[" ".join(command) for command in manifest["intake_gate"]["post_import_refresh_commands"]],
        "```",
        "",
        "## Examples",
        "",
    ]
    for row in manifest["examples"]:
        lines.append(
            f"- {row['claim_id']}: example `{row['example']}`, real candidate `{row['candidate']}`"
        )
    lines.extend(["", "## Collection Tasks", ""])
    for task in manifest.get("collection_tasks", []):
        roles = ", ".join(task.get("required_artifact_roles", [])) or "none"
        lines.append(
            f"- {task['claim_id']}: candidate `{task['candidate']}`, "
            f"status `{task['status']}`, artifact roles `{roles}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_incoming_examples(root: Path, claim_ids: list[str] | None = None) -> dict[str, Any]:
    proof = load_proof_gate(root)
    requirements = {
        requirement["claim_id"]: requirement
        for requirement in proof.EXTERNAL_REQUIREMENTS
    }
    selected = claim_ids or list(requirements)
    unknown = sorted(set(selected) - set(requirements))
    if unknown:
        raise ValueError(f"unknown proof-gate claim for incoming example: {', '.join(unknown)}")

    examples: list[dict[str, Any]] = []
    collection_tasks: list[dict[str, Any]] = []
    for claim_id in selected:
        requirement = requirements[claim_id]
        example_path = root / incoming_example_path(claim_id)
        example_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_incoming_example(proof, requirement)
        example_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        collection_tasks.append(incoming_collection_task(requirement))
        examples.append(
            {
                "claim_id": claim_id,
                "example": display_path(root, example_path),
                "candidate": f"docs/verification/incoming/{claim_id}.json",
                "sha256": sha256_file(example_path),
            }
        )

    manifest = {
        "schema": INCOMING_EXAMPLE_MANIFEST_SCHEMA,
        "status": INCOMING_EXAMPLE_STATUS,
        "examples": examples,
        "collection_tasks": collection_tasks,
        "intake_gate": {
            "write_report_command": INTAKE_GATE_COMMANDS["write_report"],
            "read_only_command": INTAKE_GATE_COMMANDS["read_only"],
            "require_all_ready_command": INTAKE_GATE_COMMANDS["require_all_ready"],
            "post_import_refresh_commands": POST_IMPORT_REFRESH_COMMANDS,
            "expected_current_decision_with_examples_only": "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED",
            "claim_boundary": "Intake gate only; examples are not evidence and must not promote proof-gate claims.",
        },
        "claim_boundary": {
            "note": "Incoming examples only; no proof-gate claim is verified by this manifest.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }
    manifest_path = root / INCOMING_EXAMPLE_DIR / "manifest.json"
    readme_path = root / INCOMING_EXAMPLE_DIR / "README.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.write_text(render_incoming_examples_readme(manifest), encoding="utf-8")
    manifest["manifest"] = display_path(root, manifest_path)
    manifest["readme"] = display_path(root, readme_path)
    return manifest


def write_incoming_gap_candidates(root: Path, claim_ids: list[str] | None = None) -> dict[str, Any]:
    selected = claim_ids or list(CLAIM_GAPS)
    unknown = sorted(set(selected) - set(CLAIM_GAPS))
    if unknown:
        raise ValueError(f"unknown gap candidate claim: {', '.join(unknown)}")

    observed_at = utc_now()
    stamp = stamp_from_timestamp(observed_at)
    bundle_dir = (
        root
        / "docs"
        / "verification"
        / "incoming"
        / "artifacts"
        / f"ghost-pulse-incoming-gap-candidates-{stamp}"
    )
    incoming_dir = root / "docs" / "verification" / "incoming"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    incoming_dir.mkdir(parents=True, exist_ok=True)

    candidates: dict[str, Any] = {}
    for claim_id in selected:
        report = build_gap_report(root, claim_id, observed_at, bundle_dir)
        candidate_path = incoming_dir / f"{claim_id}.json"
        candidate_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        candidates[claim_id] = {
            "status": report["status"],
            "candidate": display_path(root, candidate_path),
            "candidate_sha256": sha256_file(candidate_path),
            "expected_import_decision": "REJECTED",
            "read_only_import_command": [
                "python3",
                "scripts/ops/import_ghost_pulse_external_evidence.py",
                "--claim",
                claim_id,
                "--candidate",
                f"docs/verification/incoming/{claim_id}.json",
                "--require-ready",
                "--json",
            ],
            "acceptance_commands": acceptance_commands_for_claim(claim_id),
            "missing_inputs": report["missing_inputs"],
            "claim_boundary": (
                "Incoming gap candidate only; this file records absent evidence and must be "
                "rejected until real external evidence replaces it."
            ),
        }

    index = {
        "schema": INCOMING_GAP_CANDIDATE_SCHEMA,
        "timestamp_utc": observed_at,
        "status": STATUS_INCOMPLETE,
        "bundle": display_path(root, bundle_dir),
        "candidates": candidates,
        "post_import_refresh_commands": POST_IMPORT_REFRESH_COMMANDS,
        "claim_boundary": {
            "note": "Incoming gap candidates do not promote proof-gate claims.",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
    }
    (bundle_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# x0tta6bl4_pulse {report['title']} Evidence Gap",
        "",
        f"Observed at: `{report['observed_at_utc']}`",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Meaning",
        "",
        "This is a fail-closed gap record. It documents that required external evidence is absent here.",
        "It does not prove the claim and must be replaced by real authorized evidence before the proof gate can pass.",
        "",
        "## Missing Inputs",
        "",
    ]
    lines.extend(f"- {item}" for item in report["missing_inputs"])
    lines.extend(["", "## Current Measurements", ""])
    for key, value in report["measurements"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    lines.extend(f"- {failure}" for failure in report["failures"])
    lines.append("")
    return "\n".join(lines)


def artifact_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "role": GAP_ARTIFACT_ROLE,
        "path": display_path(root, path),
        "sha256": sha256_file(path),
    }


def build_gap_report(root: Path, claim_id: str, observed_at: str, bundle_dir: Path) -> dict[str, Any]:
    spec = CLAIM_GAPS[claim_id]
    gap_record = bundle_dir / f"{claim_id}-gap-record.json"
    gap_payload = {
        "claim_id": claim_id,
        "title": spec["title"],
        "missing_inputs": spec["missing_inputs"],
        "measurements": spec["measurements"],
        "required_artifact_roles": spec.get("required_artifact_roles", []),
        "gap_artifact_role": GAP_ARTIFACT_ROLE,
        "recorded_by": "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        "observed_at_utc": observed_at,
        "status": STATUS_INCOMPLETE,
    }
    gap_record.write_text(json.dumps(gap_payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = [
        f"missing external input: {item}"
        for item in spec["missing_inputs"]
    ]
    report = {
        "schema": SCHEMA,
        "claim_id": claim_id,
        "title": spec["title"],
        "status": STATUS_INCOMPLETE,
        "observed_at_utc": observed_at,
        "simulated": False,
        "dry_run": False,
        "template": False,
        "mode": "EXTERNAL_EVIDENCE_GAP_RECORD",
        "commands": [
            {
                "args": [
                    sys.executable,
                    "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
                    "--claim",
                    claim_id,
                ],
                "exit_code": 0,
            }
        ],
        "artifacts": [artifact_record(root, gap_record)],
        "measurements": spec["measurements"],
        "required_artifact_roles": spec.get("required_artifact_roles", []),
        "gap_artifact_role": GAP_ARTIFACT_ROLE,
        "missing_inputs": spec["missing_inputs"],
        "failures": failures,
        "bundle": display_path(root, bundle_dir),
        "claim_boundary": {
            "claim_verified": False,
            "note": "Required external evidence is absent; proof gate must reject this claim.",
        },
    }
    if claim_id == "production_readiness":
        report["references"] = []
    return report


def write_claim_outputs(root: Path, report: dict[str, Any]) -> dict[str, Path]:
    claim_id = report["claim_id"]
    spec = CLAIM_GAPS[claim_id]
    bundle_dir = root / report["bundle"]
    bundle_json = bundle_dir / f"{claim_id}-evidence.json"
    bundle_md = bundle_dir / f"{claim_id}-summary.md"
    latest_json = root / "docs" / "verification" / spec["latest_json"]
    latest_md = root / "docs" / "verification" / spec["latest_md"]
    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)

    latest_json.parent.mkdir(parents=True, exist_ok=True)
    bundle_json.write_text(rendered_json, encoding="utf-8")
    bundle_md.write_text(rendered_md, encoding="utf-8")
    latest_json.write_text(rendered_json, encoding="utf-8")
    latest_md.write_text(rendered_md, encoding="utf-8")
    return {
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": latest_json,
        "latest_md": latest_md,
    }


def scaffold(root: Path, claim_ids: list[str]) -> dict[str, Any]:
    observed_at = utc_now()
    stamp = stamp_from_timestamp(observed_at)
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-external-evidence-gaps-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Any] = {}
    for claim_id in claim_ids:
        report = build_gap_report(root, claim_id, observed_at, bundle_dir)
        paths = write_claim_outputs(root, report)
        outputs[claim_id] = {
            "status": report["status"],
            "latest_json": display_path(root, paths["latest_json"]),
            "latest_md": display_path(root, paths["latest_md"]),
            "bundle_json": display_path(root, paths["bundle_json"]),
            "bundle_md": display_path(root, paths["bundle_md"]),
        }

    index = {
        "timestamp_utc": observed_at,
        "status": STATUS_INCOMPLETE,
        "bundle": display_path(root, bundle_dir),
        "claims": outputs,
        "claim_boundary": "Gap records only; no external claim is verified.",
    }
    (bundle_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--claim",
        action="append",
        help="Claim to scaffold. Repeatable. Defaults to every external lab/review/readiness gap.",
    )
    parser.add_argument(
        "--incoming-examples",
        action="store_true",
        help="Also write fail-closed incoming example files under docs/verification/incoming/examples.",
    )
    parser.add_argument(
        "--examples-only",
        action="store_true",
        help="Only write incoming example files; do not replace latest gap records.",
    )
    parser.add_argument(
        "--incoming-gap-candidates",
        action="store_true",
        help=(
            "Also write fail-closed incoming gap candidate files under docs/verification/incoming. "
            "They record absent evidence and must be rejected by the importer."
        ),
    )
    parser.add_argument(
        "--gap-candidates-only",
        action="store_true",
        help="Only write fail-closed incoming gap candidate files; do not replace latest gap records.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        if args.examples_only:
            result = write_incoming_examples(root, args.claim)
        elif args.gap_candidates_only:
            result = write_incoming_gap_candidates(root, args.claim)
        else:
            claim_ids = args.claim or list(CLAIM_GAPS)
            unknown = sorted(set(claim_ids) - set(CLAIM_GAPS))
            if unknown:
                raise ValueError(f"unknown gap scaffold claim: {', '.join(unknown)}")
            result = scaffold(root, claim_ids)
            if args.incoming_examples:
                result["incoming_examples"] = write_incoming_examples(root, args.claim)
            if args.incoming_gap_candidates:
                result["incoming_gap_candidates"] = write_incoming_gap_candidates(root, claim_ids)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
