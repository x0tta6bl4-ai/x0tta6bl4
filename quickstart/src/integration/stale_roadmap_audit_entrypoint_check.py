"""Check stale roadmap audit artifacts for dead local command entrypoints.

This is a read-only diagnostic for restored/current validation artifacts that
still mention old operator scripts. It intentionally scans a narrow artifact
set and does not execute any referenced command.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


DEFAULT_ARTIFACTS = (
    ".tmp/validation-shards/current-roadmap-audit-2026-05-12-after-westworld-scoped/audit.json",
    ".tmp/validation-shards/goal-remaining-work-queue-current.json",
    ".tmp/validation-shards/goal-completion-audit-current.json",
    ".tmp/validation-shards/live-evidence-pipeline-current-2026-05-12.json",
)

ENTRYPOINT_RE = re.compile(r"\b((?:scripts/ops|tests/unit/scripts)/[A-Za-z0-9_.\-/]+\.(?:py|sh))\b")

CURRENT_SURFACE_MAP: Dict[str, Dict[str, Any]] = {
    "scripts/ops/audit_goal_completion.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/run_integration_spine_completion_gate.py",
            "src/integration/completion_gate_runner.py",
            "src/integration/production_gap_index.py",
        ],
        "note": "Legacy goal closeout audit is replaced by fail-closed integration-spine completion and gap gates.",
    },
    "scripts/ops/audit_roadmap_execution_completion.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/run_integration_spine_completion_gate.py",
            "src/integration/completion_gate_runner.py",
            "src/integration/production_gap_index.py",
        ],
        "note": "Legacy roadmap completion audit is replaced by integration-spine completion and production gap gates.",
    },
    "scripts/ops/audit_horizon2_rag_rfc_gate.py": {
        "triage_status": "horizon2_guard_blocked_by_current_v1_1_gaps",
        "current_entrypoints": [
            "src/integration/production_gap_index.py",
            "docs/verification/x0tta6bl4-active-goal-gap-audit-2026-05-20.md",
        ],
        "note": "Horizon-2/RAG work remains blocked by the current v1.1 production evidence gaps.",
    },
    "scripts/ops/audit_roadmap_external_prereqs.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "src/integration/production_gap_index.py",
            "src/integration/evidence_readiness.py",
        ],
        "note": "External prerequisites are represented as production evidence blockers in the current gates.",
    },
    "scripts/ops/audit_roadmap_live_evidence_intake.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/run_integration_spine_production_input_pipeline.py",
            "src/integration/production_input_pipeline.py",
            "src/integration/production_evidence_intake.py",
        ],
        "note": "Legacy live-evidence intake is replaced by the production input and evidence intake pipeline.",
    },
    "scripts/ops/render_roadmap_live_evidence_next_inputs.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/generate_production_raw_evidence_template_pack.py",
            "docs/verification/production-raw-evidence-operator-runbook.md",
        ],
        "note": "Legacy next-input rendering is replaced by the production raw evidence template/runbook flow.",
    },
    "scripts/ops/render_roadmap_live_evidence_operator_todo.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/generate_production_raw_evidence_template_pack.py",
            "docs/verification/production-raw-evidence-operator-runbook.md",
        ],
        "note": "Legacy operator TODO rendering is replaced by the production raw evidence template/runbook flow.",
    },
    "scripts/ops/run_roadmap_live_evidence_pipeline.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/run_integration_spine_production_input_pipeline.py",
            "scripts/ops/run_production_raw_evidence_pipeline.py",
            "src/integration/production_input_pipeline.py",
            "src/integration/production_raw_evidence_pipeline.py",
        ],
        "note": "Legacy roadmap live-evidence pipeline is replaced by integration-spine production input/raw evidence pipelines.",
    },
    "scripts/ops/scaffold_goal_live_evidence_pack.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/generate_production_raw_evidence_template_pack.py",
            "scripts/ops/run_production_raw_evidence_pipeline.py",
            "src/integration/production_raw_evidence_pipeline.py",
        ],
        "note": "Legacy live evidence scaffold is replaced by the production raw evidence template and pipeline flow.",
    },
    "scripts/ops/verify_goal_live_blockers.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "src/integration/production_gap_index.py",
            "src/integration/completion_gate_runner.py",
        ],
        "note": "Legacy live blocker verifier is replaced by production gap index and completion gate summaries.",
    },
    "scripts/ops/watch_roadmap_live_evidence_readiness.py": {
        "triage_status": "mapped_to_current_surface",
        "current_entrypoints": [
            "scripts/ops/run_production_raw_evidence_readiness.py",
            "src/integration/production_raw_evidence_readiness.py",
            "src/integration/evidence_readiness.py",
        ],
        "note": "Legacy readiness watch is replaced by production raw evidence readiness and evidence readiness gates.",
    },
}

EXTERNAL_PREREQ_ENTRYPOINTS = {
    "scripts/ops/restore_critical_payloads.sh",
}

LEGACY_LIVE_PREFIXES = (
    "scripts/ops/collect_botflow_",
    "scripts/ops/collect_live",
    "scripts/ops/scaffold_live",
    "scripts/ops/verify_live",
)

LEGACY_SPB_PREFIXES = (
    "scripts/ops/build_spb_",
    "scripts/ops/collect_spb_",
    "scripts/ops/ingest_spb_",
    "scripts/ops/render_spb_",
    "scripts/ops/run_spb_",
    "scripts/ops/scaffold_spb_",
    "scripts/ops/smoke_spb_",
    "scripts/ops/verify_spb_",
    "scripts/ops/watch_spb_",
)

LEGACY_TEST_PREFIX = "tests/unit/scripts/test_"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iter_string_values(value: Any, path: str = "$") -> Iterable[Tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_string_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_string_values(child, f"{path}[{index}]")


def _artifact_report(root: Path, artifact: str) -> Dict[str, Any]:
    path = root / artifact
    report: Dict[str, Any] = {
        "artifact": artifact,
        "exists": path.is_file(),
        "loaded": False,
        "entrypoints_seen": [],
        "entrypoints_missing": [],
        "entrypoints_present": [],
        "references": {},
    }
    if not path.is_file():
        report["error"] = "artifact missing"
        return report

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["error"] = f"unreadable JSON: {exc.__class__.__name__}: {exc}"
        return report

    references: Dict[str, List[str]] = {}
    for json_path, string_value in _iter_string_values(data):
        for entrypoint in ENTRYPOINT_RE.findall(string_value):
            references.setdefault(entrypoint, []).append(json_path)

    seen = sorted(references)
    missing = [entrypoint for entrypoint in seen if not (root / entrypoint).is_file()]
    present = [entrypoint for entrypoint in seen if (root / entrypoint).is_file()]
    report.update(
        {
            "loaded": True,
            "entrypoints_seen": seen,
            "entrypoints_missing": missing,
            "entrypoints_present": present,
            "references": {entrypoint: sorted(paths) for entrypoint, paths in references.items()},
        }
    )
    return report


def classify_entrypoint(entrypoint: str) -> Dict[str, Any]:
    mapped = CURRENT_SURFACE_MAP.get(entrypoint)
    if mapped:
        current_entrypoints = mapped["current_entrypoints"]
        return {
            "entrypoint": entrypoint,
            "triage_status": mapped["triage_status"],
            "current_entrypoints": current_entrypoints,
            "note": mapped["note"],
        }
    if entrypoint in EXTERNAL_PREREQ_ENTRYPOINTS:
        return {
            "entrypoint": entrypoint,
            "triage_status": "external_live_prereq",
            "current_entrypoints": [],
            "note": "This names an external/live restore rehearsal prerequisite, not a repo-local replacement command.",
        }
    if entrypoint.startswith(LEGACY_LIVE_PREFIXES):
        return {
            "entrypoint": entrypoint,
            "triage_status": "legacy_live_validation_surface",
            "current_entrypoints": [
                "scripts/ops/generate_production_raw_evidence_template_pack.py",
                "scripts/ops/run_production_raw_evidence_pipeline.py",
                "src/integration/production_raw_evidence_pipeline.py",
            ],
            "note": "Legacy LIVE-00x command family should be regenerated through current production raw evidence flows or retired.",
        }
    if entrypoint.startswith(LEGACY_SPB_PREFIXES):
        return {
            "entrypoint": entrypoint,
            "triage_status": "legacy_spb_validation_surface",
            "current_entrypoints": [
                "scripts/ops/generate_production_raw_evidence_template_pack.py",
                "scripts/ops/run_integration_spine_production_input_pipeline.py",
                "src/integration/production_input_pipeline.py",
            ],
            "note": "Legacy SPB tester/intake command family should not be recreated blindly; map it to current operator evidence intake or retire it.",
        }
    if entrypoint.startswith(LEGACY_TEST_PREFIX):
        return {
            "entrypoint": entrypoint,
            "triage_status": "legacy_unit_test_for_missing_surface",
            "current_entrypoints": [
                "tests/unit/test_integration_production_raw_evidence_pipeline.py",
                "tests/unit/test_integration_production_input_pipeline.py",
                "tests/unit/test_integration_completion_gate_runner.py",
            ],
            "note": "Old tests/unit/scripts references belong to missing legacy command surfaces and need regeneration or retirement with their source scripts.",
        }
    return {
        "entrypoint": entrypoint,
        "triage_status": "unclassified_missing_entrypoint",
        "current_entrypoints": [],
        "note": "No current replacement surface is encoded for this entrypoint yet; manual triage required.",
    }


def _triage_counts(items: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = str(item["triage_status"])
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _with_current_entrypoint_presence(root: Path, item: Dict[str, Any]) -> Dict[str, Any]:
    current_entrypoints = list(item.get("current_entrypoints", []))
    present = [entrypoint for entrypoint in current_entrypoints if (root / entrypoint).is_file()]
    missing = [entrypoint for entrypoint in current_entrypoints if not (root / entrypoint).is_file()]
    enriched = dict(item)
    enriched["current_entrypoints_present"] = present
    enriched["current_entrypoints_missing"] = missing
    return enriched


def build_report(root: Path, artifacts: Sequence[str] = DEFAULT_ARTIFACTS) -> Dict[str, Any]:
    artifact_reports = [_artifact_report(root, artifact) for artifact in artifacts]
    missing_artifacts = [item["artifact"] for item in artifact_reports if not item["exists"]]
    load_errors = [item["artifact"] for item in artifact_reports if item["exists"] and not item["loaded"]]
    missing_entrypoints = sorted(
        {entrypoint for item in artifact_reports for entrypoint in item["entrypoints_missing"]}
    )
    present_entrypoints = sorted(
        {entrypoint for item in artifact_reports for entrypoint in item["entrypoints_present"]}
    )
    seen_entrypoints = sorted({entrypoint for item in artifact_reports for entrypoint in item["entrypoints_seen"]})
    missing_entrypoint_triage = [
        _with_current_entrypoint_presence(root, classify_entrypoint(entrypoint)) for entrypoint in missing_entrypoints
    ]
    triage_counts = _triage_counts(missing_entrypoint_triage)
    current_entrypoint_targets_seen = sorted(
        {entrypoint for item in missing_entrypoint_triage for entrypoint in item["current_entrypoints"]}
    )
    current_entrypoint_targets_present = sorted(
        {entrypoint for item in missing_entrypoint_triage for entrypoint in item["current_entrypoints_present"]}
    )
    current_entrypoint_targets_missing = sorted(
        {entrypoint for item in missing_entrypoint_triage for entrypoint in item["current_entrypoints_missing"]}
    )
    ready = not missing_artifacts and not load_errors and not missing_entrypoints
    triage_ready = (
        not missing_artifacts
        and not load_errors
        and triage_counts.get("unclassified_missing_entrypoint", 0) == 0
        and not current_entrypoint_targets_missing
    )
    if ready:
        decision = "ENTRYPOINTS_CLEAR"
    elif triage_ready:
        decision = "STALE_AUDIT_ENTRYPOINTS_TRIAGED"
    else:
        decision = "STALE_AUDIT_ENTRYPOINTS_MISSING"

    return {
        "schema_version": "x0tta6bl4-stale-roadmap-audit-entrypoint-check-v1-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "ready": ready,
        "triage_ready": triage_ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only repo-local diagnostic for selected roadmap/completion audit artifacts. "
            "It parses local JSON, checks whether referenced script/test entrypoint files exist, "
            "classifies stale references against current repo-local surfaces, does not execute referenced "
            "commands, does not contact live systems, and cannot close /goal."
        ),
        "mutates_files": False,
        "contacts_live_systems": False,
        "artifacts": artifact_reports,
        "summary": {
            "artifacts_total": len(artifact_reports),
            "artifacts_loaded": sum(1 for item in artifact_reports if item["loaded"]),
            "missing_artifacts_total": len(missing_artifacts),
            "load_errors_total": len(load_errors),
            "entrypoints_seen_total": len(seen_entrypoints),
            "entrypoints_present_total": len(present_entrypoints),
            "entrypoints_missing_total": len(missing_entrypoints),
            "missing_entrypoint_triage_counts": triage_counts,
            "missing_entrypoints_mapped_to_current_surface": triage_counts.get("mapped_to_current_surface", 0),
            "missing_entrypoints_legacy_live_or_spb": triage_counts.get("legacy_live_validation_surface", 0)
            + triage_counts.get("legacy_spb_validation_surface", 0),
            "missing_entrypoints_external_live_prereq": triage_counts.get("external_live_prereq", 0),
            "missing_entrypoints_unclassified": triage_counts.get("unclassified_missing_entrypoint", 0),
            "current_entrypoint_targets_seen_total": len(current_entrypoint_targets_seen),
            "current_entrypoint_targets_present_total": len(current_entrypoint_targets_present),
            "current_entrypoint_targets_missing_total": len(current_entrypoint_targets_missing),
            "ready": ready,
            "triage_ready": triage_ready,
            "goal_can_be_marked_complete": False,
        },
        "missing_artifacts": missing_artifacts,
        "load_errors": load_errors,
        "entrypoints_seen": seen_entrypoints,
        "entrypoints_present": present_entrypoints,
        "entrypoints_missing": missing_entrypoints,
        "missing_entrypoint_triage": missing_entrypoint_triage,
        "current_entrypoint_targets_seen": current_entrypoint_targets_seen,
        "current_entrypoint_targets_present": current_entrypoint_targets_present,
        "current_entrypoint_targets_missing": current_entrypoint_targets_missing,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check stale roadmap audit artifacts for missing entrypoint files")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--artifact",
        dest="artifacts",
        action="append",
        help="relative JSON artifact to scan; repeatable; defaults to the known roadmap/completion surfaces",
    )
    parser.add_argument("--output-json")
    parser.add_argument("--require-clear", action="store_true")
    parser.add_argument(
        "--require-triaged",
        action="store_true",
        help="fail only when missing entrypoints are unclassified, replacement targets are absent, or artifacts fail to load",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root, tuple(args.artifacts) if args.artifacts else DEFAULT_ARTIFACTS)
    if args.output_json:
        output = Path(args.output_json)
        write_json(output if output.is_absolute() else root / output, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_clear and not report["ready"]:
        return 2
    if args.require_triaged and not report["triage_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
