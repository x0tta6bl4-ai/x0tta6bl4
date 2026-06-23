"""Operator packet index for production raw-evidence bundle replacement.

This report is read-only. It maps every raw-evidence collector to the exact
operator bundle files that must replace retained/local evidence before the
production closeout chain can proceed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.production_raw_evidence_pipeline import (
    DEFAULT_OUTPUT as DEFAULT_PIPELINE_OUTPUT,
    build_report as build_pipeline_report,
)
from src.integration.production_raw_evidence_readiness import (
    DEFAULT_INTAKE_MANIFEST,
    DEFAULT_OUTPUT as DEFAULT_READINESS_OUTPUT,
    build_report as build_readiness_report,
    utc_now,
)


DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-operator-packet-index-current.json"
DEFAULT_MD_OUTPUT = "docs/verification/production-raw-evidence-operator-packet-index-current.md"
DEFAULT_OPERATOR_BUNDLE_ROOT = ".tmp/production-raw-evidence-operator-bundle"
DEFAULT_SEMANTIC_READINESS = ".tmp/validation-shards/production-raw-evidence-semantics-current.json"
REQUIRED_PRODUCTION_FIELDS = [
    "status == VERIFIED HERE",
    "evidence_status == VERIFIED HERE when present",
    "production_ready == true",
    "production_promotion_blockers == []",
    "environment must identify a production environment",
    "collected_at must be a valid timestamp",
    "collected_by must be a real operator/CI identity",
    "source_commands must be exact commands with no placeholders",
]


def _read_json(path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, "artifact missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"artifact unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "artifact root must be a JSON object"
    return data, ""


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _by_collector(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for item in items:
        collector_id = str(item.get("collector_id", ""))
        if collector_id:
            result[collector_id] = item
    return result


def _operator_path(bundle_root: Path, collector_id: str, raw_file: Dict[str, Any]) -> Path:
    file_name = str(raw_file.get("file_name") or Path(str(raw_file.get("path", ""))).name)
    return bundle_root / collector_id / file_name


def _production_ready(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    status = data.get("evidence_status", data.get("status"))
    source_commands = data.get("source_commands")
    return (
        status == "VERIFIED HERE"
        and data.get("production_ready") is True
        and data.get("production_promotion_blockers") == []
        and isinstance(data.get("collected_at"), str)
        and bool(data.get("collected_at"))
        and isinstance(data.get("collected_by"), str)
        and bool(data.get("collected_by"))
        and isinstance(source_commands, list)
        and bool(source_commands)
        and "prod" in str(data.get("environment", "")).lower()
    )


def _file_packet(root: Path, bundle_root: Path, collector_id: str, raw_file: Dict[str, Any]) -> Dict[str, Any]:
    display_path = _operator_path(bundle_root, collector_id, raw_file)
    full_path = display_path if display_path.is_absolute() else root / display_path
    data, error = _read_json(full_path)
    ready = _production_ready(data)
    blockers: List[str] = []
    if error:
        blockers.append(error)
    if data is not None and not ready:
        if data.get("evidence_status", data.get("status")) != "VERIFIED HERE":
            blockers.append("status/evidence_status is not VERIFIED HERE")
        if data.get("production_ready") is not True:
            blockers.append("production_ready is not true")
        if data.get("production_promotion_blockers") != []:
            blockers.append("production_promotion_blockers is not empty")
        if "prod" not in str(data.get("environment", "")).lower():
            blockers.append("environment does not identify production")
    return {
        "raw_id": str(raw_file.get("raw_id", "")),
        "file_name": str(raw_file.get("file_name") or display_path.name),
        "operator_bundle_path": str(display_path),
        "currently_exists": full_path.exists(),
        "production_ready": ready,
        "replacement_required": not ready,
        "blockers": blockers,
    }


def build_report(
    root: Path,
    intake_manifest_path: Path = Path(DEFAULT_INTAKE_MANIFEST),
    semantic_readiness_path: Path = Path(DEFAULT_SEMANTIC_READINESS),
    *,
    operator_bundle_root: Path = Path(DEFAULT_OPERATOR_BUNDLE_ROOT),
) -> Dict[str, Any]:
    pipeline = build_pipeline_report(root, intake_manifest_path, semantic_readiness_path)
    readiness = build_readiness_report(root, intake_manifest_path)
    manifest, manifest_error = _read_json(intake_manifest_path)
    manifest_collectors = _dicts((manifest or {}).get("collectors"))
    pipeline_steps = _by_collector(_dicts(pipeline.get("planned_steps")))
    readiness_summary = readiness.get("summary", {}) if isinstance(readiness.get("summary"), dict) else {}
    raw_ready_for_collectors = readiness.get("ready_for_collectors") is True
    bundle_root = operator_bundle_root

    packets: List[Dict[str, Any]] = []
    local_entrypoints_missing = 0
    files_total = 0
    files_existing = 0
    files_production_ready = 0
    files_replacement_required = 0

    for collector in manifest_collectors:
        collector_id = str(collector.get("collector_id", ""))
        raw_files = _dicts(collector.get("raw_files"))
        step = pipeline_steps.get(collector_id, {})
        file_packets = [_file_packet(root, bundle_root, collector_id, raw_file) for raw_file in raw_files]
        missing_entrypoints = [
            name
            for name, exists in [
                ("collector_script", step.get("collector_script_exists")),
                ("evidence_gate_script", step.get("evidence_gate_script_exists")),
            ]
            if exists is not True
        ]
        local_entrypoints_missing += len(missing_entrypoints)
        files_total += len(file_packets)
        files_existing += sum(1 for item in file_packets if item["currently_exists"])
        files_production_ready += sum(1 for item in file_packets if item["production_ready"])
        files_replacement_required += sum(1 for item in file_packets if item["replacement_required"])
        packets.append(
            {
                "collector_id": collector_id,
                "actionable": bool(raw_files) and not missing_entrypoints,
                "collector_script": step.get("collector_script") or collector.get("collector_script", ""),
                "collector_command": step.get("collector_command") or collector.get("collector_command", ""),
                "evidence_gate_script": step.get("evidence_gate_script", ""),
                "evidence_gate_command": step.get("evidence_gate_command", ""),
                "missing_local_entrypoints": missing_entrypoints,
                "operator_bundle_root": str(bundle_root / collector_id),
                "raw_files_total": len(file_packets),
                "operator_bundle_files_existing": sum(1 for item in file_packets if item["currently_exists"]),
                "operator_bundle_files_production_ready": sum(1 for item in file_packets if item["production_ready"]),
                "operator_bundle_files_replacement_required": sum(
                    1 for item in file_packets if item["replacement_required"]
                ),
                "required_fields": REQUIRED_PRODUCTION_FIELDS,
                "files": file_packets,
                "commands": [
                    {
                        "purpose": "render template-only bundle paths for the operator; output is not evidence",
                        "command": (
                            "python3 scripts/ops/generate_production_raw_evidence_template_pack.py "
                            "--operator-bundle-root .tmp/production-raw-evidence-operator-bundle "
                            "--write-template-files --force --require-written"
                        ),
                    },
                    {
                        "purpose": "operator replaces every listed file with real production JSON",
                        "command": f"write production JSON files under {bundle_root / collector_id}",
                    },
                    {
                        "purpose": "validate returned production raw evidence bundle before import",
                        "command": (
                            "python3 scripts/ops/import_production_raw_evidence_bundle.py "
                            "--bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready"
                        ),
                    },
                    {
                        "purpose": "run collector once raw evidence is production-ready",
                        "command": step.get("collector_command", ""),
                    },
                    {
                        "purpose": "run evidence gate after collector",
                        "command": step.get("evidence_gate_command", ""),
                    },
                ],
                "fail_closed_rules": [
                    "Do not promote retained/local raw evidence to production evidence.",
                    "Do not use template-only generated files as production evidence.",
                    "Do not run collectors until every file in this packet is production_ready=true.",
                    "Do not mark /goal complete from this packet; completion audit remains authoritative.",
                ],
            }
        )

    all_actionable = bool(packets) and all(packet["actionable"] for packet in packets)
    local_handoff_complete = all_actionable and local_entrypoints_missing == 0
    production_ready = files_total > 0 and files_production_ready == files_total and raw_ready_for_collectors
    decision = "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE" if local_handoff_complete else "RAW_EVIDENCE_OPERATOR_PACKET_INCOMPLETE"
    summary = {
        "packets_total": len(packets),
        "actionable_packets": sum(1 for packet in packets if packet["actionable"]),
        "local_entrypoints_missing": local_entrypoints_missing,
        "raw_files_total": files_total,
        "operator_bundle_files_existing": files_existing,
        "operator_bundle_files_production_ready": files_production_ready,
        "operator_bundle_files_replacement_required": files_replacement_required,
        "collectors_total": len(packets),
        "collectors_with_replacements_required": sum(
            1 for packet in packets if packet["operator_bundle_files_replacement_required"] > 0
        ),
        "raw_readiness_decision": readiness.get("raw_evidence_readiness_decision", ""),
        "raw_readiness_ready_for_collectors": raw_ready_for_collectors,
        "raw_readiness_collectors_ready": readiness_summary.get("collectors_ready", 0),
        "raw_readiness_collectors_blocked": readiness_summary.get("collectors_blocked", 0),
        "raw_readiness_collectors_total": readiness_summary.get("collectors_total", 0),
        "raw_readiness_raw_files_ready": readiness_summary.get("raw_files_ready", 0),
        "raw_readiness_raw_files_local_observation": readiness_summary.get("raw_files_local_observation", 0),
        "raw_readiness_raw_files_total": readiness_summary.get("raw_files_total", 0),
        "production_ready_blocked_by_raw_readiness": files_total > 0
        and files_production_ready == files_total
        and not raw_ready_for_collectors,
    }

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-operator-packet-index-v1-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only operator packet index for raw production evidence replacement. It lists required "
            "operator bundle files and commands, but does not create production evidence, run collectors, "
            "contact live systems, mutate runtime state, or mark /goal complete."
        ),
        "decision": decision,
        "all_packets_actionable": all_actionable,
        "local_handoff_complete": local_handoff_complete,
        "production_ready": production_ready,
        "goal_can_be_marked_complete": False,
        "operator_bundle_root": str(bundle_root),
        "source_artifacts": [
            str(intake_manifest_path),
            str(semantic_readiness_path),
            DEFAULT_READINESS_OUTPUT,
            DEFAULT_PIPELINE_OUTPUT,
        ],
        "source_errors": [f"{intake_manifest_path}: {manifest_error}"] if manifest_error else [],
        "packets": packets,
        "summary": summary,
        "not_verified_yet": [] if production_ready else [
            "operator must replace every listed bundle file with production_ready=true evidence",
            "production raw-evidence readiness must reach READY_FOR_COLLECTORS",
            "completion audit must remain NOT_COMPLETE until production closeout passes",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Production Raw Evidence Operator Packet Index",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Local handoff complete: `{report['local_handoff_complete']}`",
        f"Production ready: `{report['production_ready']}`",
        f"Raw readiness decision: `{summary.get('raw_readiness_decision', '')}`",
        f"Raw readiness ready for collectors: `{summary.get('raw_readiness_ready_for_collectors')}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Collectors",
        "",
    ]
    for packet in report.get("packets", []):
        lines.append(
            f"- `{packet.get('collector_id')}`: files=`{packet.get('raw_files_total')}`, "
            f"production_ready=`{packet.get('operator_bundle_files_production_ready')}`, "
            f"replacement_required=`{packet.get('operator_bundle_files_replacement_required')}`"
        )
        for file_item in packet.get("files", []):
            if file_item.get("replacement_required"):
                lines.append(f"  - replace `{file_item.get('operator_bundle_path')}`")
    lines.extend(["", "## Summary", "", "```json", json.dumps(summary, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build raw production evidence operator packet index")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--semantic-readiness", default=DEFAULT_SEMANTIC_READINESS)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", default="")
    parser.add_argument("--require-actionable", action="store_true")
    parser.add_argument("--require-production-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.intake_manifest)
    semantic_path = Path(args.semantic_readiness)
    bundle_root = Path(args.operator_bundle_root)
    report = build_report(
        root,
        manifest_path if manifest_path.is_absolute() else root / manifest_path,
        semantic_path if semantic_path.is_absolute() else root / semantic_path,
        operator_bundle_root=bundle_root,
    )
    output_json = Path(args.output_json)
    write_json(output_json if output_json.is_absolute() else root / output_json, report)
    if args.output_md:
        output_md = Path(args.output_md)
        output_md = output_md if output_md.is_absolute() else root / output_md
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "local_handoff_complete": report["local_handoff_complete"],
        "production_ready": report["production_ready"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_production_ready and not report["production_ready"]:
        return 2
    if args.require_actionable and not report["local_handoff_complete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
