"""Read-only completion gate runner for the integration spine.

The runner joins the current production input, consistency, closeout, final
review, coverage, and completion audit shards. It replaces the old
source-restored runner artifact with a repo-generated fail-closed report. It
does not execute collectors, stage evidence, contact live systems, mutate
runtime, submit transactions, or close the goal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
DEFAULT_PRODUCTION_INPUT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_PRODUCTION_INPUT_RETURN_PACKET = ".tmp/validation-shards/integration-spine-production-input-return-packet-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_REQUIRED_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_ROLLUP_CONTRACT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_CLOSEOUT_REVIEW = ".tmp/validation-shards/integration-spine-production-closeout-review-current.json"
DEFAULT_CLOSURE_PREFLIGHT = ".tmp/validation-shards/integration-spine-production-closure-preflight-current.json"
DEFAULT_FINAL_REVIEW = ".tmp/validation-shards/integration-spine-production-final-review-current.json"
DEFAULT_OBJECTIVE_COVERAGE = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"
DEFAULT_COMPLETION_AUDIT = ".tmp/validation-shards/integration-spine-completion-audit-current.json"
DEFAULT_CURRENT_ROLLUP = ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
DEFAULT_PRODUCTION_GAP_INDEX = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_GOVERNANCE_EXECUTE_READINESS = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
DEFAULT_CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
DEFAULT_CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
EXPECTED_CURRENT_EVIDENCE_STATUS = "working_map_not_production_completion_proof"
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
COMPLETION_GATE_CROSS_PLANE_CLAIMS = (
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


@dataclass(frozen=True)
class SourceSpec:
    label: str
    path: str
    decision_keys: List[str]
    ready_decision: str
    ready_path: str


SOURCE_SPECS = [
    SourceSpec(
        "production_input_pipeline",
        DEFAULT_PRODUCTION_INPUT_PIPELINE,
        ["pipeline_decision", "decision"],
        "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
        "ready",
    ),
    SourceSpec(
        "required_evidence_consistency",
        DEFAULT_REQUIRED_CONSISTENCY,
        ["decision"],
        "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR",
        "production_ready",
    ),
    SourceSpec(
        "rollup_approval_contract",
        DEFAULT_ROLLUP_CONTRACT,
        ["decision"],
        "ROLLUP_APPROVAL_READY",
        "ready",
    ),
    SourceSpec(
        "production_closeout_review",
        DEFAULT_CLOSEOUT_REVIEW,
        ["decision"],
        "CLOSEOUT_REVIEW_READY",
        "ready",
    ),
    SourceSpec(
        "closure_preflight",
        DEFAULT_CLOSURE_PREFLIGHT,
        ["decision"],
        "PREFLIGHT_READY_FOR_FINAL_REVIEW",
        "ready",
    ),
    SourceSpec(
        "final_review",
        DEFAULT_FINAL_REVIEW,
        ["decision"],
        "FINAL_REVIEW_READY",
        "ready",
    ),
    SourceSpec(
        "objective_coverage",
        DEFAULT_OBJECTIVE_COVERAGE,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "completion_audit",
        DEFAULT_COMPLETION_AUDIT,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "current_rollup",
        DEFAULT_CURRENT_ROLLUP,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "production_gap_index",
        DEFAULT_PRODUCTION_GAP_INDEX,
        ["decision"],
        "NO_PRODUCTION_EVIDENCE_GAPS",
        "goal_can_be_marked_complete",
    ),
]


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
            "Current cross-plane evidence context is a local gate for the completion gate runner. "
            "It is not production proof by itself."
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


def _cross_plane_proof_gate_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    claim_ids: List[str] = []
    for result in _dicts((data or {}).get("claim_results")):
        claim_id = result.get("claim_id")
        if isinstance(claim_id, str) and claim_id:
            claim_ids.append(claim_id)
    return sorted(set(claim_ids))


def _cross_plane_proof_gate_missing_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    return sorted(set(COMPLETION_GATE_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


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
        blockers.extend(str(item) for item in result.get("blockers") or [] if item)
    return sorted(set(blockers))


def _cross_plane_proof_gate_allowed(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False
    required_claim_ids = set(COMPLETION_GATE_CROSS_PLANE_CLAIMS)
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
        and _value(data, "context.source_artifact_hashes_present") is True
    )


def _cross_plane_proof_gate_context(root: Path) -> Dict[str, Any]:
    path = root / DEFAULT_CROSS_PLANE_PROOF_GATE
    data = _read_json(path)
    context = data.get("context") if isinstance(data, dict) else {}
    if not isinstance(context, dict):
        context = {}
    summary = _summary(data)
    blocker_ids = _cross_plane_proof_gate_blocker_ids(data)
    return {
        "path": DEFAULT_CROSS_PLANE_PROOF_GATE,
        "exists": path.exists(),
        "loaded": isinstance(data, dict),
        "schema": (data or {}).get("schema"),
        "decision": (data or {}).get("decision"),
        "allowed": _cross_plane_proof_gate_allowed(data),
        "reported_claim_ids": _cross_plane_proof_gate_claim_ids(data),
        "required_claim_ids": list(COMPLETION_GATE_CROSS_PLANE_CLAIMS),
        "claims_total": _int_value(summary, "claims_total"),
        "claims_allowed": _int_value(summary, "claims_allowed"),
        "claims_blocked": _int_value(summary, "claims_blocked"),
        "source_artifact_hashes_present": context.get("source_artifact_hashes_present") is True,
        "map_sha256": context.get("map_sha256"),
        "audit_sha256": context.get("audit_sha256"),
        "blocker_ids": blocker_ids,
        "claim_boundary": (
            "The completion gate uses the reusable cross-plane proof gate as local "
            "claim-control evidence. It still does not create external DPI, dataplane, "
            "traffic, settlement, or production proof."
        ),
    }


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _value(data: Optional[Dict[str, Any]], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _first_present(*lookups: tuple[Dict[str, Any], str], default: Any = None) -> Any:
    for data, key in lookups:
        if key in data:
            return data.get(key)
    return default


def _first_int(*lookups: tuple[Dict[str, Any], str]) -> int:
    value = _first_present(*lookups)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _source_decision(data: Optional[Dict[str, Any]], keys: Iterable[str]) -> str:
    for key in keys:
        value = (data or {}).get(key)
        if value:
            return str(value)
    return ""


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _source_report(root: Path, spec: SourceSpec) -> Dict[str, Any]:
    data = _read_json(_resolve(root, spec.path))
    if data is None:
        return {
            "label": spec.label,
            "path": spec.path,
            "status": "MISSING",
            "ok": False,
            "decision": "",
            "expected_decision": spec.ready_decision,
            "ready": False,
            "errors": [f"missing or unreadable source artifact: {spec.path}"],
        }
    decision = _source_decision(data, spec.decision_keys)
    ready = (
        data.get("status") == "VERIFIED HERE"
        and data.get("ok") is True
        and decision == spec.ready_decision
        and _value(data, spec.ready_path) is True
    )
    errors: List[str] = []
    if data.get("status") != "VERIFIED HERE":
        errors.append("source status must be VERIFIED HERE")
    if data.get("ok") is not True:
        errors.append("source ok must be true")
    if decision != spec.ready_decision:
        errors.append(f"decision must be {spec.ready_decision}")
    if _value(data, spec.ready_path) is not True:
        errors.append(f"{spec.ready_path} must be true")
    return {
        "label": spec.label,
        "path": spec.path,
        "schema_version": data.get("schema_version", ""),
        "status": data.get("status", ""),
        "ok": data.get("ok"),
        "decision": decision,
        "expected_decision": spec.ready_decision,
        "ready": ready,
        "errors": [] if ready else errors,
    }


def build_report(root: Path) -> Dict[str, Any]:
    source_reports = [_source_report(root, spec) for spec in SOURCE_SPECS]
    source_errors = [
        error
        for report in source_reports
        for error in report.get("errors", [])
        if report.get("status") == "MISSING"
        or error.startswith("source status")
        or error.startswith("source ok")
    ]
    steps_ready = sum(1 for report in source_reports if report.get("ready") is True)
    steps_total = len(source_reports)
    local_completion_ready = not source_errors and steps_ready == steps_total
    current_evidence_context = _current_evidence_context(root)
    current_evidence_context_hash = _hash_payload(current_evidence_context)
    current_evidence_clear = _current_evidence_clear(current_evidence_context)
    current_evidence_blockers = _current_evidence_blockers(current_evidence_context)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(root)
    cross_plane_proof_gate_allowed = cross_plane_proof_gate.get("allowed") is True
    cross_plane_proof_gate_blockers = list(cross_plane_proof_gate.get("blocker_ids") or [])
    complete = local_completion_ready and current_evidence_clear and cross_plane_proof_gate_allowed

    pipeline = _read_json(root / DEFAULT_PRODUCTION_INPUT_PIPELINE) or {}
    pipeline_summary = _summary(pipeline)
    return_packet = _read_json(root / DEFAULT_PRODUCTION_INPUT_RETURN_PACKET)
    return_packet_summary = _summary(return_packet)
    return_acceptance = _read_json(root / DEFAULT_RETURN_ACCEPTANCE) or {}
    return_summary = _summary(return_acceptance)
    consistency = _read_json(root / DEFAULT_REQUIRED_CONSISTENCY) or {}
    consistency_summary = _summary(consistency)
    closeout = _read_json(root / DEFAULT_CLOSEOUT_REVIEW) or {}
    closeout_summary = _summary(closeout)
    coverage = _read_json(root / DEFAULT_OBJECTIVE_COVERAGE) or {}
    coverage_summary = _summary(coverage)
    completion = _read_json(root / DEFAULT_COMPLETION_AUDIT) or {}
    completion_summary = _summary(completion)
    current_rollup = _read_json(root / DEFAULT_CURRENT_ROLLUP) or {}
    current_rollup_summary = _summary(current_rollup)
    governance_execute = _read_json(root / DEFAULT_GOVERNANCE_EXECUTE_READINESS) or {}
    governance_summary = _summary(governance_execute)

    raw_expected = _int_value(return_summary, "raw_files_expected") or _int_value(pipeline_summary, "raw_files_expected")
    raw_staged = _int_value(return_summary, "raw_files_staged")
    external_ready = return_summary.get("external_settlement_live_rpc_ready") is True
    governance_proposal_state = governance_execute.get("proposal_state", {})
    if not isinstance(governance_proposal_state, dict):
        governance_proposal_state = {}
    governance_timelock = governance_execute.get("timelock", {})
    if not isinstance(governance_timelock, dict):
        governance_timelock = {}
    governance_executed = (
        governance_execute.get("decision") == "ALREADY_EXECUTED"
        and governance_proposal_state.get("executed") is True
        and governance_proposal_state.get("vetoed") is False
    )
    not_verified_yet: List[str] = []
    if not local_completion_ready:
        not_verified_yet.extend(
            [
                "external X0T settlement live RPC receipt is ready",
                f"{raw_expected} raw evidence files are replaced by production-grade retained evidence",
                "X0T governance proposal execute receipt and final Executed state are retained",
                "objective coverage, required consistency, rollup, closeout, final review, and completion audit are complete",
            ]
        )
    if not current_evidence_clear:
        not_verified_yet.append(
            "current cross-plane evidence context must be present and have zero blocking gaps or next actions"
        )
    if not cross_plane_proof_gate_allowed:
        not_verified_yet.append(
            "reusable cross-plane proof gate must allow production, dataplane, traffic, settlement, and DPI claims"
        )
    blocked_reason_ids = (
        ([] if local_completion_ready else ["completion_gate_sources_not_locally_ready"])
        + current_evidence_blockers
        + ([] if cross_plane_proof_gate_allowed else cross_plane_proof_gate_blockers)
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-completion-gate-runner-v6-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "local_completion_ready": local_completion_ready,
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Repo-generated read-only completion gate runner. It joins current gate artifacts "
            "and refuses completion until every production evidence gate is ready. It does not "
            "run collectors, stage files, contact live systems, mutate runtime, submit "
            "transactions, or close /goal."
        ),
        "current_evidence_context": current_evidence_context,
        "current_evidence_context_hash": current_evidence_context_hash,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "cross_plane_claim_gate": {
            "surface": "completion_gate_runner",
            "local_completion_ready": local_completion_ready,
            "goal_completion_claim_allowed": complete,
            "current_evidence_context_required": True,
            "current_evidence_context_clear": current_evidence_clear,
            "cross_plane_proof_gate_required": True,
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
            "blocked_reason_ids": blocked_reason_ids,
            "proof_claims": {
                "production_ready": False,
                "goal_completion_authorized": False,
                "dataplane_delivery_confirmed": False,
                "external_dpi_bypass_confirmed": False,
                "settlement_finality_confirmed": False,
                "live_apply_authorized": False,
            },
            "claim_boundary": (
                "The completion runner aggregates local gate reports. It does not prove live "
                "customer traffic, dataplane delivery, external DPI bypass, settlement finality, "
                "or live-apply authorization."
            ),
        },
        "source_artifacts": [spec.path for spec in SOURCE_SPECS]
        + [
            DEFAULT_PRODUCTION_INPUT_RETURN_PACKET,
            DEFAULT_RETURN_ACCEPTANCE,
            DEFAULT_GOVERNANCE_EXECUTE_READINESS,
            DEFAULT_CROSS_PLANE_PROOF_GATE,
            DEFAULT_CURRENT_CROSS_PLANE_MAP,
            DEFAULT_CURRENT_ACTIVE_AUDIT,
        ],
        "source_errors": source_errors,
        "source_reports": source_reports,
        "not_verified_yet": not_verified_yet,
        "summary": {
            "local_completion_ready": local_completion_ready,
            "current_evidence_context_included": current_evidence_context.get("included") is True,
            "current_evidence_context_clear": current_evidence_clear,
            "cross_plane_proof_gate_available": cross_plane_proof_gate.get("loaded") is True,
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
            "cross_plane_proof_gate_claims_blocked": cross_plane_proof_gate.get("claims_blocked"),
            "cross_plane_proof_gate_source_artifact_hashes_present": cross_plane_proof_gate.get(
                "source_artifact_hashes_present"
            ),
            "completion_blocked_by_cross_plane_proof_gate": (
                local_completion_ready and current_evidence_clear and not cross_plane_proof_gate_allowed
            ),
            "current_evidence_open_gaps": current_evidence_context.get("current_gap_count"),
            "current_evidence_next_actions": current_evidence_context.get("next_action_count"),
            "completion_blocked_by_current_evidence": local_completion_ready and not current_evidence_clear,
            "steps_total": steps_total,
            "steps_ready": steps_ready,
            "steps_blocked_expected": steps_total - steps_ready,
            "steps_failed_unexpected": len(source_errors),
            "production_input_blocking_inputs_total": pipeline_summary.get("blocking_inputs_total", 0),
            "production_input_blocking_external_inputs": pipeline_summary.get("blocking_external_inputs", 0),
            "production_input_blocking_raw_inputs": pipeline_summary.get("blocking_raw_inputs", 0),
            "production_input_return_packet_available": return_packet is not None,
            "production_input_return_packet_decision": (return_packet or {}).get("decision", ""),
            "production_input_return_packet_blocking_inputs_total": _int_value(
                return_packet_summary,
                "blocking_inputs_total",
            ),
            "production_input_return_packet_blocking_raw_inputs": _int_value(
                return_packet_summary,
                "blocking_raw_inputs",
            ),
            "production_input_return_packet_blocking_external_inputs": _int_value(
                return_packet_summary,
                "blocking_external_inputs",
            ),
            "production_input_return_packet_blocking_inputs_operator_input_required": _int_value(
                return_packet_summary,
                "blocking_inputs_operator_input_required",
            ),
            "production_input_return_packet_blocking_inputs_generic_operator_required": _int_value(
                return_packet_summary,
                "blocking_inputs_generic_operator_required",
            ),
            "production_input_return_packet_operator_next_actions_total": _int_value(
                return_packet_summary,
                "operator_next_actions_total",
            ),
            "production_input_return_packet_operator_next_actions_operator_input_required": _int_value(
                return_packet_summary,
                "operator_next_actions_operator_input_required",
            ),
            "production_input_return_packet_operator_next_actions_generic_blocking": _int_value(
                return_packet_summary,
                "operator_next_actions_generic_blocking",
            ),
            "production_input_return_packet_raw_files_expected": _int_value(
                return_packet_summary,
                "raw_files_expected",
            ),
            "production_input_return_packet_raw_files_missing": _int_value(
                return_packet_summary,
                "raw_files_missing",
            ),
            "production_input_return_packet_raw_files_local_observation": _int_value(
                return_packet_summary,
                "raw_files_local_observation",
            ),
            "production_input_return_packet_external_artifacts_operator_required": _int_value(
                return_packet_summary,
                "external_artifacts_operator_required",
            ),
            "collector_evidence_blockers": pipeline_summary.get("collector_evidence_blockers", 0),
            "external_settlement_ready": external_ready,
            "external_settlement_live_rpc_ready": external_ready,
            "raw_install_claim_source": "return_acceptance",
            "raw_required_evidence_files_total": raw_expected,
            "raw_required_evidence_files_ready": raw_staged,
            "required_evidence_files_total": consistency_summary.get("required_evidence_files_total", 0),
            "required_evidence_files_ready": consistency_summary.get("required_evidence_files_ready", 0),
            "raw_operator_packet_readiness_decision": consistency_summary.get(
                "raw_operator_packet_readiness_decision",
                coverage_summary.get("raw_operator_packet_readiness_decision"),
            ),
            "raw_operator_packet_readiness_ready_for_collectors": consistency_summary.get(
                "raw_operator_packet_readiness_ready_for_collectors",
                coverage_summary.get("raw_operator_packet_readiness_ready_for_collectors"),
            ),
            "raw_operator_packet_readiness_collectors_ready": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_ready",
                coverage_summary.get("raw_operator_packet_readiness_collectors_ready"),
            ),
            "raw_operator_packet_readiness_collectors_blocked": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_blocked",
                coverage_summary.get("raw_operator_packet_readiness_collectors_blocked"),
            ),
            "raw_operator_packet_readiness_collectors_total": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_total",
                coverage_summary.get("raw_operator_packet_readiness_collectors_total"),
            ),
            "raw_operator_packet_readiness_raw_files_ready": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_ready",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_ready"),
            ),
            "raw_operator_packet_readiness_raw_files_local_observation": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_local_observation",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_local_observation"),
            ),
            "raw_operator_packet_readiness_raw_files_total": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_total",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_total"),
            ),
            "raw_operator_packet_production_ready_blocked_by_raw_readiness": consistency_summary.get(
                "raw_operator_packet_production_ready_blocked_by_raw_readiness",
                coverage_summary.get("raw_operator_packet_production_ready_blocked_by_raw_readiness"),
            ),
            "external_required_evidence_files_total": consistency_summary.get("external_required_evidence_files_total", 0),
            "external_required_evidence_files_ready": consistency_summary.get("external_required_evidence_files_ready", 0),
            "current_raw_files_installed": raw_staged,
            "pipeline_raw_files_reported_installed": pipeline_summary.get("raw_files_installed", 0),
            "coverage_raw_files_reported_installed": coverage_summary.get("current_raw_files_installed", 0),
            "return_acceptance_raw_files_staged": raw_staged,
            "return_acceptance_raw_files_local_observation": return_summary.get("raw_files_local_observation", 0),
            "completion_checklist_total": completion_summary.get("checklist_total", 0),
            "completion_checklist_passed": completion_summary.get("checklist_passed", 0),
            "completion_checklist_blocking": completion_summary.get("checklist_blocking", 0),
            "completion_local_wiring_passed": completion_summary.get("local_wiring_passed", False),
            "completion_production_readiness_passed": completion_summary.get("production_readiness_passed", False),
            "external_settlement_handoff_clear": completion_summary.get("external_settlement_handoff_clear"),
            "external_settlement_handoff_decision": completion_summary.get("external_settlement_handoff_decision"),
            "external_settlement_handoff_ready_for_completion_rerun": completion_summary.get(
                "external_settlement_handoff_ready_for_completion_rerun"
            ),
            "external_settlement_capture_preflight_decision": completion_summary.get(
                "external_settlement_capture_preflight_decision"
            ),
            "external_settlement_handoff_operator_command_entrypoints_missing": completion_summary.get(
                "external_settlement_handoff_operator_command_entrypoints_missing"
            ),
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": completion_summary.get(
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "external_settlement_handoff_operator_command_shell_surface_ready": completion_summary.get(
                "external_settlement_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_governance_execute_decision": governance_execute.get(
                "decision",
                completion_summary.get("x0t_governance_execute_decision"),
            ),
            "x0t_governance_execute_ready_now": governance_summary.get(
                "execute_ready_now",
                completion_summary.get("x0t_governance_execute_ready_now"),
            ),
            "x0t_governance_execute_handoff_decision": completion_summary.get(
                "x0t_governance_execute_handoff_decision"
            ),
            "x0t_governance_execute_handoff_actionable": completion_summary.get(
                "x0t_governance_execute_handoff_actionable"
            ),
            "x0t_governance_ready_for_operator_execute": completion_summary.get(
                "x0t_governance_ready_for_operator_execute"
            ),
            "x0t_governance_handoff_operator_actions_total": completion_summary.get(
                "x0t_governance_handoff_operator_actions_total"
            ),
            "x0t_governance_handoff_operator_commands_total": completion_summary.get(
                "x0t_governance_handoff_operator_commands_total"
            ),
            "x0t_governance_handoff_operator_command_entrypoints_missing": completion_summary.get(
                "x0t_governance_handoff_operator_command_entrypoints_missing"
            ),
            "x0t_governance_handoff_operator_command_surface_ready": completion_summary.get(
                "x0t_governance_handoff_operator_command_surface_ready"
            ),
            "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": completion_summary.get(
                "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "x0t_governance_handoff_operator_command_shell_surface_ready": completion_summary.get(
                "x0t_governance_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_governance_handoff_operator_sequence_ready": completion_summary.get(
                "x0t_governance_handoff_operator_sequence_ready"
            ),
            "x0t_governance_proposal_executed": governance_executed,
            "x0t_governance_state_label": governance_proposal_state.get(
                "state_label",
                completion_summary.get("x0t_governance_state_label"),
            ),
            "x0t_governance_next_executable_after_utc": governance_summary.get(
                "next_executable_after_utc",
                completion_summary.get("x0t_governance_next_executable_after_utc"),
            ),
            "x0t_governance_seconds_until_earliest_execution_by_block_time": governance_timelock.get(
                "seconds_until_earliest_execution_by_block_time",
                completion_summary.get("x0t_governance_seconds_until_earliest_execution_by_block_time"),
            ),
            "x0t_contract_handoff_available": _first_present(
                (closeout_summary, "x0t_contract_handoff_available"),
                (completion_summary, "x0t_contract_handoff_available"),
                (coverage_summary, "closeout_x0t_contract_handoff_available"),
                default=False,
            ),
            "x0t_contract_handoff_decision": _first_present(
                (closeout_summary, "x0t_contract_handoff_decision"),
                (completion_summary, "x0t_contract_handoff_decision"),
                (coverage_summary, "closeout_x0t_contract_handoff_decision"),
                default="",
            ),
            "x0t_contract_handoff_deployment_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_deployment_ready"),
                (completion_summary, "x0t_contract_handoff_deployment_ready"),
                (coverage_summary, "closeout_x0t_contract_handoff_deployment_ready"),
                default=False,
            ),
            "x0t_contract_handoff_approval_value_required": _first_present(
                (closeout_summary, "x0t_contract_handoff_approval_value_required"),
                (completion_summary, "x0t_contract_handoff_approval_value_required"),
                default="",
            ),
            "x0t_contract_handoff_missing_inputs_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_missing_inputs_total"),
                (completion_summary, "x0t_contract_handoff_missing_inputs_total"),
            ),
            "x0t_contract_handoff_operator_actions_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_actions_total"),
                (completion_summary, "x0t_contract_handoff_operator_actions_total"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_actions_total"),
            ),
            "x0t_contract_handoff_operator_approval_required_actions_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_approval_required_actions_total"),
                (completion_summary, "x0t_contract_handoff_operator_approval_required_actions_total"),
            ),
            "x0t_contract_handoff_operator_commands_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_commands_total"),
                (completion_summary, "x0t_contract_handoff_operator_commands_total"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_commands_total"),
            ),
            "x0t_contract_handoff_operator_command_entrypoints_missing": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_command_entrypoints_missing"),
                (completion_summary, "x0t_contract_handoff_operator_command_entrypoints_missing"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_command_entrypoints_missing"),
            ),
            "x0t_contract_handoff_operator_command_surface_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_command_surface_ready"),
                (completion_summary, "x0t_contract_handoff_operator_command_surface_ready"),
                default=False,
            ),
            "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"),
                (completion_summary, "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"),
            ),
            "x0t_contract_handoff_operator_command_shell_surface_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_command_shell_surface_ready"),
                (completion_summary, "x0t_contract_handoff_operator_command_shell_surface_ready"),
                default=False,
            ),
            "x0t_contract_handoff_operator_sequence_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_sequence_ready"),
                (completion_summary, "x0t_contract_handoff_operator_sequence_ready"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_sequence_ready"),
                default=False,
            ),
            "live_rollout_handoff_available": _first_present(
                (closeout_summary, "live_rollout_handoff_available"),
                (completion_summary, "live_rollout_handoff_available"),
                (coverage_summary, "closeout_live_rollout_handoff_available"),
                default=False,
            ),
            "live_rollout_handoff_decision": _first_present(
                (closeout_summary, "live_rollout_handoff_decision"),
                (completion_summary, "live_rollout_handoff_decision"),
                (coverage_summary, "closeout_live_rollout_handoff_decision"),
                default="",
            ),
            "live_rollout_handoff_ready_for_completion_rerun": _first_present(
                (closeout_summary, "live_rollout_handoff_ready_for_completion_rerun"),
                (completion_summary, "live_rollout_handoff_ready_for_completion_rerun"),
                (coverage_summary, "closeout_live_rollout_handoff_ready_for_completion_rerun"),
                default=False,
            ),
            "live_rollout_handoff_can_close_image_digests_blocker": _first_present(
                (closeout_summary, "live_rollout_handoff_can_close_image_digests_blocker"),
                (completion_summary, "live_rollout_handoff_can_close_image_digests_blocker"),
                default=False,
            ),
            "live_rollout_handoff_missing_inputs_total": _first_int(
                (closeout_summary, "live_rollout_handoff_missing_inputs_total"),
                (completion_summary, "live_rollout_handoff_missing_inputs_total"),
            ),
            "live_rollout_handoff_operator_actions_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_actions_total"),
                (completion_summary, "live_rollout_handoff_operator_actions_total"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_actions_total"),
            ),
            "live_rollout_handoff_operator_input_required_actions_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_input_required_actions_total"),
                (completion_summary, "live_rollout_handoff_operator_input_required_actions_total"),
            ),
            "live_rollout_handoff_operator_commands_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_commands_total"),
                (completion_summary, "live_rollout_handoff_operator_commands_total"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_commands_total"),
            ),
            "live_rollout_handoff_operator_command_entrypoints_missing": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_command_entrypoints_missing"),
                (completion_summary, "live_rollout_handoff_operator_command_entrypoints_missing"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_command_entrypoints_missing"),
            ),
            "live_rollout_handoff_operator_command_surface_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_command_surface_ready"),
                (completion_summary, "live_rollout_handoff_operator_command_surface_ready"),
                default=False,
            ),
            "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"),
                (completion_summary, "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"),
            ),
            "live_rollout_handoff_operator_command_shell_surface_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_command_shell_surface_ready"),
                (completion_summary, "live_rollout_handoff_operator_command_shell_surface_ready"),
                default=False,
            ),
            "live_rollout_handoff_operator_sequence_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_sequence_ready"),
                (completion_summary, "live_rollout_handoff_operator_sequence_ready"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_sequence_ready"),
                default=False,
            ),
            "semantic_blocking_items_total": coverage_summary.get(
                "semantic_blocking_items_total",
                current_rollup_summary.get("semantic_blocking_items_total", 0),
            ),
            "semantic_preflight_errors_total": coverage_summary.get(
                "semantic_preflight_errors_total",
                current_rollup_summary.get("semantic_preflight_errors_total", 0),
            ),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Completion Gate Runner",
            f"completion_decision: {report.get('completion_decision')}",
            f"goal_can_be_marked_complete: {report.get('goal_can_be_marked_complete')}",
            f"steps_ready: {summary.get('steps_ready')}/{summary.get('steps_total')}",
            f"current_raw_files_installed: {summary.get('current_raw_files_installed')}",
            f"raw_install_claim_source: {summary.get('raw_install_claim_source')}",
            f"return_acceptance_raw_files_local_observation: {summary.get('return_acceptance_raw_files_local_observation')}",
            f"x0t_governance_execute_decision: {summary.get('x0t_governance_execute_decision')}",
            f"x0t_governance_proposal_executed: {summary.get('x0t_governance_proposal_executed')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine completion gate runner report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
    write_json(_resolve(root, args.output_json), report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_complete and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
