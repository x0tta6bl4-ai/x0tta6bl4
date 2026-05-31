#!/usr/bin/env python3
"""Read-only production-grade goal audit.

This audit checks whether the repo has reproducible local gates for the broad
production-grade claims and then keeps the final decision blocked until real
operator production evidence replaces local/retained observations.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.ops.run_cross_plane_proof_gate import (
        build_report as build_cross_plane_proof_gate_report,
    )
except Exception:  # pragma: no cover - fail closed if ops scripts are unavailable
    build_cross_plane_proof_gate_report = None


DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/production-grade-goal-audit-current.json"
DEFAULT_OUTPUT_MD = ".tmp/validation-shards/production-grade-goal-audit-current.md"
DEFAULT_COMPLETION_GATE_RUNNER = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
CURRENT_CROSS_PLANE_MAP = "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
CURRENT_ACTIVE_AUDIT = "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
PROTECTED_CURRENT_EVIDENCE_OUTPUTS = {
    CURRENT_CROSS_PLANE_MAP,
    CURRENT_ACTIVE_AUDIT,
}
REQUIRED_CROSS_PLANE_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
OPERATOR_APPROVAL_REQUIRED = "OPERATOR_APPROVAL_REQUIRED"
AFTER_BLOCKERS = "AFTER_BLOCKERS"
BLOCKING = "BLOCKING"
PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)


@dataclass(frozen=True)
class Requirement:
    id: str
    requirement: str
    artifacts: List[str]
    production_gap: str


REQUIREMENTS: List[Requirement] = [
    Requirement(
        "stable_deploy",
        "System deploys reproducibly from local/container/Kubernetes/GitOps artifacts.",
        [
            ".tmp/validation-shards/stable-deploy-gate-current.json",
            ".tmp/validation-shards/stable-deploy-evidence-gate-current.json",
            ".tmp/validation-shards/stable-deploy-evidence-collector-current.json",
            "scripts/ops/verify_stable_deploy_evidence_gate.py",
            "scripts/ops/collect_stable_deploy_evidence_bundle.py",
            "argocd/app-of-apps.yaml",
            "argocd/applications/x0tta6bl4-prod.yaml",
        ],
        "Retained production rollout/GitOps deployment evidence is still missing.",
    ),
    Requirement(
        "self_healing_pqc_mesh",
        "Self-healing PQC mesh works under hostile/multi-host conditions.",
        [
            ".tmp/validation-shards/self-healing-pqc-mesh-gate-current.json",
            ".tmp/validation-shards/self-healing-pqc-mesh-evidence-gate-current.json",
            ".tmp/validation-shards/self-healing-pqc-mesh-evidence-collector-current.json",
            "scripts/ops/verify_self_healing_pqc_mesh_evidence_gate.py",
            "scripts/ops/collect_self_healing_pqc_mesh_evidence_bundle.py",
        ],
        "Retained production hostile/multi-host mesh recovery evidence is still missing.",
    ),
    Requirement(
        "zero_trust_pqc",
        "Zero-Trust identity, mTLS, and PQC handshakes are enforced without weakening checks.",
        [
            ".tmp/validation-shards/zero-trust-pqc-gate-current.json",
            ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
            ".tmp/validation-shards/zero-trust-pqc-evidence-collector-current.json",
            "scripts/ops/verify_zero_trust_pqc_evidence_gate.py",
            "scripts/ops/collect_zero_trust_pqc_evidence_bundle.py",
        ],
        "Retained production SPIRE/mTLS/PQC customer-path evidence is still missing.",
    ),
    Requirement(
        "ebpf_observability",
        "eBPF observability is attached, measured, and wired into production monitoring.",
        [
            "ebpf/prod/verify-local.sh",
            ".tmp/validation-shards/ebpf-observability-gate-current.json",
            ".tmp/validation-shards/ebpf-observability-evidence-gate-current.json",
            ".tmp/validation-shards/ebpf-observability-evidence-collector-current.json",
            "scripts/ops/verify_ebpf_observability_evidence_gate.py",
            "scripts/ops/collect_ebpf_observability_evidence_bundle.py",
            "observability/dashboards/eBPF Telemetry.json",
        ],
        "Retained production eBPF monitoring rollout evidence is still missing.",
    ),
    Requirement(
        "gitops_signed_releases",
        "GitOps CI/CD and signed release/SBOM provenance are verifiable.",
        [
            "argocd/app-of-apps.yaml",
            "argocd/applications/x0tta6bl4-prod.yaml",
            ".tmp/validation-shards/gitops-signed-release-gate-current.json",
            ".tmp/validation-shards/safe-update-rollout-gate-current.json",
            ".tmp/validation-shards/live-rollout-evidence-gate-current.json",
            ".tmp/validation-shards/live-rollout-evidence-collector-current.json",
            ".tmp/validation-shards/signed-release-provenance-evidence-gate-current.json",
            ".tmp/validation-shards/signed-release-provenance-evidence-collector-current.json",
            "scripts/ops/verify_live_rollout_evidence_gate.py",
            "scripts/ops/collect_live_rollout_evidence_bundle.py",
            "scripts/ops/verify_signed_release_provenance_evidence_gate.py",
            "scripts/ops/collect_signed_release_provenance_evidence_bundle.py",
        ],
        "Retained production rollout/provenance and digest-pinning evidence is still missing.",
    ),
    Requirement(
        "billing_provisioning",
        "Billing and provisioning can activate/revoke paid customer access safely.",
        [
            "src/api/maas_billing.py",
            "src/services/provisioning_service.py",
            ".tmp/validation-shards/billing-provisioning-gate-current.json",
            ".tmp/validation-shards/billing-provisioning-evidence-gate-current.json",
            ".tmp/validation-shards/billing-provisioning-evidence-collector-current.json",
            "scripts/ops/verify_billing_provisioning_evidence_gate.py",
            "scripts/ops/collect_billing_provisioning_evidence_bundle.py",
        ],
        "Retained live billing/provisioning activation and revocation evidence is still missing.",
    ),
    Requirement(
        "sla_dashboards",
        "SLA dashboards and reports expose real client-facing reliability metrics.",
        [
            "scripts/generate_client_sla_report.py",
            ".tmp/validation-shards/sla-dashboard-gate-current.json",
            ".tmp/validation-shards/sla-telemetry-evidence-gate-current.json",
            ".tmp/validation-shards/sla-telemetry-evidence-collector-current.json",
            "docs/dashboards/sla-metrics.json",
            "observability/dashboards/SLO Error Budget.json",
            "scripts/ops/verify_sla_telemetry_evidence_gate.py",
            "scripts/ops/collect_sla_telemetry_evidence_bundle.py",
        ],
        "Retained production SLA telemetry and alert-drill evidence is still missing.",
    ),
    Requirement(
        "paid_client_serviceability",
        "The platform can serve paid clients with stable deploy, recovery, updates, and support evidence.",
        [
            ".tmp/validation-shards/paid-client-serviceability-gate-current.json",
            ".tmp/validation-shards/paid-client-serviceability-evidence-gate-current.json",
            ".tmp/validation-shards/paid-client-serviceability-evidence-collector-current.json",
            ".tmp/validation-shards/production-raw-evidence-readiness-current.json",
            ".tmp/validation-shards/production-raw-evidence-semantics-current.json",
            ".tmp/validation-shards/production-raw-evidence-pipeline-current.json",
            "docs/verification/production-raw-evidence-operator-runbook.md",
            "scripts/ops/verify_paid_client_serviceability_evidence_gate.py",
            "scripts/ops/collect_paid_client_serviceability_evidence_bundle.py",
        ],
        "Retained paid-client serviceability evidence and production raw evidence are still missing.",
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _decision(data: Dict[str, Any]) -> str:
    for key in (
        "entrypoint_decision",
        "decision",
        "completion_decision",
        "pipeline_decision",
        "semantic_readiness_decision",
        "raw_evidence_readiness_decision",
    ):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    for key, value in data.items():
        if key.endswith("_decision") and isinstance(value, str) and value:
            return value
    return ""


def _ready_value(data: Dict[str, Any]) -> Any:
    for key in (
        "ready",
        "ready_for_entrypoint_execution",
        "ready_for_collector_execution",
        "ready_for_collectors",
        "production_ready",
    ):
        if key in data:
            return data.get(key)
    summary = _summary(data)
    for key in summary:
        if key.endswith("_ready"):
            return summary.get(key)
    return None


def _json_artifact_check(root: Path, artifact: str) -> Optional[Dict[str, Any]]:
    if not artifact.endswith(".json"):
        return None
    path = root / artifact
    data, error = _read_json(path)
    if data is None:
        return {"name": f"{Path(artifact).stem}_json_readable", "artifact": artifact, "ok": False, "details": error}
    if not artifact.startswith(".tmp/validation-shards/"):
        return {
            "name": f"{Path(artifact).stem}_json_readable",
            "artifact": artifact,
            "ok": True,
            "details": "JSON artifact parses; status field is not required outside validation shards",
        }

    status = data.get("status")
    ok = data.get("ok")
    decision = _decision(data)
    ready = _ready_value(data)
    goal_complete = data.get("goal_can_be_marked_complete")
    verified = status == "VERIFIED HERE" and ok is not False

    if "evidence-" in artifact or "production-raw-evidence" in artifact:
        fail_closed = (
            verified
            and goal_complete is False
            and (
                ready is False
                or "BLOCKED" in decision
                or "OPERATOR_INPUT_REQUIRED" in decision
            )
        )
        production_ready = verified and ready is True and goal_complete is True
        return {
            "name": f"{Path(artifact).stem}_fail_closed_or_ready",
            "artifact": artifact,
            "ok": bool(fail_closed or production_ready),
            "details": f"status={status} ok={ok} decision={decision} ready={ready} goal_can_be_marked_complete={goal_complete}",
        }

    return {
        "name": f"{Path(artifact).stem}_verified",
        "artifact": artifact,
        "ok": bool(verified),
        "details": f"status={status} ok={ok} decision={decision}",
    }


def _production_ready(root: Path, requirement: Requirement) -> bool:
    for artifact in requirement.artifacts:
        if not artifact.endswith(".json"):
            continue
        data, _ = _read_json(root / artifact)
        if not data:
            return False
        if "evidence-" in artifact or "production-raw-evidence" in artifact:
            if data.get("goal_can_be_marked_complete") is True or _ready_value(data) is True:
                continue
            return False
    return True


def _current_evidence_context(root: Path) -> Dict[str, Any]:
    map_path = root / CURRENT_CROSS_PLANE_MAP
    audit_path = root / CURRENT_ACTIVE_AUDIT
    context: Dict[str, Any] = {
        "included": map_path.exists() and audit_path.exists(),
        "source": "docs/architecture",
        "cross_plane_map": CURRENT_CROSS_PLANE_MAP,
        "active_goal_audit": CURRENT_ACTIVE_AUDIT,
        "claim_boundary": (
            "Production-grade goal audit requires current cross-plane evidence "
            "context before it can return COMPLETE. The maps/audit are gating "
            "context, not production proof by themselves."
        ),
    }
    if not map_path.exists() or not audit_path.exists():
        context.update(
            {
                "status": "missing_current_evidence_context",
                "current_gap_count": None,
                "next_action_count": None,
                "open_gap_ids": [],
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
                "next_action_count": None,
                "open_gap_ids": [],
                "next_action_ids": [],
                "required_planes_present": False,
                "plane_ids": [],
            }
        )
        return context

    gaps = data.get("current_gaps")
    if not isinstance(gaps, list):
        gaps = []
    blocking_gaps = [
        item
        for item in gaps
        if isinstance(item, dict) and item.get("blocks_real_readiness") is not False
    ]
    non_blocking_gaps = [
        item
        for item in gaps
        if isinstance(item, dict) and item.get("blocks_real_readiness") is False
    ]
    next_actions = data.get("next_actions")
    if not isinstance(next_actions, list):
        next_actions = []
    planes = data.get("planes")
    plane_ids = set(planes) if isinstance(planes, dict) else set()
    context.update(
        {
            "status": data.get("status"),
            "current_gap_count": len(blocking_gaps),
            "tracked_gap_count": len([item for item in gaps if isinstance(item, dict)]),
            "non_blocking_gap_count": len(non_blocking_gaps),
            "next_action_count": len(next_actions),
            "open_gap_ids": [
                item.get("id")
                for item in blocking_gaps
                if item.get("id")
            ],
            "non_blocking_gap_ids": [
                item.get("id")
                for item in non_blocking_gaps
                if item.get("id")
            ],
            "next_action_ids": [
                item.get("id")
                for item in next_actions
                if isinstance(item, dict) and item.get("id")
            ],
            "required_planes_present": REQUIRED_CROSS_PLANE_PLANES.issubset(
                plane_ids
            ),
            "plane_ids": sorted(plane_ids),
        }
    )
    return context


def _current_evidence_gate_clear(context: Dict[str, Any]) -> bool:
    return bool(
        context.get("included") is True
        and context.get("status") == "working_map_not_production_completion_proof"
        and context.get("required_planes_present") is True
        and context.get("current_gap_count") == 0
        and context.get("next_action_count") == 0
    )


def _current_evidence_blocker_ids(context: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if context.get("included") is not True:
        blockers.append("current_evidence_context_missing")
    if (
        context.get("included") is True
        and context.get("status") != "working_map_not_production_completion_proof"
    ):
        blockers.append("current_evidence_context_status")
    if context.get("required_planes_present") is not True:
        blockers.append("current_evidence_context_planes")
    if context.get("current_gap_count") or context.get("next_action_count"):
        blockers.append("current_evidence_open_gaps")
    return blockers


def _cross_plane_proof_gate_context(root: Path) -> Dict[str, Any]:
    requested_claims = list(PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS)
    surface = "production_grade_goal_audit.completion"
    if build_cross_plane_proof_gate_report is None:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "available": False,
            "surface": surface,
            "requested_claim_ids": requested_claims,
            "blockers": ["cross_plane_proof_gate_unavailable"],
            "claim_boundary": (
                "Cross-plane proof gate unavailable; production-grade audit must "
                "not return COMPLETE from local artifact evidence alone."
            ),
        }
    try:
        report = build_cross_plane_proof_gate_report(
            root,
            claims=PRODUCTION_GRADE_AUDIT_CROSS_PLANE_CLAIMS,
        )
    except Exception as exc:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "available": False,
            "surface": surface,
            "requested_claim_ids": requested_claims,
            "blockers": [f"cross_plane_proof_gate_error:{type(exc).__name__}"],
            "claim_boundary": (
                "Cross-plane proof gate failed closed; production-grade audit "
                "must not return COMPLETE from local artifact evidence alone."
            ),
        }
    if not isinstance(report, dict):
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "available": False,
            "surface": surface,
            "requested_claim_ids": requested_claims,
            "blockers": ["cross_plane_proof_gate_invalid_response"],
            "claim_boundary": (
                "Cross-plane proof gate returned invalid metadata; production-grade "
                "audit must not return COMPLETE from local artifact evidence alone."
            ),
        }
    return {
        "schema": report.get("schema", "x0tta6bl4.cross_plane_proof_gate.v1"),
        "decision": report.get("decision", "CROSS_PLANE_CLAIMS_BLOCKED"),
        "allowed": report.get("allowed") is True,
        "available": True,
        "surface": surface,
        "requested_claim_ids": requested_claims,
        "summary": report.get("summary"),
        "context": report.get("context"),
        "claim_results": report.get("claim_results"),
        "claim_boundary": report.get(
            "claim_boundary",
            (
                "Production-grade audit uses the reusable cross-plane proof gate "
                "before allowing COMPLETE."
            ),
        ),
    }


def _cross_plane_proof_gate_blocker_ids(context: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if context.get("available") is False:
        blockers.append("cross_plane_proof_gate_unavailable")
    for blocker in context.get("blockers") or []:
        if isinstance(blocker, str) and blocker not in blockers:
            blockers.append(blocker)
    for result in context.get("claim_results") or []:
        if not isinstance(result, dict):
            continue
        claim_id = str(result.get("claim_id") or "unknown_claim")
        if result.get("allowed") is True:
            continue
        blockers.append(f"claim_blocked:{claim_id}")
        for blocker in result.get("blockers") or []:
            if isinstance(blocker, str):
                blockers.append(blocker)
    return sorted(set(blockers))


def _int_summary(summary: Dict[str, Any], key: str) -> int:
    value = summary.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _load_completion_gate_runner(root: Path) -> tuple[Optional[Dict[str, Any]], Dict[str, Any], str]:
    data, error = _read_json(root / DEFAULT_COMPLETION_GATE_RUNNER)
    return data, _summary(data), error


def _next_actions(
    complete: bool,
    completion_gate_summary: Dict[str, Any],
    current_evidence_context: Dict[str, Any],
    cross_plane_proof_gate: Dict[str, Any],
    *,
    cross_plane_proof_gate_action_required: bool,
) -> List[Dict[str, Any]]:
    if complete:
        return []
    actions = [
        {
            "id": "replace_operator_evidence",
            "status": OPERATOR_INPUT_REQUIRED,
            "action": "Replace retained/local raw JSON and external settlement placeholders with operator production evidence.",
        }
    ]
    if completion_gate_summary.get("x0t_contract_handoff_available") is True and (
        completion_gate_summary.get("x0t_contract_handoff_deployment_ready") is not True
    ):
        actions.append(
            {
                "id": "provide_x0t_bridge_contract_address",
                "status": OPERATOR_INPUT_REQUIRED,
                "action": "Provide the deployed Base Sepolia X0T bridge contract address; do not substitute X0TToken or MeshGovernance.",
                "source_artifact": DEFAULT_COMPLETION_GATE_RUNNER,
                "handoff_decision": completion_gate_summary.get("x0t_contract_handoff_decision", ""),
            }
        )
        if _int_summary(completion_gate_summary, "x0t_contract_handoff_operator_approval_required_actions_total") > 0:
            actions.append(
                {
                    "id": "apply_x0t_bridge_contract_address_with_approval",
                    "status": OPERATOR_APPROVAL_REQUIRED,
                    "action": "Apply the bridge address only with explicit X0T_APPLY_BRIDGE_ADDRESS_APPROVAL, then rerun contract readiness.",
                    "source_artifact": DEFAULT_COMPLETION_GATE_RUNNER,
                    "approval_value_required": completion_gate_summary.get(
                        "x0t_contract_handoff_approval_value_required",
                        "",
                    ),
                    "handoff_decision": completion_gate_summary.get("x0t_contract_handoff_decision", ""),
                }
            )
    if completion_gate_summary.get("live_rollout_handoff_available") is True and (
        completion_gate_summary.get("live_rollout_handoff_can_close_image_digests_blocker") is not True
    ):
        actions.append(
            {
                "id": "return_live_rollout_image_digest_provenance",
                "status": OPERATOR_INPUT_REQUIRED,
                "action": "Return digest-pinned runtime image references and retained per-image provenance, then rerun live rollout evidence and rollout provenance gates.",
                "source_artifact": DEFAULT_COMPLETION_GATE_RUNNER,
                "handoff_decision": completion_gate_summary.get("live_rollout_handoff_decision", ""),
            }
        )
    if not _current_evidence_gate_clear(current_evidence_context):
        actions.append(
            {
                "id": "clear_current_cross_plane_evidence_context",
                "status": BLOCKING,
                "action": (
                    "Resolve current cross-plane evidence gaps/next actions before "
                    "treating the production-grade audit as complete."
                ),
                "source_artifacts": [CURRENT_CROSS_PLANE_MAP, CURRENT_ACTIVE_AUDIT],
                "blocker_ids": _current_evidence_blocker_ids(
                    current_evidence_context
                ),
                "open_gap_ids": current_evidence_context.get("open_gap_ids", []),
                "next_action_ids": current_evidence_context.get("next_action_ids", []),
            }
        )
    if (
        cross_plane_proof_gate_action_required
        and cross_plane_proof_gate.get("allowed") is not True
    ):
        actions.append(
            {
                "id": "clear_cross_plane_proof_gate",
                "status": BLOCKING,
                "action": (
                    "Resolve cross-plane proof gate blockers before treating the "
                    "production-grade audit as complete."
                ),
                "source_artifacts": [
                    "scripts/ops/run_cross_plane_proof_gate.py",
                    CURRENT_CROSS_PLANE_MAP,
                    CURRENT_ACTIVE_AUDIT,
                ],
                "blocker_ids": _cross_plane_proof_gate_blocker_ids(
                    cross_plane_proof_gate
                ),
                "requested_claim_ids": cross_plane_proof_gate.get(
                    "requested_claim_ids",
                    [],
                ),
            }
        )
    actions.append(
        {
            "id": "rerun_production_closeout",
            "status": AFTER_BLOCKERS,
            "action": "Rerun raw evidence readiness, semantic preflight, production input pipeline, production-grade audit, and completion audit.",
        }
    )
    return actions


def _requirement_report(root: Path, requirement: Requirement) -> Dict[str, Any]:
    existing = [artifact for artifact in requirement.artifacts if (root / artifact).exists()]
    missing = [artifact for artifact in requirement.artifacts if not (root / artifact).exists()]
    artifact_checks = [
        check
        for artifact in requirement.artifacts
        for check in [_json_artifact_check(root, artifact)]
        if check is not None
    ]
    failed = [str(check["name"]) for check in artifact_checks if check.get("ok") is not True]
    production_ready = not missing and not failed and _production_ready(root, requirement)
    production_gaps = [] if production_ready else [requirement.production_gap]
    if missing:
        status = "MISSING_ARTIFACTS"
    elif failed:
        status = "ARTIFACT_CONTENT_CHECK_FAILED"
    elif production_ready:
        status = "PRODUCTION_READY"
    else:
        status = "VERIFIED_LOCAL_PRODUCTION_GAP"
    return {
        "id": requirement.id,
        "requirement": requirement.requirement,
        "artifacts": requirement.artifacts,
        "existing_artifacts": existing,
        "missing_artifacts": missing,
        "artifact_checks": artifact_checks,
        "failed_artifact_checks": failed,
        "production_gaps": production_gaps,
        "evidence_present": not missing and not failed,
        "production_ready": production_ready,
        "status": status,
    }


def build_report(root: Path, requirements: Iterable[Requirement] = REQUIREMENTS) -> Dict[str, Any]:
    rows = [_requirement_report(root, requirement) for requirement in requirements]
    missing_ids = [row["id"] for row in rows if row["missing_artifacts"]]
    failed_ids = [row["id"] for row in rows if row["failed_artifact_checks"]]
    gap_ids = [row["id"] for row in rows if row["production_gaps"]]
    requirements_complete = not missing_ids and not failed_ids and not gap_ids and bool(rows)
    current_evidence = _current_evidence_context(root)
    current_evidence_clear = _current_evidence_gate_clear(current_evidence)
    cross_plane_proof_gate = _cross_plane_proof_gate_context(root)
    cross_plane_proof_gate_clear = cross_plane_proof_gate.get("allowed") is True
    complete = requirements_complete and current_evidence_clear and cross_plane_proof_gate_clear
    completion_gate, completion_gate_summary, completion_gate_error = _load_completion_gate_runner(root)
    next_actions = _next_actions(
        complete,
        completion_gate_summary,
        current_evidence,
        cross_plane_proof_gate,
        cross_plane_proof_gate_action_required=(
            requirements_complete and current_evidence_clear
        ),
    )
    summary = {
        "requirements_total": len(rows),
        "requirements_with_all_artifacts": sum(1 for row in rows if not row["missing_artifacts"]),
        "requirements_missing_artifacts": len(missing_ids),
        "requirements_with_failed_artifact_checks": len(failed_ids),
        "requirements_with_production_gaps": len(gap_ids),
        "missing_artifact_requirement_ids": missing_ids,
        "failed_artifact_check_requirement_ids": failed_ids,
        "production_gap_requirement_ids": gap_ids,
        "requirements_complete": requirements_complete,
        "current_evidence_context_included": current_evidence.get("included"),
        "current_evidence_context_status": current_evidence.get("status"),
        "current_evidence_required_planes_present": current_evidence.get(
            "required_planes_present"
        ),
        "current_evidence_gate_clear": current_evidence_clear,
        "current_evidence_gap_count": current_evidence.get("current_gap_count"),
        "current_evidence_next_action_count": current_evidence.get(
            "next_action_count"
        ),
        "current_evidence_open_gap_ids": current_evidence.get("open_gap_ids", []),
        "current_evidence_next_action_ids": current_evidence.get(
            "next_action_ids", []
        ),
        "current_evidence_blocker_ids": _current_evidence_blocker_ids(
            current_evidence
        ),
        "cross_plane_proof_gate_available": cross_plane_proof_gate.get("available"),
        "cross_plane_proof_gate_decision": cross_plane_proof_gate.get("decision"),
        "cross_plane_proof_gate_allowed": cross_plane_proof_gate_clear,
        "cross_plane_proof_gate_requested_claim_ids": cross_plane_proof_gate.get(
            "requested_claim_ids",
            [],
        ),
        "cross_plane_proof_gate_blocker_ids": _cross_plane_proof_gate_blocker_ids(
            cross_plane_proof_gate
        ),
        "next_actions_total": len(next_actions),
        "next_actions_operator_input_required": sum(
            1 for action in next_actions if action.get("status") == OPERATOR_INPUT_REQUIRED
        ),
        "next_actions_operator_approval_required": sum(
            1 for action in next_actions if action.get("status") == OPERATOR_APPROVAL_REQUIRED
        ),
        "next_actions_after_blockers": sum(1 for action in next_actions if action.get("status") == AFTER_BLOCKERS),
        "next_actions_generic_blocking": sum(1 for action in next_actions if action.get("status") == BLOCKING),
        "completion_gate_runner_available": completion_gate is not None,
        "completion_gate_runner_error": completion_gate_error,
        "completion_gate_runner_decision": (completion_gate or {}).get("completion_decision")
        or (completion_gate or {}).get("decision"),
        "completion_gate_production_input_return_packet_available": completion_gate_summary.get(
            "production_input_return_packet_available"
        ),
        "completion_gate_production_input_return_packet_decision": completion_gate_summary.get(
            "production_input_return_packet_decision"
        ),
        "completion_gate_production_input_return_packet_blocking_inputs_total": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_blocking_inputs_total",
        ),
        "completion_gate_production_input_return_packet_blocking_raw_inputs": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_blocking_raw_inputs",
        ),
        "completion_gate_production_input_return_packet_blocking_external_inputs": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_blocking_external_inputs",
        ),
        "completion_gate_production_input_return_packet_blocking_inputs_operator_input_required": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_blocking_inputs_operator_input_required",
        ),
        "completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_blocking_inputs_generic_operator_required",
        ),
        "completion_gate_production_input_return_packet_operator_next_actions_total": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_operator_next_actions_total",
        ),
        "completion_gate_production_input_return_packet_operator_next_actions_operator_input_required": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_operator_next_actions_operator_input_required",
        ),
        "completion_gate_production_input_return_packet_operator_next_actions_generic_blocking": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_operator_next_actions_generic_blocking",
        ),
        "completion_gate_production_input_return_packet_raw_files_expected": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_raw_files_expected",
        ),
        "completion_gate_production_input_return_packet_raw_files_missing": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_raw_files_missing",
        ),
        "completion_gate_production_input_return_packet_raw_files_local_observation": _int_summary(
            completion_gate_summary,
            "production_input_return_packet_raw_files_local_observation",
        ),
        "completion_gate_x0t_contract_handoff_decision": completion_gate_summary.get(
            "x0t_contract_handoff_decision"
        ),
        "completion_gate_x0t_contract_handoff_approval_value_required": completion_gate_summary.get(
            "x0t_contract_handoff_approval_value_required"
        ),
        "completion_gate_x0t_contract_handoff_missing_inputs_total": _int_summary(
            completion_gate_summary,
            "x0t_contract_handoff_missing_inputs_total",
        ),
        "completion_gate_x0t_contract_handoff_operator_actions_total": _int_summary(
            completion_gate_summary,
            "x0t_contract_handoff_operator_actions_total",
        ),
        "completion_gate_x0t_contract_handoff_operator_approval_required_actions_total": _int_summary(
            completion_gate_summary,
            "x0t_contract_handoff_operator_approval_required_actions_total",
        ),
        "completion_gate_x0t_contract_handoff_operator_commands_total": _int_summary(
            completion_gate_summary,
            "x0t_contract_handoff_operator_commands_total",
        ),
        "completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready": completion_gate_summary.get(
            "x0t_contract_handoff_operator_command_shell_surface_ready"
        ),
        "completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": _int_summary(
            completion_gate_summary,
            "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders",
        ),
        "completion_gate_x0t_contract_handoff_operator_sequence_ready": completion_gate_summary.get(
            "x0t_contract_handoff_operator_sequence_ready"
        ),
        "completion_gate_live_rollout_handoff_decision": completion_gate_summary.get(
            "live_rollout_handoff_decision"
        ),
        "completion_gate_live_rollout_handoff_missing_inputs_total": _int_summary(
            completion_gate_summary,
            "live_rollout_handoff_missing_inputs_total",
        ),
        "completion_gate_live_rollout_handoff_operator_actions_total": _int_summary(
            completion_gate_summary,
            "live_rollout_handoff_operator_actions_total",
        ),
        "completion_gate_live_rollout_handoff_operator_input_required_actions_total": _int_summary(
            completion_gate_summary,
            "live_rollout_handoff_operator_input_required_actions_total",
        ),
        "completion_gate_live_rollout_handoff_operator_commands_total": _int_summary(
            completion_gate_summary,
            "live_rollout_handoff_operator_commands_total",
        ),
        "completion_gate_live_rollout_handoff_operator_command_shell_surface_ready": completion_gate_summary.get(
            "live_rollout_handoff_operator_command_shell_surface_ready"
        ),
        "completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _int_summary(
            completion_gate_summary,
            "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders",
        ),
        "completion_gate_live_rollout_handoff_operator_sequence_ready": completion_gate_summary.get(
            "live_rollout_handoff_operator_sequence_ready"
        ),
    }
    return {
        "schema_version": "x0tta6bl4-production-grade-goal-audit-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "objective": (
            "Verify the broader production-grade readiness envelope without promoting local, "
            "template, or retained component evidence into production proof."
        ),
        "claim_boundary": (
            "Read-only artifact audit. It reads current local evidence reports and checks that "
            "missing production evidence remains fail-closed. It also requires current cross-plane "
            "evidence context to be present and clear and the reusable cross-plane proof gate to "
            "allow the requested strong claims before returning COMPLETE. It does not run "
            "collectors, contact live systems, mutate runtime state, or mark /goal complete."
        ),
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "summary": summary,
        "current_evidence_context": current_evidence,
        "cross_plane_proof_gate": cross_plane_proof_gate,
        "prompt_to_artifact_checklist": rows,
        "next_actions": next_actions,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_output_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _output_path_is_protected(root: Path, value: str) -> bool:
    output_path = _resolve_output_path(root, value).resolve()
    protected = {
        _resolve_output_path(root, item).resolve()
        for item in PROTECTED_CURRENT_EVIDENCE_OUTPUTS
    }
    return output_path in protected


def _guard_output_path(root: Path, value: str, *, flag: str) -> None:
    if _output_path_is_protected(root, value):
        raise SystemExit(
            f"{flag} must not overwrite current evidence source artifact: {value}"
        )


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "# Production Grade Goal Audit",
        "",
        f"- decision: `{payload['completion_decision']}`",
        f"- goal_can_be_marked_complete: `{payload['goal_can_be_marked_complete']}`",
        "",
        "| requirement | status | production gaps |",
        "|---|---|---|",
    ]
    for row in payload.get("prompt_to_artifact_checklist", []):
        gaps = "<br>".join(row.get("production_gaps", [])) or "-"
        lines.append(f"| {row.get('id')} | `{row.get('status')}` | {gaps} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit production-grade goal readiness")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    _guard_output_path(root, args.output_json, flag="--output-json")
    _guard_output_path(root, args.output_md, flag="--output-md")
    report = build_report(root)
    write_json(_resolve_output_path(root, args.output_json), report)
    write_markdown(_resolve_output_path(root, args.output_md), report)

    if args.output == "json":
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
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

    if args.require_complete and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
