"""Operator packet index for production raw-evidence bundle replacement.

This report is read-only. It maps every raw-evidence collector to the exact
operator bundle files that must replace retained/local evidence before the
production closeout chain can proceed.
"""

from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
DEFAULT_CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
EXPECTED_CURRENT_EVIDENCE_STATUS = "working_map_not_production_completion_proof"
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
REQUIRED_CROSS_PLANE_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}
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


def _hash_payload(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "0x" + hashlib.sha256(body).hexdigest()


def _current_evidence_context(root: Path) -> Dict[str, Any]:
    map_path = root / DEFAULT_CURRENT_CROSS_PLANE_MAP
    audit_path = root / DEFAULT_CURRENT_ACTIVE_AUDIT
    context: Dict[str, Any] = {
        "included": map_path.exists() and audit_path.exists(),
        "source": "docs/architecture",
        "cross_plane_map": DEFAULT_CURRENT_CROSS_PLANE_MAP,
        "active_goal_audit": DEFAULT_CURRENT_ACTIVE_AUDIT,
        "claim_boundary": (
            "Current cross-plane evidence context is a local gate for this raw evidence "
            "operator packet. It is not production proof by itself."
        ),
    }
    if not map_path.exists() or not audit_path.exists():
        context.update(
            {
                "status": "missing_current_evidence_context",
                "current_gap_count": None,
                "tracked_gap_count": None,
                "non_blocking_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
                "non_blocking_gap_ids": [],
                "next_action_ids": [],
                "required_planes_present": False,
                "plane_ids": [],
            }
        )
        return context
    try:
        data = json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as exc:
        context.update(
            {
                "status": "invalid_current_evidence_map",
                "error": str(exc),
                "current_gap_count": None,
                "tracked_gap_count": None,
                "non_blocking_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
                "non_blocking_gap_ids": [],
                "next_action_ids": [],
                "required_planes_present": False,
                "plane_ids": [],
            }
        )
        return context
    if not isinstance(data, dict):
        context.update(
            {
                "status": "invalid_current_evidence_map",
                "error": "current evidence map must be a JSON object",
                "current_gap_count": None,
                "tracked_gap_count": None,
                "non_blocking_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
                "non_blocking_gap_ids": [],
                "next_action_ids": [],
                "required_planes_present": False,
                "plane_ids": [],
            }
        )
        return context

    gaps = _dicts(data.get("current_gaps"))
    next_actions = _dicts(data.get("next_actions"))
    blocking_gaps = [item for item in gaps if item.get("blocks_real_readiness") is not False]
    non_blocking_gaps = [item for item in gaps if item.get("blocks_real_readiness") is False]
    planes = data.get("planes")
    plane_ids = sorted(str(key) for key in planes) if isinstance(planes, dict) else []
    context.update(
        {
            "status": data.get("status"),
            "current_gap_count": len(blocking_gaps),
            "tracked_gap_count": len(gaps),
            "non_blocking_gap_count": len(non_blocking_gaps),
            "next_action_count": len(next_actions),
            "open_gap_ids": [str(item.get("id")) for item in blocking_gaps if item.get("id")],
            "non_blocking_gap_ids": [str(item.get("id")) for item in non_blocking_gaps if item.get("id")],
            "next_action_ids": [str(item.get("id")) for item in next_actions if item.get("id")],
            "required_planes_present": REQUIRED_CROSS_PLANE_PLANES.issubset(set(plane_ids)),
            "plane_ids": plane_ids,
        }
    )
    return context


def _current_evidence_clear(context: Dict[str, Any]) -> bool:
    return (
        context.get("included") is True
        and context.get("status") == EXPECTED_CURRENT_EVIDENCE_STATUS
        and context.get("required_planes_present") is True
        and context.get("current_gap_count") == 0
        and context.get("next_action_count") == 0
    )


def _current_evidence_blockers(context: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if context.get("included") is not True:
        blockers.append("current_evidence_context_missing")
    if context.get("status") != EXPECTED_CURRENT_EVIDENCE_STATUS:
        blockers.append("current_evidence_context_status")
    if context.get("required_planes_present") is not True:
        blockers.append("current_evidence_required_planes_missing")
    if context.get("current_gap_count"):
        blockers.append("current_evidence_open_gaps")
    if context.get("next_action_count"):
        blockers.append("current_evidence_next_actions_open")
    return blockers


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _cross_plane_proof_gate_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    claim_ids: List[str] = []
    for result in _dicts((data or {}).get("claim_results")):
        claim_id = result.get("claim_id")
        if isinstance(claim_id, str) and claim_id:
            claim_ids.append(claim_id)
    return sorted(set(claim_ids))


def _cross_plane_proof_gate_missing_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    return sorted(set(RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


def _cross_plane_proof_gate_blocker_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    blockers: List[str] = []
    if not data:
        return ["cross_plane_proof_gate_missing"]
    if data.get("schema") != CROSS_PLANE_PROOF_GATE_SCHEMA:
        blockers.append("cross_plane_proof_gate_schema_invalid")
    if data.get("decision") != CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION:
        blockers.append("cross_plane_proof_gate_not_allowed")
    if data.get("allowed") is not True:
        blockers.append("cross_plane_proof_gate_blocked")
    context = data.get("context")
    if not isinstance(context, dict) or context.get("source_artifact_hashes_present") is not True:
        blockers.append("cross_plane_proof_gate_source_artifact_hashes_missing")
    for claim_id in _cross_plane_proof_gate_missing_claim_ids(data):
        blockers.append(f"cross_plane_proof_gate_missing_claim:{claim_id}")
    for result in _dicts(data.get("claim_results")):
        claim_id = str(result.get("claim_id") or "unknown_claim")
        if result.get("allowed") is True:
            continue
        blockers.append(f"claim_blocked:{claim_id}")
        result_blockers = result.get("blockers")
        if isinstance(result_blockers, list):
            blockers.extend(str(item) for item in result_blockers if item)
    return sorted(set(blockers))


def _cross_plane_proof_gate_allowed(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    required_claim_ids = set(RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS)
    claim_results = {
        str(result.get("claim_id")): result
        for result in _dicts(data.get("claim_results"))
        if isinstance(result.get("claim_id"), str)
    }
    return (
        data.get("schema") == CROSS_PLANE_PROOF_GATE_SCHEMA
        and data.get("decision") == CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION
        and data.get("allowed") is True
        and not _cross_plane_proof_gate_missing_claim_ids(data)
        and all(claim_results[claim_id].get("allowed") is True for claim_id in required_claim_ids)
        and isinstance(data.get("context"), dict)
        and data["context"].get("source_artifact_hashes_present") is True
    )


def _cross_plane_proof_gate_context(root: Path) -> Dict[str, Any]:
    path = root / DEFAULT_CROSS_PLANE_PROOF_GATE
    data = _read_json(path)[0]
    context = data.get("context") if isinstance(data, dict) else {}
    if not isinstance(context, dict):
        context = {}
    summary = (data or {}).get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return {
        "path": DEFAULT_CROSS_PLANE_PROOF_GATE,
        "exists": path.exists(),
        "loaded": isinstance(data, dict),
        "schema": (data or {}).get("schema"),
        "decision": (data or {}).get("decision"),
        "allowed": _cross_plane_proof_gate_allowed(data),
        "reported_claim_ids": _cross_plane_proof_gate_claim_ids(data),
        "required_claim_ids": list(RAW_OPERATOR_PACKET_CROSS_PLANE_CLAIMS),
        "claims_total": _as_int(summary.get("claims_total")),
        "claims_allowed": _as_int(summary.get("claims_allowed")),
        "claims_blocked": _as_int(summary.get("claims_blocked")),
        "source_artifact_hashes_present": context.get("source_artifact_hashes_present") is True,
        "map_sha256": context.get("map_sha256"),
        "audit_sha256": context.get("audit_sha256"),
        "blocker_ids": _cross_plane_proof_gate_blocker_ids(data),
        "claim_boundary": (
            "The raw-evidence operator packet uses the reusable cross-plane proof gate "
            "as local claim-control evidence. It does not create external DPI, "
            "dataplane, traffic, settlement, or production proof."
        ),
    }


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
    local_production_ready = files_total > 0 and files_production_ready == files_total and raw_ready_for_collectors
    current_evidence_context = _current_evidence_context(root)
    current_evidence_context_hash = _hash_payload(current_evidence_context)
    current_evidence_clear = _current_evidence_clear(current_evidence_context)
    current_evidence_blockers = _current_evidence_blockers(current_evidence_context)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(root)
    cross_plane_proof_gate_allowed = cross_plane_proof_gate.get("allowed") is True
    cross_plane_proof_gate_blockers = list(cross_plane_proof_gate.get("blocker_ids") or [])
    production_ready = local_production_ready and current_evidence_clear and cross_plane_proof_gate_allowed
    decision = "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE" if local_handoff_complete else "RAW_EVIDENCE_OPERATOR_PACKET_INCOMPLETE"
    summary = {
        "packets_total": len(packets),
        "actionable_packets": sum(1 for packet in packets if packet["actionable"]),
        "local_entrypoints_missing": local_entrypoints_missing,
        "local_production_ready": local_production_ready,
        "current_evidence_context_included": current_evidence_context.get("included") is True,
        "current_evidence_context_clear": current_evidence_clear,
        "cross_plane_proof_gate_available": cross_plane_proof_gate.get("loaded") is True,
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
        "cross_plane_proof_gate_claims_blocked": cross_plane_proof_gate.get("claims_blocked"),
        "cross_plane_proof_gate_source_artifact_hashes_present": cross_plane_proof_gate.get(
            "source_artifact_hashes_present"
        ),
        "current_evidence_open_gaps": current_evidence_context.get("current_gap_count"),
        "current_evidence_next_actions": current_evidence_context.get("next_action_count"),
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
        "production_ready_blocked_by_current_evidence": local_production_ready and not current_evidence_clear,
        "production_ready_blocked_by_cross_plane_proof_gate": (
            local_production_ready and current_evidence_clear and not cross_plane_proof_gate_allowed
        ),
    }
    blocked_reason_ids = (
        ([] if local_production_ready else ["raw_operator_packet_not_production_ready"])
        + current_evidence_blockers
        + ([] if cross_plane_proof_gate_allowed else cross_plane_proof_gate_blockers)
    )

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
        "current_evidence_context": current_evidence_context,
        "current_evidence_context_hash": current_evidence_context_hash,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "cross_plane_claim_gate": {
            "surface": "production_raw_evidence_operator_packet",
            "claim_boundary": (
                "This report can allow only a local raw-evidence operator-packet claim unless "
                "current cross-plane evidence context is clear and the reusable proof gate allows "
                "the strong claim set. It cannot prove goal completion, live apply, dataplane "
                "delivery, DPI bypass, traffic delivery, customer traffic, or settlement finality."
            ),
            "local_production_ready": local_production_ready,
            "current_evidence_context_required": True,
            "current_evidence_context_clear": current_evidence_clear,
            "cross_plane_proof_gate_required": True,
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
            "production_ready_claim_allowed": production_ready,
            "blocked_reason_ids": blocked_reason_ids,
            "proof_claims": {
                "goal_completion_authorized": False,
                "dataplane_delivery_confirmed": False,
                "dpi_bypass_confirmed": False,
                "settlement_finality_confirmed": False,
                "live_apply_authorized": False,
            },
        },
        "operator_bundle_root": str(bundle_root),
        "source_artifacts": [
            str(intake_manifest_path),
            str(semantic_readiness_path),
            DEFAULT_READINESS_OUTPUT,
            DEFAULT_PIPELINE_OUTPUT,
            DEFAULT_CURRENT_CROSS_PLANE_MAP,
            DEFAULT_CURRENT_ACTIVE_AUDIT,
            DEFAULT_CROSS_PLANE_PROOF_GATE,
        ],
        "source_errors": [f"{intake_manifest_path}: {manifest_error}"] if manifest_error else [],
        "packets": packets,
        "summary": summary,
        "not_verified_yet": []
        if production_ready
        else (
            [
                "operator must replace every listed bundle file with production_ready=true evidence",
                "production raw-evidence readiness must reach READY_FOR_COLLECTORS",
            ]
            if not local_production_ready
            else []
        )
        + (
            [
                "current cross-plane evidence context must be present, cover all required planes, and have no blocking gaps or next actions",
            ]
            if not current_evidence_clear
            else []
        )
        + (
            [
                "reusable cross-plane proof gate must allow raw operator-packet production claims",
            ]
            if not cross_plane_proof_gate_allowed
            else []
        )
        + ["completion audit must remain NOT_COMPLETE until production closeout passes"],
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
