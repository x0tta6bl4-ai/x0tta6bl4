#!/usr/bin/env python3
"""Read-only production-grade goal audit.

This audit checks whether the repo has reproducible local gates for the broad
production-grade claims and then keeps the final decision blocked until real
operator production evidence replaces local/retained observations.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/production-grade-goal-audit-current.json"
DEFAULT_OUTPUT_MD = ".tmp/validation-shards/production-grade-goal-audit-current.md"
DEFAULT_COMPLETION_GATE_RUNNER = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
OPERATOR_APPROVAL_REQUIRED = "OPERATOR_APPROVAL_REQUIRED"
AFTER_BLOCKERS = "AFTER_BLOCKERS"
BLOCKING = "BLOCKING"


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
    return False


def _int_summary(summary: Dict[str, Any], key: str) -> int:
    value = summary.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _load_completion_gate_runner(root: Path) -> tuple[Optional[Dict[str, Any]], Dict[str, Any], str]:
    data, error = _read_json(root / DEFAULT_COMPLETION_GATE_RUNNER)
    return data, _summary(data), error


def _next_actions(complete: bool, completion_gate_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    complete = not missing_ids and not failed_ids and not gap_ids and bool(rows)
    completion_gate, completion_gate_summary, completion_gate_error = _load_completion_gate_runner(root)
    next_actions = _next_actions(complete, completion_gate_summary)
    summary = {
        "requirements_total": len(rows),
        "requirements_with_all_artifacts": sum(1 for row in rows if not row["missing_artifacts"]),
        "requirements_missing_artifacts": len(missing_ids),
        "requirements_with_failed_artifact_checks": len(failed_ids),
        "requirements_with_production_gaps": len(gap_ids),
        "missing_artifact_requirement_ids": missing_ids,
        "failed_artifact_check_requirement_ids": failed_ids,
        "production_gap_requirement_ids": gap_ids,
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
            "missing production evidence remains fail-closed. It does not run collectors, contact "
            "live systems, mutate runtime state, or mark /goal complete."
        ),
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "summary": summary,
        "prompt_to_artifact_checklist": rows,
        "next_actions": next_actions,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    report = build_report(root)
    write_json(root / args.output_json if not Path(args.output_json).is_absolute() else Path(args.output_json), report)
    write_markdown(root / args.output_md if not Path(args.output_md).is_absolute() else Path(args.output_md), report)

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
