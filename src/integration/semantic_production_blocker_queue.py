"""Build the integration-spine semantic production blocker queue.

The queue is derived from retained local pipeline artifacts. It describes what
operator/live evidence still has to replace current component evidence; it does
not collect evidence, call live services, mutate runtime, or close the goal.
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
DEFAULT_COVERAGE = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
DEFAULT_CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
EXPECTED_CURRENT_EVIDENCE_STATUS = "working_map_not_production_completion_proof"
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS = (
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
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
BLOCKING = "BLOCKING"

COLLECTOR_LAYERS = {
    "external-settlement": ["settlement_reward_loop", "production_closeout"],
    "self-healing-pqc-mesh": ["identity", "safe_actuator", "production_closeout"],
    "zero-trust-pqc": ["identity", "policy_engine", "production_closeout"],
    "paid-client-serviceability": ["settlement_reward_loop", "safe_actuator", "production_closeout"],
    "live-rollout": ["safe_actuator", "production_closeout"],
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
            "Current cross-plane evidence context is a local gate for this semantic "
            "blocker queue. It is not production proof by itself."
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
    return sorted(set(SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


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
    required_claim_ids = set(SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS)
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
        "required_claim_ids": list(SEMANTIC_QUEUE_CROSS_PLANE_CLAIMS),
        "claims_total": _as_int(summary.get("claims_total")),
        "claims_allowed": _as_int(summary.get("claims_allowed")),
        "claims_blocked": _as_int(summary.get("claims_blocked")),
        "source_artifact_hashes_present": context.get("source_artifact_hashes_present") is True,
        "map_sha256": context.get("map_sha256"),
        "audit_sha256": context.get("audit_sha256"),
        "blocker_ids": _cross_plane_proof_gate_blocker_ids(data),
        "claim_boundary": (
            "The semantic blocker queue uses the reusable cross-plane proof gate as "
            "local claim-control evidence. It does not create external DPI, dataplane, "
            "traffic, settlement, or production proof."
        ),
    }


def _subject_from_name(name: str) -> str:
    return Path(name).stem


def _raw_subject_for_error(error: str, raw_files: List[Dict[str, Any]]) -> tuple[str, str]:
    subjects = [
        (_subject_from_name(str(item.get("name", ""))), str(item.get("path", "")))
        for item in raw_files
        if item.get("name") or item.get("path")
    ]
    for subject, path in subjects:
        if subject and (error == subject or error.startswith(f"{subject} ")):
            return subject, path
    fallback = error.split(" ", 1)[0].strip() or "unknown"
    for subject, path in subjects:
        if subject == fallback:
            return subject, path
    return fallback, ""


def _layers_for(collector_id: str, error: str) -> List[str]:
    layers = list(COLLECTOR_LAYERS.get(collector_id, ["production_closeout"]))
    if "operator-manifest" in error and "identity" not in layers:
        layers.insert(0, "identity")
    if any(marker in error for marker in ("payment", "settlement", "entitlement", "paid")) and "settlement_reward_loop" not in layers:
        layers.append("settlement_reward_loop")
    return sorted(set(layers), key=layers.index)


def _operator_action(subject: str, error: str, path: str) -> str:
    target = path or f"<retained raw path for {subject}>"
    return f"replace {target} with retained production evidence so this check passes: {error}"


def _external_blockers(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    blocking_inputs = [
        item
        for item in _dicts(pipeline.get("blocking_inputs"))
        if item.get("kind") == "external_settlement" or item.get("evidence_key") == "external_settlement"
    ]
    if not blocking_inputs and pipeline.get("summary", {}).get("external_settlement_ready") is False:
        blocking_inputs = [
            {
                "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                "errors": ["submitted external X0T settlement receipt with matching live RPC report is missing"],
                "required_action": "submit/locate real X0T transaction receipt, retain settlement-submit.json, and verify it against live Base RPC",
            }
        ]
    for idx, item in enumerate(blocking_inputs, start=1):
        errors = _strings(item.get("errors")) or ["submitted external X0T settlement receipt with matching live RPC report is missing"]
        items.append(
            {
                "id": f"external_settlement:{idx:03d}",
                "collector_id": "external-settlement",
                "raw_subject": "settlement-submit",
                "raw_evidence_path": item.get("destination_path", ".tmp/external-settlement-evidence/settlement-submit.json"),
                "preflight_error": errors[0],
                "operator_action": item.get("required_action")
                or "submit/locate real X0T transaction receipt, retain settlement-submit.json, and verify it against live Base RPC",
                "layers": COLLECTOR_LAYERS["external-settlement"],
                "status": OPERATOR_INPUT_REQUIRED,
            }
        )
    return items


def _collector_blockers(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for command in _dicts(pipeline.get("command_results")):
        collector_id = str(command.get("collector_id", ""))
        raw_files = _dicts((command.get("stdout_json") or {}).get("raw_files"))
        for idx, error in enumerate(_strings(command.get("preflight_errors")), start=1):
            subject, path = _raw_subject_for_error(error, raw_files)
            items.append(
                {
                    "id": f"{collector_id}:{idx:03d}",
                    "collector_id": collector_id,
                    "raw_subject": subject,
                    "raw_evidence_path": path,
                    "preflight_error": error,
                    "operator_action": _operator_action(subject, error, path),
                    "layers": _layers_for(collector_id, error),
                    "status": OPERATOR_INPUT_REQUIRED,
                }
            )
    return items


@dataclass(frozen=True)
class QueueInputs:
    root: Path
    pipeline_path: Path
    coverage_path: Path
    return_acceptance_path: Path
    pipeline_display: str = DEFAULT_PIPELINE
    coverage_display: str = DEFAULT_COVERAGE
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE


def build_queue(inputs: QueueInputs) -> Dict[str, Any]:
    pipeline = _read_json(inputs.pipeline_path)
    coverage = _read_json(inputs.coverage_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    source_errors: List[str] = []
    if pipeline is None:
        source_errors.append(f"missing or unreadable production input pipeline: {inputs.pipeline_display}")
        pipeline = {}
    if coverage is None:
        source_errors.append(f"missing or unreadable objective coverage audit: {inputs.coverage_display}")
        coverage = {}
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable production input return acceptance: {inputs.return_acceptance_display}")
        return_acceptance = {}
    elif return_acceptance.get("status") != "VERIFIED HERE" or return_acceptance.get("ok") is not True:
        source_errors.append("production input return acceptance status must be VERIFIED HERE and ok true")

    blocking_items = _external_blockers(pipeline) + _collector_blockers(pipeline)
    by_collector: Dict[str, int] = {}
    by_layer: Dict[str, int] = {}
    item_status_counts: Dict[str, int] = {}
    for item in blocking_items:
        collector_id = str(item.get("collector_id", ""))
        by_collector[collector_id] = by_collector.get(collector_id, 0) + 1
        item_status = str(item.get("status", ""))
        item_status_counts[item_status] = item_status_counts.get(item_status, 0) + 1
        for layer in _strings(item.get("layers")):
            by_layer[layer] = by_layer.get(layer, 0) + 1

    pipeline_summary = _summary(pipeline)
    coverage_summary = _summary(coverage)
    return_summary = _summary(return_acceptance)
    semantic_preflight_errors_total = sum(1 for item in blocking_items if item.get("collector_id") != "external-settlement")
    raw_ready = return_summary.get("raw_ready_to_stage") is True
    local_queue_clear = not blocking_items and not source_errors and raw_ready
    current_evidence_context = _current_evidence_context(inputs.root)
    current_evidence_context_hash = _hash_payload(current_evidence_context)
    current_evidence_clear = _current_evidence_clear(current_evidence_context)
    current_evidence_blockers = _current_evidence_blockers(current_evidence_context)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(inputs.root)
    cross_plane_proof_gate_allowed = cross_plane_proof_gate.get("allowed") is True
    cross_plane_proof_gate_blockers = list(cross_plane_proof_gate.get("blocker_ids") or [])
    complete = local_queue_clear and current_evidence_clear and cross_plane_proof_gate_allowed
    if complete:
        completion_decision = "COMPLETE"
    elif local_queue_clear:
        completion_decision = (
            "BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
            if not current_evidence_clear
            else "BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
        )
    else:
        completion_decision = "NOT_COMPLETE"
    blocked_reason_ids = (
        ([] if local_queue_clear else ["semantic_blocker_queue_not_clear"])
        + current_evidence_blockers
        + ([] if cross_plane_proof_gate_allowed else cross_plane_proof_gate_blockers)
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-semantic-production-blocker-queue-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": completion_decision,
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Generated from current retained pipeline/objective audit artifacts. "
            "Does not create or upgrade production evidence."
        ),
        "current_evidence_context": current_evidence_context,
        "current_evidence_context_hash": current_evidence_context_hash,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "cross_plane_claim_gate": {
            "surface": "integration_spine_semantic_production_blocker_queue",
            "claim_boundary": (
                "This report can allow only a local semantic blocker queue claim unless "
                "current cross-plane evidence context is clear and the reusable proof gate "
                "allows the strong claim set. It cannot prove production readiness, dataplane "
                "delivery, traffic delivery, DPI bypass, settlement finality, or live apply."
            ),
            "local_queue_clear": local_queue_clear,
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
            inputs.pipeline_display,
            inputs.coverage_display,
            inputs.return_acceptance_display,
            DEFAULT_CURRENT_CROSS_PLANE_MAP,
            DEFAULT_CURRENT_ACTIVE_AUDIT,
            DEFAULT_CROSS_PLANE_PROOF_GATE,
        ],
        "source_errors": source_errors,
        "blocking_items": blocking_items,
        "priority_order": [str(item.get("id", "")) for item in blocking_items if item.get("id")],
        "not_verified_yet": []
        if complete
        else (
            [
                "operator/live production evidence must clear every semantic preflight blocker",
                "external settlement receipt must be retained and verified against live RPC",
            ]
            if not local_queue_clear
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
                "reusable cross-plane proof gate must allow semantic blocker queue completion claims",
            ]
            if not cross_plane_proof_gate_allowed
            else []
        ),
        "summary": {
            "local_queue_clear": local_queue_clear,
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
            "goal_completion_blocked_by_current_evidence": local_queue_clear and not current_evidence_clear,
            "goal_completion_blocked_by_cross_plane_proof_gate": (
                local_queue_clear and current_evidence_clear and not cross_plane_proof_gate_allowed
            ),
            "blocking_items_total": len(blocking_items),
            "blocking_items_operator_input_required": item_status_counts.get(OPERATOR_INPUT_REQUIRED, 0),
            "blocking_items_generic_blocking": item_status_counts.get(BLOCKING, 0),
            "semantic_preflight_errors_total": semantic_preflight_errors_total,
            "external_settlement_blockers": by_collector.get("external-settlement", 0),
            "collector_groups_blocking": sum(1 for key, count in by_collector.items() if key != "external-settlement" and count > 0),
            "current_collector_evidence_blockers": pipeline_summary.get(
                "collector_evidence_blockers",
                coverage_summary.get("current_collector_evidence_blockers", 0),
            ),
            "current_external_settlement_ready": pipeline_summary.get(
                "external_settlement_ready",
                coverage_summary.get("current_external_settlement_ready", False),
            ),
            "current_raw_files_expected": return_summary.get(
                "raw_files_expected",
                pipeline_summary.get("raw_files_expected", coverage_summary.get("current_raw_files_expected", 0)),
            ),
            "current_raw_files_installed": return_summary.get("raw_files_staged", 0),
            "raw_install_claim_source": "return_acceptance",
            "pipeline_raw_files_reported_installed": pipeline_summary.get(
                "raw_files_installed",
                coverage_summary.get("current_raw_files_installed", 0),
            ),
            "return_acceptance_raw_files_ready_to_stage": return_summary.get("raw_files_ready_to_stage", 0),
            "return_acceptance_raw_files_destination_existing": return_summary.get("raw_files_destination_existing", 0),
            "return_acceptance_raw_files_local_observation": return_summary.get("raw_files_local_observation", 0),
            "return_acceptance_raw_ready_to_stage": raw_ready,
            "by_collector": by_collector,
            "by_layer": by_layer,
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
    parser = argparse.ArgumentParser(description="Build the integration-spine semantic production blocker queue")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-clear", action="store_true", help="return 2 unless no semantic blockers remain")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_queue(
        QueueInputs(
            root=root,
            pipeline_path=_resolve(root, args.pipeline),
            coverage_path=_resolve(root, args.coverage),
            return_acceptance_path=_resolve(root, args.return_acceptance),
            pipeline_display=args.pipeline,
            coverage_display=args.coverage,
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
    if args.require_clear and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
