"""Production evidence gap index for the integration spine.

This read-only gate turns the existing production next-input and import
artifacts into a compact operator priority list. It does not collect live
evidence, stage files, submit settlement transactions, or mark the goal
complete by itself.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS


DEFAULT_NEXT_INPUTS = ".tmp/validation-shards/integration-spine-production-next-inputs-current.json"
DEFAULT_PRODUCTION_IMPORT = ".tmp/validation-shards/integration-spine-production-evidence-import-current.json"
DEFAULT_COMPLETION_AUDIT = ".tmp/validation-shards/integration-spine-completion-audit-current.json"
DEFAULT_PRODUCTION_INTAKE = ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json"
DEFAULT_GOVERNANCE_EXECUTE_READINESS = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"
DEFAULT_GOVERNANCE_EXECUTE_HANDOFF = ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF = ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json"
DEFAULT_ROLLOUT_PROVENANCE = ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_OUTPUT_MD = "docs/verification/integration-spine-production-gap-index-2026-05-20.md"
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"


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


def _as_bool(value: Any) -> bool:
    return value is True


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _completion_item_evidence(completion_audit: Optional[Dict[str, Any]], item_id: str) -> Dict[str, Any]:
    items = (completion_audit or {}).get("checklist", [])
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            evidence = item.get("evidence", {})
            return evidence if isinstance(evidence, dict) else {}
    return {}


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _entrypoint_exists(root: Path, entrypoint: str) -> bool:
    path = Path(entrypoint)
    if path.is_absolute():
        return path.exists()
    return (root / path).exists()


def _x0t_contract_command_checks(root: Path, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected_by_action = {
        "validate_bridge_address": "scripts/ops/apply_x0t_bridge_contract_address.py",
        "apply_bridge_address_with_operator_approval": "scripts/ops/apply_x0t_bridge_contract_address.py",
        "rerun_contract_readiness": "scripts/ops/check_x0t_contract_readiness.py",
        "rerun_completion_audit": "src/integration/completion_audit.py",
        "rerun_production_gap_index": "src/integration/production_gap_index.py",
    }
    checks: List[Dict[str, Any]] = []
    for action in actions:
        action_id = str(action.get("id", ""))
        commands = [str(action.get("command", "") or "")]
        commands.extend(str(command) for command in action.get("commands", []) if isinstance(command, str))
        for command in commands:
            if not command:
                continue
            expected = expected_by_action.get(action_id)
            if not expected:
                continue
            checks.append(
                {
                    "action_id": action_id,
                    "command": command,
                    "expected_entrypoint": expected,
                    "entrypoint_exists": _entrypoint_exists(root, expected),
                    "shell_redirection_placeholder": "",
                    "shell_redirection_placeholder_detected": False,
                    "status": "READY" if _entrypoint_exists(root, expected) else "MISSING_ENTRYPOINT",
                }
            )
    return checks


def _x0t_contract_operator_handoff(
    root: Path,
    completion_summary: Dict[str, Any],
    bridge_config_evidence: Dict[str, Any],
    contract_readiness_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    deployment_ready = completion_summary.get("x0t_contract_deployment_ready") is True
    bridge_decision = completion_summary.get(
        "x0t_bridge_config_decision",
        bridge_config_evidence.get("decision"),
    )
    contract_decision = completion_summary.get(
        "x0t_contract_readiness_decision",
        contract_readiness_evidence.get("decision"),
    )
    missing_inputs = _dict_list(contract_readiness_evidence.get("missing_inputs"))
    if not missing_inputs and not deployment_ready:
        missing_inputs = [
            {
                "id": "operator_contract_addresses",
                "paths": ["charts/x0tta-mesh-operator/examples/meshcluster-production.yaml"],
                "reason": (
                    "operator bridge config still needs its own deployed bridge contract address; "
                    "do not substitute X0TToken or MeshGovernance"
                ),
                "status": OPERATOR_INPUT_REQUIRED,
                "commands": [
                    'export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"',
                    'python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready',
                    'X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready',
                    "python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md",
                ],
            }
        ]

    approval_env = str(
        bridge_config_evidence.get("approval_env")
        or bridge_config_evidence.get("write", {}).get("approval_env")
        or "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
    )
    approval_value = str(
        bridge_config_evidence.get("approval_value_required")
        or bridge_config_evidence.get("write", {}).get("approval_value_required")
        or "apply-bridge-address-base-sepolia"
    )
    actions: List[Dict[str, Any]] = []
    if not deployment_ready:
        actions = [
            {
                "id": "provide_bridge_address",
                "status": "OPERATOR_INPUT_REQUIRED",
                "command": 'export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"',
                "submits_transaction": False,
                "mutates_config": False,
            },
            {
                "id": "validate_bridge_address",
                "status": "OPERATOR_INPUT_REQUIRED",
                "command": 'python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready',
                "submits_transaction": False,
                "mutates_config": False,
            },
            {
                "id": "apply_bridge_address_with_operator_approval",
                "status": "OPERATOR_APPROVAL_REQUIRED",
                "command": f'{approval_env}={approval_value} python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready',
                "requires_operator_approval": True,
                "submits_transaction": False,
                "mutates_config": True,
            },
            {
                "id": "rerun_contract_readiness",
                "status": "AFTER_APPLY",
                "command": "python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md",
                "submits_transaction": False,
                "mutates_config": False,
            },
            {
                "id": "rerun_completion_audit",
                "status": "AFTER_APPLY",
                "command": (
                    "python3 -m src.integration.completion_audit --root . "
                    "--output-json .tmp/validation-shards/integration-spine-completion-audit-current.json "
                    "--output-md docs/verification/integration-spine-completion-audit-2026-05-20.md"
                ),
                "submits_transaction": False,
                "mutates_config": False,
            },
            {
                "id": "rerun_production_gap_index",
                "status": "AFTER_APPLY",
                "command": (
                    "python3 -m src.integration.production_gap_index --root . "
                    "--output-json .tmp/validation-shards/integration-spine-production-gap-index-current.json "
                    "--output-md docs/verification/integration-spine-production-gap-index-2026-05-20.md"
                ),
                "submits_transaction": False,
                "mutates_config": False,
            },
        ]

    command_checks = _x0t_contract_command_checks(root, actions)
    missing_entrypoints = sum(1 for item in command_checks if item.get("entrypoint_exists") is not True)
    return {
        "available": bool(completion_summary or bridge_config_evidence or contract_readiness_evidence),
        "decision": (
            "X0T_CONTRACT_DEPLOYMENT_CONFIG_READY"
            if deployment_ready
            else "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
        ),
        "deployment_ready": deployment_ready,
        "contract_readiness_decision": contract_decision,
        "bridge_config_decision": bridge_decision,
        "bridge_config_ready": completion_summary.get(
            "x0t_bridge_config_ready",
            bridge_config_evidence.get("bridge_config_ready"),
        ),
        "bridge_address_input_ready": completion_summary.get(
            "x0t_bridge_address_input_ready",
            bridge_config_evidence.get("bridge_address_input_ready"),
        ),
        "configured_bridge_ready": completion_summary.get(
            "x0t_bridge_configured_bridge_ready",
            bridge_config_evidence.get("configured_bridge_ready"),
        ),
        "approval_env": approval_env,
        "approval_value_required": approval_value,
        "missing_inputs": missing_inputs,
        "operator_next_actions": actions,
        "operator_command_checks": command_checks,
        "operator_command_entrypoints_missing": missing_entrypoints,
        "operator_command_surface_ready": missing_entrypoints == 0,
    }


def _live_rollout_operator_handoff(rollout_provenance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = (rollout_provenance or {}).get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    missing_inputs = _dict_list((rollout_provenance or {}).get("missing_inputs"))[:10]
    operator_next_actions = _dict_list((rollout_provenance or {}).get("operator_next_actions"))[:10]
    operator_command_checks = _dict_list((rollout_provenance or {}).get("operator_command_checks"))[:10]
    return {
        "available": rollout_provenance is not None,
        "decision": (rollout_provenance or {}).get("operator_handoff_decision"),
        "rollout_decision": (rollout_provenance or {}).get("decision"),
        "ready_for_completion_rerun": (rollout_provenance or {}).get("ready_for_completion_rerun"),
        "can_close_image_digests_blocker": summary.get("can_close_image_digests_blocker"),
        "missing_inputs_total": summary.get("missing_inputs_total", 0),
        "operator_actions_total": summary.get("operator_actions_total", 0),
        "operator_commands_total": summary.get("operator_commands_total", 0),
        "operator_command_entrypoints_missing": summary.get("operator_command_entrypoints_missing", 0),
        "operator_command_surface_ready": summary.get("operator_command_surface_ready"),
        "operator_commands_with_shell_redirection_placeholders": summary.get(
            "operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "operator_command_shell_surface_ready": summary.get("operator_command_shell_surface_ready"),
        "missing_inputs": missing_inputs,
        "operator_next_actions": operator_next_actions,
        "operator_command_checks": operator_command_checks,
    }


@dataclass
class EvidenceGap:
    evidence_key: str
    blocker_class: str
    source_artifact_path: str = ""
    source_artifact_exists: bool = False
    source_ready: bool = False
    supporting_artifact_path: str = ""
    supporting_artifact_exists: bool = False
    operator_action: str = ""
    verification_command: str = ""
    collector_command: str = ""
    top_errors: List[str] = field(default_factory=list)
    raw_paths_to_replace: List[str] = field(default_factory=list)
    operator_bundle_file_report_summary: Dict[str, Any] = field(default_factory=dict)
    intake_blocking_reasons: List[str] = field(default_factory=list)
    consistency_errors: List[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.blocker_class == "READY"

    @property
    def priority_weight(self) -> int:
        order = {
            "MISSING_SOURCE_ARTIFACT": 0,
            "SOURCE_ARTIFACT_BLOCKED": 1,
            "ROUTE_MISSING": 2,
            "IMPORT_MISMATCH": 3,
            "READY": 9,
        }
        return order.get(self.blocker_class, 8)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_key": self.evidence_key,
            "ready": self.ready,
            "blocker_class": self.blocker_class,
            "source_artifact_path": self.source_artifact_path,
            "source_artifact_exists": self.source_artifact_exists,
            "source_ready": self.source_ready,
            "supporting_artifact_path": self.supporting_artifact_path,
            "supporting_artifact_exists": self.supporting_artifact_exists,
            "operator_action": self.operator_action,
            "verification_command": self.verification_command,
            "collector_command": self.collector_command,
            "top_errors": self.top_errors,
            "raw_paths_to_replace": self.raw_paths_to_replace,
            "operator_bundle_file_report_summary": self.operator_bundle_file_report_summary,
            "intake_blocking_reasons": self.intake_blocking_reasons,
            "consistency_errors": self.consistency_errors,
        }


@dataclass
class ProductionGapIndexGate:
    root: Path
    next_inputs_path: Path
    production_import_path: Path
    completion_audit_path: Path
    production_intake_path: Optional[Path] = None
    governance_execute_readiness_path: Optional[Path] = None
    governance_execute_handoff_path: Optional[Path] = None
    external_settlement_handoff_path: Optional[Path] = None
    rollout_provenance_path: Optional[Path] = None
    next_inputs_display: str = DEFAULT_NEXT_INPUTS
    production_import_display: str = DEFAULT_PRODUCTION_IMPORT
    completion_audit_display: str = DEFAULT_COMPLETION_AUDIT
    production_intake_display: str = DEFAULT_PRODUCTION_INTAKE
    governance_execute_readiness_display: str = DEFAULT_GOVERNANCE_EXECUTE_READINESS
    governance_execute_handoff_display: str = DEFAULT_GOVERNANCE_EXECUTE_HANDOFF
    external_settlement_handoff_display: str = DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF
    rollout_provenance_display: str = DEFAULT_ROLLOUT_PROVENANCE
    next_inputs: Optional[Dict[str, Any]] = None
    production_import: Optional[Dict[str, Any]] = None
    completion_audit: Optional[Dict[str, Any]] = None
    production_intake: Optional[Dict[str, Any]] = None
    governance_execute_readiness: Optional[Dict[str, Any]] = None
    governance_execute_handoff: Optional[Dict[str, Any]] = None
    external_settlement_handoff: Optional[Dict[str, Any]] = None
    rollout_provenance: Optional[Dict[str, Any]] = None

    @classmethod
    def load(
        cls,
        next_inputs_path: Path,
        production_import_path: Path,
        completion_audit_path: Path,
        production_intake_path: Optional[Path] = None,
        governance_execute_readiness_path: Optional[Path] = None,
        governance_execute_handoff_path: Optional[Path] = None,
        external_settlement_handoff_path: Optional[Path] = None,
        rollout_provenance_path: Optional[Path] = None,
        next_inputs_display: str = DEFAULT_NEXT_INPUTS,
        production_import_display: str = DEFAULT_PRODUCTION_IMPORT,
        completion_audit_display: str = DEFAULT_COMPLETION_AUDIT,
        production_intake_display: str = DEFAULT_PRODUCTION_INTAKE,
        governance_execute_readiness_display: str = DEFAULT_GOVERNANCE_EXECUTE_READINESS,
        governance_execute_handoff_display: str = DEFAULT_GOVERNANCE_EXECUTE_HANDOFF,
        external_settlement_handoff_display: str = DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF,
        rollout_provenance_display: str = DEFAULT_ROLLOUT_PROVENANCE,
        root: Optional[Path] = None,
    ) -> "ProductionGapIndexGate":
        return cls(
            root=root or Path.cwd(),
            next_inputs_path=next_inputs_path,
            production_import_path=production_import_path,
            completion_audit_path=completion_audit_path,
            production_intake_path=production_intake_path,
            governance_execute_readiness_path=governance_execute_readiness_path,
            governance_execute_handoff_path=governance_execute_handoff_path,
            external_settlement_handoff_path=external_settlement_handoff_path,
            rollout_provenance_path=rollout_provenance_path,
            next_inputs_display=next_inputs_display,
            production_import_display=production_import_display,
            completion_audit_display=completion_audit_display,
            production_intake_display=production_intake_display,
            governance_execute_readiness_display=governance_execute_readiness_display,
            governance_execute_handoff_display=governance_execute_handoff_display,
            external_settlement_handoff_display=external_settlement_handoff_display,
            rollout_provenance_display=rollout_provenance_display,
            next_inputs=_read_json(next_inputs_path),
            production_import=_read_json(production_import_path),
            completion_audit=_read_json(completion_audit_path),
            production_intake=_read_json(production_intake_path) if production_intake_path else None,
            governance_execute_readiness=_read_json(governance_execute_readiness_path)
            if governance_execute_readiness_path
            else None,
            governance_execute_handoff=_read_json(governance_execute_handoff_path)
            if governance_execute_handoff_path
            else None,
            external_settlement_handoff=_read_json(external_settlement_handoff_path)
            if external_settlement_handoff_path
            else None,
            rollout_provenance=_read_json(rollout_provenance_path)
            if rollout_provenance_path
            else None,
        )

    def _next_input_by_key(self) -> Dict[str, Dict[str, Any]]:
        items = (self.next_inputs or {}).get("required_inputs", [])
        if not isinstance(items, list):
            return {}
        return {str(item.get("evidence_key", "")): item for item in items if isinstance(item, dict)}

    def _import_result_by_key(self) -> Dict[str, Dict[str, Any]]:
        items = (self.production_import or {}).get("source_results", [])
        if not isinstance(items, list):
            return {}
        return {str(item.get("evidence_key", "")): item for item in items if isinstance(item, dict)}

    def _intake_status_by_key(self) -> Dict[str, Dict[str, Any]]:
        items = (self.production_intake or {}).get("evidence_key_statuses", [])
        if not isinstance(items, list):
            return {}
        return {str(item.get("evidence_key", "")): item for item in items if isinstance(item, dict)}

    def _gap_for_key(
        self,
        key: str,
        next_item: Optional[Dict[str, Any]],
        import_item: Optional[Dict[str, Any]],
        intake_item: Optional[Dict[str, Any]],
    ) -> EvidenceGap:
        if next_item is None and import_item is None:
            return EvidenceGap(
                evidence_key=key,
                blocker_class="ROUTE_MISSING",
                consistency_errors=["evidence key is missing from next-inputs and production-import artifacts"],
            )

        next_item = next_item or {}
        import_item = import_item or {}
        intake_item = intake_item or {}
        source_path = str(next_item.get("source_artifact_path") or import_item.get("artifact_path") or "")
        source_exists = _as_bool(next_item.get("source_artifact_exists")) or _as_bool(import_item.get("artifact_exists"))
        source_ready = _as_bool(next_item.get("ready")) and _as_bool(import_item.get("ready"))
        file_report_summary = intake_item.get("operator_bundle_file_report_summary", {})
        if not isinstance(file_report_summary, dict):
            file_report_summary = {}
        top_errors = [
            str(error)
            for error in (
                next_item.get("errors")
                or next_item.get("collector_preflight_errors")
                or import_item.get("errors")
                or []
            )
            if isinstance(error, str)
        ][:5]
        raw_paths = [
            str(path)
            for path in next_item.get("collector_semantic_blocker_raw_paths", [])
            if isinstance(path, str)
        ][:10]
        intake_blocking_reasons = [
            str(reason)
            for reason in intake_item.get("missing_or_blocking_reasons", [])
            if isinstance(reason, str)
        ][:10]

        consistency_errors: List[str] = []
        import_path = str(import_item.get("artifact_path", ""))
        if source_path and import_path and source_path != import_path:
            consistency_errors.append(f"next-input source path differs from production-import artifact path: {source_path} != {import_path}")
        if _as_bool(next_item.get("ready")) != _as_bool(import_item.get("ready")):
            consistency_errors.append("next-input ready flag differs from production-import ready flag")

        if consistency_errors:
            blocker_class = "IMPORT_MISMATCH"
        elif not source_exists:
            blocker_class = "MISSING_SOURCE_ARTIFACT"
        elif not source_ready:
            blocker_class = "SOURCE_ARTIFACT_BLOCKED"
        else:
            blocker_class = "READY"

        return EvidenceGap(
            evidence_key=key,
            blocker_class=blocker_class,
            source_artifact_path=source_path,
            source_artifact_exists=source_exists,
            source_ready=source_ready,
            supporting_artifact_path=str(import_item.get("supporting_artifact_path", "")),
            supporting_artifact_exists=_as_bool(import_item.get("supporting_artifact_exists")),
            operator_action=str(next_item.get("operator_action", "")),
            verification_command=str(next_item.get("verification_command", "")),
            collector_command=str(next_item.get("collector_command", "")),
            top_errors=top_errors,
            raw_paths_to_replace=raw_paths,
            operator_bundle_file_report_summary=file_report_summary,
            intake_blocking_reasons=intake_blocking_reasons,
            consistency_errors=consistency_errors,
        )

    def evidence_gaps(self) -> List[EvidenceGap]:
        next_by_key = self._next_input_by_key()
        import_by_key = self._import_result_by_key()
        intake_by_key = self._intake_status_by_key()
        gaps = [
            self._gap_for_key(key, next_by_key.get(key), import_by_key.get(key), intake_by_key.get(key))
            for key in sorted(REQUIRED_EVIDENCE_KEYS)
        ]
        return sorted(gaps, key=lambda gap: (gap.priority_weight, gap.evidence_key))

    def report(self) -> Dict[str, Any]:
        source_missing = self.next_inputs is None
        import_missing = self.production_import is None
        completion_missing = self.completion_audit is None
        intake_missing = self.production_intake is None
        governance_configured = self.governance_execute_readiness_path is not None
        governance_missing = governance_configured and self.governance_execute_readiness is None
        governance_handoff_configured = self.governance_execute_handoff_path is not None
        governance_handoff_missing = governance_handoff_configured and self.governance_execute_handoff is None
        external_handoff_configured = self.external_settlement_handoff_path is not None
        external_handoff_missing = external_handoff_configured and self.external_settlement_handoff is None
        rollout_configured = self.rollout_provenance_path is not None
        rollout_missing = rollout_configured and self.rollout_provenance is None
        gaps = self.evidence_gaps()
        blocking = [gap for gap in gaps if not gap.ready]
        ready = [gap for gap in gaps if gap.ready]

        completion_summary = (self.completion_audit or {}).get("summary", {})
        if not isinstance(completion_summary, dict):
            completion_summary = {}
        completion_total = _as_int(completion_summary.get("checklist_total"))
        completion_passed = _as_int(completion_summary.get("checklist_passed"))
        completion_blocking = _as_int(completion_summary.get("checklist_blocking"))
        completion_clear = (
            not completion_missing
            and self.completion_audit.get("goal_can_be_marked_complete") is True
            and self.completion_audit.get("completion_decision") == "COMPLETE"
        )
        governance_summary = (self.governance_execute_readiness or {}).get("summary", {})
        if not isinstance(governance_summary, dict):
            governance_summary = {}
        governance_state = (self.governance_execute_readiness or {}).get("proposal_state", {})
        if not isinstance(governance_state, dict):
            governance_state = {}
        governance_timelock = (self.governance_execute_readiness or {}).get("timelock", {})
        if not isinstance(governance_timelock, dict):
            governance_timelock = {}
        governance_executed = (
            not governance_missing
            and (not governance_configured or (
                (self.governance_execute_readiness or {}).get("decision") == "ALREADY_EXECUTED"
                and governance_state.get("executed") is True
                and governance_state.get("vetoed") is False
            ))
        )
        governance_blocked = governance_configured and not governance_executed
        governance_handoff_summary = (self.governance_execute_handoff or {}).get("summary", {})
        if not isinstance(governance_handoff_summary, dict):
            governance_handoff_summary = {}
        governance_handoff_approval = (self.governance_execute_handoff or {}).get("approval_boundary", {})
        if not isinstance(governance_handoff_approval, dict):
            governance_handoff_approval = {}
        governance_handoff_missing_inputs = _dict_list(
            (self.governance_execute_handoff or {}).get("missing_inputs")
        )[:10]
        governance_handoff_operator_next_actions = _dict_list(
            (self.governance_execute_handoff or {}).get("operator_next_actions")
        )[:10]
        governance_handoff_operator_command_checks = _dict_list(
            (self.governance_execute_handoff or {}).get("operator_command_checks")
        )[:10]
        governance_handoff_clear = (
            not governance_handoff_configured
            or (
                not governance_handoff_missing
                and (self.governance_execute_handoff or {}).get("status") == "VERIFIED HERE"
                and (self.governance_execute_handoff or {}).get("ok") is True
                and str((self.governance_execute_handoff or {}).get("schema_version", "")).endswith(
                    "v2-repo-generated"
                )
                and (self.governance_execute_handoff or {}).get("handoff_actionable") is True
                and (self.governance_execute_handoff or {}).get("goal_can_be_marked_complete") is False
                and (self.governance_execute_handoff or {}).get("mutates_chain") is False
                and (self.governance_execute_handoff or {}).get("runs_live_rpc") is False
                and (self.governance_execute_handoff or {}).get("submits_transaction") is False
                and governance_handoff_summary.get("source_errors_total") == 0
                and (
                    not governance_configured
                    or governance_handoff_summary.get("readiness_decision")
                    == (self.governance_execute_readiness or {}).get("decision")
                )
                and governance_handoff_approval.get("approval_env") == "X0T_EXECUTE_PROPOSAL_APPROVAL"
                and governance_handoff_approval.get("can_submit_without_operator_approval") is False
                and governance_handoff_summary.get("operator_commands_total") == 5
                and governance_handoff_summary.get("operator_command_entrypoints_missing") == 0
                and governance_handoff_summary.get("operator_command_surface_ready") is True
                and governance_handoff_summary.get("operator_commands_with_shell_redirection_placeholders") == 0
                and governance_handoff_summary.get("operator_command_shell_surface_ready") is True
                and governance_handoff_summary.get("operator_sequence_ready") is True
            )
        )
        governance_handoff_blocked = governance_handoff_configured and not governance_handoff_clear
        external_handoff_summary = (self.external_settlement_handoff or {}).get("summary", {})
        if not isinstance(external_handoff_summary, dict):
            external_handoff_summary = {}
        external_handoff_missing_inputs = _dict_list(
            (self.external_settlement_handoff or {}).get("missing_inputs")
        )[:10]
        external_handoff_operator_next_actions = _dict_list(
            (self.external_settlement_handoff or {}).get("operator_next_actions")
        )[:10]
        external_handoff_operator_command_checks = _dict_list(
            (self.external_settlement_handoff or {}).get("operator_command_checks")
        )[:10]
        external_handoff_clear = (
            not external_handoff_configured
            or (
                not external_handoff_missing
                and (self.external_settlement_handoff or {}).get("status") == "VERIFIED HERE"
                and (self.external_settlement_handoff or {}).get("ok") is True
                and str((self.external_settlement_handoff or {}).get("schema_version", "")).endswith(
                    "v6-repo-generated"
                )
                and (self.external_settlement_handoff or {}).get("handoff_decision")
                in {
                    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY",
                    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
                }
                and (self.external_settlement_handoff or {}).get("goal_can_be_marked_complete") is False
                and (self.external_settlement_handoff or {}).get("mutates_chain") is False
                and (self.external_settlement_handoff or {}).get("runs_live_rpc") is False
                and (self.external_settlement_handoff or {}).get("submits_transaction") is False
                and external_handoff_summary.get("source_errors_total") == 0
                and external_handoff_summary.get("capture_preflight_available") is True
                and external_handoff_summary.get("capture_preflight_decision")
                in {"CAPTURE_INPUTS_READY", "CAPTURE_INPUTS_BLOCKED"}
                and isinstance(external_handoff_summary.get("capture_inputs_ready"), bool)
                and external_handoff_summary.get("operator_actions_total") == 6
                and external_handoff_summary.get("operator_commands_total") == 5
                and external_handoff_summary.get("operator_command_entrypoints_missing") == 0
                and external_handoff_summary.get("operator_command_surface_ready") is True
                and external_handoff_summary.get("operator_commands_with_shell_redirection_placeholders") == 0
                and external_handoff_summary.get("operator_command_shell_surface_ready") is True
            )
        )
        external_handoff_ready = (
            external_handoff_clear
            and (self.external_settlement_handoff or {}).get("ready_for_completion_rerun") is True
        )
        external_handoff_blocked = external_handoff_configured and not external_handoff_clear
        rollout_summary = (self.rollout_provenance or {}).get("summary", {})
        if not isinstance(rollout_summary, dict):
            rollout_summary = {}
        live_rollout_operator_handoff = _live_rollout_operator_handoff(self.rollout_provenance)
        rollout_handoff_clear = (
            not rollout_configured
            or (
                not rollout_missing
                and (self.rollout_provenance or {}).get("status") == "VERIFIED HERE"
                and (self.rollout_provenance or {}).get("ok") is True
                and (self.rollout_provenance or {}).get("schema_version")
                == "x0tta6bl4-live-rollout-image-digests-closure-attempt-v2"
                and (self.rollout_provenance or {}).get("decision")
                in {"READY_TO_CLOSE", "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"}
                and (self.rollout_provenance or {}).get("operator_handoff_decision")
                in {
                    "LIVE_ROLLOUT_IMAGE_DIGESTS_READY",
                    "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
                }
                and (self.rollout_provenance or {}).get("goal_can_be_marked_complete") is False
                and isinstance((self.rollout_provenance or {}).get("ready_for_completion_rerun"), bool)
                and isinstance(rollout_summary.get("can_close_image_digests_blocker"), bool)
                and rollout_summary.get("operator_command_entrypoints_missing") == 0
                and rollout_summary.get("operator_command_surface_ready") is True
                and rollout_summary.get("operator_commands_with_shell_redirection_placeholders") == 0
                and rollout_summary.get("operator_command_shell_surface_ready") is True
            )
        )
        rollout_handoff_ready = (
            rollout_handoff_clear
            and (self.rollout_provenance or {}).get("ready_for_completion_rerun") is True
            and rollout_summary.get("can_close_image_digests_blocker") is True
        )
        rollout_handoff_blocked = rollout_configured and not rollout_handoff_clear
        passport_evidence = _completion_item_evidence(
            self.completion_audit,
            "production_evidence_replacement_passport_clear",
        )
        semantic_evidence = _completion_item_evidence(
            self.completion_audit,
            "semantic_production_blocker_queue_reproducible",
        )
        raw_inventory_evidence = _completion_item_evidence(
            self.completion_audit,
            "raw_evidence_inventory_reproducible",
        )
        required_consistency_evidence = _completion_item_evidence(
            self.completion_audit,
            "required_evidence_consistency_valid",
        )
        x0t_bridge_config_evidence = _completion_item_evidence(
            self.completion_audit,
            "x0t_bridge_config_handoff_actionable",
        )
        x0t_contract_readiness_evidence = _completion_item_evidence(
            self.completion_audit,
            "x0t_contract_readiness_reproducible",
        )
        x0t_contract_operator_handoff = _x0t_contract_operator_handoff(
            self.root,
            completion_summary,
            x0t_bridge_config_evidence,
            x0t_contract_readiness_evidence,
        )
        source_artifacts_clear = not source_missing and not import_missing and not blocking
        external_handoff_stale_after_source_clear = (
            external_handoff_configured
            and external_handoff_clear
            and source_artifacts_clear
            and not external_handoff_ready
        )
        all_clear = (
            source_artifacts_clear
            and completion_clear
            and not governance_blocked
            and not governance_handoff_blocked
            and not external_handoff_blocked
            and (not external_handoff_configured or external_handoff_ready)
            and not rollout_handoff_blocked
            and (not rollout_configured or rollout_handoff_ready)
        )

        missing_source = [gap for gap in blocking if gap.blocker_class == "MISSING_SOURCE_ARTIFACT"]
        blocked_source = [gap for gap in blocking if gap.blocker_class == "SOURCE_ARTIFACT_BLOCKED"]
        route_missing = [gap for gap in blocking if gap.blocker_class == "ROUTE_MISSING"]
        mismatched = [gap for gap in blocking if gap.blocker_class == "IMPORT_MISMATCH"]
        bundle_manifest_identity_mismatches_total = sum(
            int(gap.operator_bundle_file_report_summary.get("manifest_identity_mismatches_total", 0) or 0)
            for gap in gaps
        )
        bundle_collector_id_mismatches = sum(
            int(gap.operator_bundle_file_report_summary.get("collector_id_mismatches", 0) or 0)
            for gap in gaps
        )
        bundle_raw_id_mismatches = sum(
            int(gap.operator_bundle_file_report_summary.get("raw_id_mismatches", 0) or 0)
            for gap in gaps
        )
        bundle_file_name_mismatches = sum(
            int(gap.operator_bundle_file_report_summary.get("file_name_mismatches", 0) or 0)
            for gap in gaps
        )

        blocking_reasons: List[str] = []
        if source_missing:
            blocking_reasons.append("production next-inputs artifact is missing or unreadable")
        if import_missing:
            blocking_reasons.append("production evidence import artifact is missing or unreadable")
        if completion_missing:
            blocking_reasons.append("completion audit artifact is missing or unreadable")
        if governance_missing:
            blocking_reasons.append("X0T governance execute-readiness artifact is missing or unreadable")
        if governance_handoff_missing:
            blocking_reasons.append("X0T governance execute operator handoff artifact is missing or unreadable")
        elif governance_handoff_blocked:
            blocking_reasons.append("X0T governance execute operator handoff is not actionable/read-only")
        elif governance_blocked:
            blocking_reasons.append("X0T governance proposal is not executed")
        if external_handoff_missing:
            blocking_reasons.append("External X0T settlement operator handoff artifact is missing or unreadable")
        elif external_handoff_blocked:
            blocking_reasons.append("External X0T settlement operator handoff is not read-only/current/aligned")
        elif external_handoff_stale_after_source_clear:
            blocking_reasons.append("External X0T settlement operator handoff is not ready for completion rerun")
        if rollout_missing:
            blocking_reasons.append("Live rollout image digest/provenance handoff artifact is missing or unreadable")
        elif rollout_handoff_blocked:
            blocking_reasons.append("Live rollout image digest/provenance handoff is not read-only/current/aligned")
        elif rollout_configured and not rollout_handoff_ready:
            blocking_reasons.append("Live rollout image digest/provenance handoff is not ready for completion rerun")
        if completion_summary.get("x0t_contract_deployment_ready") is False:
            blocking_reasons.append("X0T contract deployment config is not ready")
        if missing_source:
            blocking_reasons.append("one or more required source artifacts are missing")
        if blocked_source:
            blocking_reasons.append("one or more source artifacts exist but their evidence gates are blocked")
        if route_missing:
            blocking_reasons.append("one or more required evidence keys are missing from the input/import routes")
        if mismatched:
            blocking_reasons.append("one or more input/import route pairs disagree")
        if not completion_clear:
            blocking_reasons.append("completion audit is not COMPLETE")

        return {
            "schema_version": "x0tta6bl4-integration-spine-production-gap-index-v1",
            "generated_at": utc_now(),
            "status": "VERIFIED HERE",
            "ok": True,
            "claim_boundary": (
                "Read-only production evidence gap index. It reads existing next-input, import, "
                "completion-audit, production-intake, governance handoff, external-settlement "
                "handoff, and rollout provenance artifacts; it does not collect live evidence, "
                "stage files, submit settlement transactions, mutate runtime state, or close /goal."
            ),
            "decision": "NO_PRODUCTION_EVIDENCE_GAPS" if all_clear else "BLOCKED_ON_OPERATOR_EVIDENCE",
            "goal_can_be_marked_complete": all_clear,
            "source_artifacts": [
                self.next_inputs_display,
                self.production_import_display,
                self.completion_audit_display,
                self.production_intake_display,
            ]
            + ([self.governance_execute_readiness_display] if governance_configured else [])
            + ([self.governance_execute_handoff_display] if governance_handoff_configured else [])
            + ([self.external_settlement_handoff_display] if external_handoff_configured else [])
            + ([self.rollout_provenance_display] if rollout_configured else []),
            "summary": {
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "ready_evidence_keys": len(ready),
                "pending_evidence_keys": len(blocking),
                "missing_source_artifacts": len(missing_source),
                "blocked_source_artifacts": len(blocked_source),
                "route_missing": len(route_missing),
                "import_mismatches": len(mismatched),
                "source_artifacts_clear": source_artifacts_clear,
                "completion_audit_clear": completion_clear,
                "completion_local_wiring_passed": _as_bool(completion_summary.get("local_wiring_passed")),
                "completion_production_readiness_passed": _as_bool(
                    completion_summary.get("production_readiness_passed")
                ),
                "raw_operator_packet_readiness_decision": completion_summary.get(
                    "raw_operator_packet_readiness_decision",
                    required_consistency_evidence.get("raw_operator_packet_readiness_decision"),
                ),
                "raw_operator_packet_readiness_ready_for_collectors": completion_summary.get(
                    "raw_operator_packet_readiness_ready_for_collectors",
                    required_consistency_evidence.get("raw_operator_packet_readiness_ready_for_collectors"),
                ),
                "raw_operator_packet_readiness_collectors_ready": completion_summary.get(
                    "raw_operator_packet_readiness_collectors_ready",
                    required_consistency_evidence.get("raw_operator_packet_readiness_collectors_ready"),
                ),
                "raw_operator_packet_readiness_collectors_blocked": completion_summary.get(
                    "raw_operator_packet_readiness_collectors_blocked",
                    required_consistency_evidence.get("raw_operator_packet_readiness_collectors_blocked"),
                ),
                "raw_operator_packet_readiness_collectors_total": completion_summary.get(
                    "raw_operator_packet_readiness_collectors_total",
                    required_consistency_evidence.get("raw_operator_packet_readiness_collectors_total"),
                ),
                "raw_operator_packet_readiness_raw_files_ready": completion_summary.get(
                    "raw_operator_packet_readiness_raw_files_ready",
                    required_consistency_evidence.get("raw_operator_packet_readiness_raw_files_ready"),
                ),
                "raw_operator_packet_readiness_raw_files_local_observation": completion_summary.get(
                    "raw_operator_packet_readiness_raw_files_local_observation",
                    required_consistency_evidence.get("raw_operator_packet_readiness_raw_files_local_observation"),
                ),
                "raw_operator_packet_readiness_raw_files_total": completion_summary.get(
                    "raw_operator_packet_readiness_raw_files_total",
                    required_consistency_evidence.get("raw_operator_packet_readiness_raw_files_total"),
                ),
                "raw_operator_packet_production_ready_blocked_by_raw_readiness": completion_summary.get(
                    "raw_operator_packet_production_ready_blocked_by_raw_readiness",
                    required_consistency_evidence.get("raw_operator_packet_production_ready_blocked_by_raw_readiness"),
                ),
                "production_intake_available": not intake_missing,
                "completion_checklist_total": completion_total,
                "completion_checklist_passed": completion_passed,
                "completion_checklist_blocking": completion_blocking,
                "completion_checklist_remaining": max(completion_total - completion_passed, 0),
                "x0t_governance_execute_readiness_available": self.governance_execute_readiness is not None,
                "x0t_governance_execute_decision": (self.governance_execute_readiness or {}).get("decision"),
                "x0t_governance_execute_ready_now": governance_summary.get("execute_ready_now"),
                "x0t_governance_execute_handoff_available": self.governance_execute_handoff is not None,
                "x0t_governance_execute_handoff_clear": governance_handoff_clear,
                "x0t_governance_execute_handoff_decision": (
                    self.governance_execute_handoff or {}
                ).get(
                    "handoff_decision",
                    completion_summary.get("x0t_governance_execute_handoff_decision"),
                ),
                "x0t_governance_execute_handoff_actionable": (
                    self.governance_execute_handoff or {}
                ).get(
                    "handoff_actionable",
                    completion_summary.get("x0t_governance_execute_handoff_actionable"),
                ),
                "x0t_governance_ready_for_operator_execute": (
                    self.governance_execute_handoff or {}
                ).get(
                    "ready_for_operator_execute",
                    completion_summary.get("x0t_governance_ready_for_operator_execute"),
                ),
                "x0t_governance_execute_handoff_source_errors_total": governance_handoff_summary.get(
                    "source_errors_total"
                ),
                "x0t_governance_execute_handoff_missing_inputs_total": governance_handoff_summary.get(
                    "missing_inputs_total",
                    completion_summary.get("x0t_governance_handoff_missing_inputs_total"),
                ),
                "x0t_governance_execute_handoff_operator_actions_total": governance_handoff_summary.get(
                    "operator_actions_total",
                    completion_summary.get("x0t_governance_handoff_operator_actions_total"),
                ),
                "x0t_governance_execute_handoff_operator_commands_total": governance_handoff_summary.get(
                    "operator_commands_total",
                    completion_summary.get("x0t_governance_handoff_operator_commands_total"),
                ),
                "x0t_governance_execute_handoff_operator_command_entrypoints_missing": governance_handoff_summary.get(
                    "operator_command_entrypoints_missing",
                    completion_summary.get("x0t_governance_handoff_operator_command_entrypoints_missing"),
                ),
                "x0t_governance_execute_handoff_operator_command_surface_ready": governance_handoff_summary.get(
                    "operator_command_surface_ready",
                    completion_summary.get("x0t_governance_handoff_operator_command_surface_ready"),
                ),
                "x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders": governance_handoff_summary.get(
                    "operator_commands_with_shell_redirection_placeholders",
                    completion_summary.get("x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"),
                ),
                "x0t_governance_execute_handoff_operator_command_shell_surface_ready": governance_handoff_summary.get(
                    "operator_command_shell_surface_ready",
                    completion_summary.get("x0t_governance_handoff_operator_command_shell_surface_ready"),
                ),
                "x0t_governance_execute_handoff_operator_sequence_ready": governance_handoff_summary.get(
                    "operator_sequence_ready",
                    completion_summary.get("x0t_governance_handoff_operator_sequence_ready"),
                ),
                "x0t_governance_approval_value_required": governance_handoff_approval.get(
                    "expected_value",
                    completion_summary.get("x0t_governance_approval_value_required"),
                ),
                "x0t_governance_proposal_executed": governance_executed and governance_configured,
                "x0t_governance_state_label": governance_state.get("state_label"),
                "x0t_governance_next_executable_after_utc": governance_summary.get("next_executable_after_utc"),
                "x0t_governance_seconds_until_earliest_execution_by_block_time": governance_timelock.get(
                    "seconds_until_earliest_execution_by_block_time"
                ),
                "x0t_bridge_config_decision": completion_summary.get("x0t_bridge_config_decision"),
                "x0t_bridge_config_ready": completion_summary.get("x0t_bridge_config_ready"),
                "x0t_bridge_address_input_ready": completion_summary.get("x0t_bridge_address_input_ready"),
                "x0t_bridge_configured_bridge_ready": completion_summary.get(
                    "x0t_bridge_configured_bridge_ready"
                ),
                "x0t_contract_readiness_decision": completion_summary.get("x0t_contract_readiness_decision"),
                "x0t_contract_readiness_clear": completion_summary.get("x0t_contract_readiness_clear"),
                "x0t_contract_build_env_ready": completion_summary.get("x0t_contract_build_env_ready"),
                "x0t_contract_build_verification_ready": completion_summary.get(
                    "x0t_contract_build_verification_ready"
                ),
                "x0t_contract_bridge_source_ready": completion_summary.get(
                    "x0t_contract_bridge_source_ready"
                ),
                "x0t_contract_operator_configs_ready": completion_summary.get(
                    "x0t_contract_operator_configs_ready"
                ),
                "x0t_contract_missing_inputs_total": completion_summary.get(
                    "x0t_contract_missing_inputs_total"
                ),
                "x0t_contract_deployment_ready": completion_summary.get("x0t_contract_deployment_ready"),
                "x0t_contract_operator_handoff_available": x0t_contract_operator_handoff.get("available"),
                "x0t_contract_operator_handoff_decision": x0t_contract_operator_handoff.get("decision"),
                "x0t_contract_operator_actions_total": len(
                    x0t_contract_operator_handoff.get("operator_next_actions", [])
                ),
                "x0t_contract_operator_command_entrypoints_missing": x0t_contract_operator_handoff.get(
                    "operator_command_entrypoints_missing"
                ),
                "x0t_contract_operator_command_surface_ready": x0t_contract_operator_handoff.get(
                    "operator_command_surface_ready"
                ),
                "x0t_contract_approval_value_required": x0t_contract_operator_handoff.get(
                    "approval_value_required"
                ),
                "external_settlement_handoff_available": self.external_settlement_handoff is not None,
                "external_settlement_handoff_clear": external_handoff_clear,
                "external_settlement_handoff_decision": (
                    self.external_settlement_handoff or {}
                ).get("handoff_decision"),
                "external_settlement_handoff_ready_for_completion_rerun": (
                    self.external_settlement_handoff or {}
                ).get("ready_for_completion_rerun"),
                "external_settlement_handoff_source_errors_total": external_handoff_summary.get(
                    "source_errors_total"
                ),
                "external_settlement_capture_preflight_decision": external_handoff_summary.get(
                    "capture_preflight_decision"
                ),
                "external_settlement_capture_inputs_ready": external_handoff_summary.get(
                    "capture_inputs_ready"
                ),
                "external_settlement_handoff_missing_inputs_total": external_handoff_summary.get(
                    "missing_inputs_total"
                ),
                "external_settlement_handoff_operator_actions_total": external_handoff_summary.get(
                    "operator_actions_total"
                ),
                "external_settlement_handoff_operator_commands_total": external_handoff_summary.get(
                    "operator_commands_total"
                ),
                "external_settlement_handoff_operator_command_entrypoints_missing": external_handoff_summary.get(
                    "operator_command_entrypoints_missing"
                ),
                "external_settlement_handoff_operator_command_surface_ready": external_handoff_summary.get(
                    "operator_command_surface_ready"
                ),
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": external_handoff_summary.get(
                    "operator_commands_with_shell_redirection_placeholders"
                ),
                "external_settlement_handoff_operator_command_shell_surface_ready": external_handoff_summary.get(
                    "operator_command_shell_surface_ready"
                ),
                "live_rollout_handoff_available": self.rollout_provenance is not None,
                "live_rollout_handoff_clear": rollout_handoff_clear,
                "live_rollout_handoff_decision": live_rollout_operator_handoff.get("decision"),
                "live_rollout_ready_for_completion_rerun": live_rollout_operator_handoff.get(
                    "ready_for_completion_rerun"
                ),
                "live_rollout_can_close_image_digests_blocker": live_rollout_operator_handoff.get(
                    "can_close_image_digests_blocker"
                ),
                "live_rollout_handoff_missing_inputs_total": live_rollout_operator_handoff.get(
                    "missing_inputs_total"
                ),
                "live_rollout_handoff_operator_actions_total": live_rollout_operator_handoff.get(
                    "operator_actions_total"
                ),
                "live_rollout_handoff_operator_commands_total": live_rollout_operator_handoff.get(
                    "operator_commands_total"
                ),
                "live_rollout_handoff_operator_command_entrypoints_missing": live_rollout_operator_handoff.get(
                    "operator_command_entrypoints_missing"
                ),
                "live_rollout_handoff_operator_command_surface_ready": live_rollout_operator_handoff.get(
                    "operator_command_surface_ready"
                ),
                "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": live_rollout_operator_handoff.get(
                    "operator_commands_with_shell_redirection_placeholders"
                ),
                "live_rollout_handoff_operator_command_shell_surface_ready": live_rollout_operator_handoff.get(
                    "operator_command_shell_surface_ready"
                ),
                "primary_blocker_evidence_key": blocking[0].evidence_key if blocking else "",
                "bundle_manifest_identity_mismatches_total": bundle_manifest_identity_mismatches_total,
                "bundle_collector_id_mismatches": bundle_collector_id_mismatches,
                "bundle_raw_id_mismatches": bundle_raw_id_mismatches,
                "bundle_file_name_mismatches": bundle_file_name_mismatches,
                "raw_install_claim_source": passport_evidence.get(
                    "raw_install_claim_source",
                    semantic_evidence.get("raw_install_claim_source", raw_inventory_evidence.get("raw_install_claim_source", "")),
                ),
                "current_raw_files_installed": _as_int(
                    passport_evidence.get(
                        "current_raw_files_installed",
                        semantic_evidence.get("current_raw_files_installed", 0),
                    )
                ),
                "coverage_raw_files_reported_installed": _as_int(
                    passport_evidence.get(
                        "coverage_raw_files_reported_installed",
                        semantic_evidence.get(
                            "pipeline_raw_files_reported_installed",
                            raw_inventory_evidence.get("pipeline_raw_files_reported_installed", 0),
                        ),
                    )
                ),
                "return_acceptance_raw_files_staged": _as_int(
                    passport_evidence.get(
                        "return_acceptance_raw_files_staged",
                        raw_inventory_evidence.get("return_acceptance_raw_files_staged", 0),
                    )
                ),
                "return_acceptance_raw_files_local_observation": _as_int(
                    passport_evidence.get(
                        "return_acceptance_raw_files_local_observation",
                        raw_inventory_evidence.get("return_acceptance_raw_files_local_observation", 0),
                    )
                ),
            },
            "operator_priority_order": [gap.evidence_key for gap in blocking],
            "ready_evidence_keys": [gap.evidence_key for gap in ready],
            "blocking_evidence_keys": [gap.evidence_key for gap in blocking],
            "evidence_gaps": [gap.to_dict() for gap in gaps],
            "x0t_governance_operator_handoff": {
                "available": self.governance_execute_handoff is not None,
                "decision": (self.governance_execute_handoff or {}).get("handoff_decision"),
                "actionable": (self.governance_execute_handoff or {}).get("handoff_actionable"),
                "ready_for_operator_execute": (self.governance_execute_handoff or {}).get(
                    "ready_for_operator_execute"
                ),
                "readiness_decision": governance_handoff_summary.get("readiness_decision"),
                "execute_ready_now": governance_handoff_summary.get("execute_ready_now"),
                "approval_env": governance_handoff_approval.get("approval_env"),
                "approval_value_required": governance_handoff_approval.get("expected_value"),
                "missing_inputs": governance_handoff_missing_inputs,
                "operator_next_actions": governance_handoff_operator_next_actions,
                "operator_command_checks": governance_handoff_operator_command_checks,
            },
            "x0t_contract_operator_handoff": x0t_contract_operator_handoff,
            "live_rollout_operator_handoff": live_rollout_operator_handoff,
            "external_settlement_operator_handoff": {
                "available": self.external_settlement_handoff is not None,
                "decision": (self.external_settlement_handoff or {}).get("handoff_decision"),
                "ready_for_completion_rerun": (self.external_settlement_handoff or {}).get(
                    "ready_for_completion_rerun"
                ),
                "capture_preflight_decision": external_handoff_summary.get("capture_preflight_decision"),
                "capture_inputs_ready": external_handoff_summary.get("capture_inputs_ready"),
                "missing_inputs": external_handoff_missing_inputs,
                "operator_next_actions": external_handoff_operator_next_actions,
                "operator_command_checks": external_handoff_operator_command_checks,
            },
            "blocking_reasons": blocking_reasons,
            "required_next_evidence": (
                [
                    "x0t_governance_handoff: regenerate the read-only execute operator handoff current shard and verify it is actionable/read-only."
                ]
                if governance_handoff_blocked
                else []
            )
            + (
                [
                    "external_settlement_handoff: regenerate the read-only external settlement operator handoff current shard and verify capture-preflight plus command-surface alignment."
                ]
                if external_handoff_blocked
                else []
            )
            + (
                [
                    "external_settlement_handoff: rerun the read-only external settlement operator handoff after settlement evidence gates are ready."
                ]
                if external_handoff_stale_after_source_clear
                else []
            )
            + (
                [
                    "live_rollout_handoff: regenerate the read-only rollout provenance current shard and verify image digest/provenance command-surface alignment."
                ]
                if rollout_handoff_blocked
                else []
            )
            + (
                [
                    "live_rollout_handoff: follow the image digest/provenance operator handoff, return digest-pinned runtime image evidence with retained provenance, then rerun rollout provenance and current rollup."
                ]
                if rollout_configured and rollout_handoff_clear and not rollout_handoff_ready
                else []
            )
            + (
                [
                    (
                        "x0t_governance: follow the read-only execute operator handoff, execute proposal 1 only with explicit operator approval when state is Ready, and retain final Executed-state evidence."
                        if governance_handoff_clear
                        else "x0t_governance: rerun the read-only execute-readiness check, execute proposal 1 only with explicit operator approval when state is Ready, and retain final Executed-state evidence."
                    )
                ]
                if governance_blocked
                else []
            )
            + (
                [
                    "x0t_contract: provide and apply the deployed Base Sepolia bridge contract address with the approved read-only/config-only bridge-config operator path, then rerun contract readiness and completion audit."
                ]
                if completion_summary.get("x0t_contract_deployment_ready") is False
                else []
            ) + [
                f"{gap.evidence_key}: {gap.operator_action or 'provide ready retained production evidence'}"
                for gap in blocking
            ],
            "not_verified_yet": [] if all_clear else [
                "all required production evidence keys are backed by ready source artifacts",
                "X0T contract deployment config has a deployed bridge address",
                "X0T governance proposal 1 has final Executed-state evidence",
                "integration-spine completion audit is COMPLETE",
            ],
        }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_operator_handoff_section(
    lines: List[str],
    title: str,
    handoff: Any,
    overview_fields: List[tuple[str, str]],
) -> None:
    if not isinstance(handoff, dict) or handoff.get("available") is not True:
        return
    lines.extend([title, ""])
    for label, key in overview_fields:
        lines.append(f"- {label}: `{handoff.get(key)}`")

    lines.extend(["", "### Missing Inputs", ""])
    missing_inputs = _dict_list(handoff.get("missing_inputs"))
    if missing_inputs:
        for item in missing_inputs:
            item_id = str(item.get("id", ""))
            status = str(item.get("status", ""))
            lines.append(f"- `{item_id}` - `{status}`")
            reason = str(item.get("reason", "") or "")
            command = str(item.get("required_command") or item.get("command") or "")
            artifact = str(item.get("required_artifact", "") or "")
            if reason:
                lines.append(f"  reason: {reason}")
            if command:
                lines.append(f"  command: `{command}`")
            commands = [str(command) for command in item.get("commands", []) if isinstance(command, str)]
            for command_item in commands:
                lines.append(f"  command: `{command_item}`")
            if artifact:
                lines.append(f"  artifact: `{artifact}`")
    else:
        lines.append("- none")

    lines.extend(["", "### Next Actions", ""])
    next_actions = _dict_list(handoff.get("operator_next_actions"))
    if next_actions:
        for index, item in enumerate(next_actions, start=1):
            item_id = str(item.get("id", ""))
            status = str(item.get("status", ""))
            lines.append(f"{index}. `{item_id}` - `{status}`")
            description = str(item.get("description", "") or "")
            if description:
                lines.append(f"   description: {description}")
            command = str(item.get("command", "") or "")
            if command:
                lines.append(f"   command: `{command}`")
            commands = [str(command) for command in item.get("commands", []) if isinstance(command, str)]
            for command_item in commands:
                lines.append(f"   command: `{command_item}`")
            artifact = str(item.get("required_artifact", "") or "")
            if artifact:
                lines.append(f"   artifact: `{artifact}`")
            acceptance = str(item.get("acceptance_rule", "") or "")
            if acceptance:
                lines.append(f"   acceptance: {acceptance}")
            if "requires_operator_approval" in item:
                lines.append(f"   requires operator approval: `{item.get('requires_operator_approval')}`")
            if "submits_transaction" in item:
                lines.append(f"   submits transaction: `{item.get('submits_transaction')}`")
    else:
        lines.append("- none")

    lines.extend(["", "### Command Surface", ""])
    command_checks = _dict_list(handoff.get("operator_command_checks"))
    if command_checks:
        for item in command_checks:
            action_id = str(item.get("action_id", ""))
            status = str(item.get("status", ""))
            entrypoint = str(item.get("expected_entrypoint", "") or "")
            entrypoint_exists = item.get("entrypoint_exists")
            lines.append(f"- `{action_id}` - `{status}`")
            if entrypoint:
                lines.append(f"  entrypoint: `{entrypoint}` exists=`{entrypoint_exists}`")
    else:
        lines.append("- none")
    lines.append("")


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    evidence_gaps = report.get("evidence_gaps", [])
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(evidence_gaps, list):
        evidence_gaps = []

    lines = [
        "# Integration Spine Production Gap Index",
        "",
        f"Generated: `{report.get('generated_at', '')}`",
        f"Decision: `{report.get('decision', '')}`",
        f"Goal can be marked complete: `{report.get('goal_can_be_marked_complete')}`",
        "",
        "## Claim Boundary",
        "",
        str(report.get("claim_boundary", "")),
        "",
        "## Summary",
        "",
        f"- required evidence keys: `{summary.get('required_evidence_keys_total', 0)}`",
        f"- ready evidence keys: `{summary.get('ready_evidence_keys', 0)}`",
        f"- pending evidence keys: `{summary.get('pending_evidence_keys', 0)}`",
        f"- missing source artifacts: `{summary.get('missing_source_artifacts', 0)}`",
        f"- blocked source artifacts: `{summary.get('blocked_source_artifacts', 0)}`",
        f"- route missing: `{summary.get('route_missing', 0)}`",
        f"- import mismatches: `{summary.get('import_mismatches', 0)}`",
        f"- completion audit clear: `{summary.get('completion_audit_clear')}`",
        (
            "- completion checklist: "
            f"`{summary.get('completion_checklist_passed', 0)}/"
            f"{summary.get('completion_checklist_total', 0)} passed`, "
            f"`{summary.get('completion_checklist_blocking', 0)} blocking`"
        ),
        f"- local wiring passed: `{summary.get('completion_local_wiring_passed')}`",
        f"- production readiness passed: `{summary.get('completion_production_readiness_passed')}`",
        f"- raw readiness decision: `{summary.get('raw_operator_packet_readiness_decision', '')}`",
        (
            "- raw readiness files: "
            f"`{summary.get('raw_operator_packet_readiness_raw_files_ready', 0)}/"
            f"{summary.get('raw_operator_packet_readiness_raw_files_total', 0)} ready`, "
            f"`{summary.get('raw_operator_packet_readiness_raw_files_local_observation', 0)} local observation`"
        ),
        f"- governance execute decision: `{summary.get('x0t_governance_execute_decision', '')}`",
        f"- governance execute handoff: `{summary.get('x0t_governance_execute_handoff_decision', '')}`",
        f"- governance handoff actionable: `{summary.get('x0t_governance_execute_handoff_actionable')}`",
        f"- governance proposal executed: `{summary.get('x0t_governance_proposal_executed')}`",
        (
            "- governance handoff commands: "
            f"`{summary.get('x0t_governance_execute_handoff_operator_commands_total', 0)} commands`, "
            f"`{summary.get('x0t_governance_execute_handoff_operator_command_entrypoints_missing', 0)} missing`, "
            f"`{summary.get('x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders', 0)} shell placeholders`, "
            f"`sequence_ready={summary.get('x0t_governance_execute_handoff_operator_sequence_ready')}`"
        ),
        f"- X0T bridge config: `{summary.get('x0t_bridge_config_decision', '')}`",
        f"- X0T contract readiness: `{summary.get('x0t_contract_readiness_decision', '')}`",
        f"- X0T contract deployment ready: `{summary.get('x0t_contract_deployment_ready')}`",
        f"- X0T contract operator handoff: `{summary.get('x0t_contract_operator_handoff_decision', '')}`",
        f"- external settlement handoff: `{summary.get('external_settlement_handoff_decision', '')}`",
        f"- external settlement handoff clear: `{summary.get('external_settlement_handoff_clear')}`",
        f"- external settlement capture preflight: `{summary.get('external_settlement_capture_preflight_decision', '')}`",
        (
            "- external settlement handoff commands: "
            f"`{summary.get('external_settlement_handoff_operator_commands_total', 0)} commands`, "
            f"`{summary.get('external_settlement_handoff_operator_command_entrypoints_missing', 0)} missing`, "
            f"`{summary.get('external_settlement_handoff_operator_commands_with_shell_redirection_placeholders', 0)} shell placeholders`"
        ),
        f"- live rollout handoff: `{summary.get('live_rollout_handoff_decision', '')}`",
        f"- live rollout ready for completion rerun: `{summary.get('live_rollout_ready_for_completion_rerun')}`",
        (
            "- live rollout handoff commands: "
            f"`{summary.get('live_rollout_handoff_operator_commands_total', 0)} commands`, "
            f"`{summary.get('live_rollout_handoff_operator_command_entrypoints_missing', 0)} missing`, "
            f"`{summary.get('live_rollout_handoff_operator_commands_with_shell_redirection_placeholders', 0)} shell placeholders`"
        ),
        "",
    ]

    _append_operator_handoff_section(
        lines,
        "## X0T Contract Deployment Operator Handoff",
        report.get("x0t_contract_operator_handoff", {}),
        [
            ("decision", "decision"),
            ("deployment ready", "deployment_ready"),
            ("contract readiness", "contract_readiness_decision"),
            ("bridge config", "bridge_config_decision"),
            ("approval value required", "approval_value_required"),
        ],
    )
    _append_operator_handoff_section(
        lines,
        "## X0T Governance Execute Operator Handoff",
        report.get("x0t_governance_operator_handoff", {}),
        [
            ("decision", "decision"),
            ("actionable", "actionable"),
            ("ready for operator execute", "ready_for_operator_execute"),
            ("readiness decision", "readiness_decision"),
            ("execute ready now", "execute_ready_now"),
            ("approval value required", "approval_value_required"),
        ],
    )
    _append_operator_handoff_section(
        lines,
        "## External Settlement Operator Handoff",
        report.get("external_settlement_operator_handoff", {}),
        [
            ("decision", "decision"),
            ("ready for completion rerun", "ready_for_completion_rerun"),
            ("capture preflight", "capture_preflight_decision"),
            ("capture inputs ready", "capture_inputs_ready"),
        ],
    )
    _append_operator_handoff_section(
        lines,
        "## Live Rollout Image Digest Operator Handoff",
        report.get("live_rollout_operator_handoff", {}),
        [
            ("decision", "decision"),
            ("rollout decision", "rollout_decision"),
            ("ready for completion rerun", "ready_for_completion_rerun"),
            ("can close image digests blocker", "can_close_image_digests_blocker"),
        ],
    )

    lines.extend(
        [
            "## Operator Priority Order",
            "",
        ]
    )

    blocking_by_key = {
        str(gap.get("evidence_key", "")): gap
        for gap in evidence_gaps
        if isinstance(gap, dict)
    }
    priority = report.get("operator_priority_order", [])
    if not isinstance(priority, list):
        priority = []
    if priority:
        for index, key in enumerate(priority, start=1):
            gap = blocking_by_key.get(str(key), {})
            source_path = gap.get("source_artifact_path", "")
            action = gap.get("operator_action", "")
            lines.append(
                f"{index}. `{key}` - `{gap.get('blocker_class', '')}`"
                + (f" at `{source_path}`" if source_path else "")
            )
            if action:
                lines.append(f"   action: {action}")
            collector_command = str(gap.get("collector_command", "") or "")
            verification_command = str(gap.get("verification_command", "") or "")
            if collector_command:
                lines.append(f"   collector: `{collector_command}`")
            if verification_command:
                lines.append(f"   verify: `{verification_command}`")
            raw_paths = [
                str(path)
                for path in gap.get("raw_paths_to_replace", [])
                if isinstance(path, str) and path
            ]
            if raw_paths:
                lines.append("   raw files to replace:")
                for raw_path in raw_paths[:5]:
                    lines.append(f"   - `{raw_path}`")
                remaining = len(raw_paths) - 5
                if remaining > 0:
                    lines.append(f"   - `... {remaining} more`")
            top_errors = [
                str(error)
                for error in gap.get("top_errors", [])
                if isinstance(error, str) and error
            ]
            if top_errors:
                lines.append(f"   first blocker: {top_errors[0]}")
    else:
        lines.append("No blocking evidence keys.")

    lines.extend(
        [
            "",
            "## Blocking Reasons",
            "",
        ]
    )
    reasons = report.get("blocking_reasons", [])
    if isinstance(reasons, list) and reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Required Next Evidence",
            "",
        ]
    )
    next_evidence = report.get("required_next_evidence", [])
    if isinstance(next_evidence, list) and next_evidence:
        lines.extend(f"- {item}" for item in next_evidence)
    else:
        lines.append("- none")

    lines.extend(["", "## Source Artifacts", ""])
    source_artifacts = report.get("source_artifacts", [])
    if isinstance(source_artifacts, list) and source_artifacts:
        lines.extend(f"- `{path}`" for path in source_artifacts)
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production evidence gap index")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--next-inputs", default=DEFAULT_NEXT_INPUTS)
    parser.add_argument("--production-import", default=DEFAULT_PRODUCTION_IMPORT)
    parser.add_argument("--completion-audit", default=DEFAULT_COMPLETION_AUDIT)
    parser.add_argument("--production-intake", default=DEFAULT_PRODUCTION_INTAKE)
    parser.add_argument("--governance-execute-readiness", default=DEFAULT_GOVERNANCE_EXECUTE_READINESS)
    parser.add_argument("--governance-execute-handoff", default=DEFAULT_GOVERNANCE_EXECUTE_HANDOFF)
    parser.add_argument("--external-settlement-handoff", default=DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF)
    parser.add_argument("--rollout-provenance", default=DEFAULT_ROLLOUT_PROVENANCE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", default="", help=f"optional markdown output path, e.g. {DEFAULT_OUTPUT_MD}")
    parser.add_argument("--require-clear", action="store_true", help="return 2 unless all production evidence gaps are clear")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    next_input = Path(args.next_inputs)
    import_input = Path(args.production_import)
    completion_input = Path(args.completion_audit)
    intake_input = Path(args.production_intake)
    governance_input = Path(args.governance_execute_readiness)
    governance_handoff_input = Path(args.governance_execute_handoff)
    external_handoff_input = Path(args.external_settlement_handoff)
    rollout_input = Path(args.rollout_provenance)
    gate = ProductionGapIndexGate.load(
        next_inputs_path=next_input if next_input.is_absolute() else root / next_input,
        production_import_path=import_input if import_input.is_absolute() else root / import_input,
        completion_audit_path=completion_input if completion_input.is_absolute() else root / completion_input,
        production_intake_path=intake_input if intake_input.is_absolute() else root / intake_input,
        governance_execute_readiness_path=governance_input if governance_input.is_absolute() else root / governance_input,
        governance_execute_handoff_path=governance_handoff_input
        if governance_handoff_input.is_absolute()
        else root / governance_handoff_input,
        external_settlement_handoff_path=external_handoff_input
        if external_handoff_input.is_absolute()
        else root / external_handoff_input,
        rollout_provenance_path=rollout_input if rollout_input.is_absolute() else root / rollout_input,
        root=root,
        next_inputs_display=str(next_input),
        production_import_display=str(import_input),
        completion_audit_display=str(completion_input),
        production_intake_display=str(intake_input),
        governance_execute_readiness_display=str(governance_input),
        governance_execute_handoff_display=str(governance_handoff_input),
        external_settlement_handoff_display=str(external_handoff_input),
        rollout_provenance_display=str(rollout_input),
    )
    report = gate.report()
    write_json(root / args.output_json, report)
    if args.output_md:
        output_md = Path(args.output_md)
        md_path = output_md if output_md.is_absolute() else root / output_md
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": report["goal_can_be_marked_complete"],
        "summary": report["summary"],
        "operator_priority_order": report["operator_priority_order"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_clear and report["decision"] != "NO_PRODUCTION_EVIDENCE_GAPS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
