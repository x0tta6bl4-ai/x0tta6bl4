"""Build the integration-spine raw evidence inventory.

The inventory classifies retained raw evidence files against the current
semantic production blocker queue. It is read-only and cannot promote component
evidence to production proof by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json"
DEFAULT_CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
DEFAULT_CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
EXPECTED_CURRENT_EVIDENCE_STATUS = "working_map_not_production_completion_proof"
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS = (
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


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
            "inventory. It is not production proof by itself."
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
    return sorted(set(RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


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
    required_claim_ids = set(RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS)
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
    data = _read_json(path)
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
        "required_claim_ids": list(RAW_EVIDENCE_INVENTORY_CROSS_PLANE_CLAIMS),
        "claims_total": _as_int(summary.get("claims_total")),
        "claims_allowed": _as_int(summary.get("claims_allowed")),
        "claims_blocked": _as_int(summary.get("claims_blocked")),
        "source_artifact_hashes_present": context.get("source_artifact_hashes_present") is True,
        "map_sha256": context.get("map_sha256"),
        "audit_sha256": context.get("audit_sha256"),
        "blocker_ids": _cross_plane_proof_gate_blocker_ids(data),
        "claim_boundary": (
            "The raw-evidence inventory uses the reusable cross-plane proof gate as "
            "local claim-control evidence. It does not create external DPI, dataplane, "
            "traffic, settlement, or production proof."
        ),
    }


def _collector_counts(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for record in records:
        collector = str(record.get("collector", ""))
        classification = str(record.get("classification", ""))
        result.setdefault(collector, {})
        result[collector][classification] = result[collector].get(classification, 0) + 1
    return result


def _status(data: Dict[str, Any]) -> Any:
    return data.get("evidence_status", data.get("status"))


def _explicit_bool(data: Dict[str, Any], key: str) -> bool:
    return data.get(key) is True or data.get(f"_{key}") is True


def _blockers_by_path(semantic_queue: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for item in _dicts(semantic_queue.get("blocking_items")):
        path = str(item.get("raw_evidence_path", ""))
        if path:
            result.setdefault(path, []).append(item)
    return result


def _record(root: Path, install: Dict[str, Any], blockers_by_path: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    display_path = str(install.get("destination_path", ""))
    path = Path(display_path)
    data = _read_json(path if path.is_absolute() else root / path) or {}
    blockers = blockers_by_path.get(display_path, [])
    production_promotion_blockers = _strings(data.get("production_promotion_blockers"))
    template_only = _explicit_bool(data, "template_only") or data.get("_not_evidence") is True
    fake_or_simulated = _explicit_bool(data, "fake_or_simulated")
    semantic_errors = [str(item.get("preflight_error", "")) for item in blockers if item.get("preflight_error")]
    explicit_production_ready = data.get("production_ready") is True or data.get("production_claim") is True
    verified_here_component = data.get("evidence_status") == "VERIFIED HERE" and data.get("status") == "VERIFIED HERE"

    if template_only:
        classification = "TEMPLATE_ONLY"
    elif fake_or_simulated:
        classification = "FAKE_OR_SIMULATED"
    elif blockers or production_promotion_blockers or not explicit_production_ready:
        classification = "RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE"
    else:
        classification = "PRODUCTION_GRADE"
    usable = classification == "PRODUCTION_GRADE"

    return {
        "path": display_path,
        "collector": install.get("collector_id", ""),
        "subject": Path(display_path).stem,
        "status": data.get("status", "NOT_FOUND" if not data else ""),
        "evidence_status": _status(data) or ("NOT_FOUND" if not data else ""),
        "environment": data.get("environment"),
        "template_only": template_only,
        "fake_or_simulated": fake_or_simulated,
        "verified_here_component_evidence": verified_here_component,
        "production_promotion_blockers_total": len(production_promotion_blockers),
        "semantic_blockers_total": len(blockers),
        "semantic_blocker_ids": [str(item.get("id", "")) for item in blockers if item.get("id")],
        "semantic_preflight_errors": semantic_errors,
        "classification": classification,
        "usable_for_goal_completion": usable,
        "claim_boundary_blocks_production_promotion": not usable,
    }


@dataclass(frozen=True)
class InventoryInputs:
    root: Path
    pipeline_path: Path
    semantic_queue_path: Path
    return_acceptance_path: Path
    pipeline_display: str = DEFAULT_PIPELINE
    semantic_queue_display: str = DEFAULT_SEMANTIC_QUEUE
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE


def build_inventory(inputs: InventoryInputs) -> Dict[str, Any]:
    pipeline = _read_json(inputs.pipeline_path)
    semantic_queue = _read_json(inputs.semantic_queue_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    source_errors: List[str] = []
    if pipeline is None:
        source_errors.append(f"missing or unreadable production input pipeline: {inputs.pipeline_display}")
        pipeline = {}
    if semantic_queue is None:
        source_errors.append(f"missing or unreadable semantic blocker queue: {inputs.semantic_queue_display}")
        semantic_queue = {}
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable production input return acceptance: {inputs.return_acceptance_display}")
        return_acceptance = {}
    elif return_acceptance.get("status") != "VERIFIED HERE" or return_acceptance.get("ok") is not True:
        source_errors.append("production input return acceptance status must be VERIFIED HERE and ok true")

    blockers = _blockers_by_path(semantic_queue)
    records = [
        _record(inputs.root, item, blockers)
        for item in _dicts(pipeline.get("raw_install_results"))
        if item.get("destination_path")
    ]
    usable = [item for item in records if item.get("usable_for_goal_completion") is True]
    semantic_blocking_files = [item for item in records if item.get("semantic_blockers_total", 0) > 0]
    pipeline_summary = _summary(pipeline)
    return_summary = _summary(return_acceptance)
    files_total = len(records)
    return_raw_expected = _int_value(return_summary, "raw_files_expected")
    return_raw_staged = _int_value(return_summary, "raw_files_staged")
    return_raw_ready_to_stage = _int_value(return_summary, "raw_files_ready_to_stage")
    return_raw_local_observation = _int_value(return_summary, "raw_files_local_observation")
    return_raw_destination_existing = _int_value(return_summary, "raw_files_destination_existing")
    return_raw_ready = return_summary.get("raw_ready_to_stage") is True
    return_acceptance_covers_records = return_raw_expected == files_total and return_raw_staged == files_total
    local_inventory_clear = (
        bool(records)
        and len(usable) == files_total
        and not source_errors
        and return_acceptance_covers_records
        and return_raw_ready
        and return_raw_local_observation == 0
    )
    current_evidence_context = _current_evidence_context(inputs.root)
    current_evidence_context_hash = _hash_payload(current_evidence_context)
    current_evidence_clear = _current_evidence_clear(current_evidence_context)
    current_evidence_blockers = _current_evidence_blockers(current_evidence_context)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(inputs.root)
    cross_plane_proof_gate_allowed = cross_plane_proof_gate.get("allowed") is True
    cross_plane_proof_gate_blockers = list(cross_plane_proof_gate.get("blocker_ids") or [])
    complete = local_inventory_clear and current_evidence_clear and cross_plane_proof_gate_allowed
    if complete:
        completion_decision = "COMPLETE"
    elif local_inventory_clear:
        completion_decision = (
            "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
            if not current_evidence_clear
            else "BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
        )
    else:
        completion_decision = "NOT_COMPLETE"
    blocked_reason_ids = (
        ([] if local_inventory_clear else ["raw_evidence_inventory_not_clear"])
        + current_evidence_blockers
        + ([] if cross_plane_proof_gate_allowed else cross_plane_proof_gate_blockers)
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-raw-evidence-inventory-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": completion_decision,
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Inventory of current retained raw evidence files for the four semantic production collectors. "
            "It classifies evidence; it does not create production proof or upgrade readiness."
        ),
        "current_evidence_context": current_evidence_context,
        "current_evidence_context_hash": current_evidence_context_hash,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "cross_plane_claim_gate": {
            "surface": "integration_spine_raw_evidence_inventory",
            "claim_boundary": (
                "This report can allow only a local raw-evidence inventory claim unless current "
                "cross-plane evidence context is clear and the reusable proof gate allows the "
                "strong claim set. It cannot prove production readiness, dataplane delivery, "
                "traffic delivery, DPI bypass, settlement finality, goal completion, or live apply."
            ),
            "local_inventory_clear": local_inventory_clear,
            "current_evidence_context_required": True,
            "current_evidence_context_clear": current_evidence_clear,
            "cross_plane_proof_gate_required": True,
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
            "goal_completion_claim_allowed": complete,
            "blocked_reason_ids": blocked_reason_ids,
            "proof_claims": {
                "production_ready": False,
                "dataplane_delivery_confirmed": False,
                "dpi_bypass_confirmed": False,
                "settlement_finality_confirmed": False,
                "live_apply_authorized": False,
            },
        },
        "source_artifacts": [
            inputs.semantic_queue_display,
            inputs.pipeline_display,
            inputs.return_acceptance_display,
            DEFAULT_CURRENT_CROSS_PLANE_MAP,
            DEFAULT_CURRENT_ACTIVE_AUDIT,
            DEFAULT_CROSS_PLANE_PROOF_GATE,
        ],
        "source_errors": source_errors,
        "records": records,
        "not_verified_yet": []
        if complete
        else (
            [
                "retained raw evidence files must be production-grade and free of semantic blockers",
                "production input return acceptance must report ready staged raw evidence with no local observations",
            ]
            if not local_inventory_clear
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
                "reusable cross-plane proof gate must allow raw-evidence inventory completion claims",
            ]
            if not cross_plane_proof_gate_allowed
            else []
        ),
        "summary": {
            "local_inventory_clear": local_inventory_clear,
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
            "goal_completion_blocked_by_current_evidence": local_inventory_clear and not current_evidence_clear,
            "goal_completion_blocked_by_cross_plane_proof_gate": (
                local_inventory_clear and current_evidence_clear and not cross_plane_proof_gate_allowed
            ),
            "files_total": files_total,
            "pipeline_raw_files_expected": pipeline_summary.get("raw_files_expected", files_total),
            "pipeline_raw_files_installed": pipeline_summary.get("raw_files_installed", files_total),
            "pipeline_raw_files_reported_installed": pipeline_summary.get("raw_files_installed", files_total),
            "raw_install_claim_source": "return_acceptance",
            "return_acceptance_raw_files_expected": return_raw_expected,
            "return_acceptance_raw_files_staged": return_raw_staged,
            "return_acceptance_raw_files_ready_to_stage": return_raw_ready_to_stage,
            "return_acceptance_raw_files_destination_existing": return_raw_destination_existing,
            "return_acceptance_raw_files_local_observation": return_raw_local_observation,
            "return_acceptance_raw_ready_to_stage": return_raw_ready,
            "return_acceptance_covers_records": return_acceptance_covers_records,
            "classification_counts": _count_by(records, "classification"),
            "collector_classification_counts": _collector_counts(records),
            "template_only_files": sum(1 for item in records if item.get("template_only") is True),
            "fake_or_simulated_files": sum(1 for item in records if item.get("fake_or_simulated") is True),
            "usable_for_goal_completion_files": len(usable),
            "semantic_blockers_total": sum(int(item.get("semantic_blockers_total", 0)) for item in records),
            "semantic_blocking_files": len(semantic_blocking_files),
            "verified_here_component_files": sum(1 for item in records if item.get("verified_here_component_evidence") is True),
            "source_errors_total": len(source_errors),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the integration-spine raw evidence inventory")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless every retained raw file is production-grade")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_inventory(
        InventoryInputs(
            root=root,
            pipeline_path=_resolve(root, args.pipeline),
            semantic_queue_path=_resolve(root, args.semantic_queue),
            return_acceptance_path=_resolve(root, args.return_acceptance),
            pipeline_display=args.pipeline,
            semantic_queue_display=args.semantic_queue,
            return_acceptance_display=args.return_acceptance,
        )
    )
    write_json(_resolve(root, args.output_json), report)
    print(
        json.dumps(
            {
                "completion_decision": report["completion_decision"],
                "goal_can_be_marked_complete": report["goal_can_be_marked_complete"],
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
