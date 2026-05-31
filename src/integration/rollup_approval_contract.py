"""Read-only rollup approval contract for integration spine production evidence.

The contract consolidates current production evidence gates into one local
approval report. It is deliberately read-only: it hashes retained source
artifacts, records blocking evidence, and refuses to mark the objective complete
without production-ready evidence from the upstream gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_PASSPORT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json"
DEFAULT_SOURCE_CANDIDATE_VERIFICATION = (
    ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-verification-current.json"
)
DEFAULT_REPLACEMENT_PASSPORT_VERIFICATION = (
    ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json"
)
DEFAULT_REQUIRED_EVIDENCE_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
DEFAULT_CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"
EXPECTED_CURRENT_EVIDENCE_STATUS = "working_map_not_production_completion_proof"
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"
ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS = (
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
    kind: str
    evidence_key: str
    decision_keys: List[str]
    ready_summary_key: str
    expected_decision: str


SOURCE_SPECS = [
    SourceSpec(
        label="self_healing_pqc_mesh",
        path=".tmp/validation-shards/self-healing-pqc-mesh-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="multi_host_mesh",
        decision_keys=["decision", "self_healing_pqc_mesh_decision"],
        ready_summary_key="self_healing_pqc_mesh_ready",
        expected_decision="READY_TO_INSTALL",
    ),
    SourceSpec(
        label="zero_trust_pqc",
        path=".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="live_spire_mtls",
        decision_keys=["decision", "zero_trust_pqc_decision"],
        ready_summary_key="zero_trust_pqc_ready",
        expected_decision="READY_TO_INSTALL",
    ),
    SourceSpec(
        label="live_rollout",
        path=".tmp/validation-shards/live-rollout-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="safe_rollout_rollback",
        decision_keys=["decision", "live_rollout_decision", "rollout_decision"],
        ready_summary_key="live_rollout_ready",
        expected_decision="READY_TO_INSTALL",
    ),
    SourceSpec(
        label="paid_client_serviceability",
        path=".tmp/validation-shards/paid-client-serviceability-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="paid_client_path",
        decision_keys=["decision", "paid_client_serviceability_decision"],
        ready_summary_key="paid_client_serviceability_ready",
        expected_decision="READY_TO_INSTALL",
    ),
    SourceSpec(
        label="stable_deploy",
        path=".tmp/validation-shards/stable-deploy-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="stable-deploy",
        decision_keys=["entrypoint_decision"],
        ready_summary_key="ready_for_entrypoint_execution",
        expected_decision="RAW_EVIDENCE_GATE_READY",
    ),
    SourceSpec(
        label="ebpf_observability",
        path=".tmp/validation-shards/ebpf-observability-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="ebpf-observability",
        decision_keys=["entrypoint_decision"],
        ready_summary_key="ready_for_entrypoint_execution",
        expected_decision="RAW_EVIDENCE_GATE_READY",
    ),
    SourceSpec(
        label="signed_release_provenance",
        path=".tmp/validation-shards/signed-release-provenance-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="signed-release-provenance",
        decision_keys=["entrypoint_decision"],
        ready_summary_key="ready_for_entrypoint_execution",
        expected_decision="RAW_EVIDENCE_GATE_READY",
    ),
    SourceSpec(
        label="billing_provisioning",
        path=".tmp/validation-shards/billing-provisioning-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="billing-provisioning",
        decision_keys=["entrypoint_decision"],
        ready_summary_key="ready_for_entrypoint_execution",
        expected_decision="RAW_EVIDENCE_GATE_READY",
    ),
    SourceSpec(
        label="sla_telemetry",
        path=".tmp/validation-shards/sla-telemetry-evidence-gate-current.json",
        kind="raw_evidence",
        evidence_key="sla-telemetry",
        decision_keys=["entrypoint_decision"],
        ready_summary_key="ready_for_entrypoint_execution",
        expected_decision="RAW_EVIDENCE_GATE_READY",
    ),
    SourceSpec(
        label="external_settlement",
        path=".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
        kind="external_settlement",
        evidence_key="external_settlement",
        decision_keys=["decision", "x0t_external_settlement_decision"],
        ready_summary_key="x0t_external_settlement_ready",
        expected_decision="READY_TO_PROMOTE",
    ),
    SourceSpec(
        label="evidence_source_candidate_audit",
        path=DEFAULT_SOURCE_CANDIDATE_VERIFICATION,
        kind="source_candidate_audit_verification",
        evidence_key="evidence_source_candidate_audit",
        decision_keys=["decision"],
        ready_summary_key="ready",
        expected_decision="VALID_EVIDENCE_SOURCE_CANDIDATE_AUDIT_CLEAR",
    ),
    SourceSpec(
        label="production_evidence_replacement_passport",
        path=DEFAULT_REPLACEMENT_PASSPORT_VERIFICATION,
        kind="production_evidence_replacement_passport_verification",
        evidence_key="production_evidence_replacement_passport",
        decision_keys=["decision"],
        ready_summary_key="ready",
        expected_decision="VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR",
    ),
    SourceSpec(
        label="required_evidence_consistency",
        path=DEFAULT_REQUIRED_EVIDENCE_CONSISTENCY,
        kind="required_evidence_consistency",
        evidence_key="required_evidence_consistency",
        decision_keys=["decision"],
        ready_summary_key="production_ready",
        expected_decision="VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR",
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_payload(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "0x" + hashlib.sha256(body).hexdigest()


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _source_decision(data: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _not_verified_yet_count(data: Dict[str, Any]) -> int:
    value = data.get("not_verified_yet", [])
    return len(value) if isinstance(value, list) else 0


def _ready_from_source(data: Dict[str, Any], spec: SourceSpec) -> bool:
    summary = _summary(data)
    decision = _source_decision(data, spec.decision_keys)
    return (
        data.get("status") == "VERIFIED HERE"
        and data.get("ok") is True
        and decision == spec.expected_decision
        and (
            data.get("ready") is True
            or data.get("production_ready") is True
            or data.get(spec.ready_summary_key) is True
            or summary.get(spec.ready_summary_key) is True
            or summary.get("production_ready") is True
        )
    )


def _evidence_file_status(*, ready: bool, exists: bool) -> str:
    if ready:
        return "VALID"
    if not exists:
        return "MISSING"
    return "OPERATOR_INPUT_REQUIRED"


def _evidence_file_invalid(status: Any) -> bool:
    return status in {"BLOCKING", "OPERATOR_INPUT_REQUIRED"}


def _current_evidence_context(root: Path) -> Dict[str, Any]:
    map_path = root / DEFAULT_CURRENT_CROSS_PLANE_MAP
    audit_path = root / DEFAULT_CURRENT_ACTIVE_AUDIT
    context: Dict[str, Any] = {
        "included": map_path.exists() and audit_path.exists(),
        "source": "docs/architecture",
        "cross_plane_map": DEFAULT_CURRENT_CROSS_PLANE_MAP,
        "active_goal_audit": DEFAULT_CURRENT_ACTIVE_AUDIT,
        "claim_boundary": (
            "Current cross-plane evidence context is a local review gate for this "
            "approval rollup. It is not production proof and cannot authorize live apply."
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

    gaps = data.get("current_gaps")
    gap_items = _dicts(gaps)
    next_actions = _dicts(data.get("next_actions"))
    blocking_gaps = [item for item in gap_items if item.get("blocks_real_readiness") is not False]
    non_blocking_gaps = [item for item in gap_items if item.get("blocks_real_readiness") is False]
    planes = data.get("planes")
    plane_ids = sorted(str(key) for key in planes) if isinstance(planes, dict) else []
    context.update(
        {
            "status": data.get("status"),
            "current_gap_count": len(blocking_gaps),
            "tracked_gap_count": len(gap_items),
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
    return sorted(set(ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


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
    required_claim_ids = set(ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS)
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
        "required_claim_ids": list(ROLLUP_APPROVAL_CROSS_PLANE_CLAIMS),
        "claims_total": _as_int(summary.get("claims_total")),
        "claims_allowed": _as_int(summary.get("claims_allowed")),
        "claims_blocked": _as_int(summary.get("claims_blocked")),
        "source_artifact_hashes_present": context.get("source_artifact_hashes_present") is True,
        "map_sha256": context.get("map_sha256"),
        "audit_sha256": context.get("audit_sha256"),
        "blocker_ids": _cross_plane_proof_gate_blocker_ids(data),
        "claim_boundary": (
            "The rollup approval contract uses the reusable cross-plane proof gate as "
            "local claim-control evidence. It does not create external DPI, dataplane, "
            "traffic, settlement, or production proof."
        ),
    }


def _evidence_items(passport: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = _dicts(passport.get("required_evidence_files"))
    if items:
        return items
    return _dicts(passport.get("replacement_items"))


def _evidence_files_for_source(root: Path, items: List[Dict[str, Any]], spec: SourceSpec) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for item in items:
        if item.get("evidence_key") != spec.evidence_key:
            continue
        rel_path = str(item.get("retained_destination_path") or item.get("operator_return_path") or "")
        path = root / rel_path if rel_path else root
        exists = bool(rel_path) and path.exists()
        ready = item.get("ready") is True and item.get("blocks_production") is not True and exists
        errors: List[str] = []
        if not rel_path:
            errors.append("required evidence item has no retained destination path")
        if rel_path and not exists:
            errors.append("retained evidence file is missing")
        if item.get("ready") is not True:
            errors.append("required evidence item is not ready")
        if item.get("blocks_production") is True:
            errors.append("required evidence item still blocks production")
        files.append(
            {
                "item_id": item.get("item_id", ""),
                "name": Path(rel_path).name if rel_path else "",
                "path": rel_path,
                "sha256": _sha256_file(path) if exists else "",
                "status": _evidence_file_status(ready=ready, exists=exists),
                "ready": ready,
                "errors": errors,
            }
        )
    return files


def _source_report(root: Path, spec: SourceSpec, passport_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    path = root / spec.path
    data = _read_json(path)
    if data is None:
        return {
            "evidence_key": spec.evidence_key,
            "kind": spec.kind,
            "gate_path": spec.path,
            "gate_sha256": "",
            "status": "MISSING",
            "ok": False,
            "decision": "",
            "expected_decision": spec.expected_decision,
            "ready": False,
            "source_error": f"missing or unreadable source report: {spec.path}",
            "errors": [f"missing or unreadable source report: {spec.path}"],
            "evidence_files": [],
            "evidence_files_total": 0,
            "evidence_files_valid": 0,
            "evidence_files_missing": 0,
            "evidence_files_invalid": 0,
            "evidence_files_operator_input_required": 0,
            "not_verified_yet_count": 1,
        }

    evidence_files = _evidence_files_for_source(root, passport_items, spec)
    ready = _ready_from_source(data, spec)
    decision = _source_decision(data, spec.decision_keys)
    errors: List[str] = []
    if not ready:
        if data.get("status") != "VERIFIED HERE":
            errors.append("source report status must be VERIFIED HERE")
        if data.get("ok") is not True:
            errors.append("source report ok must be true")
        if decision != spec.expected_decision:
            errors.append(f"decision must be {spec.expected_decision}")
        if not (
            data.get("ready") is True
            or data.get("production_ready") is True
            or data.get(spec.ready_summary_key) is True
            or _summary(data).get(spec.ready_summary_key) is True
            or _summary(data).get("production_ready") is True
        ):
            errors.append(f"{spec.ready_summary_key} must be true")

    return {
        "evidence_key": spec.evidence_key,
        "kind": spec.kind,
        "gate_path": spec.path,
        "gate_sha256": _sha256_file(path),
        "schema_version": data.get("schema_version", ""),
        "status": data.get("status", ""),
        "ok": data.get("ok"),
        "decision": decision,
        "expected_decision": spec.expected_decision,
        "ready_summary_key": spec.ready_summary_key,
        "ready": ready,
        "errors": errors,
        "evidence_files": evidence_files,
        "evidence_files_total": len(evidence_files),
        "evidence_files_valid": sum(1 for item in evidence_files if item["status"] == "VALID"),
        "evidence_files_missing": sum(1 for item in evidence_files if item["status"] == "MISSING"),
        "evidence_files_invalid": sum(1 for item in evidence_files if _evidence_file_invalid(item["status"])),
        "evidence_files_operator_input_required": sum(
            1 for item in evidence_files if item["status"] == "OPERATOR_INPUT_REQUIRED"
        ),
        "not_verified_yet_count": _not_verified_yet_count(data),
    }


def build_report(root: Path, passport_path: Path, passport_display: str = DEFAULT_PASSPORT) -> Dict[str, Any]:
    passport = _read_json(passport_path)
    source_errors: List[str] = []
    if passport is None:
        source_errors.append(f"missing or unreadable passport: {passport_display}")
        passport = {}

    passport_items = _evidence_items(passport)
    source_reports = [_source_report(root, spec, passport_items) for spec in SOURCE_SPECS]
    for report in source_reports:
        source_error = report.get("source_error")
        if source_error:
            source_errors.append(str(source_error))

    all_evidence_files = [
        evidence_file
        for report in source_reports
        for evidence_file in report.get("evidence_files", [])
        if isinstance(evidence_file, dict)
    ]
    evidence_total = len(all_evidence_files)
    evidence_valid = sum(1 for item in all_evidence_files if item.get("status") == "VALID")
    evidence_missing = sum(1 for item in all_evidence_files if item.get("status") == "MISSING")
    evidence_invalid = sum(1 for item in all_evidence_files if _evidence_file_invalid(item.get("status")))
    evidence_operator_input_required = sum(
        1 for item in all_evidence_files if item.get("status") == "OPERATOR_INPUT_REQUIRED"
    )
    sources_ready = sum(1 for report in source_reports if report.get("ready") is True)
    sources_total = len(source_reports)
    local_ready = not source_errors and evidence_total > 0 and evidence_valid == evidence_total and sources_ready == sources_total
    current_evidence_context = _current_evidence_context(root)
    current_evidence_context_hash = _hash_payload(current_evidence_context)
    current_evidence_clear = _current_evidence_clear(current_evidence_context)
    current_evidence_blockers = _current_evidence_blockers(current_evidence_context)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(root)
    cross_plane_proof_gate_allowed = cross_plane_proof_gate.get("allowed") is True
    cross_plane_proof_gate_blockers = list(cross_plane_proof_gate.get("blocker_ids") or [])
    ready = local_ready and current_evidence_clear and cross_plane_proof_gate_allowed
    if ready:
        decision = "ROLLUP_APPROVAL_READY"
    elif local_ready:
        decision = (
            "ROLLUP_APPROVAL_BLOCKED_ON_CURRENT_EVIDENCE_CONTEXT"
            if not current_evidence_clear
            else "ROLLUP_APPROVAL_BLOCKED_ON_CROSS_PLANE_PROOF_GATE"
        )
    else:
        decision = "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
    blocked_reason_ids = (
        ([] if local_ready else ["local_source_gates_not_ready"])
        + current_evidence_blockers
        + ([] if cross_plane_proof_gate_allowed else cross_plane_proof_gate_blockers)
    )

    source_rollup = {
        "source_reports": [
            {
                "evidence_key": report.get("evidence_key"),
                "kind": report.get("kind"),
                "gate_path": report.get("gate_path"),
                "gate_sha256": report.get("gate_sha256"),
                "decision": report.get("decision"),
                "ready": report.get("ready"),
                "evidence_files": report.get("evidence_files", []),
            }
            for report in source_reports
        ],
    }
    source_rollup["source_rollup_hash"] = _hash_payload(source_rollup)

    report = {
        "schema_version": "x0tta6bl4-integration-spine-rollup-approval-contract-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "ready": ready,
        "decision": decision,
        "goal_can_be_marked_complete": False,
        "claim_boundary": "local_evidence_rollup_approval_only_no_live_apply",
        "current_evidence_context": current_evidence_context,
        "current_evidence_context_hash": current_evidence_context_hash,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "cross_plane_claim_gate": {
            "surface": "integration_spine_rollup_approval_contract",
            "claim_boundary": (
                "This report can only say that retained local evidence is ready for "
                "closeout review when current cross-plane context is clear and the "
                "reusable proof gate allows the strong claim set. It cannot claim "
                "production readiness, dataplane delivery, DPI bypass, settlement "
                "finality, traffic delivery, or live-apply authorization."
            ),
            "local_source_gates_ready": local_ready,
            "current_evidence_context_required": True,
            "current_evidence_context_clear": current_evidence_clear,
            "cross_plane_proof_gate_required": True,
            "cross_plane_proof_gate_allowed": cross_plane_proof_gate_allowed,
            "ready_for_closeout_review_claim_allowed": ready,
            "blocked_reason_ids": blocked_reason_ids,
            "proof_claims": {
                "production_ready": False,
                "dataplane_delivery_confirmed": False,
                "dpi_bypass_confirmed": False,
                "settlement_finality_confirmed": False,
                "goal_completion_authorized": False,
                "live_apply_authorized": False,
            },
        },
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "guardrails": {
            "local_contract_only": True,
            "live_apply_allowed": False,
            "closeout_gate_still_required": True,
            "network_calls": False,
            "docker_calls": False,
            "systemd_calls": False,
            "xui_or_xray_calls": False,
        },
        "operator_approval": {
            "approved": False,
            "approval_id": "",
            "operator_id": "",
            "approved_at": "",
            "live_apply_authorized": False,
            "ready_for_closeout_review": ready,
            "acknowledgements": {
                "source_gate_reports_reviewed": False,
                "evidence_file_hashes_reviewed": False,
                "no_template_or_mock_evidence": False,
                "no_live_mutation_from_approval": False,
                "closeout_gate_must_still_pass": False,
                "current_evidence_context_reviewed": False,
                "cross_plane_proof_gate_reviewed": False,
                "cross_plane_claim_boundary_reviewed": False,
            },
        },
        "source_artifacts": [
            passport_display,
            DEFAULT_CROSS_PLANE_PROOF_GATE,
            DEFAULT_CURRENT_CROSS_PLANE_MAP,
            DEFAULT_CURRENT_ACTIVE_AUDIT,
        ]
        + [spec.path for spec in SOURCE_SPECS],
        "source_errors": source_errors,
        "source_reports": source_reports,
        "source_rollup": source_rollup,
        "not_verified_yet": []
        if ready
        else (
            [
                "all source gates must report production-ready evidence",
                "every required evidence file must be retained and ready",
            ]
            if not local_ready
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
                "reusable cross-plane proof gate must allow rollup closeout-review claims",
            ]
            if not cross_plane_proof_gate_allowed
            else []
        )
        + [
            "operator approval is still local contract only and does not authorize live apply",
        ],
        "summary": {
            "sources_total": sources_total,
            "sources_ready": sources_ready,
            "sources_blocking": sources_total - sources_ready,
            "source_errors_total": len(source_errors),
            "evidence_files_total": evidence_total,
            "evidence_files_valid": evidence_valid,
            "evidence_files_missing": evidence_missing,
            "evidence_files_invalid": evidence_invalid,
            "evidence_files_operator_input_required": evidence_operator_input_required,
            "approval_recorded": False,
            "local_sources_ready": local_ready,
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
            "ready_for_closeout_review": ready,
            "ready_for_closeout_review_blocked_by_current_evidence": local_ready and not current_evidence_clear,
            "ready_for_closeout_review_blocked_by_cross_plane_proof_gate": (
                local_ready and current_evidence_clear and not cross_plane_proof_gate_allowed
            ),
        },
    }
    report["approval_contract_hash"] = _hash_payload(
        {
            "source_rollup_hash": source_rollup["source_rollup_hash"],
            "current_evidence_context_hash": current_evidence_context_hash,
            "summary": report["summary"],
            "decision": report["decision"],
        }
    )
    return report


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine rollup approval contract")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--passport", default=DEFAULT_PASSPORT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless the rollup contract is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    passport_input = Path(args.passport)
    passport_path = passport_input if passport_input.is_absolute() else root / passport_input
    report = build_report(root, passport_path, str(passport_input))
    write_json(root / args.output_json, report)
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "ready": report["ready"],
                "goal_can_be_marked_complete": False,
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
