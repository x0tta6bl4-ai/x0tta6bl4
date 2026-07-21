"""Completion audit for the x0tta6bl4 integration-spine objective.

The audit intentionally separates local wiring proof from production proof.
Passing the local spine tests is necessary, but not sufficient, for the user
objective. Production is complete only when the retained evidence artifacts also
show external settlement, rollout provenance, semantic readiness, and the
production gap index source routes as ready.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


OBJECTIVE = (
    "Connect all x0tta6bl4 layers and components into one system through a "
    "single identity, event bus, policy engine, safe actuator, and "
    "settlement/reward loop, then bring that system to production."
)

REQUIRED_WIRING_KEYS = {
    "identity",
    "event_bus",
    "policy_engine",
    "safe_actuator",
    "settlement_reward_loop",
}

REQUIRED_EVIDENCE_KEYS = {
    "billing-provisioning",
    "ebpf-observability",
    "external_settlement",
    "live_spire_mtls",
    "multi_host_mesh",
    "paid_client_path",
    "safe_rollout_rollback",
    "signed-release-provenance",
    "sla-telemetry",
    "stable-deploy",
}

RAW_PRODUCTION_EVIDENCE_KEYS = {
    "billing-provisioning",
    "ebpf-observability",
    "live_spire_mtls",
    "multi_host_mesh",
    "paid_client_path",
    "safe_rollout_rollback",
    "signed-release-provenance",
    "sla-telemetry",
    "stable-deploy",
}

BUNDLE_MANIFEST_IDENTITY_COUNTERS = (
    "bundle_files_total",
    "bundle_files_available",
    "bundle_manifest_identity_mismatches_total",
    "bundle_raw_id_mismatches",
    "bundle_collector_id_mismatches",
    "bundle_file_name_mismatches",
)

ARTIFACTS = {
    "code_wiring": ".tmp/validation-shards/integration-spine-code-wiring-current.json",
    "code_wiring_source": "src/integration/code_wiring.py",
    "code_wiring_test": "tests/unit/test_integration_spine.py",
    "token_bridge_source": "src/dao/token_bridge.py",
    "token_bridge_test": "tests/unit/dao/test_token_bridge_unit.py",
    "current_rollup": ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
    "current_rollup_source": "src/integration/current_evidence_rollup.py",
    "current_rollup_test": "tests/unit/test_integration_current_evidence_rollup.py",
    "raw_inventory": ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json",
    "raw_inventory_source": "src/integration/raw_evidence_inventory.py",
    "raw_inventory_test": "tests/unit/test_integration_raw_evidence_inventory.py",
    "semantic_queue": ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
    "semantic_queue_source": "src/integration/semantic_production_blocker_queue.py",
    "semantic_queue_test": "tests/unit/test_integration_semantic_production_blocker_queue.py",
    "evidence_readiness": ".tmp/validation-shards/integration-spine-evidence-readiness-current.json",
    "source_candidate_audit": ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json",
    "production_intake": ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json",
    "production_gap_index": ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
    "operator_packet": ".tmp/validation-shards/integration-spine-operator-evidence-packet-current.json",
    "operator_packet_index": ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json",
    "zero_trust_pqc_gate": ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
    "self_healing_pqc_mesh_gate": ".tmp/validation-shards/self-healing-pqc-mesh-evidence-gate-current.json",
    "paid_client_serviceability_gate": ".tmp/validation-shards/paid-client-serviceability-evidence-gate-current.json",
    "live_rollout_gate": ".tmp/validation-shards/live-rollout-evidence-gate-current.json",
    "external_settlement": ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
    "external_settlement_source": "src/integration/external_settlement.py",
    "image_digests": ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json",
    "rollout_provenance_source": "src/integration/rollout_provenance.py",
    "rollout_provenance_test": "tests/unit/test_integration_rollout_provenance.py",
    "rollout_image_provenance_scaffold": ".tmp/validation-shards/live-rollout-image-provenance-scaffold-current.json",
    "rollout_image_provenance_scaffold_script": "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py",
    "spine_source": "src/integration/spine.py",
    "spine_test": "tests/unit/test_integration_spine.py",
    "source_candidate_source": "src/integration/evidence_source_candidates.py",
    "source_candidate_test": "tests/unit/test_integration_evidence_source_candidates.py",
    "operator_bundle_gate_source": "src/integration/operator_bundle_gate.py",
    "operator_bundle_gate_test": "tests/unit/test_integration_operator_bundle_gate.py",
    "operator_bundle_identity": ".tmp/validation-shards/integration-spine-operator-bundle-identity-current.json",
    "operator_bundle_identity_source": "src/integration/operator_bundle_identity.py",
    "operator_bundle_identity_test": "tests/unit/test_integration_operator_bundle_identity.py",
    "operator_bundle_identity_patch": ".tmp/validation-shards/integration-spine-operator-bundle-identity-patch-current.json",
    "operator_bundle_identity_patch_script": "scripts/ops/apply_operator_bundle_identity_patch.py",
    "operator_bundle_identity_patch_test": "tests/unit/scripts/test_apply_operator_bundle_identity_patch.py",
    "operator_packet_source": "src/integration/operator_evidence_packet.py",
    "operator_packet_test": "tests/unit/test_integration_operator_evidence_packet.py",
    "replacement_passport": ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json",
    "replacement_passport_verification": ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json",
    "replacement_passport_source": "src/integration/production_evidence_replacement_passport.py",
    "replacement_passport_test": "tests/unit/test_integration_production_evidence_replacement_passport.py",
    "raw_bundle_import_script": "scripts/ops/import_production_raw_evidence_bundle.py",
    "raw_template_pack_script": "scripts/ops/generate_production_raw_evidence_template_pack.py",
    "x0t_settlement_scaffold_script": "scripts/ops/scaffold_x0t_external_settlement_evidence.py",
    "x0t_settlement_evidence_script": "scripts/ops/verify_x0t_external_settlement_evidence.py",
    "x0t_settlement_live_rpc_script": "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
    "governance_execute_readiness": ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
    "governance_execute_readiness_source": "src/integration/x0t_governance_execute_readiness.py",
    "governance_execute_readiness_script": "scripts/ops/check_x0t_governance_execute_readiness.py",
    "governance_execute_readiness_test": "tests/unit/test_x0t_governance_execute_readiness.py",
    "governance_execute_handoff": ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json",
    "governance_execute_handoff_source": "src/integration/x0t_governance_execute_handoff.py",
    "governance_execute_handoff_script": "scripts/ops/run_x0t_governance_execute_handoff.py",
    "governance_execute_handoff_test": "tests/unit/test_x0t_governance_execute_handoff.py",
    "x0t_bridge_config": ".tmp/validation-shards/x0t-bridge-config-current.json",
    "x0t_bridge_config_source": "src/integration/x0t_bridge_config.py",
    "x0t_bridge_config_script": "scripts/ops/apply_x0t_bridge_contract_address.py",
    "x0t_bridge_config_test": "tests/unit/dao/test_x0t_bridge_config.py",
    "x0t_contract_readiness": ".tmp/validation-shards/x0t-contract-readiness-current.json",
    "x0t_contract_readiness_source": "src/integration/x0t_contract_readiness.py",
    "x0t_contract_readiness_script": "scripts/ops/check_x0t_contract_readiness.py",
    "x0t_contract_readiness_test": "tests/unit/dao/test_x0t_contract_readiness.py",
    "x0t_contract_build_verification": ".tmp/validation-shards/x0t-contract-build-verification-current.json",
    "x0t_contract_build_verification_source": "src/integration/x0t_contract_build_verification.py",
    "x0t_contract_build_verification_script": "scripts/ops/verify_x0t_contract_build.py",
    "x0t_contract_build_verification_test": "tests/unit/dao/test_x0t_contract_build_verification.py",
    "x0t_bridge_contract_source": "src/dao/contracts/contracts/X0TBridge.sol",
    "x0t_bridge_deploy_script": "src/dao/contracts/scripts/deploy_bridge.js",
    "x0t_bridge_contract_test": "src/dao/contracts/test/X0TBridge.test.js",
    "production_validation_wrapper_test": "tests/unit/test_ops_production_evidence_validation_wrappers.py",
    "required_evidence_consistency": ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json",
    "required_evidence_consistency_source": "src/integration/required_evidence_consistency.py",
    "required_evidence_consistency_test": "tests/unit/test_integration_required_evidence_consistency.py",
    "rollup_approval_contract": ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json",
    "rollup_approval_contract_source": "src/integration/rollup_approval_contract.py",
    "rollup_approval_contract_test": "tests/unit/test_integration_rollup_approval_contract.py",
    "production_input_return_acceptance": ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
    "production_input_return_acceptance_source": "src/integration/production_input_return_acceptance.py",
    "production_input_return_acceptance_test": "tests/unit/test_integration_production_input_return_acceptance.py",
    "production_input_pipeline": ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
    "production_input_pipeline_source": "src/integration/production_input_pipeline.py",
    "production_input_pipeline_test": "tests/unit/test_integration_production_input_pipeline.py",
    "production_closeout_review": ".tmp/validation-shards/integration-spine-production-closeout-review-current.json",
    "production_closeout_review_source": "src/integration/production_closeout_review.py",
    "production_closeout_review_test": "tests/unit/test_integration_production_closeout_review.py",
    "verify_entrypoint": "scripts/verify-v1.1.sh",
}


@dataclass
class LoadedArtifact:
    logical_name: str
    path: str
    exists: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def value(self, dotted_path: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current


@dataclass
class AuditItem:
    item_id: str
    requirement: str
    artifacts: List[str]
    passed: bool
    status: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.item_id,
            "requirement": self.requirement,
            "artifacts": self.artifacts,
            "passed": self.passed,
            "status": self.status,
            "evidence": self.evidence,
            "gaps": self.gaps,
        }


BLOCKED_STATUSES = {
    "AFTER_BLOCKERS",
    "BLOCKING",
    "OPERATOR_APPROVAL_REQUIRED",
    "OPERATOR_INPUT_REQUIRED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_artifacts(root: Path) -> Dict[str, LoadedArtifact]:
    loaded: Dict[str, LoadedArtifact] = {}
    for name, rel_path in ARTIFACTS.items():
        path = root / rel_path
        if not path.exists():
            loaded[name] = LoadedArtifact(name, rel_path, False, error="missing")
            continue
        if path.suffix == ".json":
            try:
                loaded[name] = LoadedArtifact(
                    name,
                    rel_path,
                    True,
                    data=json.loads(path.read_text(encoding="utf-8")),
                )
            except Exception as exc:
                loaded[name] = LoadedArtifact(name, rel_path, True, error=str(exc))
        else:
            loaded[name] = LoadedArtifact(name, rel_path, True)
    return loaded


def _missing_artifacts(artifacts: Dict[str, LoadedArtifact], names: Iterable[str]) -> List[str]:
    return [artifacts[name].path for name in names if not artifacts[name].exists or artifacts[name].error]


def _item(
    item_id: str,
    requirement: str,
    artifacts: Dict[str, LoadedArtifact],
    artifact_names: List[str],
    predicate: Callable[[], bool],
    evidence: Dict[str, Any],
    gap_builder: Callable[[], List[str]],
    blocked_status: str | Callable[[], str] = "BLOCKING",
) -> AuditItem:
    missing = _missing_artifacts(artifacts, artifact_names)
    gaps = list(gap_builder())
    if missing:
        gaps.extend(f"missing or unreadable artifact: {path}" for path in missing)
    passed = not missing and predicate()
    if passed:
        status = "PASS"
    elif missing:
        status = "BLOCKING"
    else:
        status = blocked_status() if callable(blocked_status) else blocked_status
        if status not in BLOCKED_STATUSES:
            status = "BLOCKING"
    return AuditItem(
        item_id=item_id,
        requirement=requirement,
        artifacts=[artifacts[name].path for name in artifact_names],
        passed=passed,
        status=status,
        evidence=evidence,
        gaps=[] if passed else gaps,
    )


def _item_evidence(items: List[AuditItem], item_id: str) -> Dict[str, Any]:
    for item in items:
        if item.item_id == item_id:
            return item.evidence
    return {}


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _status_counts(items: Iterable[AuditItem]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _governance_execution_blocked_status(
    governance_execute: LoadedArtifact,
    governance_execute_handoff: LoadedArtifact,
) -> str:
    if governance_execute.value("decision") == "READY_TO_EXECUTE" and (
        governance_execute.value("summary.execute_ready_now") is True
        or governance_execute_handoff.value("ready_for_operator_execute") is True
    ):
        return "OPERATOR_APPROVAL_REQUIRED"
    if governance_execute.value("decision") in {
        "NOT_READY_TIMELOCK_ACTIVE",
        "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    }:
        return "AFTER_BLOCKERS"
    return "BLOCKING"


def _code_wiring_trace_valid(code: LoadedArtifact) -> bool:
    summary = code.value("summary", {})
    if not isinstance(summary, dict):
        return False
    trace_total = summary.get("trace_cases_total")
    trace_passed = summary.get("trace_cases_passed")
    return (
        bool(code.value("ok"))
        and code.value("status") == "VERIFIED HERE"
        and str(code.value("schema_version", "")).endswith("v2-repo-generated")
        and _is_non_negative_int(trace_total)
        and trace_total > 0
        and trace_passed == trace_total
        and summary.get("trace_cases_failed") == 0
        and summary.get("canonical_identity_consistent") is True
        and summary.get("policy_before_actuator_verified") is True
        and summary.get("simulated_actuator_blocks_settlement") is True
        and summary.get("settlement_failure_fails_closed") is True
        and summary.get("simulated_settlement_fails_closed") is True
        and summary.get("token_rewards_local_only_fails_closed") is True
        and code.value("goal_can_be_marked_complete") is False
        and code.value("mutates_runtime") is False
        and code.value("contacts_live_systems") is False
        and code.value("submits_transaction") is False
    )


def _code_wiring_trace_gaps(code: LoadedArtifact) -> List[str]:
    summary = code.value("summary", {})
    gaps: List[str] = []
    if not str(code.value("schema_version", "")).endswith("v2-repo-generated"):
        gaps.append("code wiring report is not repo-generated v2 executable trace evidence")
    if not isinstance(summary, dict):
        return gaps + ["code wiring report does not expose summary counters"]
    if summary.get("trace_cases_failed") != 0:
        gaps.append("code wiring executable trace has failing cases")
    if summary.get("trace_cases_passed") != summary.get("trace_cases_total"):
        gaps.append("code wiring trace pass count does not match total")
    if summary.get("canonical_identity_consistent") is not True:
        gaps.append("canonical identity consistency is not verified across EventBus trace events")
    if summary.get("policy_before_actuator_verified") is not True:
        gaps.append("policy-before-actuator ordering is not verified")
    if summary.get("simulated_actuator_blocks_settlement") is not True:
        gaps.append("simulated actuator fail-closed behavior is not verified")
    if summary.get("settlement_failure_fails_closed") is not True:
        gaps.append("settlement failure fail-closed behavior is not verified")
    if summary.get("simulated_settlement_fails_closed") is not True:
        gaps.append("simulated settlement fail-closed behavior is not verified")
    if summary.get("token_rewards_local_only_fails_closed") is not True:
        gaps.append("TokenRewards local-only settlement fail-closed behavior is not verified")
    return gaps


def _operator_bundle_manifest_identity_counters(gate: LoadedArtifact) -> Dict[str, Any]:
    return {
        field: gate.value(f"summary.{field}")
        for field in BUNDLE_MANIFEST_IDENTITY_COUNTERS
    }


def _operator_bundle_manifest_identity_counters_valid(gate: LoadedArtifact) -> bool:
    counters = _operator_bundle_manifest_identity_counters(gate)
    files_total = counters["bundle_files_total"]
    files_available = counters["bundle_files_available"]
    if not _is_non_negative_int(files_total) or files_total <= 0:
        return False
    if not _is_non_negative_int(files_available) or files_available > files_total:
        return False
    for field in BUNDLE_MANIFEST_IDENTITY_COUNTERS[2:]:
        value = counters[field]
        if not _is_non_negative_int(value) or value > files_total:
            return False
    return True


def _operator_bundle_manifest_identity_counter_gaps(gates: Iterable[LoadedArtifact]) -> List[str]:
    gaps: List[str] = []
    for gate in gates:
        if not _operator_bundle_manifest_identity_counters_valid(gate):
            gaps.append(f"{gate.logical_name} does not expose valid manifest identity counters")
    return gaps


def _operator_bundle_manifest_identity_audit_gaps(
    gates: Iterable[LoadedArtifact],
    verify_text: str,
) -> List[str]:
    gaps = _operator_bundle_manifest_identity_counter_gaps(gates)
    if "tests/unit/test_integration_operator_bundle_gate.py" not in verify_text:
        gaps.append("operator bundle gate test is not included in scripts/verify-v1.1.sh")
    return gaps


def _operator_packet_raw_identity_suggestion_summaries(
    operator_packet_index: LoadedArtifact,
) -> Dict[str, Dict[str, Any]]:
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    return {
        str(item.get("evidence_key")): item
        for item in summaries
        if isinstance(item, dict)
        and item.get("packet_kind") == "raw_production_bundle"
        and str(item.get("evidence_key")) in RAW_PRODUCTION_EVIDENCE_KEYS
    }


def _operator_packet_raw_identity_suggestions_valid(
    operator_packet_index: LoadedArtifact,
    operator_bundle_identity: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    if (
        operator_bundle_identity.value("decision") == "OPERATOR_BUNDLE_IDENTITY_CLEAN"
        and operator_bundle_identity.value("summary.files_needing_identity_update") == 0
        and operator_bundle_identity.value("summary.manifest_identity_mismatches_total") == 0
    ):
        return True
    raw_summaries = _operator_packet_raw_identity_suggestion_summaries(operator_packet_index)
    if set(raw_summaries) != RAW_PRODUCTION_EVIDENCE_KEYS:
        return False
    for item in raw_summaries.values():
        updates_total = item.get("identity_updates_total")
        plan = item.get("identity_update_plan")
        if not _is_non_negative_int(updates_total) or updates_total <= 0:
            return False
        if not isinstance(plan, list) or len(plan) != updates_total:
            return False
        for plan_item in plan:
            if not isinstance(plan_item, dict):
                return False
            suggested = plan_item.get("suggested_fields", {})
            if not isinstance(suggested, dict):
                return False
            if not all(suggested.get(field) for field in ("collector_id", "raw_id", "file_name")):
                return False
            mismatch_fields = plan_item.get("identity_mismatch_fields", [])
            if not isinstance(mismatch_fields, list) or not mismatch_fields:
                return False
            if not plan_item.get("path"):
                return False
    return True


def _operator_packet_raw_identity_suggestion_gaps(
    operator_packet_index: LoadedArtifact,
    operator_bundle_identity: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    if (
        operator_bundle_identity.value("decision") == "OPERATOR_BUNDLE_IDENTITY_CLEAN"
        and operator_bundle_identity.value("summary.files_needing_identity_update") == 0
        and operator_bundle_identity.value("summary.manifest_identity_mismatches_total") == 0
    ):
        return []
    raw_summaries = _operator_packet_raw_identity_suggestion_summaries(operator_packet_index)
    gaps: List[str] = []
    for key in sorted(RAW_PRODUCTION_EVIDENCE_KEYS - set(raw_summaries)):
        gaps.append(f"operator packet index is missing raw identity suggestions for {key}")
    for key, item in raw_summaries.items():
        updates_total = item.get("identity_updates_total")
        plan = item.get("identity_update_plan")
        if not _is_non_negative_int(updates_total) or updates_total <= 0:
            gaps.append(f"{key} packet summary has no identity updates count")
            continue
        if not isinstance(plan, list) or len(plan) != updates_total:
            gaps.append(f"{key} packet summary identity_update_plan does not match identity_updates_total")
            continue
        for plan_item in plan:
            suggested = plan_item.get("suggested_fields", {}) if isinstance(plan_item, dict) else {}
            mismatch_fields = plan_item.get("identity_mismatch_fields", []) if isinstance(plan_item, dict) else []
            if (
                not isinstance(suggested, dict)
                or not all(suggested.get(field) for field in ("collector_id", "raw_id", "file_name"))
                or not isinstance(mismatch_fields, list)
                or not mismatch_fields
                or not plan_item.get("path")
            ):
                gaps.append(f"{key} packet summary has an incomplete identity suggestion item")
                break
    return gaps


IDENTITY_PATCH_SCRIPT = "scripts/ops/apply_operator_bundle_identity_patch.py"


def _operator_packet_identity_patch_dry_run_summaries(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> Dict[str, Dict[str, Any]]:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return {}
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for item in summaries:
        if (
            not isinstance(item, dict)
            or item.get("packet_kind") != "raw_production_bundle"
            or str(item.get("evidence_key")) not in expected
        ):
            continue
        commands = item.get("commands", [])
        if not isinstance(commands, list):
            continue
        command_texts = [
            str(command.get("command", ""))
            for command in commands
            if isinstance(command, dict)
        ]
        has_dry_run = any(
            IDENTITY_PATCH_SCRIPT in command
            and " --apply" not in command
            for command in command_texts
        )
        has_apply = any(
            IDENTITY_PATCH_SCRIPT in command
            and " --apply" in command
            for command in command_texts
        )
        if has_dry_run and has_apply:
            result[str(item.get("evidence_key"))] = item
    return result


def _operator_packet_identity_patch_dry_run_commands_valid(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> bool:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return True
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    if not raw_summaries:
        return False
    with_commands = _operator_packet_identity_patch_dry_run_summaries(operator_packet_index, priority_order)
    return set(with_commands) == set(raw_summaries)


def _operator_packet_identity_patch_dry_run_command_gaps(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> List[str]:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    if not raw_summaries:
        return ["operator packet index does not expose raw production packet summaries"]
    with_commands = _operator_packet_identity_patch_dry_run_summaries(operator_packet_index, priority_order)
    gaps: List[str] = []
    for key in sorted(set(raw_summaries) - set(with_commands)):
        gaps.append(f"{key} packet is missing identity patch dry-run/apply command pair")
    return gaps


def _operator_packet_replacement_passport_command_summaries(
    operator_packet_index: LoadedArtifact,
) -> Dict[str, Dict[str, Any]]:
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for item in summaries:
        if not isinstance(item, dict):
            continue
        evidence_key = str(item.get("evidence_key", ""))
        commands = item.get("commands", [])
        if not isinstance(commands, list):
            continue
        if any(
            isinstance(command, dict)
            and "src.integration.production_evidence_replacement_passport" in str(command.get("command", ""))
            for command in commands
        ):
            result[evidence_key] = item
    return result


def _operator_packet_replacement_passport_commands_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    packets_total = operator_packet_index.value("summary.packets_total")
    if packets_total != pending_evidence_keys:
        return False
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list) or len(summaries) != pending_evidence_keys:
        return False
    with_command = _operator_packet_replacement_passport_command_summaries(operator_packet_index)
    return len(with_command) == pending_evidence_keys


def _operator_packet_replacement_passport_command_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    with_command = _operator_packet_replacement_passport_command_summaries(operator_packet_index)
    gaps: List[str] = []
    if operator_packet_index.value("summary.packets_total") != pending_evidence_keys:
        gaps.append("operator packet index packet count does not match pending evidence key count")
    for item in summaries:
        if not isinstance(item, dict):
            continue
        evidence_key = str(item.get("evidence_key", ""))
        if evidence_key and evidence_key not in with_command:
            gaps.append(f"{evidence_key} packet is missing production_evidence_replacement_passport rerun command")
    if not summaries:
        gaps.append("operator packet index does not list any packet summaries")
    return gaps


OPERATOR_PACKET_POST_INTAKE_COMMANDS = (
    "src.integration.production_input_return_acceptance",
    "src.integration.production_input_pipeline",
    "src.integration.production_closeout_review",
)


def _operator_packet_post_intake_command_summaries(
    operator_packet_index: LoadedArtifact,
) -> Dict[str, Dict[str, Any]]:
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for item in summaries:
        if not isinstance(item, dict):
            continue
        evidence_key = str(item.get("evidence_key", ""))
        commands = item.get("commands", [])
        if not isinstance(commands, list):
            continue
        command_text = "\n".join(
            str(command.get("command", ""))
            for command in commands
            if isinstance(command, dict)
        )
        if all(fragment in command_text for fragment in OPERATOR_PACKET_POST_INTAKE_COMMANDS):
            result[evidence_key] = item
    return result


def _operator_packet_post_intake_commands_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list) or not summaries:
        return False
    packets_total = operator_packet_index.value("summary.packets_total")
    if packets_total != len(summaries):
        return False
    with_commands = _operator_packet_post_intake_command_summaries(operator_packet_index)
    return len(with_commands) == len(summaries)


def _operator_packet_post_intake_command_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    with_commands = _operator_packet_post_intake_command_summaries(operator_packet_index)
    gaps: List[str] = []
    if operator_packet_index.value("summary.packets_total") != len(summaries):
        gaps.append("operator packet index packet count does not match packet_summaries length")
    for item in summaries:
        if not isinstance(item, dict):
            continue
        evidence_key = str(item.get("evidence_key", ""))
        if evidence_key and evidence_key not in with_commands:
            gaps.append(
                f"{evidence_key} packet is missing return-acceptance, input-pipeline, "
                "or closeout-review rerun command"
            )
    if not summaries:
        gaps.append("operator packet index does not list any packet summaries")
    return gaps


RAW_TEMPLATE_PACK_COMMAND = "scripts/ops/generate_production_raw_evidence_template_pack.py"
RAW_PRODUCTION_OPERATOR_INPUT_FRAGMENTS = (
    "production environment identifier",
    "operator or CI identity",
    "source_commands",
    "domain-specific production observations",
)
RAW_PRODUCTION_REQUIRED_FIELD_FRAGMENTS = (
    "status or evidence_status",
    "collector_id",
    "raw_id",
    "file_name",
    "collected_at",
    "collected_by",
    "source_commands",
    "production_ready",
    "production_promotion_blockers",
    "claim_boundary/environment",
    "template/mock/placeholder markers",
)
SAFE_ROLLOUT_REQUIRED_INPUT_FRAGMENTS = (
    "digest-pinned",
    "provenance artifacts",
)


def _operator_packet_raw_template_pack_summaries(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> Dict[str, Dict[str, Any]]:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return {}
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    return {
        str(item.get("evidence_key")): item
        for item in summaries
        if isinstance(item, dict)
        and item.get("packet_kind") == "raw_production_bundle"
        and str(item.get("evidence_key")) in expected
    }


def _operator_packet_raw_template_pack_commands_valid(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> bool:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return True
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    if not raw_summaries:
        return False
    for item in raw_summaries.values():
        commands = item.get("commands", [])
        fail_closed_rules = item.get("fail_closed_rules", [])
        if not isinstance(commands, list) or not isinstance(fail_closed_rules, list):
            return False
        command_ready = any(
            isinstance(command, dict)
            and RAW_TEMPLATE_PACK_COMMAND in str(command.get("command", ""))
            and command.get("existing_entrypoint") is True
            for command in commands
        )
        fail_closed_ready = any(
            "raw evidence template pack" in str(rule)
            and "production evidence" in str(rule)
            for rule in fail_closed_rules
        )
        if not command_ready or not fail_closed_ready:
            return False
    return True


def _operator_packet_raw_template_pack_command_gaps(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> List[str]:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    gaps: List[str] = []
    if not raw_summaries:
        gaps.append("operator packet index does not expose raw production packet summaries")
    for key, item in raw_summaries.items():
        commands = item.get("commands", [])
        fail_closed_rules = item.get("fail_closed_rules", [])
        command_items = commands if isinstance(commands, list) else []
        rule_items = fail_closed_rules if isinstance(fail_closed_rules, list) else []
        if not any(
            isinstance(command, dict)
            and RAW_TEMPLATE_PACK_COMMAND in str(command.get("command", ""))
            and command.get("existing_entrypoint") is True
            for command in command_items
        ):
            gaps.append(f"{key} packet is missing the production raw evidence template-pack command")
        if not any(
            "raw evidence template pack" in str(rule)
            and "production evidence" in str(rule)
            for rule in rule_items
        ):
            gaps.append(f"{key} packet is missing the raw-template-pack fail-closed rule")
    return gaps


def _operator_packet_raw_required_inputs_valid(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> bool:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return True
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    if not raw_summaries:
        return False
    for key, item in raw_summaries.items():
        operator_inputs = item.get("required_operator_inputs", [])
        required_fields = item.get("required_fields", [])
        commands = item.get("commands", [])
        if not isinstance(operator_inputs, list) or not isinstance(required_fields, list) or not isinstance(commands, list):
            return False
        input_text = "\n".join(str(value) for value in operator_inputs)
        field_text = "\n".join(str(value) for value in required_fields)
        if not all(fragment in input_text for fragment in RAW_PRODUCTION_OPERATOR_INPUT_FRAGMENTS):
            return False
        if not all(fragment in field_text for fragment in RAW_PRODUCTION_REQUIRED_FIELD_FRAGMENTS):
            return False
        if key == "safe_rollout_rollback" and not all(
            fragment in input_text for fragment in SAFE_ROLLOUT_REQUIRED_INPUT_FRAGMENTS
        ):
            return False
        if not any(
            isinstance(command, dict)
            and command.get("requires_operator_input") is True
            and "write real production JSON files" in str(command.get("command", ""))
            for command in commands
        ):
            return False
    return True


def _operator_packet_raw_required_input_gaps(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> List[str]:
    expected = {key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS}
    if not expected:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    raw_summaries = _operator_packet_raw_template_pack_summaries(operator_packet_index, priority_order)
    gaps: List[str] = []
    if not raw_summaries:
        gaps.append("operator packet index does not expose raw production packet summaries")
    for key, item in raw_summaries.items():
        operator_inputs = item.get("required_operator_inputs", [])
        required_fields = item.get("required_fields", [])
        commands = item.get("commands", [])
        input_text = "\n".join(str(value) for value in operator_inputs) if isinstance(operator_inputs, list) else ""
        field_text = "\n".join(str(value) for value in required_fields) if isinstance(required_fields, list) else ""
        command_items = commands if isinstance(commands, list) else []
        if not isinstance(operator_inputs, list):
            gaps.append(f"{key} packet required_operator_inputs is not a list")
        if not isinstance(required_fields, list):
            gaps.append(f"{key} packet required_fields is not a list")
        if not isinstance(commands, list):
            gaps.append(f"{key} packet commands is not a list")
        for fragment in RAW_PRODUCTION_OPERATOR_INPUT_FRAGMENTS:
            if fragment not in input_text:
                gaps.append(f"{key} required_operator_inputs missing: {fragment}")
        for fragment in RAW_PRODUCTION_REQUIRED_FIELD_FRAGMENTS:
            if fragment not in field_text:
                gaps.append(f"{key} required_fields missing: {fragment}")
        if key == "safe_rollout_rollback":
            for fragment in SAFE_ROLLOUT_REQUIRED_INPUT_FRAGMENTS:
                if fragment not in input_text:
                    gaps.append(f"{key} required_operator_inputs missing: {fragment}")
        if not any(
            isinstance(command, dict)
            and command.get("requires_operator_input") is True
            and "write real production JSON files" in str(command.get("command", ""))
            for command in command_items
        ):
            gaps.append(f"{key} packet is missing the required operator JSON write step")
    return gaps


def _operator_packet_rollout_scaffold_command_valid(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> bool:
    if "safe_rollout_rollback" not in priority_order:
        return True
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return False
    for item in summaries:
        if not isinstance(item, dict) or item.get("evidence_key") != "safe_rollout_rollback":
            continue
        commands = item.get("commands", [])
        fail_closed_rules = item.get("fail_closed_rules", [])
        if not isinstance(commands, list) or not isinstance(fail_closed_rules, list):
            return False
        scaffold_command_ready = any(
            isinstance(command, dict)
            and "scaffold_live_rollout_image_provenance_evidence.py" in str(command.get("command", ""))
            and command.get("existing_entrypoint") is True
            for command in commands
        )
        fail_closed_ready = any(
            "scaffold templates" in str(rule)
            for rule in fail_closed_rules
        )
        return scaffold_command_ready and fail_closed_ready
    return False


def _operator_packet_rollout_scaffold_command_gaps(
    operator_packet_index: LoadedArtifact,
    priority_order: List[str],
) -> List[str]:
    if "safe_rollout_rollback" not in priority_order:
        return []
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return ["operator packet index does not expose packet_summaries"]
    for item in summaries:
        if not isinstance(item, dict) or item.get("evidence_key") != "safe_rollout_rollback":
            continue
        commands = item.get("commands", [])
        fail_closed_rules = item.get("fail_closed_rules", [])
        gaps: List[str] = []
        command_items = commands if isinstance(commands, list) else []
        rule_items = fail_closed_rules if isinstance(fail_closed_rules, list) else []
        if not any(
            isinstance(command, dict)
            and "scaffold_live_rollout_image_provenance_evidence.py" in str(command.get("command", ""))
            and command.get("existing_entrypoint") is True
            for command in command_items
        ):
            gaps.append("safe_rollout_rollback packet is missing the live rollout image provenance scaffold command")
        if not any("scaffold templates" in str(rule) for rule in rule_items):
            gaps.append("safe_rollout_rollback packet is missing the scaffold-template fail-closed rule")
        return gaps
    return ["operator packet index is missing safe_rollout_rollback packet summary"]


EXTERNAL_SETTLEMENT_WRAPPER_COMMANDS = (
    "scripts/ops/verify_x0t_external_settlement_evidence.py",
    "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
)
EXTERNAL_SETTLEMENT_SCAFFOLD_COMMAND = "scripts/ops/scaffold_x0t_external_settlement_evidence.py"
EXTERNAL_SETTLEMENT_CAPTURE_COMMAND_GROUPS = (
    ("src.integration.external_settlement", "--preflight-capture-inputs", "--require-preflight-ready"),
    ("src.integration.external_settlement", "--capture-from-rpc", "--write-evidence", "--require-ready"),
)
EXTERNAL_SETTLEMENT_OPERATOR_INPUT_COMMANDS = (
    "X0T_BASE_RPC_URL",
    "X0T_SETTLEMENT_TX_HASH",
    "X0T_DESTINATION_CHAIN",
    "X0T_SETTLEMENT_ID",
)
EXTERNAL_SETTLEMENT_OPERATOR_INPUT_FRAGMENTS = (
    "transaction hash",
    "destination Base chain",
    "settlement_id",
    "read-only RPC URL",
    "source commands and explorer URL",
)
EXTERNAL_SETTLEMENT_REQUIRED_FIELD_FRAGMENTS = (
    "transaction_hash",
    "destination_chain",
    "settlement_id",
    "source_commands",
    "explorer_url",
    "packet_hash",
)
GOVERNANCE_EXECUTE_DECISIONS = {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
    "VETOED_NOT_EXECUTABLE",
    "NOT_READY_STATE_NOT_EXECUTABLE",
}


def _operator_packet_external_settlement_summary(operator_packet_index: LoadedArtifact) -> Dict[str, Any]:
    summaries = operator_packet_index.value("packet_summaries", []) or []
    if not isinstance(summaries, list):
        return {}
    for item in summaries:
        if isinstance(item, dict) and item.get("evidence_key") == "external_settlement":
            return item
    return {}


def _operator_packet_external_settlement_operator_inputs_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    if summary.get("packet_kind") != "external_settlement":
        return False
    operator_inputs = summary.get("required_operator_inputs", [])
    required_fields = summary.get("required_fields", [])
    commands = summary.get("commands", [])
    if not isinstance(operator_inputs, list) or not isinstance(required_fields, list) or not isinstance(commands, list):
        return False
    input_text = "\n".join(str(item) for item in operator_inputs)
    field_text = "\n".join(str(item) for item in required_fields)
    operator_input_commands = [
        str(command.get("command", ""))
        for command in commands
        if isinstance(command, dict)
        and command.get("requires_operator_input") is True
        and str(command.get("command", "")).startswith("export X0T_")
    ]
    return (
        all(fragment in input_text for fragment in EXTERNAL_SETTLEMENT_OPERATOR_INPUT_FRAGMENTS)
        and all(fragment in field_text for fragment in EXTERNAL_SETTLEMENT_REQUIRED_FIELD_FRAGMENTS)
        and all(
            any(fragment in command for command in operator_input_commands)
            for fragment in EXTERNAL_SETTLEMENT_OPERATOR_INPUT_COMMANDS
        )
    )


def _operator_packet_external_settlement_operator_input_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    if not summary:
        return ["operator packet index does not expose the external_settlement packet summary"]
    if summary.get("packet_kind") != "external_settlement":
        return ["external_settlement packet summary has the wrong packet_kind"]
    operator_inputs = summary.get("required_operator_inputs", [])
    required_fields = summary.get("required_fields", [])
    commands = summary.get("commands", [])
    gaps: List[str] = []
    input_text = "\n".join(str(item) for item in operator_inputs) if isinstance(operator_inputs, list) else ""
    field_text = "\n".join(str(item) for item in required_fields) if isinstance(required_fields, list) else ""
    command_items = commands if isinstance(commands, list) else []
    operator_input_commands = [
        str(command.get("command", ""))
        for command in command_items
        if isinstance(command, dict)
        and command.get("requires_operator_input") is True
        and str(command.get("command", "")).startswith("export X0T_")
    ]
    for fragment in EXTERNAL_SETTLEMENT_OPERATOR_INPUT_FRAGMENTS:
        if fragment not in input_text:
            gaps.append(f"external_settlement required_operator_inputs missing: {fragment}")
    for fragment in EXTERNAL_SETTLEMENT_REQUIRED_FIELD_FRAGMENTS:
        if fragment not in field_text:
            gaps.append(f"external_settlement required_fields missing: {fragment}")
    for fragment in EXTERNAL_SETTLEMENT_OPERATOR_INPUT_COMMANDS:
        if not any(fragment in command for command in operator_input_commands):
            gaps.append(f"external_settlement packet is missing required operator input export: {fragment}")
    if not isinstance(operator_inputs, list):
        gaps.append("external_settlement packet required_operator_inputs is not a list")
    if not isinstance(required_fields, list):
        gaps.append("external_settlement packet required_fields is not a list")
    if not isinstance(commands, list):
        gaps.append("external_settlement packet commands is not a list")
    return gaps


def _operator_packet_external_settlement_wrapper_commands_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    commands = summary.get("commands", []) if isinstance(summary, dict) else []
    if not isinstance(commands, list):
        return False
    command_text = "\n".join(
        str(command.get("command", ""))
        for command in commands
        if isinstance(command, dict)
    )
    return (
        summary.get("packet_kind") == "external_settlement"
        and summary.get("commands_missing_entrypoints") == 0
        and all(fragment in command_text for fragment in EXTERNAL_SETTLEMENT_WRAPPER_COMMANDS)
    )


def _operator_packet_external_settlement_capture_commands_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
    verify_text: str,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    commands = summary.get("commands", []) if isinstance(summary, dict) else []
    if not isinstance(commands, list):
        return False
    command_items = [
        command
        for command in commands
        if isinstance(command, dict)
    ]
    return (
        summary.get("packet_kind") == "external_settlement"
        and summary.get("commands_missing_entrypoints") == 0
        and all(
            any(
                command.get("existing_entrypoint") is True
                and all(fragment in str(command.get("command", "")) for fragment in fragments)
                for command in command_items
            )
            for fragments in EXTERNAL_SETTLEMENT_CAPTURE_COMMAND_GROUPS
        )
        and "integration-spine external settlement capture preflight fails closed" in verify_text
        and "CAPTURE_INPUTS_BLOCKED" in verify_text
    )


def _operator_packet_external_settlement_capture_command_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
    verify_text: str,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    if not summary:
        return ["operator packet index does not expose the external_settlement packet summary"]
    commands = summary.get("commands", [])
    if not isinstance(commands, list):
        return ["external_settlement packet summary does not expose commands"]
    command_items = [
        command
        for command in commands
        if isinstance(command, dict)
    ]
    gaps: List[str] = []
    for fragments in EXTERNAL_SETTLEMENT_CAPTURE_COMMAND_GROUPS:
        if not any(
            command.get("existing_entrypoint") is True
            and all(fragment in str(command.get("command", "")) for fragment in fragments)
            for command in command_items
        ):
            gaps.append(
                "external_settlement packet is missing capture command group: "
                + " ".join(fragments)
            )
    if summary.get("commands_missing_entrypoints") != 0:
        gaps.append("external_settlement packet reports missing command entrypoints")
    if summary.get("packet_kind") != "external_settlement":
        gaps.append("external_settlement packet summary has the wrong packet_kind")
    if "integration-spine external settlement capture preflight fails closed" not in verify_text:
        gaps.append("scripts/verify-v1.1.sh does not run the external settlement capture preflight smoke")
    if "CAPTURE_INPUTS_BLOCKED" not in verify_text:
        gaps.append("scripts/verify-v1.1.sh does not assert the blocked capture-input decision")
    return gaps


def _operator_packet_external_settlement_wrapper_command_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    if not summary:
        return ["operator packet index does not expose the external_settlement packet summary"]
    commands = summary.get("commands", [])
    if not isinstance(commands, list):
        return ["external_settlement packet summary does not expose commands"]
    command_text = "\n".join(
        str(command.get("command", ""))
        for command in commands
        if isinstance(command, dict)
    )
    gaps = [
        f"external_settlement packet is missing {fragment}"
        for fragment in EXTERNAL_SETTLEMENT_WRAPPER_COMMANDS
        if fragment not in command_text
    ]
    if summary.get("commands_missing_entrypoints") != 0:
        gaps.append("external_settlement packet reports missing command entrypoints")
    if summary.get("packet_kind") != "external_settlement":
        gaps.append("external_settlement packet summary has the wrong packet_kind")
    return gaps


def _operator_packet_external_settlement_scaffold_command_valid(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> bool:
    if pending_evidence_keys == 0:
        return True
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    commands = summary.get("commands", []) if isinstance(summary, dict) else []
    fail_closed_rules = summary.get("fail_closed_rules", []) if isinstance(summary, dict) else []
    if not isinstance(commands, list) or not isinstance(fail_closed_rules, list):
        return False
    command_ready = any(
        isinstance(command, dict)
        and EXTERNAL_SETTLEMENT_SCAFFOLD_COMMAND in str(command.get("command", ""))
        and command.get("existing_entrypoint") is True
        for command in commands
    )
    fail_closed_ready = any("scaffold templates" in str(rule) for rule in fail_closed_rules)
    return command_ready and fail_closed_ready


def _operator_packet_external_settlement_scaffold_command_gaps(
    operator_packet_index: LoadedArtifact,
    pending_evidence_keys: int,
) -> List[str]:
    if pending_evidence_keys == 0:
        return []
    summary = _operator_packet_external_settlement_summary(operator_packet_index)
    if not summary:
        return ["operator packet index does not expose the external_settlement packet summary"]
    commands = summary.get("commands", [])
    fail_closed_rules = summary.get("fail_closed_rules", [])
    command_items = commands if isinstance(commands, list) else []
    rule_items = fail_closed_rules if isinstance(fail_closed_rules, list) else []
    gaps: List[str] = []
    if not any(
        isinstance(command, dict)
        and EXTERNAL_SETTLEMENT_SCAFFOLD_COMMAND in str(command.get("command", ""))
        and command.get("existing_entrypoint") is True
        for command in command_items
    ):
        gaps.append("external_settlement packet is missing the external settlement scaffold command")
    if not any("scaffold templates" in str(rule) for rule in rule_items):
        gaps.append("external_settlement packet is missing the scaffold-template fail-closed rule")
    return gaps


def _command_entrypoint_exists(root: Path, command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    for part in parts:
        if part.endswith(".py") or part.endswith(".sh"):
            return (root / part).exists()
    if len(parts) >= 3 and parts[0] == "python3" and parts[1] == "-m":
        return (root / (parts[2].replace(".", "/") + ".py")).exists()
    return False


def _replacement_passport_validation_commands(
    replacement_passport: LoadedArtifact,
) -> List[str]:
    commands: List[str] = []
    items = replacement_passport.value("replacement_items", []) or []
    if not isinstance(items, list):
        return commands
    for item in items:
        if not isinstance(item, dict):
            continue
        contract = item.get("replacement_contract", {})
        if not isinstance(contract, dict):
            continue
        for command in contract.get("validation_commands", []) or []:
            if isinstance(command, str) and command not in commands:
                commands.append(command)
    return commands


def _replacement_passport_scaffold_commands(
    replacement_passport: LoadedArtifact,
) -> List[str]:
    commands: List[str] = []
    items = replacement_passport.value("replacement_items", []) or []
    if not isinstance(items, list):
        return commands
    for item in items:
        if not isinstance(item, dict):
            continue
        contract = item.get("replacement_contract", {})
        if not isinstance(contract, dict):
            continue
        command = contract.get("external_scaffold_command")
        if isinstance(command, str) and command and command not in commands:
            commands.append(command)
    return commands


def _replacement_passport_validation_command_gaps(
    root: Path,
    replacement_passport: LoadedArtifact,
    verify_text: str,
) -> List[str]:
    commands = _replacement_passport_validation_commands(replacement_passport)
    gaps = [
        f"replacement passport validation command has no local entrypoint: {command}"
        for command in commands
        if not _command_entrypoint_exists(root, command)
    ]
    if not commands:
        gaps.append("replacement passport does not expose validation_commands")
    if "tests/unit/test_ops_production_evidence_validation_wrappers.py" not in verify_text:
        gaps.append("production evidence validation wrapper tests are not included in scripts/verify-v1.1.sh")
    return gaps


def _replacement_passport_scaffold_command_gaps(
    root: Path,
    replacement_passport: LoadedArtifact,
    verify_text: str,
) -> List[str]:
    commands = _replacement_passport_scaffold_commands(replacement_passport)
    gaps = [
        f"replacement passport external scaffold command has no local entrypoint: {command}"
        for command in commands
        if not _command_entrypoint_exists(root, command)
    ]
    if not commands:
        gaps.append("replacement passport does not expose an external settlement scaffold command")
    if "tests/unit/test_ops_production_evidence_validation_wrappers.py" not in verify_text:
        gaps.append("external settlement scaffold wrapper test is not included in scripts/verify-v1.1.sh")
    return gaps


def build_checklist(root: Path) -> List[AuditItem]:
    artifacts = load_artifacts(root)
    code = artifacts["code_wiring"]
    rollup = artifacts["current_rollup"]
    raw = artifacts["raw_inventory"]
    semantic = artifacts["semantic_queue"]
    readiness = artifacts["evidence_readiness"]
    source_candidates = artifacts["source_candidate_audit"]
    intake = artifacts["production_intake"]
    gap_index = artifacts["production_gap_index"]
    operator_packet = artifacts["operator_packet"]
    operator_packet_index = artifacts["operator_packet_index"]
    operator_bundle_identity = artifacts["operator_bundle_identity"]
    operator_bundle_identity_patch = artifacts["operator_bundle_identity_patch"]
    replacement_passport = artifacts["replacement_passport"]
    replacement_passport_verification = artifacts["replacement_passport_verification"]
    required_evidence_consistency = artifacts["required_evidence_consistency"]
    rollup_approval_contract = artifacts["rollup_approval_contract"]
    production_input_return_acceptance = artifacts["production_input_return_acceptance"]
    production_input_pipeline = artifacts["production_input_pipeline"]
    production_closeout_review = artifacts["production_closeout_review"]
    governance_execute = artifacts["governance_execute_readiness"]
    governance_execute_handoff = artifacts["governance_execute_handoff"]
    x0t_bridge_config = artifacts["x0t_bridge_config"]
    x0t_contract_readiness = artifacts["x0t_contract_readiness"]
    x0t_contract_build = artifacts["x0t_contract_build_verification"]
    operator_bundle_gates = [
        artifacts["zero_trust_pqc_gate"],
        artifacts["self_healing_pqc_mesh_gate"],
        artifacts["paid_client_serviceability_gate"],
        artifacts["live_rollout_gate"],
    ]
    settlement = artifacts["external_settlement"]
    image = artifacts["image_digests"]
    rollout_image_provenance_scaffold = artifacts["rollout_image_provenance_scaffold"]

    wiring_covered = set((code.data or {}).get("wiring_covered", {}).keys())
    missing_wiring = sorted(REQUIRED_WIRING_KEYS - wiring_covered)

    verify_text = ""
    verify_path = root / ARTIFACTS["verify_entrypoint"]
    if verify_path.exists():
        verify_text = verify_path.read_text(encoding="utf-8", errors="replace")

    pending_evidence_keys = gap_index.value("summary.pending_evidence_keys", 0) or 0
    primary_gap_key = gap_index.value("summary.primary_blocker_evidence_key", "")
    priority_order = gap_index.value("operator_priority_order", []) or []
    expected_packet_key = primary_gap_key or (priority_order[0] if priority_order else "")
    operator_packet_actionable = (
        operator_packet.value("status") == "VERIFIED HERE"
        and operator_packet.value("ok") is True
        and operator_packet.value("actionable") is True
        and operator_packet.value("summary.commands_missing_entrypoints") == 0
        and (
            (
                pending_evidence_keys > 0
                and operator_packet.value("decision") == "OPERATOR_ACTION_REQUIRED"
                and operator_packet.value("summary.operator_action_required") is True
                and operator_packet.value("selected_evidence_key") == expected_packet_key
                and operator_packet.value("selected_evidence_key") in REQUIRED_EVIDENCE_KEYS
                and operator_packet.value("summary.commands_total", 0) > 0
            )
            or (
                pending_evidence_keys == 0
                and operator_packet.value("decision") == "NO_ACTION_REQUIRED"
                and operator_packet.value("summary.operator_action_required") is False
            )
        )
    )

    items: List[AuditItem] = [
        _item(
            "local_spine_code_wiring",
            "Local spine code connects the required identity, event, policy, actuator, and settlement adapters.",
            artifacts,
            ["code_wiring", "code_wiring_source", "code_wiring_test", "spine_source", "spine_test"],
            lambda: _code_wiring_trace_valid(code) and not missing_wiring,
            {
                "status": code.value("status"),
                "ok": code.value("ok"),
                "schema_version": code.value("schema_version"),
                "wiring_covered": sorted(wiring_covered),
                "required_wiring": sorted(REQUIRED_WIRING_KEYS),
                "trace_cases_total": code.value("summary.trace_cases_total"),
                "trace_cases_passed": code.value("summary.trace_cases_passed"),
                "trace_cases_failed": code.value("summary.trace_cases_failed"),
                "canonical_identity_consistent": code.value("summary.canonical_identity_consistent"),
                "policy_before_actuator_verified": code.value("summary.policy_before_actuator_verified"),
                "simulated_actuator_blocks_settlement": code.value(
                    "summary.simulated_actuator_blocks_settlement"
                ),
                "settlement_failure_fails_closed": code.value(
                    "summary.settlement_failure_fails_closed"
                ),
                "simulated_settlement_fails_closed": code.value(
                    "summary.simulated_settlement_fails_closed"
                ),
                "token_rewards_local_only_fails_closed": code.value(
                    "summary.token_rewards_local_only_fails_closed"
                ),
            },
            lambda: [f"missing wiring key: {key}" for key in missing_wiring]
            + _code_wiring_trace_gaps(code),
        ),
        _item(
            "single_identity_contract",
            "Every spine request carries one canonical identity with node_id, SPIFFE ID, optional DID, and optional reward wallet.",
            artifacts,
            ["code_wiring", "spine_source", "spine_test"],
            lambda: "identity" in wiring_covered and "SpineIdentity" in (root / ARTIFACTS["spine_source"]).read_text(encoding="utf-8", errors="replace"),
            {"wiring_entry": code.value("wiring_covered.identity")},
            lambda: ["SpineIdentity contract not evidenced"],
        ),
        _item(
            "event_bus_contract",
            "The spine emits auditable events through the project EventBus.",
            artifacts,
            ["code_wiring", "spine_source", "spine_test"],
            lambda: "event_bus" in wiring_covered and "EventBus" in (root / ARTIFACTS["spine_source"]).read_text(encoding="utf-8", errors="replace"),
            {"wiring_entry": code.value("wiring_covered.event_bus")},
            lambda: ["EventBus wiring not evidenced"],
        ),
        _item(
            "policy_engine_contract",
            "Policy evaluation happens before any actuator or settlement side effect and fails closed.",
            artifacts,
            ["code_wiring", "spine_source", "spine_test"],
            lambda: "policy_engine" in wiring_covered and "POLICY_DENIED" in (root / ARTIFACTS["spine_source"]).read_text(encoding="utf-8", errors="replace"),
            {"wiring_entry": code.value("wiring_covered.policy_engine")},
            lambda: ["policy fail-closed contract not evidenced"],
        ),
        _item(
            "safe_actuator_contract",
            "The actuator blocks missing, failed, exception, or simulated execution before settlement.",
            artifacts,
            ["code_wiring", "spine_source", "spine_test"],
            lambda: "safe_actuator" in wiring_covered and "ACTUATOR_SIMULATED" in (root / ARTIFACTS["spine_source"]).read_text(encoding="utf-8", errors="replace"),
            {"wiring_entry": code.value("wiring_covered.safe_actuator")},
            lambda: ["safe actuator fail-closed contract not evidenced"],
        ),
        _item(
            "settlement_reward_contract",
            "Reward settlement is called only after identity validation, policy allow, and successful non-simulated action.",
            artifacts,
            ["code_wiring", "spine_source", "spine_test"],
            lambda: "settlement_reward_loop" in wiring_covered and "reward_relay" in (root / ARTIFACTS["spine_source"]).read_text(encoding="utf-8", errors="replace"),
            {"wiring_entry": code.value("wiring_covered.settlement_reward_loop")},
            lambda: ["settlement/reward adapter contract not evidenced"],
        ),
        _item(
            "verify_entrypoint_includes_spine",
            "The non-fast local verification entrypoint includes integration spine, current rollup, semantic queue, raw evidence inventory, source-candidate, operator-bundle-gate, operator-bundle-identity, operator-packet, completion-audit, production-evidence-intake, evidence-readiness, X0T token bridge, X0T settlement-gate, X0T governance execute-readiness/handoff, and rollout-provenance unit tests.",
            artifacts,
            [
                "verify_entrypoint",
                "spine_test",
                "token_bridge_source",
                "token_bridge_test",
                "current_rollup_test",
                "semantic_queue_test",
                "raw_inventory_test",
                "source_candidate_test",
                "operator_bundle_gate_test",
                "operator_bundle_identity_test",
                "operator_packet_test",
                "governance_execute_readiness_test",
                "governance_execute_handoff_test",
                "code_wiring",
            ],
            lambda: (
                "tests/unit/test_integration_spine.py" in verify_text
                and "tests/unit/test_integration_completion_audit.py" in verify_text
                and "tests/unit/test_integration_current_evidence_rollup.py" in verify_text
                and "tests/unit/test_integration_semantic_production_blocker_queue.py" in verify_text
                and "tests/unit/test_integration_raw_evidence_inventory.py" in verify_text
                and "tests/unit/test_integration_evidence_source_candidates.py" in verify_text
                and "tests/unit/test_integration_operator_bundle_gate.py" in verify_text
                and "tests/unit/test_integration_operator_bundle_identity.py" in verify_text
                and "tests/unit/test_integration_operator_evidence_packet.py" in verify_text
                and "tests/unit/test_integration_production_evidence_intake.py" in verify_text
                and "tests/unit/test_integration_evidence_readiness.py" in verify_text
                and "tests/unit/test_integration_external_settlement.py" in verify_text
                and "tests/unit/test_integration_rollout_provenance.py" in verify_text
                and "tests/unit/test_integration_rollup_approval_contract.py" in verify_text
                and "tests/unit/test_integration_production_input_return_acceptance.py" in verify_text
                and "tests/unit/test_integration_production_closeout_review.py" in verify_text
                and "tests/unit/test_x0t_governance_execute_readiness.py" in verify_text
                and "tests/unit/test_x0t_governance_execute_handoff.py" in verify_text
                and "tests/unit/dao/test_token_bridge_unit.py" in verify_text
                and "tests/unit/dao/test_x0t_bridge_config.py" in verify_text
                and "tests/unit/dao/test_x0t_contract_readiness.py" in verify_text
                and "tests/unit/dao/test_x0t_contract_build_verification.py" in verify_text
                and "BridgeDeposit" in (root / ARTIFACTS["token_bridge_source"]).read_text(
                    encoding="utf-8", errors="replace"
                )
            ),
            {"verify_entrypoint_integration": code.value("verify_entrypoint_integration")},
            lambda: [
                "scripts/verify-v1.1.sh must include integration spine, current rollup, semantic queue, raw evidence inventory, source candidate, operator bundle gate, operator bundle identity, operator packet, completion audit, production evidence intake, evidence readiness, TokenBridge BridgeDeposit coverage, external settlement, X0T governance execute-readiness/handoff, rollout provenance, rollup approval contract, production input return acceptance, and production closeout review unit tests"
            ],
        ),
        _item(
            "x0t_bridge_config_handoff_actionable",
            "X0T bridge contract address configuration has a repo-generated fail-closed operator path that rejects placeholders and governance/token addresses before config mutation.",
            artifacts,
            [
                "x0t_bridge_config",
                "x0t_bridge_config_source",
                "x0t_bridge_config_script",
                "x0t_bridge_config_test",
                "verify_entrypoint",
            ],
            lambda: (
                x0t_bridge_config.value("status") == "VERIFIED HERE"
                and x0t_bridge_config.value("ok") is True
                and x0t_bridge_config.value("schema_version") == "x0tta6bl4-x0t-bridge-config-v1"
                and x0t_bridge_config.value("decision")
                in {
                    "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
                    "X0T_BRIDGE_CONFIG_READY_TO_APPLY",
                    "X0T_BRIDGE_CONFIG_READY",
                }
                and x0t_bridge_config.value("goal_can_be_marked_complete") is False
                and x0t_bridge_config.value("mutates_chain") is False
                and x0t_bridge_config.value("runs_live_rpc") is False
                and x0t_bridge_config.value("submits_transaction") is False
                and x0t_bridge_config.value("write.approval_env") == "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
                and x0t_bridge_config.value("write.approval_value_required") == "apply-bridge-address-base-sepolia"
                and "tests/unit/dao/test_x0t_bridge_config.py" in verify_text
                and "X0T bridge config current shard is actionable and fail-closed" in verify_text
            ),
            {
                "decision": x0t_bridge_config.value("decision"),
                "bridge_config_ready": x0t_bridge_config.value("bridge_config_ready"),
                "bridge_address_input_ready": x0t_bridge_config.value("summary.bridge_address_input_ready"),
                "configured_bridge_ready": x0t_bridge_config.value("summary.configured_bridge_ready"),
                "write_performed": x0t_bridge_config.value("summary.write_performed"),
                "approval_env": x0t_bridge_config.value("write.approval_env"),
                "approval_value_required": x0t_bridge_config.value("write.approval_value_required"),
                "missing_inputs_total": x0t_bridge_config.value("summary.missing_inputs_total"),
                "test_in_verify_entrypoint": "tests/unit/dao/test_x0t_bridge_config.py" in verify_text,
                "smoke_in_verify_entrypoint": "X0T bridge config current shard is actionable and fail-closed" in verify_text,
            },
            lambda: [
                "X0T bridge config shard is missing, unsafe, not fail-closed, or not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "x0t_contract_readiness_reproducible",
            "X0T contract/deployment readiness is generated by repo code, includes Node 22 Hardhat compile/test evidence, and exposes bridge config commands without submitting transactions.",
            artifacts,
            [
                "x0t_contract_readiness",
                "x0t_contract_readiness_source",
                "x0t_contract_readiness_script",
                "x0t_contract_readiness_test",
                "x0t_contract_build_verification",
                "x0t_contract_build_verification_source",
                "x0t_contract_build_verification_script",
                "x0t_contract_build_verification_test",
                "x0t_bridge_contract_source",
                "x0t_bridge_deploy_script",
                "x0t_bridge_contract_test",
                "x0t_bridge_config",
                "verify_entrypoint",
            ],
            lambda: (
                x0t_contract_readiness.value("status") == "VERIFIED HERE"
                and x0t_contract_readiness.value("ok") is True
                and x0t_contract_readiness.value("schema_version") == "x0tta6bl4-x0t-contract-readiness-v1"
                and x0t_contract_readiness.value("goal_can_be_marked_complete") is False
                and x0t_contract_readiness.value("mutates_chain") is False
                and x0t_contract_readiness.value("runs_live_rpc") is False
                and x0t_contract_readiness.value("submits_transaction") is False
                and x0t_contract_readiness.value("summary.build_env_ready") is True
                and x0t_contract_readiness.value("summary.contract_build_verification_ready") is True
                and x0t_contract_readiness.value("summary.base_sepolia_manifest_ready") is True
                and x0t_contract_readiness.value("summary.legacy_contract_surface_ready") is True
                and x0t_contract_readiness.value("summary.bridge_contract_source_ready") is True
                and x0t_contract_build.value("contract_build_verified") is True
                and x0t_contract_build.value("summary.hardhat_compile_ready") is True
                and x0t_contract_build.value("summary.hardhat_test_ready") is True
                and "tests/unit/dao/test_x0t_contract_readiness.py" in verify_text
                and "tests/unit/dao/test_x0t_contract_build_verification.py" in verify_text
                and "X0T contract/deployment readiness current shard is verified and fail-closed" in verify_text
                and "X0T contract build verification artifact proves Node 22 Hardhat compile/test" in verify_text
            ),
            {
                "decision": x0t_contract_readiness.value("decision"),
                "contract_readiness_clear": x0t_contract_readiness.value("contract_readiness_clear"),
                "build_env_ready": x0t_contract_readiness.value("summary.build_env_ready"),
                "contract_build_verification_ready": x0t_contract_readiness.value("summary.contract_build_verification_ready"),
                "deployment_config_ready": x0t_contract_readiness.value("summary.deployment_config_ready"),
                "operator_configs_ready": x0t_contract_readiness.value("summary.operator_configs_ready"),
                "bridge_contract_source_ready": x0t_contract_readiness.value("summary.bridge_contract_source_ready"),
                "contract_build_verified": x0t_contract_build.value("contract_build_verified"),
                "hardhat_compile_ready": x0t_contract_build.value("summary.hardhat_compile_ready"),
                "hardhat_test_ready": x0t_contract_build.value("summary.hardhat_test_ready"),
                "missing_inputs": x0t_contract_readiness.value("missing_inputs", []),
                "test_in_verify_entrypoint": "tests/unit/dao/test_x0t_contract_readiness.py" in verify_text,
            },
            lambda: [
                "X0T contract readiness/build verification is missing, stale, unsafe, or not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "x0t_governance_execute_readiness_reproducible",
            "X0T governance proposal execute-readiness is generated by a read-only local wrapper, covered by unit tests, and never submits transactions.",
            artifacts,
            [
                "governance_execute_readiness",
                "governance_execute_readiness_source",
                "governance_execute_readiness_script",
                "governance_execute_readiness_test",
                "verify_entrypoint",
            ],
            lambda: (
                governance_execute.value("status") == "VERIFIED HERE"
                and governance_execute.value("ok") is True
                and governance_execute.value("decision") in GOVERNANCE_EXECUTE_DECISIONS
                and governance_execute.value("goal_can_be_marked_complete") is False
                and governance_execute.value("mutates_chain") is False
                and governance_execute.value("submits_transaction") is False
                and governance_execute.value("runs_live_rpc") is True
                and "tests/unit/test_x0t_governance_execute_readiness.py" in verify_text
            ),
            {
                "decision": governance_execute.value("decision"),
                "proposal_id": governance_execute.value("proposal_id"),
                "state_label": governance_execute.value("proposal_state.state_label"),
                "execute_ready_now": governance_execute.value("summary.execute_ready_now"),
                "proposal_executed": governance_execute.value("proposal_state.executed"),
                "proposal_vetoed": governance_execute.value("proposal_state.vetoed"),
                "next_executable_after_utc": governance_execute.value("summary.next_executable_after_utc"),
                "seconds_until_earliest_execution_by_block_time": governance_execute.value(
                    "timelock.seconds_until_earliest_execution_by_block_time"
                ),
                "mutates_chain": governance_execute.value("mutates_chain"),
                "submits_transaction": governance_execute.value("submits_transaction"),
                "runs_live_rpc": governance_execute.value("runs_live_rpc"),
                "test_in_verify_entrypoint": "tests/unit/test_x0t_governance_execute_readiness.py" in verify_text,
            },
            lambda: [
                "governance execute-readiness shard is missing, stale, not read-only, or not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "x0t_governance_execute_handoff_actionable",
            "X0T governance proposal execution has a repo-generated read-only operator handoff with explicit approval and receipt boundaries.",
            artifacts,
            [
                "governance_execute_handoff",
                "governance_execute_handoff_source",
                "governance_execute_handoff_script",
                "governance_execute_handoff_test",
                "governance_execute_readiness",
                "verify_entrypoint",
            ],
            lambda: (
                governance_execute_handoff.value("status") == "VERIFIED HERE"
                and governance_execute_handoff.value("ok") is True
                and str(governance_execute_handoff.value("schema_version", "")).endswith("v2-repo-generated")
                and governance_execute_handoff.value("handoff_actionable") is True
                and governance_execute_handoff.value("goal_can_be_marked_complete") is False
                and governance_execute_handoff.value("mutates_chain") is False
                and governance_execute_handoff.value("runs_live_rpc") is False
                and governance_execute_handoff.value("submits_transaction") is False
                and governance_execute_handoff.value("summary.operator_actions_total") == 5
                and governance_execute_handoff.value("summary.operator_commands_total") == 5
                and governance_execute_handoff.value("summary.operator_command_entrypoints_missing") == 0
                and governance_execute_handoff.value("summary.operator_command_surface_ready") is True
                and governance_execute_handoff.value("summary.operator_commands_with_shell_redirection_placeholders") == 0
                and governance_execute_handoff.value("summary.operator_command_shell_surface_ready") is True
                and governance_execute_handoff.value("summary.operator_sequence_ready") is True
                and governance_execute_handoff.value("approval_boundary.approval_env")
                == "X0T_EXECUTE_PROPOSAL_APPROVAL"
                and governance_execute_handoff.value("approval_boundary.expected_value")
                == "execute-proposal-1-base-sepolia"
                and governance_execute_handoff.value("approval_boundary.can_submit_without_operator_approval")
                is False
                and governance_execute_handoff.value("summary.readiness_decision")
                == governance_execute.value("decision")
                and "tests/unit/test_x0t_governance_execute_handoff.py" in verify_text
                and "X0T governance execute operator handoff is actionable and read-only" in verify_text
            ),
            {
                "handoff_decision": governance_execute_handoff.value("handoff_decision"),
                "handoff_actionable": governance_execute_handoff.value("handoff_actionable"),
                "ready_for_operator_execute": governance_execute_handoff.value("ready_for_operator_execute"),
                "readiness_decision": governance_execute_handoff.value("summary.readiness_decision"),
                "approval_env": governance_execute_handoff.value("approval_boundary.approval_env"),
                "approval_value_required": governance_execute_handoff.value(
                    "approval_boundary.expected_value"
                ),
                "can_submit_without_operator_approval": governance_execute_handoff.value(
                    "approval_boundary.can_submit_without_operator_approval"
                ),
                "mutates_chain": governance_execute_handoff.value("mutates_chain"),
                "runs_live_rpc": governance_execute_handoff.value("runs_live_rpc"),
                "submits_transaction": governance_execute_handoff.value("submits_transaction"),
                "operator_actions_total": governance_execute_handoff.value("summary.operator_actions_total"),
                "operator_commands_total": governance_execute_handoff.value("summary.operator_commands_total"),
                "operator_command_entrypoints_missing": governance_execute_handoff.value(
                    "summary.operator_command_entrypoints_missing"
                ),
                "operator_command_surface_ready": governance_execute_handoff.value(
                    "summary.operator_command_surface_ready"
                ),
                "operator_commands_with_shell_redirection_placeholders": governance_execute_handoff.value(
                    "summary.operator_commands_with_shell_redirection_placeholders"
                ),
                "operator_command_shell_surface_ready": governance_execute_handoff.value(
                    "summary.operator_command_shell_surface_ready"
                ),
                "operator_sequence_ready": governance_execute_handoff.value("summary.operator_sequence_ready"),
                "test_in_verify_entrypoint": "tests/unit/test_x0t_governance_execute_handoff.py" in verify_text,
                "smoke_in_verify_entrypoint": "X0T governance execute operator handoff is actionable and read-only"
                in verify_text,
            },
            lambda: [
                "governance execute handoff is missing, stale, not read-only, lacks approval/command boundaries, disagrees with readiness, or is not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "current_evidence_rollup_reproducible",
            "The current evidence rollup is generated by repo code, covered by unit tests, and composes external settlement, rollout provenance, and semantic readiness without mutating live state.",
            artifacts,
            ["current_rollup", "current_rollup_source", "current_rollup_test", "external_settlement", "image_digests", "semantic_queue", "verify_entrypoint"],
            lambda: (
                rollup.value("status") == "VERIFIED HERE"
                and rollup.value("ok") is True
                and rollup.value("completion_decision") in {"NOT_COMPLETE", "COMPLETE"}
                and rollup.value("summary.source_errors_total") == 0
                and rollup.value("summary.external_settlement_decision") == settlement.value("decision")
                and rollup.value("summary.image_digests_decision") == image.value("decision")
                and rollup.value("summary.semantic_blocking_items_total") == semantic.value("summary.blocking_items_total")
                and "tests/unit/test_integration_current_evidence_rollup.py" in verify_text
            ),
            {
                "completion_decision": rollup.value("completion_decision"),
                "goal_can_be_marked_complete": rollup.value("goal_can_be_marked_complete"),
                "source_errors_total": rollup.value("summary.source_errors_total"),
                "top_blockers_total": rollup.value("summary.top_blockers_total"),
                "external_settlement_decision": rollup.value("summary.external_settlement_decision"),
                "image_digests_decision": rollup.value("summary.image_digests_decision"),
                "semantic_blocking_items_total": rollup.value("summary.semantic_blocking_items_total"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_current_evidence_rollup.py" in verify_text,
            },
            lambda: [
                "current evidence rollup is missing, stale, not covered by scripts/verify-v1.1.sh, or has source-read/cross-source consistency errors",
            ],
        ),
        _item(
            "semantic_production_blocker_queue_reproducible",
            "The semantic production blocker queue is generated by repo code, covered by unit tests, and exposes source-read errors separately from production blockers.",
            artifacts,
            [
                "semantic_queue",
                "semantic_queue_source",
                "semantic_queue_test",
                "production_input_return_acceptance",
                "verify_entrypoint",
            ],
            lambda: (
                semantic.value("status") == "VERIFIED HERE"
                and semantic.value("ok") is True
                and semantic.value("completion_decision") in {"NOT_COMPLETE", "COMPLETE"}
                and semantic.value("summary.source_errors_total") == 0
                and semantic.value("summary.blocking_items_total", 0) >= 0
                and semantic.value("summary.semantic_preflight_errors_total", 0) >= 0
                and semantic.value("summary.raw_install_claim_source") == "return_acceptance"
                and semantic.value("summary.pipeline_raw_files_reported_installed") is not None
                and "tests/unit/test_integration_semantic_production_blocker_queue.py" in verify_text
            ),
            {
                "completion_decision": semantic.value("completion_decision"),
                "goal_can_be_marked_complete": semantic.value("goal_can_be_marked_complete"),
                "blocking_items_total": semantic.value("summary.blocking_items_total"),
                "semantic_preflight_errors_total": semantic.value("summary.semantic_preflight_errors_total"),
                "current_raw_files_installed": semantic.value("summary.current_raw_files_installed"),
                "pipeline_raw_files_reported_installed": semantic.value("summary.pipeline_raw_files_reported_installed"),
                "return_acceptance_raw_files_local_observation": semantic.value("summary.return_acceptance_raw_files_local_observation"),
                "source_errors_total": semantic.value("summary.source_errors_total"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_semantic_production_blocker_queue.py" in verify_text,
            },
            lambda: [
                "semantic production blocker queue is missing, stale, not covered by scripts/verify-v1.1.sh, or has source-read errors",
            ],
        ),
        _item(
            "raw_evidence_inventory_reproducible",
            "The raw evidence inventory is generated by repo code, covered by unit tests, and classifies retained raw files without upgrading local/component evidence.",
            artifacts,
            [
                "raw_inventory",
                "raw_inventory_source",
                "raw_inventory_test",
                "semantic_queue",
                "production_input_return_acceptance",
                "verify_entrypoint",
            ],
            lambda: (
                raw.value("status") == "VERIFIED HERE"
                and raw.value("ok") is True
                and raw.value("completion_decision") in {"NOT_COMPLETE", "COMPLETE"}
                and raw.value("summary.source_errors_total") == 0
                and raw.value("summary.files_total", 0) > 0
                and raw.value("summary.raw_install_claim_source") == "return_acceptance"
                and _is_non_negative_int(raw.value("summary.return_acceptance_raw_files_expected"))
                and raw.value("summary.return_acceptance_raw_files_expected") >= raw.value("summary.files_total", 0)
                and raw.value("summary.pipeline_raw_files_reported_installed") is not None
                and "tests/unit/test_integration_raw_evidence_inventory.py" in verify_text
            ),
            {
                "completion_decision": raw.value("completion_decision"),
                "goal_can_be_marked_complete": raw.value("goal_can_be_marked_complete"),
                "files_total": raw.value("summary.files_total"),
                "raw_install_claim_source": raw.value("summary.raw_install_claim_source"),
                "return_acceptance_raw_files_expected": raw.value("summary.return_acceptance_raw_files_expected"),
                "pipeline_raw_files_reported_installed": raw.value("summary.pipeline_raw_files_reported_installed"),
                "return_acceptance_raw_files_staged": raw.value("summary.return_acceptance_raw_files_staged"),
                "return_acceptance_raw_files_local_observation": raw.value("summary.return_acceptance_raw_files_local_observation"),
                "usable_for_goal_completion_files": raw.value("summary.usable_for_goal_completion_files"),
                "semantic_blockers_total": raw.value("summary.semantic_blockers_total"),
                "classification_counts": raw.value("summary.classification_counts"),
                "source_errors_total": raw.value("summary.source_errors_total"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_raw_evidence_inventory.py" in verify_text,
            },
            lambda: [
                "raw evidence inventory is missing, stale, not covered by scripts/verify-v1.1.sh, or has source-read errors",
            ],
        ),
        _item(
            "rollout_provenance_gate_reproducible",
            "The live-rollout image digest/provenance gate is generated by repo code, covered by unit tests, and fails closed on tag-based or missing provenance artifacts.",
            artifacts,
            ["image_digests", "rollout_provenance_source", "rollout_provenance_test", "verify_entrypoint"],
            lambda: (
                image.value("status") == "VERIFIED HERE"
                and image.value("ok") is True
                and image.value("decision") in {"CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS", "READY_TO_CLOSE"}
                and image.value("goal_can_be_marked_complete") is False
                and image.value("summary.raw_deploy_images_total", 0) > 0
                and image.value("summary.collector_image_digest_preflight_errors", 0) >= 0
                and "tests/unit/test_integration_rollout_provenance.py" in verify_text
            ),
            {
                "decision": image.value("decision"),
                "can_close_image_digests_blocker": image.value("summary.can_close_image_digests_blocker"),
                "raw_deploy_images_total": image.value("summary.raw_deploy_images_total"),
                "raw_deploy_images_digest_pinned": image.value("summary.raw_deploy_images_digest_pinned"),
                "collector_image_digest_preflight_errors": image.value("summary.collector_image_digest_preflight_errors"),
                "runtime_image_provenance_artifacts_retained_here": image.value("summary.runtime_image_provenance_artifacts_retained_here"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_rollout_provenance.py" in verify_text,
            },
            lambda: [
                "rollout provenance gate is missing, stale, not covered by scripts/verify-v1.1.sh, or lacks current image digest counters",
            ],
        ),
        _item(
            "rollout_image_provenance_scaffold_available",
            "The live-rollout image digest/provenance blocker has a template-only operator scaffold that is covered by tests and rejected as evidence.",
            artifacts,
            [
                "rollout_image_provenance_scaffold",
                "rollout_image_provenance_scaffold_script",
                "production_validation_wrapper_test",
                "verify_entrypoint",
            ],
            lambda: (
                rollout_image_provenance_scaffold.value("status") == "VERIFIED HERE"
                and rollout_image_provenance_scaffold.value("ok") is True
                and rollout_image_provenance_scaffold.value("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
                and rollout_image_provenance_scaffold.value("goal_can_be_marked_complete") is False
                and rollout_image_provenance_scaffold.value("materializes_evidence") is False
                and rollout_image_provenance_scaffold.value("contacts_registry") is False
                and rollout_image_provenance_scaffold.value("contacts_cluster") is False
                and rollout_image_provenance_scaffold.value("runs_cosign") is False
                and rollout_image_provenance_scaffold.value("mutates_vpn_runtime") is False
                and rollout_image_provenance_scaffold.value("summary.template_files_total") == 4
                and rollout_image_provenance_scaffold.value("summary.templates_marked_not_evidence") is True
                and rollout_image_provenance_scaffold.value("summary.template_validation_rejects_as_rollout_evidence") is True
                and rollout_image_provenance_scaffold.value("summary.current_runtime_tag_refs_total") == 7
                and "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
                and "scaffold_live_rollout_image_provenance_evidence.py" in verify_text
            ),
            {
                "scaffold_decision": rollout_image_provenance_scaffold.value("scaffold_decision"),
                "template_files_total": rollout_image_provenance_scaffold.value("summary.template_files_total"),
                "template_validation_rejects_as_rollout_evidence": rollout_image_provenance_scaffold.value(
                    "summary.template_validation_rejects_as_rollout_evidence"
                ),
                "current_runtime_tag_refs_total": rollout_image_provenance_scaffold.value(
                    "summary.current_runtime_tag_refs_total"
                ),
                "test_in_verify_entrypoint": "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text,
                "smoke_in_verify_entrypoint": "scaffold_live_rollout_image_provenance_evidence.py" in verify_text,
            },
            lambda: [
                "live-rollout image provenance scaffold is missing, unsafe, not covered by tests, or not included in scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "source_candidate_audit_reproducible",
            "The source-candidate audit is generated by repo code and covers all required production evidence keys before intake consumes it.",
            artifacts,
            ["source_candidate_audit", "source_candidate_source", "source_candidate_test"],
            lambda: (
                source_candidates.value("status") == "VERIFIED HERE"
                and source_candidates.value("ok") is True
                and set(source_candidates.value("required_evidence_keys", [])) == REQUIRED_EVIDENCE_KEYS
                and source_candidates.value("summary.required_inputs_total") == len(REQUIRED_EVIDENCE_KEYS)
                and source_candidates.value("summary.routes_total") == len(REQUIRED_EVIDENCE_KEYS)
            ),
            {
                "decision": source_candidates.value("decision"),
                "required_evidence_keys": source_candidates.value("required_evidence_keys"),
                "required_inputs_ready": source_candidates.value("summary.required_inputs_ready"),
                "required_inputs_total": source_candidates.value("summary.required_inputs_total"),
                "ready_source_candidates_total": source_candidates.value("summary.ready_source_candidates_total"),
                "routes_total": source_candidates.value("summary.routes_total"),
            },
            lambda: [
                "source-candidate audit is missing, stale, or does not cover every required production evidence key",
            ],
        ),
        _item(
            "operator_bundle_gates_fail_closed",
            "Raw production blocker bundle gates are generated by repo code, covered by unit tests, and either fail closed on partial bundles or declare READY_TO_INSTALL for real production bundles.",
            artifacts,
            [
                "zero_trust_pqc_gate",
                "self_healing_pqc_mesh_gate",
                "paid_client_serviceability_gate",
                "live_rollout_gate",
                "operator_bundle_gate_source",
                "operator_bundle_gate_test",
                "verify_entrypoint",
            ],
            lambda: (
                all(gate.value("status") == "VERIFIED HERE" for gate in operator_bundle_gates)
                and all(gate.value("ok") is True for gate in operator_bundle_gates)
                and all(gate.value("goal_can_be_marked_complete") is False for gate in operator_bundle_gates)
                and all(gate.value("decision") in {"BLOCKED", "READY_TO_INSTALL"} for gate in operator_bundle_gates)
                and "tests/unit/test_integration_operator_bundle_gate.py" in verify_text
            ),
            {
                "gate_decisions": {
                    gate.logical_name: gate.value("decision") for gate in operator_bundle_gates
                },
                "gate_ready": {
                    gate.logical_name: gate.value("summary.production_ready") for gate in operator_bundle_gates
                },
                "test_in_verify_entrypoint": "tests/unit/test_integration_operator_bundle_gate.py" in verify_text,
            },
            lambda: [
                "one or more raw production blocker bundle gates is missing, unreadable, not repo-tested, or does not fail closed",
            ],
        ),
        _item(
            "operator_bundle_manifest_identity_audited",
            "Raw production blocker bundle gates expose manifest identity binding counters for collector_id, raw_id, and file_name.",
            artifacts,
            [
                "zero_trust_pqc_gate",
                "self_healing_pqc_mesh_gate",
                "paid_client_serviceability_gate",
                "live_rollout_gate",
                "operator_bundle_gate_source",
                "operator_bundle_gate_test",
                "verify_entrypoint",
            ],
            lambda: (
                all(
                    _operator_bundle_manifest_identity_counters_valid(gate)
                    for gate in operator_bundle_gates
                )
                and "tests/unit/test_integration_operator_bundle_gate.py" in verify_text
            ),
            {
                "gate_manifest_identity_counters": {
                    gate.logical_name: _operator_bundle_manifest_identity_counters(gate)
                    for gate in operator_bundle_gates
                },
                "test_in_verify_entrypoint": "tests/unit/test_integration_operator_bundle_gate.py" in verify_text,
            },
            lambda: _operator_bundle_manifest_identity_audit_gaps(operator_bundle_gates, verify_text),
        ),
        _item(
            "operator_bundle_identity_plan_available",
            "The raw operator bundle manifest identity gap has a generated read-only remediation plan covered by unit tests.",
            artifacts,
            [
                "operator_bundle_identity",
                "operator_bundle_identity_source",
                "operator_bundle_identity_test",
                "verify_entrypoint",
            ],
            lambda: (
                operator_bundle_identity.value("status") == "VERIFIED HERE"
                and operator_bundle_identity.value("ok") is True
                and operator_bundle_identity.value("goal_can_be_marked_complete") is False
                and operator_bundle_identity.value("decision") in {
                    "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED",
                    "OPERATOR_BUNDLE_IDENTITY_CLEAN",
                }
                and _is_non_negative_int(operator_bundle_identity.value("summary.files_total"))
                and operator_bundle_identity.value("summary.files_total") > 0
                and _is_non_negative_int(operator_bundle_identity.value("summary.files_available"))
                and operator_bundle_identity.value("summary.files_available") <= operator_bundle_identity.value("summary.files_total")
                and _is_non_negative_int(operator_bundle_identity.value("summary.manifest_identity_mismatches_total"))
                and _is_non_negative_int(operator_bundle_identity.value("summary.collector_id_mismatches"))
                and _is_non_negative_int(operator_bundle_identity.value("summary.raw_id_mismatches"))
                and _is_non_negative_int(operator_bundle_identity.value("summary.file_name_mismatches"))
                and _is_non_negative_int(operator_bundle_identity.value("summary.identity_patch_entries_total"))
                and operator_bundle_identity.value("summary.identity_patch_entries_total")
                == operator_bundle_identity.value("summary.files_needing_identity_update")
                and _is_non_negative_int(operator_bundle_identity.value("summary.identity_patch_operations_total"))
                and operator_bundle_identity.value("summary.identity_patch_operations_total")
                >= operator_bundle_identity.value("summary.manifest_identity_mismatches_total")
                and "tests/unit/test_integration_operator_bundle_identity.py" in verify_text
            ),
            {
                "decision": operator_bundle_identity.value("decision"),
                "files_total": operator_bundle_identity.value("summary.files_total"),
                "files_available": operator_bundle_identity.value("summary.files_available"),
                "files_needing_identity_update": operator_bundle_identity.value("summary.files_needing_identity_update"),
                "manifest_identity_mismatches_total": operator_bundle_identity.value("summary.manifest_identity_mismatches_total"),
                "collector_id_mismatches": operator_bundle_identity.value("summary.collector_id_mismatches"),
                "raw_id_mismatches": operator_bundle_identity.value("summary.raw_id_mismatches"),
                "file_name_mismatches": operator_bundle_identity.value("summary.file_name_mismatches"),
                "identity_patch_entries_total": operator_bundle_identity.value("summary.identity_patch_entries_total"),
                "identity_patch_operations_total": operator_bundle_identity.value("summary.identity_patch_operations_total"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_operator_bundle_identity.py" in verify_text,
            },
            lambda: [
                "operator bundle manifest identity report is missing, stale, lacks a patch manifest, or is not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "operator_bundle_identity_patch_entrypoint_available",
            "The raw operator bundle manifest identity plan has a safe dry-run/apply entrypoint that only touches collector_id/raw_id/file_name.",
            artifacts,
            [
                "operator_bundle_identity",
                "operator_bundle_identity_patch",
                "operator_bundle_identity_patch_script",
                "operator_bundle_identity_patch_test",
                "verify_entrypoint",
            ],
            lambda: (
                operator_bundle_identity.value("status") == "VERIFIED HERE"
                and operator_bundle_identity_patch.value("status") == "VERIFIED HERE"
                and operator_bundle_identity_patch.value("ok") is True
                and operator_bundle_identity_patch.value("goal_can_be_marked_complete") is False
                and operator_bundle_identity_patch.value("decision")
                in {
                    "IDENTITY_PATCH_DRY_RUN_READY",
                    "IDENTITY_PATCH_NOT_NEEDED",
                    "IDENTITY_PATCH_APPLIED",
                }
                and operator_bundle_identity_patch.value("mutates_files_outside_operator_bundle") is False
                and operator_bundle_identity_patch.value("mutates_nl") is False
                and operator_bundle_identity_patch.value("mutates_spb") is False
                and operator_bundle_identity_patch.value("mutates_vpn_runtime") is False
                and operator_bundle_identity_patch.value("materializes_evidence") is False
                and operator_bundle_identity_patch.value("installs_raw_evidence") is False
                and operator_bundle_identity_patch.value("promotes_production_ready") is False
                and operator_bundle_identity_patch.value("changes_evidence_status") is False
                and operator_bundle_identity_patch.value("summary.plan_entries_total")
                == operator_bundle_identity.value("summary.identity_patch_entries_total")
                and operator_bundle_identity_patch.value("summary.unsafe_operations_total") == 0
                and "tests/unit/scripts/test_apply_operator_bundle_identity_patch.py" in verify_text
            ),
            {
                "decision": operator_bundle_identity_patch.value("decision"),
                "apply_requested": operator_bundle_identity_patch.value("apply_requested"),
                "plan_entries_total": operator_bundle_identity_patch.value("summary.plan_entries_total"),
                "would_update_files": operator_bundle_identity_patch.value("summary.would_update_files"),
                "updated_files": operator_bundle_identity_patch.value("summary.updated_files"),
                "unsafe_operations_total": operator_bundle_identity_patch.value("summary.unsafe_operations_total"),
                "test_in_verify_entrypoint": "tests/unit/scripts/test_apply_operator_bundle_identity_patch.py" in verify_text,
            },
            lambda: [
                "operator bundle identity patch dry-run/apply entrypoint is missing, stale, unsafe, or not covered by scripts/verify-v1.1.sh",
            ],
        ),
        _item(
            "operator_evidence_packet_actionable",
            "The next production blocker has a generated operator evidence packet with existing verifier entrypoints and fail-closed instructions.",
            artifacts,
            ["operator_packet", "operator_packet_source", "operator_packet_test", "production_gap_index"],
            lambda: operator_packet_actionable,
            {
                "decision": operator_packet.value("decision"),
                "actionable": operator_packet.value("actionable"),
                "selected_evidence_key": operator_packet.value("selected_evidence_key"),
                "expected_packet_key": expected_packet_key,
                "commands_total": operator_packet.value("summary.commands_total"),
                "commands_missing_entrypoints": operator_packet.value("summary.commands_missing_entrypoints"),
                "operator_action_required": operator_packet.value("summary.operator_action_required"),
                "required_artifacts_total": operator_packet.value("summary.required_artifacts_total"),
            },
            lambda: [
                "operator evidence packet is missing, stale, or points to commands without existing verifier entrypoints",
            ],
        ),
        _item(
            "operator_evidence_packet_index_complete",
            "Every current production evidence blocker has an actionable operator evidence packet with existing collector and verifier entrypoints.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test", "production_gap_index"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and operator_packet_index.value("all_packets_actionable") is True
                and operator_packet_index.value("summary.packets_total") == pending_evidence_keys
                and operator_packet_index.value("summary.commands_missing_entrypoints_total") == 0
                and operator_packet_index.value("summary.packets_with_missing_entrypoints") == 0
            ),
            {
                "decision": operator_packet_index.value("decision"),
                "all_packets_actionable": operator_packet_index.value("all_packets_actionable"),
                "packets_total": operator_packet_index.value("summary.packets_total"),
                "actionable_packets": operator_packet_index.value("summary.actionable_packets"),
                "packets_with_missing_entrypoints": operator_packet_index.value("summary.packets_with_missing_entrypoints"),
                "commands_missing_entrypoints_total": operator_packet_index.value("summary.commands_missing_entrypoints_total"),
            },
            lambda: [
                "one or more production blocker packets still reference missing local collector/verifier entrypoints",
            ],
        ),
        _item(
            "operator_packet_identity_suggestions_available",
            "Raw production blocker operator packets expose per-file manifest identity suggestions for collector_id, raw_id, and file_name.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test", "operator_bundle_identity"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_raw_identity_suggestions_valid(
                    operator_packet_index,
                    operator_bundle_identity,
                    pending_evidence_keys,
                )
            ),
            {
                "raw_packet_identity_updates": {
                    key: {
                        "identity_updates_total": item.get("identity_updates_total"),
                        "identity_update_plan_total": len(item.get("identity_update_plan", []) or []),
                    }
                    for key, item in _operator_packet_raw_identity_suggestion_summaries(operator_packet_index).items()
                },
                "pending_evidence_keys": pending_evidence_keys,
            },
            lambda: _operator_packet_raw_identity_suggestion_gaps(
                operator_packet_index,
                operator_bundle_identity,
                pending_evidence_keys,
            ),
        ),
        _item(
            "operator_packet_identity_patch_dry_run_command_available",
            "Raw production blocker operator packets expose an identity-only dry-run patch command before the guarded --apply command.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "operator_bundle_identity_patch_script",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_identity_patch_dry_run_commands_valid(
                    operator_packet_index,
                    priority_order,
                )
            ),
            {
                "raw_priority_keys": [
                    key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS
                ],
                "raw_packets_with_identity_patch_dry_run_pair": len(
                    _operator_packet_identity_patch_dry_run_summaries(
                        operator_packet_index,
                        priority_order,
                    )
                ),
            },
            lambda: _operator_packet_identity_patch_dry_run_command_gaps(
                operator_packet_index,
                priority_order,
            ),
        ),
        _item(
            "operator_packet_replacement_passport_command_available",
            "Every current production blocker packet tells the operator to rerun the production evidence replacement passport before intake/completion.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test", "replacement_passport"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_replacement_passport_commands_valid(operator_packet_index, pending_evidence_keys)
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "packets_total": operator_packet_index.value("summary.packets_total"),
                "packets_with_replacement_passport_command": len(
                    _operator_packet_replacement_passport_command_summaries(operator_packet_index)
                ),
            },
            lambda: _operator_packet_replacement_passport_command_gaps(operator_packet_index, pending_evidence_keys),
        ),
        _item(
            "operator_packet_post_intake_commands_available",
            "Every current production blocker packet tells the operator to rerun return acceptance, input pipeline, and closeout review before final completion/gap gates.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "production_input_return_acceptance_source",
                "production_input_pipeline_source",
                "production_closeout_review_source",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_post_intake_commands_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                )
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "packets_total": operator_packet_index.value("summary.packets_total"),
                "packets_with_post_intake_commands": len(
                    _operator_packet_post_intake_command_summaries(operator_packet_index)
                ),
            },
            lambda: _operator_packet_post_intake_command_gaps(
                operator_packet_index,
                pending_evidence_keys,
            ),
        ),
        _item(
            "operator_packet_raw_template_pack_command_available",
            "Raw production blocker operator packets expose the template-only raw evidence template-pack command and an explicit fail-closed rule.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "raw_template_pack_script",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_raw_template_pack_commands_valid(
                    operator_packet_index,
                    priority_order,
                )
            ),
            {
                "raw_priority_keys": [
                    key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS
                ],
                "raw_template_pack_command_present": _operator_packet_raw_template_pack_commands_valid(
                    operator_packet_index,
                    priority_order,
                ),
            },
            lambda: _operator_packet_raw_template_pack_command_gaps(
                operator_packet_index,
                priority_order,
            ),
        ),
        _item(
            "operator_packet_raw_required_inputs_available",
            "Raw production blocker operator packets expose the required production inputs, required raw evidence fields, and an explicit operator JSON write step.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_raw_required_inputs_valid(
                    operator_packet_index,
                    priority_order,
                )
            ),
            {
                "raw_priority_keys": [
                    key for key in priority_order if key in RAW_PRODUCTION_EVIDENCE_KEYS
                ],
                "raw_required_inputs_present": _operator_packet_raw_required_inputs_valid(
                    operator_packet_index,
                    priority_order,
                ),
            },
            lambda: _operator_packet_raw_required_input_gaps(
                operator_packet_index,
                priority_order,
            ),
        ),
        _item(
            "operator_packet_external_settlement_wrapper_commands_available",
            "The external settlement operator packet includes both retained-evidence and live-RPC wrapper verifiers before source-candidate/intake promotion.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "x0t_settlement_evidence_script",
                "x0t_settlement_live_rpc_script",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_external_settlement_wrapper_commands_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                )
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "external_settlement_commands": [
                    command.get("command", "")
                    for command in _operator_packet_external_settlement_summary(operator_packet_index).get("commands", [])
                    if isinstance(command, dict)
                ],
            },
            lambda: _operator_packet_external_settlement_wrapper_command_gaps(
                operator_packet_index,
                pending_evidence_keys,
            ),
        ),
        _item(
            "operator_packet_external_settlement_operator_inputs_available",
            "The external settlement operator packet exposes the required operator inputs, required receipt fields, and X0T environment exports before any capture or verifier command.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_external_settlement_operator_inputs_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                )
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "required_operator_inputs": _operator_packet_external_settlement_summary(operator_packet_index).get(
                    "required_operator_inputs", []
                ),
                "required_fields_total": len(
                    _operator_packet_external_settlement_summary(operator_packet_index).get(
                        "required_fields", []
                    )
                    or []
                ),
            },
            lambda: _operator_packet_external_settlement_operator_input_gaps(
                operator_packet_index,
                pending_evidence_keys,
            ),
        ),
        _item(
            "operator_packet_external_settlement_capture_commands_available",
            "The external settlement operator packet exposes fail-closed capture-input preflight and live read-only RPC capture commands, and the fast verifier proves the preflight blocks without operator inputs.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "external_settlement_source",
                "verify_entrypoint",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_external_settlement_capture_commands_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                    verify_text,
                )
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "capture_preflight_smoke_in_verify_entrypoint": (
                    "integration-spine external settlement capture preflight fails closed" in verify_text
                ),
                "capture_inputs_blocked_assertion_in_verify_entrypoint": "CAPTURE_INPUTS_BLOCKED" in verify_text,
                "external_settlement_commands": [
                    command.get("command", "")
                    for command in _operator_packet_external_settlement_summary(operator_packet_index).get("commands", [])
                    if isinstance(command, dict)
                    and "src.integration.external_settlement" in str(command.get("command", ""))
                ],
            },
            lambda: _operator_packet_external_settlement_capture_command_gaps(
                operator_packet_index,
                pending_evidence_keys,
                verify_text,
            ),
        ),
        _item(
            "operator_packet_external_settlement_scaffold_command_available",
            "The external settlement operator packet exposes the template-only settlement scaffold command and an explicit fail-closed rule.",
            artifacts,
            [
                "operator_packet_index",
                "operator_packet_source",
                "operator_packet_test",
                "x0t_settlement_scaffold_script",
            ],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_external_settlement_scaffold_command_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                )
            ),
            {
                "pending_evidence_keys": pending_evidence_keys,
                "scaffold_command_present": _operator_packet_external_settlement_scaffold_command_valid(
                    operator_packet_index,
                    pending_evidence_keys,
                ),
            },
            lambda: _operator_packet_external_settlement_scaffold_command_gaps(
                operator_packet_index,
                pending_evidence_keys,
            ),
        ),
        _item(
            "external_settlement_template_rejection_smoke_available",
            "The fast verification entrypoint proves that an external settlement template copied to the retained evidence path is rejected.",
            artifacts,
            [
                "verify_entrypoint",
                "x0t_settlement_scaffold_script",
                "x0t_settlement_evidence_script",
                "production_validation_wrapper_test",
            ],
            lambda: (
                (root / ARTIFACTS["x0t_settlement_scaffold_script"]).exists()
                and (root / ARTIFACTS["x0t_settlement_evidence_script"]).exists()
                and "integration-spine external settlement template is rejected as retained evidence" in verify_text
                and "verify_x0t_external_settlement_evidence.py" in verify_text
                and "template_only must not be true" in verify_text
                and "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
            ),
            {
                "smoke_in_verify_entrypoint": (
                    "integration-spine external settlement template is rejected as retained evidence" in verify_text
                ),
                "retained_evidence_verifier_in_verify_entrypoint": (
                    "verify_x0t_external_settlement_evidence.py" in verify_text
                ),
                "template_rejection_assertion_in_verify_entrypoint": (
                    "template_only must not be true" in verify_text
                ),
                "test_in_verify_entrypoint": (
                    "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
                ),
            },
            lambda: [
                "scripts/verify-v1.1.sh must prove external settlement templates are rejected when copied to the retained evidence path",
            ],
        ),
        _item(
            "raw_evidence_template_rejection_smoke_available",
            "The fast verification entrypoint proves that generated raw-evidence templates copied into an operator bundle are rejected.",
            artifacts,
            [
                "verify_entrypoint",
                "raw_template_pack_script",
                "raw_bundle_import_script",
                "production_validation_wrapper_test",
            ],
            lambda: (
                (root / ARTIFACTS["raw_template_pack_script"]).exists()
                and (root / ARTIFACTS["raw_bundle_import_script"]).exists()
                and "integration-spine production raw evidence templates are rejected as operator bundle evidence" in verify_text
                and "generate_production_raw_evidence_template_pack.py" in verify_text
                and "import_production_raw_evidence_bundle.py" in verify_text
                and "template/mock/placeholder markers must be absent" in verify_text
                and "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
            ),
            {
                "smoke_in_verify_entrypoint": (
                    "integration-spine production raw evidence templates are rejected as operator bundle evidence" in verify_text
                ),
                "raw_template_pack_in_verify_entrypoint": (
                    "generate_production_raw_evidence_template_pack.py" in verify_text
                ),
                "raw_bundle_import_in_verify_entrypoint": (
                    "import_production_raw_evidence_bundle.py" in verify_text
                ),
                "template_rejection_assertion_in_verify_entrypoint": (
                    "template/mock/placeholder markers must be absent" in verify_text
                ),
                "test_in_verify_entrypoint": (
                    "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
                ),
            },
            lambda: [
                "scripts/verify-v1.1.sh must prove generated raw-evidence templates are rejected when copied into an operator bundle",
            ],
        ),
        _item(
            "live_rollout_image_template_rejection_smoke_available",
            "The fast verification entrypoint proves that a live-rollout image provenance template copied into an operator bundle is rejected.",
            artifacts,
            [
                "verify_entrypoint",
                "rollout_image_provenance_scaffold_script",
                "raw_bundle_import_script",
                "production_validation_wrapper_test",
            ],
            lambda: (
                (root / ARTIFACTS["rollout_image_provenance_scaffold_script"]).exists()
                and (root / ARTIFACTS["raw_bundle_import_script"]).exists()
                and "integration-spine live rollout image template is rejected as operator bundle evidence" in verify_text
                and "scaffold_live_rollout_image_provenance_evidence.py" in verify_text
                and "import_production_raw_evidence_bundle.py" in verify_text
                and "template/mock/placeholder markers must be absent" in verify_text
                and "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
            ),
            {
                "smoke_in_verify_entrypoint": (
                    "integration-spine live rollout image template is rejected as operator bundle evidence" in verify_text
                ),
                "rollout_scaffold_in_verify_entrypoint": (
                    "scaffold_live_rollout_image_provenance_evidence.py" in verify_text
                ),
                "raw_bundle_import_in_verify_entrypoint": (
                    "import_production_raw_evidence_bundle.py" in verify_text
                ),
                "template_rejection_assertion_in_verify_entrypoint": (
                    "template/mock/placeholder markers must be absent" in verify_text
                ),
                "test_in_verify_entrypoint": (
                    "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text
                ),
            },
            lambda: [
                "scripts/verify-v1.1.sh must prove live rollout image provenance templates are rejected when copied into an operator bundle",
            ],
        ),
        _item(
            "operator_packet_rollout_image_scaffold_command_available",
            "The safe rollout operator packet exposes the template-only image digest/provenance scaffold command and an explicit fail-closed rule.",
            artifacts,
            ["operator_packet_index", "operator_packet_source", "operator_packet_test"],
            lambda: (
                operator_packet_index.value("status") == "VERIFIED HERE"
                and operator_packet_index.value("ok") is True
                and _operator_packet_rollout_scaffold_command_valid(operator_packet_index, priority_order)
            ),
            {
                "safe_rollout_in_priority_order": "safe_rollout_rollback" in priority_order,
                "priority_order": priority_order,
                "scaffold_command_present": _operator_packet_rollout_scaffold_command_valid(
                    operator_packet_index,
                    priority_order,
                ),
            },
            lambda: _operator_packet_rollout_scaffold_command_gaps(operator_packet_index, priority_order),
        ),
        _item(
            "replacement_passport_validation_commands_available",
            "Every validation command emitted by the production evidence replacement passport has a local fail-closed entrypoint covered by tests.",
            artifacts,
            [
                "replacement_passport",
                "replacement_passport_source",
                "replacement_passport_test",
                "raw_bundle_import_script",
                "x0t_settlement_evidence_script",
                "x0t_settlement_live_rpc_script",
                "production_validation_wrapper_test",
                "verify_entrypoint",
            ],
            lambda: (
                replacement_passport.value("status") == "VERIFIED HERE"
                and replacement_passport.value("ok") is True
                and bool(_replacement_passport_validation_commands(replacement_passport))
                and not _replacement_passport_validation_command_gaps(root, replacement_passport, verify_text)
            ),
            {
                "validation_commands": _replacement_passport_validation_commands(replacement_passport),
                "validation_commands_total": len(_replacement_passport_validation_commands(replacement_passport)),
                "test_in_verify_entrypoint": "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text,
            },
            lambda: _replacement_passport_validation_command_gaps(root, replacement_passport, verify_text),
        ),
        _item(
            "replacement_passport_external_scaffold_command_available",
            "The production evidence replacement passport exposes an external settlement scaffold entrypoint that writes templates only and is covered by tests.",
            artifacts,
            [
                "replacement_passport",
                "replacement_passport_source",
                "replacement_passport_test",
                "x0t_settlement_scaffold_script",
                "production_validation_wrapper_test",
                "verify_entrypoint",
            ],
            lambda: (
                replacement_passport.value("status") == "VERIFIED HERE"
                and replacement_passport.value("ok") is True
                and bool(_replacement_passport_scaffold_commands(replacement_passport))
                and not _replacement_passport_scaffold_command_gaps(root, replacement_passport, verify_text)
            ),
            {
                "scaffold_commands": _replacement_passport_scaffold_commands(replacement_passport),
                "scaffold_commands_total": len(_replacement_passport_scaffold_commands(replacement_passport)),
                "test_in_verify_entrypoint": "tests/unit/test_ops_production_evidence_validation_wrappers.py" in verify_text,
            },
            lambda: _replacement_passport_scaffold_command_gaps(root, replacement_passport, verify_text),
        ),
        _item(
            "production_evidence_replacement_passport_clear",
            "Every scaffold, template, mock, or local-observation evidence input has a reproducible replacement passport and is backed by retained production evidence.",
            artifacts,
            [
                "replacement_passport",
                "replacement_passport_verification",
                "replacement_passport_source",
                "replacement_passport_test",
                "production_input_return_acceptance",
                "verify_entrypoint",
            ],
            lambda: (
                replacement_passport.value("status") == "VERIFIED HERE"
                and replacement_passport.value("ok") is True
                and replacement_passport_verification.value("status") == "VERIFIED HERE"
                and replacement_passport_verification.value("ok") is True
                and replacement_passport_verification.value("valid") is True
                and replacement_passport_verification.value("summary.checks_failed") == 0
                and replacement_passport_verification.value("summary.passport_decision") == replacement_passport.value("decision")
                and replacement_passport.value("decision") == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
                and replacement_passport.value("production_ready") is True
                and replacement_passport.value("summary.items_total", 0) > 0
                and replacement_passport.value("summary.items_ready") == replacement_passport.value("summary.items_total")
                and replacement_passport.value("summary.items_blocking") == 0
                and replacement_passport.value("summary.required_evidence_files_ready") == replacement_passport.value("summary.required_evidence_files_total")
                and replacement_passport.value("summary.source_errors_total") == 0
                and replacement_passport.value("summary.raw_install_claim_source") == "return_acceptance"
                and replacement_passport.value("summary.current_raw_files_installed")
                == replacement_passport.value("summary.return_acceptance_raw_files_staged")
                and "tests/unit/test_integration_production_evidence_replacement_passport.py" in verify_text
            ),
            {
                "decision": replacement_passport.value("decision"),
                "production_ready": replacement_passport.value("production_ready"),
                "items_total": replacement_passport.value("summary.items_total"),
                "items_ready": replacement_passport.value("summary.items_ready"),
                "items_blocking": replacement_passport.value("summary.items_blocking"),
                "required_evidence_files_total": replacement_passport.value("summary.required_evidence_files_total"),
                "required_evidence_files_ready": replacement_passport.value("summary.required_evidence_files_ready"),
                "raw_install_claim_source": replacement_passport.value("summary.raw_install_claim_source"),
                "current_raw_files_installed": replacement_passport.value("summary.current_raw_files_installed"),
                "coverage_raw_files_reported_installed": replacement_passport.value("summary.coverage_raw_files_reported_installed"),
                "return_acceptance_raw_files_staged": replacement_passport.value("summary.return_acceptance_raw_files_staged"),
                "return_acceptance_raw_files_local_observation": replacement_passport.value("summary.return_acceptance_raw_files_local_observation"),
                "source_errors_total": replacement_passport.value("summary.source_errors_total"),
                "verification_decision": replacement_passport_verification.value("decision"),
                "verification_valid": replacement_passport_verification.value("valid"),
                "verification_checks_failed": replacement_passport_verification.value("summary.checks_failed"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_production_evidence_replacement_passport.py" in verify_text,
            },
            lambda: [
                "production evidence replacement passport is missing, stale, not covered by scripts/verify-v1.1.sh, or still blocked on scaffold/template/mock/local-observation replacement",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "required_evidence_consistency_valid",
            "Passport, operator packet index, input manifest, return acceptance, pipeline, rollup, and closeout reports agree on the required evidence file set.",
            artifacts,
            [
                "required_evidence_consistency",
                "required_evidence_consistency_source",
                "required_evidence_consistency_test",
                "replacement_passport",
                "operator_packet_index",
                "verify_entrypoint",
            ],
            lambda: (
                required_evidence_consistency.value("status") == "VERIFIED HERE"
                and required_evidence_consistency.value("ok") is True
                and required_evidence_consistency.value("valid") is True
                and required_evidence_consistency.value("summary.errors_total") == 0
                and required_evidence_consistency.value("summary.packet_passport_item_coverage_ready") is True
                and required_evidence_consistency.value("summary.required_evidence_files_total")
                == replacement_passport.value("summary.required_evidence_files_total")
                and required_evidence_consistency.value("summary.packet_required_evidence_files_total")
                == replacement_passport.value("summary.required_evidence_files_total")
                and required_evidence_consistency.value("decision")
                in {
                    "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR",
                    "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR",
                }
                and "tests/unit/test_integration_required_evidence_consistency.py" in verify_text
            ),
            {
                "decision": required_evidence_consistency.value("decision"),
                "valid": required_evidence_consistency.value("valid"),
                "production_ready": required_evidence_consistency.value("production_ready"),
                "errors_total": required_evidence_consistency.value("summary.errors_total"),
                "required_evidence_files_total": required_evidence_consistency.value("summary.required_evidence_files_total"),
                "packet_required_evidence_files_total": required_evidence_consistency.value("summary.packet_required_evidence_files_total"),
                "packet_passport_item_coverage_ready": required_evidence_consistency.value("summary.packet_passport_item_coverage_ready"),
                "raw_operator_packet_readiness_decision": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_decision"
                ),
                "raw_operator_packet_readiness_ready_for_collectors": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_ready_for_collectors"
                ),
                "raw_operator_packet_readiness_collectors_ready": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_collectors_ready"
                ),
                "raw_operator_packet_readiness_collectors_blocked": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_collectors_blocked"
                ),
                "raw_operator_packet_readiness_collectors_total": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_collectors_total"
                ),
                "raw_operator_packet_readiness_raw_files_ready": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_raw_files_ready"
                ),
                "raw_operator_packet_readiness_raw_files_local_observation": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_raw_files_local_observation"
                ),
                "raw_operator_packet_readiness_raw_files_total": required_evidence_consistency.value(
                    "summary.raw_operator_packet_readiness_raw_files_total"
                ),
                "raw_operator_packet_production_ready_blocked_by_raw_readiness": required_evidence_consistency.value(
                    "summary.raw_operator_packet_production_ready_blocked_by_raw_readiness"
                ),
                "test_in_verify_entrypoint": "tests/unit/test_integration_required_evidence_consistency.py" in verify_text,
            },
            lambda: [
                "required evidence consistency report is missing, stale, not covered by scripts/verify-v1.1.sh, or disagrees across required evidence sources",
            ],
        ),
        _item(
            "rollup_approval_contract_reproducible",
            "The rollup approval contract is generated by repo code, covered by unit tests, and reports source-read errors separately from operator evidence blockers.",
            artifacts,
            [
                "rollup_approval_contract",
                "rollup_approval_contract_source",
                "rollup_approval_contract_test",
                "replacement_passport",
                "required_evidence_consistency",
                "verify_entrypoint",
            ],
            lambda: (
                rollup_approval_contract.value("status") == "VERIFIED HERE"
                and rollup_approval_contract.value("ok") is True
                and rollup_approval_contract.value("decision")
                in {"ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE", "ROLLUP_APPROVAL_READY"}
                and rollup_approval_contract.value("summary.source_errors_total") == 0
                and rollup_approval_contract.value("summary.sources_total", 0) > 0
                and rollup_approval_contract.value("summary.evidence_files_total")
                == replacement_passport.value("summary.required_evidence_files_total")
                and rollup_approval_contract.value("summary.evidence_files_valid")
                == required_evidence_consistency.value("summary.required_evidence_files_ready")
                and "tests/unit/test_integration_rollup_approval_contract.py" in verify_text
            ),
            {
                "decision": rollup_approval_contract.value("decision"),
                "ready": rollup_approval_contract.value("ready"),
                "sources_total": rollup_approval_contract.value("summary.sources_total"),
                "sources_ready": rollup_approval_contract.value("summary.sources_ready"),
                "source_errors_total": rollup_approval_contract.value("summary.source_errors_total"),
                "evidence_files_total": rollup_approval_contract.value("summary.evidence_files_total"),
                "evidence_files_valid": rollup_approval_contract.value("summary.evidence_files_valid"),
                "required_evidence_files_total": replacement_passport.value("summary.required_evidence_files_total"),
                "required_evidence_files_ready": required_evidence_consistency.value("summary.required_evidence_files_ready"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_rollup_approval_contract.py" in verify_text,
            },
            lambda: [
                "rollup approval contract is missing, stale, not covered by scripts/verify-v1.1.sh, or still mixes source-read errors with operator evidence blockers",
            ],
        ),
        _item(
            "production_input_return_acceptance_reproducible",
            "The production input return acceptance report is generated by repo code, covered by unit tests, and exposes stage blockers with a stable decision.",
            artifacts,
            [
                "production_input_return_acceptance",
                "production_input_return_acceptance_source",
                "production_input_return_acceptance_test",
                "required_evidence_consistency",
                "verify_entrypoint",
            ],
            lambda: (
                production_input_return_acceptance.value("status") == "VERIFIED HERE"
                and production_input_return_acceptance.value("ok") is True
                and production_input_return_acceptance.value("decision")
                in {
                    "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE",
                    "RETURN_ACCEPTANCE_READY",
                }
                and production_input_return_acceptance.value("summary.source_errors_total") == 0
                and production_input_return_acceptance.value("summary.evidence_keys_total") == len(REQUIRED_EVIDENCE_KEYS)
                and production_input_return_acceptance.value("summary.raw_files_expected")
                == required_evidence_consistency.value("summary.raw_required_evidence_files_total")
                and production_input_return_acceptance.value("summary.external_artifacts_expected")
                == required_evidence_consistency.value("summary.external_required_evidence_files_total")
                and production_input_return_acceptance.value("summary.ready_for_pipeline_install")
                is production_input_return_acceptance.value("ready_for_pipeline_install")
                and "tests/unit/test_integration_production_input_return_acceptance.py" in verify_text
            ),
            {
                "decision": production_input_return_acceptance.value("decision"),
                "ready_to_stage": production_input_return_acceptance.value("ready_to_stage"),
                "ready_for_pipeline_install": production_input_return_acceptance.value("ready_for_pipeline_install"),
                "source_errors_total": production_input_return_acceptance.value("summary.source_errors_total"),
                "evidence_keys_total": production_input_return_acceptance.value("summary.evidence_keys_total"),
                "evidence_keys_ready_to_stage": production_input_return_acceptance.value("summary.evidence_keys_ready_to_stage"),
                "raw_files_expected": production_input_return_acceptance.value("summary.raw_files_expected"),
                "external_artifacts_expected": production_input_return_acceptance.value("summary.external_artifacts_expected"),
                "external_settlement_live_rpc_ready": production_input_return_acceptance.value("summary.external_settlement_live_rpc_ready"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_production_input_return_acceptance.py" in verify_text,
            },
            lambda: [
                "production input return acceptance report is missing, stale, not covered by scripts/verify-v1.1.sh, or has source-read errors",
            ],
        ),
        _item(
            "production_input_pipeline_reproducible",
            "The production input pipeline report is repo-generated, covered by unit tests, and reports installed raw files from return-acceptance rather than stale local observations.",
            artifacts,
            [
                "production_input_pipeline",
                "production_input_pipeline_source",
                "production_input_pipeline_test",
                "production_input_return_acceptance",
                "verify_entrypoint",
            ],
            lambda: (
                production_input_pipeline.value("status") == "VERIFIED HERE"
                and production_input_pipeline.value("ok") is True
                and str(production_input_pipeline.value("schema_version", "")).endswith("v4-repo-generated")
                and "source-restored" not in str(production_input_pipeline.value("schema_version", ""))
                and production_input_pipeline.value("pipeline_decision")
                in {
                    "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE",
                    "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
                }
                and production_input_pipeline.value("summary.source_errors_total") == 0
                and production_input_pipeline.value("summary.raw_files_install_claim_source") == "return_acceptance"
                and production_input_pipeline.value("summary.raw_files_installed")
                == production_input_return_acceptance.value("summary.raw_files_staged")
                and production_input_pipeline.value("summary.raw_files_staged")
                == production_input_return_acceptance.value("summary.raw_files_staged")
                and production_input_pipeline.value("summary.raw_files_preflight_reported_installed")
                == production_input_return_acceptance.value("summary.raw_files_staged")
                and production_input_pipeline.value("summary.raw_files_local_observation")
                == production_input_return_acceptance.value("summary.raw_files_local_observation")
                and production_input_pipeline.value("summary.external_settlement_live_rpc_ready")
                is production_input_return_acceptance.value("summary.external_settlement_live_rpc_ready")
                and production_input_pipeline.value("summary.ready") is production_input_pipeline.value("ready")
                and production_input_pipeline.value("mutates_files") is False
                and production_input_pipeline.value("runs_collectors") is False
                and production_input_pipeline.value("runs_live_rpc") is False
                and "tests/unit/test_integration_production_input_pipeline.py" in verify_text
            ),
            {
                "schema_version": production_input_pipeline.value("schema_version"),
                "pipeline_decision": production_input_pipeline.value("pipeline_decision"),
                "ready": production_input_pipeline.value("ready"),
                "source_errors_total": production_input_pipeline.value("summary.source_errors_total"),
                "raw_files_install_claim_source": production_input_pipeline.value("summary.raw_files_install_claim_source"),
                "raw_files_installed": production_input_pipeline.value("summary.raw_files_installed"),
                "raw_files_staged": production_input_pipeline.value("summary.raw_files_staged"),
                "raw_files_preflight_reported_installed": production_input_pipeline.value("summary.raw_files_preflight_reported_installed"),
                "raw_files_local_observation": production_input_pipeline.value("summary.raw_files_local_observation"),
                "return_acceptance_raw_files_staged": production_input_return_acceptance.value("summary.raw_files_staged"),
                "test_in_verify_entrypoint": "tests/unit/test_integration_production_input_pipeline.py" in verify_text,
            },
            lambda: [
                "production input pipeline report is missing, stale/source-restored, not covered by scripts/verify-v1.1.sh, or no longer derives installed raw counts from return-acceptance",
            ],
        ),
        _item(
            "production_closeout_review_reproducible",
            "The production closeout review is generated by repo code, covered by unit tests, and summarizes closeout blockers without closing the goal.",
            artifacts,
            [
                "production_closeout_review",
                "production_closeout_review_source",
                "production_closeout_review_test",
                "rollup_approval_contract",
                "required_evidence_consistency",
                "verify_entrypoint",
            ],
            lambda: (
                production_closeout_review.value("status") == "VERIFIED HERE"
                and production_closeout_review.value("ok") is True
                and production_closeout_review.value("decision")
                in {
                    "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
                    "CLOSEOUT_REVIEW_READY",
                }
                and production_closeout_review.value("summary.source_errors_total") == 0
                and production_closeout_review.value("summary.sources_total", 0) > 0
                and production_closeout_review.value("summary.rollup_evidence_files_total")
                == rollup_approval_contract.value("summary.evidence_files_total")
                and production_closeout_review.value("summary.required_evidence_files_total")
                == required_evidence_consistency.value("summary.required_evidence_files_total")
                and production_closeout_review.value("summary.ready") is production_closeout_review.value("ready")
                and production_closeout_review.value("summary.raw_files_install_claim_source")
                in {"return_acceptance", "input_pipeline"}
                and production_closeout_review.value("summary.raw_files_pipeline_reported_installed") is not None
                and production_closeout_review.value("summary.raw_files_existing_or_retained") is not None
                and "tests/unit/test_integration_production_closeout_review.py" in verify_text
            ),
            {
                "decision": production_closeout_review.value("decision"),
                "ready": production_closeout_review.value("ready"),
                "sources_total": production_closeout_review.value("summary.sources_total"),
                "sources_ready": production_closeout_review.value("summary.sources_ready"),
                "source_errors_total": production_closeout_review.value("summary.source_errors_total"),
                "blocking_inputs_total": production_closeout_review.value("summary.blocking_inputs_total"),
                "raw_files_installed": production_closeout_review.value("summary.raw_files_installed"),
                "raw_files_install_claim_source": production_closeout_review.value("summary.raw_files_install_claim_source"),
                "raw_files_pipeline_reported_installed": production_closeout_review.value("summary.raw_files_pipeline_reported_installed"),
                "raw_files_existing_or_retained": production_closeout_review.value("summary.raw_files_existing_or_retained"),
                "required_evidence_files_total": production_closeout_review.value("summary.required_evidence_files_total"),
                "rollup_evidence_files_total": production_closeout_review.value("summary.rollup_evidence_files_total"),
                "x0t_contract_handoff_available": production_closeout_review.value(
                    "summary.x0t_contract_handoff_available"
                ),
                "x0t_contract_handoff_decision": production_closeout_review.value(
                    "summary.x0t_contract_handoff_decision"
                ),
                "x0t_contract_handoff_deployment_ready": production_closeout_review.value(
                    "summary.x0t_contract_handoff_deployment_ready"
                ),
                "x0t_contract_handoff_approval_value_required": production_closeout_review.value(
                    "summary.x0t_contract_handoff_approval_value_required"
                ),
                "x0t_contract_handoff_missing_inputs_total": production_closeout_review.value(
                    "summary.x0t_contract_handoff_missing_inputs_total"
                ),
                "x0t_contract_handoff_operator_actions_total": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_actions_total"
                ),
                "x0t_contract_handoff_operator_approval_required_actions_total": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_approval_required_actions_total"
                ),
                "x0t_contract_handoff_operator_commands_total": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_commands_total"
                ),
                "x0t_contract_handoff_operator_command_entrypoints_missing": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_command_entrypoints_missing"
                ),
                "x0t_contract_handoff_operator_command_surface_ready": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_command_surface_ready"
                ),
                "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"
                ),
                "x0t_contract_handoff_operator_command_shell_surface_ready": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_command_shell_surface_ready"
                ),
                "x0t_contract_handoff_operator_sequence_ready": production_closeout_review.value(
                    "summary.x0t_contract_handoff_operator_sequence_ready"
                ),
                "live_rollout_handoff_available": production_closeout_review.value(
                    "summary.live_rollout_handoff_available"
                ),
                "live_rollout_handoff_decision": production_closeout_review.value(
                    "summary.live_rollout_handoff_decision"
                ),
                "live_rollout_handoff_ready_for_completion_rerun": production_closeout_review.value(
                    "summary.live_rollout_handoff_ready_for_completion_rerun"
                ),
                "live_rollout_handoff_can_close_image_digests_blocker": production_closeout_review.value(
                    "summary.live_rollout_handoff_can_close_image_digests_blocker"
                ),
                "live_rollout_handoff_missing_inputs_total": production_closeout_review.value(
                    "summary.live_rollout_handoff_missing_inputs_total"
                ),
                "live_rollout_handoff_operator_actions_total": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_actions_total"
                ),
                "live_rollout_handoff_operator_input_required_actions_total": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_input_required_actions_total"
                ),
                "live_rollout_handoff_operator_commands_total": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_commands_total"
                ),
                "live_rollout_handoff_operator_command_entrypoints_missing": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_command_entrypoints_missing"
                ),
                "live_rollout_handoff_operator_command_surface_ready": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_command_surface_ready"
                ),
                "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"
                ),
                "live_rollout_handoff_operator_command_shell_surface_ready": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_command_shell_surface_ready"
                ),
                "live_rollout_handoff_operator_sequence_ready": production_closeout_review.value(
                    "summary.live_rollout_handoff_operator_sequence_ready"
                ),
                "test_in_verify_entrypoint": "tests/unit/test_integration_production_closeout_review.py" in verify_text,
            },
            lambda: [
                "production closeout review is missing, stale, not covered by scripts/verify-v1.1.sh, or still has source-read errors",
            ],
        ),
        _item(
            "production_evidence_intake_ready",
            "Operator-supplied production evidence is ready to install for all required integration-spine evidence keys.",
            artifacts,
            ["production_intake"],
            lambda: (
                intake.value("decision") == "READY_FOR_INSTALL"
                and intake.value("summary.ready_for_install") is True
                and intake.value("summary.required_evidence_keys_ready") == intake.value("summary.required_evidence_keys_total")
                and intake.value("summary.required_evidence_keys_pending") == 0
                and intake.value("summary.raw_operator_bundle_syntax_ready") is True
                and intake.value("summary.source_candidate_gate_ready") is True
                and intake.value("summary.production_import_gate_ready") is True
            ),
            {
                "decision": intake.value("decision"),
                "ready_for_install": intake.value("summary.ready_for_install"),
                "required_evidence_keys_ready": intake.value("summary.required_evidence_keys_ready"),
                "required_evidence_keys_total": intake.value("summary.required_evidence_keys_total"),
                "required_evidence_keys_pending": intake.value("summary.required_evidence_keys_pending"),
                "pending_evidence_keys": intake.value("pending_evidence_keys"),
            },
            lambda: [
                "production evidence intake is not ready for install",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "production_gap_index_sources_clear",
            "The production gap index has no source-artifact, route, or import mismatch blockers for required evidence keys.",
            artifacts,
            ["production_gap_index"],
            lambda: (
                gap_index.value("status") == "VERIFIED HERE"
                and gap_index.value("ok") is True
                and gap_index.value("summary.required_evidence_keys_total") == len(REQUIRED_EVIDENCE_KEYS)
                and gap_index.value("summary.pending_evidence_keys") == 0
                and gap_index.value("summary.missing_source_artifacts") == 0
                and gap_index.value("summary.blocked_source_artifacts") == 0
                and gap_index.value("summary.route_missing") == 0
                and gap_index.value("summary.import_mismatches") == 0
                and gap_index.value("summary.source_artifacts_clear") is True
                and gap_index.value("summary.external_settlement_handoff_clear") is True
                and gap_index.value("summary.external_settlement_handoff_ready_for_completion_rerun") is True
                and gap_index.value("summary.external_settlement_handoff_operator_command_entrypoints_missing") == 0
                and gap_index.value(
                    "summary.external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"
                ) == 0
                and gap_index.value("summary.external_settlement_handoff_operator_command_shell_surface_ready") is True
                and gap_index.value("operator_priority_order") == []
                and gap_index.value("blocking_evidence_keys") == []
            ),
            {
                "decision": gap_index.value("decision"),
                "goal_can_be_marked_complete": gap_index.value("goal_can_be_marked_complete"),
                "pending_evidence_keys": gap_index.value("summary.pending_evidence_keys"),
                "missing_source_artifacts": gap_index.value("summary.missing_source_artifacts"),
                "blocked_source_artifacts": gap_index.value("summary.blocked_source_artifacts"),
                "route_missing": gap_index.value("summary.route_missing"),
                "import_mismatches": gap_index.value("summary.import_mismatches"),
                "source_artifacts_clear": gap_index.value("summary.source_artifacts_clear"),
                "completion_audit_clear": gap_index.value("summary.completion_audit_clear"),
                "external_settlement_handoff_clear": gap_index.value(
                    "summary.external_settlement_handoff_clear"
                ),
                "external_settlement_handoff_decision": gap_index.value(
                    "summary.external_settlement_handoff_decision"
                ),
                "external_settlement_handoff_ready_for_completion_rerun": gap_index.value(
                    "summary.external_settlement_handoff_ready_for_completion_rerun"
                ),
                "external_settlement_capture_preflight_decision": gap_index.value(
                    "summary.external_settlement_capture_preflight_decision"
                ),
                "external_settlement_handoff_operator_command_entrypoints_missing": gap_index.value(
                    "summary.external_settlement_handoff_operator_command_entrypoints_missing"
                ),
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": gap_index.value(
                    "summary.external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"
                ),
                "external_settlement_handoff_operator_command_shell_surface_ready": gap_index.value(
                    "summary.external_settlement_handoff_operator_command_shell_surface_ready"
                ),
                "raw_operator_packet_readiness_decision": gap_index.value(
                    "summary.raw_operator_packet_readiness_decision"
                ),
                "raw_operator_packet_readiness_ready_for_collectors": gap_index.value(
                    "summary.raw_operator_packet_readiness_ready_for_collectors"
                ),
                "raw_operator_packet_readiness_collectors_ready": gap_index.value(
                    "summary.raw_operator_packet_readiness_collectors_ready"
                ),
                "raw_operator_packet_readiness_collectors_blocked": gap_index.value(
                    "summary.raw_operator_packet_readiness_collectors_blocked"
                ),
                "raw_operator_packet_readiness_collectors_total": gap_index.value(
                    "summary.raw_operator_packet_readiness_collectors_total"
                ),
                "raw_operator_packet_readiness_raw_files_ready": gap_index.value(
                    "summary.raw_operator_packet_readiness_raw_files_ready"
                ),
                "raw_operator_packet_readiness_raw_files_local_observation": gap_index.value(
                    "summary.raw_operator_packet_readiness_raw_files_local_observation"
                ),
                "raw_operator_packet_readiness_raw_files_total": gap_index.value(
                    "summary.raw_operator_packet_readiness_raw_files_total"
                ),
                "primary_blocker_evidence_key": gap_index.value("summary.primary_blocker_evidence_key"),
                "operator_priority_order": gap_index.value("operator_priority_order"),
                "blocking_evidence_keys": gap_index.value("blocking_evidence_keys"),
            },
            lambda: [
                "production gap index still has source-artifact, route, or import mismatch blockers",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "semantic_production_blockers_closed",
            "Semantic production blocker queue is empty and the integration objective can be marked complete.",
            artifacts,
            ["semantic_queue", "evidence_readiness"],
            lambda: (
                semantic.value("goal_can_be_marked_complete") is True
                and semantic.value("summary.blocking_items_total") == 0
                and semantic.value("summary.semantic_preflight_errors_total") == 0
                and readiness.value("summary.semantic_queue_ready") is True
            ),
            {
                "goal_can_be_marked_complete": semantic.value("goal_can_be_marked_complete"),
                "completion_decision": semantic.value("completion_decision"),
                "blocking_items_total": semantic.value("summary.blocking_items_total"),
                "semantic_preflight_errors_total": semantic.value("summary.semantic_preflight_errors_total"),
                "by_layer": semantic.value("summary.by_layer"),
                "by_collector": semantic.value("summary.by_collector"),
                "readiness_gate": readiness.value("summary.semantic_queue_ready"),
            },
            lambda: [
                "semantic queue still has blockers or does not allow completion",
            ],
            lambda: "BLOCKING"
            if semantic.value("summary.source_errors_total", 0)
            else "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "external_x0t_settlement_ready",
            "A real external X0T settlement receipt is retained and verified against live Base RPC.",
            artifacts,
            ["external_settlement"],
            lambda: (
                settlement.value("summary.x0t_external_settlement_ready") is True
                and settlement.value("summary.live_rpc_ready") is True
                and settlement.value("summary.expected_evidence_file_exists") is True
                and settlement.value("summary.fake_external_settlement_prevention_enforced") is True
            ),
            {
                "decision": settlement.value("decision"),
                "expected_evidence_path": settlement.value("summary.expected_evidence_path"),
                "expected_evidence_file_exists": settlement.value("summary.expected_evidence_file_exists"),
                "x0t_external_settlement_ready": settlement.value("summary.x0t_external_settlement_ready"),
                "live_rpc_ready": settlement.value("summary.live_rpc_ready"),
                "fake_prevention_enforced": settlement.value("summary.fake_external_settlement_prevention_enforced"),
            },
            lambda: [
                "real settlement receipt and live RPC verification are not ready",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "x0t_governance_proposal_executed",
            "X0T governance proposal 1 has final executed-state evidence before production closeout.",
            artifacts,
            ["governance_execute_readiness"],
            lambda: (
                governance_execute.value("decision") == "ALREADY_EXECUTED"
                and governance_execute.value("proposal_state.executed") is True
                and governance_execute.value("proposal_state.vetoed") is False
                and governance_execute.value("summary.execute_ready_now") is False
                and governance_execute.value("mutates_chain") is False
                and governance_execute.value("submits_transaction") is False
            ),
            {
                "decision": governance_execute.value("decision"),
                "state_label": governance_execute.value("proposal_state.state_label"),
                "proposal_executed": governance_execute.value("proposal_state.executed"),
                "proposal_vetoed": governance_execute.value("proposal_state.vetoed"),
                "execute_ready_now": governance_execute.value("summary.execute_ready_now"),
                "next_executable_after_utc": governance_execute.value("summary.next_executable_after_utc"),
                "seconds_until_earliest_execution_by_block_time": governance_execute.value(
                    "timelock.seconds_until_earliest_execution_by_block_time"
                ),
                "not_verified_yet": governance_execute.value("not_verified_yet", []),
            },
            lambda: [
                "governance proposal execution is not complete; rerun the read-only readiness check first and execute only with explicit operator approval when the contract state is Ready",
            ],
            lambda: _governance_execution_blocked_status(
                governance_execute,
                governance_execute_handoff,
            ),
        ),
        _item(
            "x0t_contract_deployment_ready",
            "X0T contract package and operator deployment config are production-ready, including the deployed bridge contract address.",
            artifacts,
            ["x0t_contract_readiness", "x0t_bridge_config"],
            lambda: (
                x0t_contract_readiness.value("contract_readiness_clear") is True
                and x0t_contract_readiness.value("decision") == "CONTRACT_READINESS_CLEAR"
                and x0t_contract_readiness.value("summary.deployment_config_ready") is True
                and x0t_contract_readiness.value("summary.operator_configs_ready") is True
                and x0t_contract_readiness.value("summary.missing_inputs_total") == 0
                and not x0t_contract_readiness.value("missing_inputs", [])
                and x0t_bridge_config.value("bridge_config_ready") is True
                and x0t_bridge_config.value("decision") == "X0T_BRIDGE_CONFIG_READY"
                and x0t_bridge_config.value("summary.bridge_address_input_ready") is True
                and x0t_bridge_config.value("summary.configured_bridge_ready") is True
                and x0t_bridge_config.value("summary.missing_inputs_total") == 0
                and not x0t_bridge_config.value("missing_inputs", [])
            ),
            {
                "contract_readiness_decision": x0t_contract_readiness.value("decision"),
                "contract_readiness_clear": x0t_contract_readiness.value("contract_readiness_clear"),
                "deployment_config_ready": x0t_contract_readiness.value("summary.deployment_config_ready"),
                "operator_configs_ready": x0t_contract_readiness.value("summary.operator_configs_ready"),
                "bridge_contract_source_ready": x0t_contract_readiness.value("summary.bridge_contract_source_ready"),
                "contract_missing_inputs": x0t_contract_readiness.value("missing_inputs", []),
                "contract_missing_inputs_total": x0t_contract_readiness.value("summary.missing_inputs_total"),
                "bridge_config_decision": x0t_bridge_config.value("decision"),
                "bridge_config_ready": x0t_bridge_config.value("bridge_config_ready"),
                "bridge_address_input_ready": x0t_bridge_config.value("summary.bridge_address_input_ready"),
                "configured_bridge_ready": x0t_bridge_config.value("summary.configured_bridge_ready"),
                "bridge_missing_inputs": x0t_bridge_config.value("missing_inputs", []),
                "bridge_missing_inputs_total": x0t_bridge_config.value("summary.missing_inputs_total"),
            },
            lambda: [
                "X0T contract/deployment config is not production-ready; a deployed bridge contract address is still missing or not applied",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "live_rollout_digest_and_provenance_ready",
            "Production rollout evidence has digest-pinned runtime images and retained provenance artifacts.",
            artifacts,
            ["image_digests"],
            lambda: (
                image.value("summary.can_close_image_digests_blocker") is True
                and image.value("summary.raw_deploy_images_total", 0) > 0
                and image.value("summary.raw_deploy_images_digest_pinned") == image.value("summary.raw_deploy_images_total")
                and image.value("summary.runtime_image_provenance_artifacts_retained_here") is True
            ),
            {
                "decision": image.value("decision"),
                "can_close_image_digests_blocker": image.value("summary.can_close_image_digests_blocker"),
                "raw_deploy_images_total": image.value("summary.raw_deploy_images_total"),
                "raw_deploy_images_digest_pinned": image.value("summary.raw_deploy_images_digest_pinned"),
                "runtime_image_provenance_artifacts_retained_here": image.value("summary.runtime_image_provenance_artifacts_retained_here"),
            },
            lambda: [
                "runtime image digests/provenance are not ready",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "raw_evidence_is_production_grade",
            "All retained raw evidence files are production-grade and usable for goal completion.",
            artifacts,
            ["raw_inventory", "evidence_readiness"],
            lambda: (
                raw.value("summary.files_total", 0) > 0
                and raw.value("summary.usable_for_goal_completion_files") == raw.value("summary.files_total")
                and raw.value("summary.semantic_blockers_total") == 0
                and readiness.value("summary.raw_inventory_ready") is True
            ),
            {
                "files_total": raw.value("summary.files_total"),
                "usable_for_goal_completion_files": raw.value("summary.usable_for_goal_completion_files"),
                "semantic_blockers_total": raw.value("summary.semantic_blockers_total"),
                "classification_counts": raw.value("summary.classification_counts"),
                "readiness_gate": readiness.value("summary.raw_inventory_ready"),
            },
            lambda: [
                "retained raw evidence is still component evidence or has semantic blockers",
            ],
            "OPERATOR_INPUT_REQUIRED",
        ),
        _item(
            "current_rollup_complete",
            "The current rollup agrees that production objective completion is ready.",
            artifacts,
            ["current_rollup"],
            lambda: (
                rollup.value("goal_can_be_marked_complete") is True
                and rollup.value("completion_decision") == "COMPLETE"
            ),
            {
                "completion_decision": rollup.value("completion_decision"),
                "goal_can_be_marked_complete": rollup.value("goal_can_be_marked_complete"),
                "summary": rollup.value("summary"),
            },
            lambda: ["current rollup still reports NOT_COMPLETE or false completion flag"],
            "AFTER_BLOCKERS",
        ),
    ]
    return items


def build_audit(root: Path) -> Dict[str, Any]:
    checklist = build_checklist(root)
    passed = sum(1 for item in checklist if item.passed)
    failed = len(checklist) - passed
    checklist_status_counts = _status_counts(checklist)
    complete = failed == 0
    required_consistency_evidence = _item_evidence(checklist, "required_evidence_consistency_valid")
    production_gap_evidence = _item_evidence(checklist, "production_gap_index_sources_clear")
    governance_readiness_evidence = _item_evidence(checklist, "x0t_governance_execute_readiness_reproducible")
    governance_handoff_evidence = _item_evidence(checklist, "x0t_governance_execute_handoff_actionable")
    governance_execution_evidence = _item_evidence(checklist, "x0t_governance_proposal_executed")
    x0t_bridge_config_evidence = _item_evidence(checklist, "x0t_bridge_config_handoff_actionable")
    x0t_contract_readiness_evidence = _item_evidence(checklist, "x0t_contract_readiness_reproducible")
    x0t_contract_deployment_evidence = _item_evidence(checklist, "x0t_contract_deployment_ready")
    production_closeout_evidence = _item_evidence(checklist, "production_closeout_review_reproducible")
    return {
        "schema_version": "x0tta6bl4-integration-spine-completion-audit-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "objective": OBJECTIVE,
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "summary": {
            "checklist_total": len(checklist),
            "checklist_passed": passed,
            "checklist_blocking": failed,
            "checklist_status_counts": checklist_status_counts,
            "checklist_generic_blocking": checklist_status_counts.get("BLOCKING", 0),
            "checklist_operator_input_required": checklist_status_counts.get(
                "OPERATOR_INPUT_REQUIRED", 0
            ),
            "checklist_operator_approval_required": checklist_status_counts.get(
                "OPERATOR_APPROVAL_REQUIRED", 0
            ),
            "checklist_after_blockers": checklist_status_counts.get("AFTER_BLOCKERS", 0),
            "blocking_items_generic_blocking": checklist_status_counts.get("BLOCKING", 0),
            "blocking_items_operator_input_required": checklist_status_counts.get(
                "OPERATOR_INPUT_REQUIRED", 0
            ),
            "blocking_items_operator_approval_required": checklist_status_counts.get(
                "OPERATOR_APPROVAL_REQUIRED", 0
            ),
            "blocking_items_after_blockers": checklist_status_counts.get("AFTER_BLOCKERS", 0),
            "raw_operator_packet_readiness_decision": required_consistency_evidence.get(
                "raw_operator_packet_readiness_decision"
            ),
            "raw_operator_packet_readiness_ready_for_collectors": required_consistency_evidence.get(
                "raw_operator_packet_readiness_ready_for_collectors"
            ),
            "raw_operator_packet_readiness_collectors_ready": required_consistency_evidence.get(
                "raw_operator_packet_readiness_collectors_ready"
            ),
            "raw_operator_packet_readiness_collectors_blocked": required_consistency_evidence.get(
                "raw_operator_packet_readiness_collectors_blocked"
            ),
            "raw_operator_packet_readiness_collectors_total": required_consistency_evidence.get(
                "raw_operator_packet_readiness_collectors_total"
            ),
            "raw_operator_packet_readiness_raw_files_ready": required_consistency_evidence.get(
                "raw_operator_packet_readiness_raw_files_ready"
            ),
            "raw_operator_packet_readiness_raw_files_local_observation": required_consistency_evidence.get(
                "raw_operator_packet_readiness_raw_files_local_observation"
            ),
            "raw_operator_packet_readiness_raw_files_total": required_consistency_evidence.get(
                "raw_operator_packet_readiness_raw_files_total"
            ),
            "raw_operator_packet_production_ready_blocked_by_raw_readiness": required_consistency_evidence.get(
                "raw_operator_packet_production_ready_blocked_by_raw_readiness"
            ),
            "production_gap_raw_operator_packet_readiness_decision": production_gap_evidence.get(
                "raw_operator_packet_readiness_decision"
            ),
            "external_settlement_handoff_clear": production_gap_evidence.get(
                "external_settlement_handoff_clear"
            ),
            "external_settlement_handoff_decision": production_gap_evidence.get(
                "external_settlement_handoff_decision"
            ),
            "external_settlement_handoff_ready_for_completion_rerun": production_gap_evidence.get(
                "external_settlement_handoff_ready_for_completion_rerun"
            ),
            "external_settlement_capture_preflight_decision": production_gap_evidence.get(
                "external_settlement_capture_preflight_decision"
            ),
            "external_settlement_handoff_operator_command_entrypoints_missing": production_gap_evidence.get(
                "external_settlement_handoff_operator_command_entrypoints_missing"
            ),
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": production_gap_evidence.get(
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "external_settlement_handoff_operator_command_shell_surface_ready": production_gap_evidence.get(
                "external_settlement_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_governance_execute_decision": governance_readiness_evidence.get("decision"),
            "x0t_governance_execute_ready_now": governance_readiness_evidence.get("execute_ready_now"),
            "x0t_governance_execute_handoff_decision": governance_handoff_evidence.get("handoff_decision"),
            "x0t_governance_execute_handoff_actionable": governance_handoff_evidence.get("handoff_actionable"),
            "x0t_governance_ready_for_operator_execute": governance_handoff_evidence.get(
                "ready_for_operator_execute"
            ),
            "x0t_governance_handoff_operator_actions_total": governance_handoff_evidence.get(
                "operator_actions_total"
            ),
            "x0t_governance_handoff_operator_commands_total": governance_handoff_evidence.get(
                "operator_commands_total"
            ),
            "x0t_governance_handoff_operator_command_entrypoints_missing": governance_handoff_evidence.get(
                "operator_command_entrypoints_missing"
            ),
            "x0t_governance_handoff_operator_command_surface_ready": governance_handoff_evidence.get(
                "operator_command_surface_ready"
            ),
            "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": governance_handoff_evidence.get(
                "operator_commands_with_shell_redirection_placeholders"
            ),
            "x0t_governance_handoff_operator_command_shell_surface_ready": governance_handoff_evidence.get(
                "operator_command_shell_surface_ready"
            ),
            "x0t_governance_handoff_operator_sequence_ready": governance_handoff_evidence.get(
                "operator_sequence_ready"
            ),
            "x0t_governance_approval_value_required": governance_handoff_evidence.get(
                "approval_value_required"
            ),
            "x0t_governance_proposal_executed": governance_execution_evidence.get("proposal_executed"),
            "x0t_governance_state_label": governance_readiness_evidence.get("state_label"),
            "x0t_governance_next_executable_after_utc": governance_readiness_evidence.get(
                "next_executable_after_utc"
            ),
            "x0t_governance_seconds_until_earliest_execution_by_block_time": governance_readiness_evidence.get(
                "seconds_until_earliest_execution_by_block_time"
            ),
            "x0t_bridge_config_decision": x0t_bridge_config_evidence.get("decision"),
            "x0t_bridge_config_ready": x0t_bridge_config_evidence.get("bridge_config_ready"),
            "x0t_bridge_address_input_ready": x0t_bridge_config_evidence.get("bridge_address_input_ready"),
            "x0t_bridge_configured_bridge_ready": x0t_bridge_config_evidence.get("configured_bridge_ready"),
            "x0t_contract_readiness_decision": x0t_contract_readiness_evidence.get("decision"),
            "x0t_contract_readiness_clear": x0t_contract_readiness_evidence.get("contract_readiness_clear"),
            "x0t_contract_build_env_ready": x0t_contract_readiness_evidence.get("build_env_ready"),
            "x0t_contract_build_verification_ready": x0t_contract_readiness_evidence.get(
                "contract_build_verification_ready"
            ),
            "x0t_contract_bridge_source_ready": x0t_contract_deployment_evidence.get(
                "bridge_contract_source_ready"
            ),
            "x0t_contract_operator_configs_ready": x0t_contract_readiness_evidence.get(
                "operator_configs_ready"
            ),
            "x0t_contract_missing_inputs_total": x0t_contract_deployment_evidence.get(
                "contract_missing_inputs_total"
            ),
            "x0t_contract_deployment_ready": x0t_contract_deployment_evidence.get(
                "contract_readiness_clear"
            )
            is True
            and x0t_contract_deployment_evidence.get("bridge_config_ready") is True,
            "x0t_contract_handoff_available": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_available"),
                production_gap_evidence.get("x0t_contract_operator_handoff_available"),
            ),
            "x0t_contract_handoff_decision": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_decision"),
                production_gap_evidence.get("x0t_contract_operator_handoff_decision"),
            ),
            "x0t_contract_handoff_deployment_ready": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_deployment_ready"),
                production_gap_evidence.get("x0t_contract_deployment_ready"),
            ),
            "x0t_contract_handoff_approval_value_required": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_approval_value_required"),
                production_gap_evidence.get("x0t_contract_approval_value_required"),
            ),
            "x0t_contract_handoff_missing_inputs_total": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_missing_inputs_total"),
                production_gap_evidence.get("x0t_contract_missing_inputs_total"),
            ),
            "x0t_contract_handoff_operator_actions_total": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_operator_actions_total"),
                production_gap_evidence.get("x0t_contract_operator_actions_total"),
            ),
            "x0t_contract_handoff_operator_approval_required_actions_total": production_closeout_evidence.get(
                "x0t_contract_handoff_operator_approval_required_actions_total"
            ),
            "x0t_contract_handoff_operator_commands_total": production_closeout_evidence.get(
                "x0t_contract_handoff_operator_commands_total"
            ),
            "x0t_contract_handoff_operator_command_entrypoints_missing": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_operator_command_entrypoints_missing"),
                production_gap_evidence.get("x0t_contract_operator_command_entrypoints_missing"),
            ),
            "x0t_contract_handoff_operator_command_surface_ready": _first_not_none(
                production_closeout_evidence.get("x0t_contract_handoff_operator_command_surface_ready"),
                production_gap_evidence.get("x0t_contract_operator_command_surface_ready"),
            ),
            "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": production_closeout_evidence.get(
                "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "x0t_contract_handoff_operator_command_shell_surface_ready": production_closeout_evidence.get(
                "x0t_contract_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_contract_handoff_operator_sequence_ready": production_closeout_evidence.get(
                "x0t_contract_handoff_operator_sequence_ready"
            ),
            "live_rollout_handoff_available": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_available"),
                production_gap_evidence.get("live_rollout_handoff_available"),
            ),
            "live_rollout_handoff_decision": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_decision"),
                production_gap_evidence.get("live_rollout_handoff_decision"),
            ),
            "live_rollout_handoff_ready_for_completion_rerun": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_ready_for_completion_rerun"),
                production_gap_evidence.get("live_rollout_ready_for_completion_rerun"),
            ),
            "live_rollout_handoff_can_close_image_digests_blocker": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_can_close_image_digests_blocker"),
                production_gap_evidence.get("live_rollout_can_close_image_digests_blocker"),
            ),
            "live_rollout_handoff_missing_inputs_total": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_missing_inputs_total"),
                production_gap_evidence.get("live_rollout_handoff_missing_inputs_total"),
            ),
            "live_rollout_handoff_operator_actions_total": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_operator_actions_total"),
                production_gap_evidence.get("live_rollout_handoff_operator_actions_total"),
            ),
            "live_rollout_handoff_operator_input_required_actions_total": production_closeout_evidence.get(
                "live_rollout_handoff_operator_input_required_actions_total"
            ),
            "live_rollout_handoff_operator_commands_total": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_operator_commands_total"),
                production_gap_evidence.get("live_rollout_handoff_operator_commands_total"),
            ),
            "live_rollout_handoff_operator_command_entrypoints_missing": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_operator_command_entrypoints_missing"),
                production_gap_evidence.get("live_rollout_handoff_operator_command_entrypoints_missing"),
            ),
            "live_rollout_handoff_operator_command_surface_ready": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_operator_command_surface_ready"),
                production_gap_evidence.get("live_rollout_handoff_operator_command_surface_ready"),
            ),
            "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _first_not_none(
                production_closeout_evidence.get(
                    "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"
                ),
                production_gap_evidence.get(
                    "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"
                ),
            ),
            "live_rollout_handoff_operator_command_shell_surface_ready": _first_not_none(
                production_closeout_evidence.get("live_rollout_handoff_operator_command_shell_surface_ready"),
                production_gap_evidence.get("live_rollout_handoff_operator_command_shell_surface_ready"),
            ),
            "live_rollout_handoff_operator_sequence_ready": production_closeout_evidence.get(
                "live_rollout_handoff_operator_sequence_ready"
            ),
            "local_wiring_passed": all(
                item.passed
                for item in checklist
                if item.item_id
                in {
                    "local_spine_code_wiring",
                    "single_identity_contract",
                    "event_bus_contract",
                    "policy_engine_contract",
                    "safe_actuator_contract",
                    "settlement_reward_contract",
                    "verify_entrypoint_includes_spine",
                    "x0t_bridge_config_handoff_actionable",
                    "x0t_contract_readiness_reproducible",
                    "x0t_governance_execute_readiness_reproducible",
                    "x0t_governance_execute_handoff_actionable",
                    "current_evidence_rollup_reproducible",
                    "semantic_production_blocker_queue_reproducible",
                    "raw_evidence_inventory_reproducible",
                    "rollout_provenance_gate_reproducible",
                    "operator_bundle_manifest_identity_audited",
                    "operator_bundle_identity_plan_available",
                    "operator_bundle_identity_patch_entrypoint_available",
                    "operator_packet_identity_patch_dry_run_command_available",
                    "operator_packet_external_settlement_wrapper_commands_available",
                    "operator_packet_external_settlement_operator_inputs_available",
                    "operator_packet_external_settlement_capture_commands_available",
                    "operator_packet_external_settlement_scaffold_command_available",
                    "external_settlement_template_rejection_smoke_available",
                    "raw_evidence_template_rejection_smoke_available",
                    "live_rollout_image_template_rejection_smoke_available",
                    "operator_packet_post_intake_commands_available",
                    "operator_packet_raw_template_pack_command_available",
                    "operator_packet_raw_required_inputs_available",
                    "operator_packet_rollout_image_scaffold_command_available",
                    "replacement_passport_validation_commands_available",
                    "replacement_passport_external_scaffold_command_available",
                    "rollup_approval_contract_reproducible",
                    "production_input_return_acceptance_reproducible",
                    "production_input_pipeline_reproducible",
                    "production_closeout_review_reproducible",
                }
            ),
            "production_readiness_passed": all(
                item.passed
                for item in checklist
                if item.item_id
                in {
                    "semantic_production_blockers_closed",
                    "operator_evidence_packet_index_complete",
                    "operator_packet_replacement_passport_command_available",
                    "required_evidence_consistency_valid",
                    "production_evidence_replacement_passport_clear",
                    "production_evidence_intake_ready",
                    "production_gap_index_sources_clear",
                    "external_x0t_settlement_ready",
                    "x0t_governance_proposal_executed",
                    "x0t_contract_deployment_ready",
                    "live_rollout_digest_and_provenance_ready",
                    "raw_evidence_is_production_grade",
                    "current_rollup_complete",
                }
            ),
        },
        "checklist": [item.to_dict() for item in checklist],
        "blocking_items": [item.to_dict() for item in checklist if not item.passed],
    }


def render_markdown(audit: Dict[str, Any]) -> str:
    lines = [
        "# Integration Spine Completion Audit",
        "",
        f"Generated: `{audit['generated_at']}`",
        f"Status: `{audit['status']}`",
        f"Completion decision: `{audit['completion_decision']}`",
        f"Goal can be marked complete: `{audit['goal_can_be_marked_complete']}`",
        "",
        "## Objective",
        "",
        audit["objective"],
        "",
        "## Summary",
        "",
    ]
    for key, value in audit["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Checklist", ""])
    for item in audit["checklist"]:
        status = item.get("status") or ("PASS" if item["passed"] else "BLOCKING")
        lines.append(f"- `{item['id']}`: `{status}` - {item['requirement']}")
        if item["gaps"]:
            for gap in item["gaps"]:
                lines.append(f"  - gap: {gap}")
    lines.append("")
    return "\n".join(lines)


def write_outputs(audit: Dict[str, Any], output_json: Optional[Path], output_md: Optional[Path]) -> None:
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(audit, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(audit), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit x0tta6bl4 integration-spine completion evidence")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", help="write audit JSON to this path")
    parser.add_argument("--output-md", help="write audit markdown to this path")
    parser.add_argument("--require-complete", action="store_true", help="return 2 when completion audit is not complete")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="explicit fail-closed readiness gate: return 2 unless completion audit is complete and all critical items are closed",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    audit = build_audit(root)
    write_outputs(
        audit,
        Path(args.output_json) if args.output_json else None,
        Path(args.output_md) if args.output_md else None,
    )
    print(json.dumps({
        "completion_decision": audit["completion_decision"],
        "goal_can_be_marked_complete": audit["goal_can_be_marked_complete"],
        "summary": audit["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_complete and not audit["goal_can_be_marked_complete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
