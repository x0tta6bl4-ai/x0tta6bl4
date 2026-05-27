"""Operator evidence packet builder for the integration-spine production gate.

This module turns the current machine-readable gap/audit artifacts into
actionable packets for blocked production evidence keys. It is read-only: it
never creates evidence, submits transactions, contacts RPC providers, installs
bundles, or marks the goal complete.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_GAP_INDEX = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_SOURCE_CANDIDATE_AUDIT = ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
DEFAULT_NEXT_INPUTS = ".tmp/validation-shards/integration-spine-production-next-inputs-current.json"
DEFAULT_REPLACEMENT_PASSPORT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/integration-spine-operator-evidence-packet-current.json"
DEFAULT_OUTPUT_ALL_JSON = ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json"

EXTERNAL_SETTLEMENT_FIELDS = [
    "status or evidence_status == VERIFIED HERE",
    "settlement_submitted == true",
    "destination_chain is base-sepolia/base_sepolia or base-mainnet/base",
    "settlement_id is specific and non-placeholder",
    "token_symbol == X0T",
    "transaction_receipt_status indicates a successful mined receipt",
    "block_number is positive",
    "block_hash is a 0x-prefixed 32-byte hash",
    "from_address and to_address are 0x-prefixed 20-byte addresses",
    "transaction_hash is a 0x-prefixed 32-byte hash",
    "source_commands contains at least two exact retained commands and includes the exact transaction hash",
    "explorer_url is HTTPS, matches destination_chain, and contains the exact transaction hash",
    "packet_hash is a 64-character lowercase hex digest matching the canonical receipt payload",
    "template_only is absent or false",
]

RAW_PRODUCTION_FIELDS = [
    "status or evidence_status == VERIFIED HERE",
    "collector_id matches the intake manifest collector_id",
    "raw_id matches the intake manifest raw_id",
    "file_name matches the intake manifest file_name",
    "collected_at is a UTC timestamp",
    "collected_by is a specific operator or CI identity",
    "source_commands is a non-empty list of exact commands, API calls, CI jobs, or operator procedures",
    "production_ready == true",
    "production_promotion_blockers is absent or empty",
    "claim_boundary/environment does not describe local, test, staging, simulation, or production-like context",
    "template/mock/placeholder markers are absent",
]

RAW_TEMPLATE_PACK_COMMAND = (
    "python3 scripts/ops/generate_production_raw_evidence_template_pack.py "
    "--write-template-files --force"
)
RETURN_ACCEPTANCE_COMMAND = (
    "python3 -m src.integration.production_input_return_acceptance --root . --require-ready"
)
INPUT_PIPELINE_COMMAND = (
    "python3 -m src.integration.production_input_pipeline --root . --require-ready"
)
CLOSEOUT_REVIEW_COMMAND = (
    "python3 -m src.integration.production_closeout_review --root . --require-ready"
)


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


def _by_key(items: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {str(item.get("evidence_key", "")): item for item in items if isinstance(item, dict)}


def _gap_by_key(gap_index: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _by_key((gap_index or {}).get("evidence_gaps", []))


def _route_by_key(source_audit: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _by_key((source_audit or {}).get("evidence_source_routes", []))


def _next_by_key(next_inputs: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return _by_key((next_inputs or {}).get("required_inputs", []))


def _operator_bundle_candidate(route: Dict[str, Any]) -> Dict[str, Any]:
    for candidate in route.get("source_candidates", []):
        if isinstance(candidate, dict) and str(candidate.get("source_id", "")).startswith("operator_bundle:"):
            return candidate
    return {}


def _identity_update_plan(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for report in candidate.get("file_reports", []):
        if not isinstance(report, dict):
            continue
        mismatch_fields = [
            field
            for field, key in (
                ("collector_id", "collector_id_matches_manifest"),
                ("raw_id", "raw_id_matches_manifest"),
                ("file_name", "file_name_matches_manifest"),
            )
            if report.get("available") and report.get(key) is not True
        ]
        if not mismatch_fields:
            continue
        suggested_fields = {
            "collector_id": report.get("manifest_collector_id"),
            "raw_id": report.get("manifest_raw_id"),
            "file_name": report.get("manifest_file_name"),
        }
        current_fields = {
            "collector_id": report.get("evidence_collector_id"),
            "raw_id": report.get("evidence_raw_id"),
            "file_name": report.get("evidence_file_name"),
        }
        plan.append(
            {
                "path": report.get("artifact_path", ""),
                "available": report.get("available"),
                "suggested_fields": suggested_fields,
                "current_fields": current_fields,
                "identity_mismatch_fields": mismatch_fields,
                "json_merge_patch": suggested_fields,
                "json_patch_operations": [
                    {
                        "op": "add" if current_fields.get(field) is None else "replace",
                        "path": f"/{field}",
                        "value": suggested_fields.get(field),
                    }
                    for field in mismatch_fields
                ],
            }
        )
    return plan


def _replacement_items_by_key(replacement_passport: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    items = (replacement_passport or {}).get("required_evidence_files", [])
    if not isinstance(items, list):
        return {}
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("evidence_key", ""))
        if not key:
            continue
        by_key.setdefault(key, []).append(
            {
                "item_id": item.get("item_id", ""),
                "kind": item.get("kind", ""),
                "evidence_key": key,
                "raw_id": item.get("raw_id", ""),
                "ready": item.get("ready"),
                "blocks_production": item.get("blocks_production"),
                "current_status": item.get("current_status", ""),
                "replacement_status": item.get("replacement_status", ""),
                "operator_return_path": item.get("operator_return_path", ""),
                "retained_destination_path": item.get("retained_destination_path", ""),
                "required_action": item.get("required_action", ""),
                "required_statuses": [
                    str(value)
                    for value in item.get("required_statuses", [])
                    if isinstance(value, str)
                ],
                "required_operator_provenance_fields": [
                    str(value)
                    for value in item.get("required_operator_provenance_fields", [])
                    if isinstance(value, str)
                ],
                "required_hash_binding_fields": [
                    str(value)
                    for value in item.get("required_hash_binding_fields", [])
                    if isinstance(value, str)
                ],
                "production_evidence_requirements": [
                    str(value)
                    for value in item.get("production_evidence_requirements", [])
                    if isinstance(value, str)
                ],
                "semantic_json_pointers": [
                    str(value)
                    for value in item.get("semantic_json_pointers", [])
                    if isinstance(value, str)
                ],
                "validation_commands": [
                    str(value)
                    for value in item.get("validation_commands", [])
                    if isinstance(value, str)
                ],
                "objective_blocking_row_ids": [
                    str(value)
                    for value in item.get("objective_blocking_row_ids", [])
                    if isinstance(value, str)
                ],
            }
        )
    return by_key


def _replacement_passport_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "items_total": len(items),
        "items_ready": sum(1 for item in items if item.get("ready") is True),
        "items_blocking": sum(1 for item in items if item.get("blocks_production") is True),
        "semantic_json_pointers_total": sum(len(item.get("semantic_json_pointers", [])) for item in items),
        "production_evidence_requirements_total": sum(
            len(item.get("production_evidence_requirements", [])) for item in items
        ),
    }


def _primary_key(gap_index: Optional[Dict[str, Any]], target_key: str = "") -> str:
    if target_key:
        return target_key
    order = (gap_index or {}).get("operator_priority_order", [])
    if isinstance(order, list) and order:
        return str(order[0])
    summary = (gap_index or {}).get("summary", {})
    return str(summary.get("primary_blocker_evidence_key", ""))


def _blocker_keys(gap_index: Optional[Dict[str, Any]], selected_key: str) -> List[str]:
    keys: List[str] = []

    def add(value: Any) -> None:
        key = str(value or "").strip()
        if key and key not in keys:
            keys.append(key)

    for value in (gap_index or {}).get("operator_priority_order", []) or []:
        add(value)
    for value in (gap_index or {}).get("blocking_evidence_keys", []) or []:
        add(value)
    for key in _gap_by_key(gap_index):
        add(key)
    add(selected_key)
    return keys


def _command(command: str, *, purpose: str, existing: bool = True, required_input: bool = False) -> Dict[str, Any]:
    return {
        "purpose": purpose,
        "command": command,
        "existing_entrypoint": existing,
        "requires_operator_input": required_input,
    }


def _raw_domain_operator_inputs(key: str) -> List[str]:
    if key == "safe_rollout_rollback":
        return [
            "digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image",
            "retained per-image cosign/SLSA provenance artifacts for current deployed image digests",
        ]
    return []


def _raw_domain_commands(root: Path, key: str) -> List[Dict[str, Any]]:
    if key != "safe_rollout_rollback":
        return []
    scaffold = "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force"
    rollout_provenance = "python3 -m src.integration.rollout_provenance --root . --require-ready"
    return [
        _command(
            scaffold,
            purpose=(
                "render template-only image digest/provenance intake files for the operator; "
                "these templates are not production evidence"
            ),
            existing=_script_exists(root, scaffold),
            required_input=True,
        ),
        _command(
            rollout_provenance,
            purpose="run the image digest/provenance closure gate after live rollout evidence is in place",
            existing=_script_exists(root, rollout_provenance),
            required_input=True,
        )
    ]


def _raw_domain_acceptance_checks(key: str) -> List[str]:
    if key == "safe_rollout_rollback":
        return [
            "rollout provenance gate reports READY_TO_CLOSE for digest-pinned runtime images and retained per-image provenance",
        ]
    return []


def _script_exists(root: Path, command: str) -> bool:
    parts = shlex.split(command)
    for part in parts:
        if part.endswith(".py") or part.endswith(".sh"):
            return (root / part).exists()
    if len(parts) >= 3 and parts[0] == "python3" and parts[1] == "-m":
        module_path = root / (parts[2].replace(".", "/") + ".py")
        return module_path.exists()
    return bool(command)


def _collector_script_name(collector_id: str) -> str:
    return collector_id.replace("-", "_")


def _raw_collector_command(route: Dict[str, Any], next_item: Dict[str, Any]) -> str:
    command = str(next_item.get("collector_command") or route.get("collector_command") or "")
    if command:
        return command
    collector_id = str(route.get("collector_id") or "")
    if not collector_id:
        return ""
    return f"python3 scripts/ops/collect_{_collector_script_name(collector_id)}_evidence_bundle.py --require-ready"


def _raw_verification_command(route: Dict[str, Any], next_item: Dict[str, Any]) -> str:
    command = str(next_item.get("verification_command") or route.get("verification_command") or "")
    if command:
        return command
    collector_id = str(route.get("collector_id") or "")
    if not collector_id:
        return ""
    return f"python3 scripts/ops/verify_{_collector_script_name(collector_id)}_evidence_gate.py --require-ready"


def _packet_actionable(report: Dict[str, Any]) -> bool:
    summary = report.get("summary", {})
    selected_key = str(report.get("selected_evidence_key") or "")
    decision = report.get("decision")
    if report.get("status") != "VERIFIED HERE" or report.get("ok") is not True:
        return False
    if summary.get("commands_missing_entrypoints") != 0:
        return False
    if decision == "NO_ACTION_REQUIRED":
        return selected_key == "" and summary.get("operator_action_required") is False
    return (
        decision == "OPERATOR_ACTION_REQUIRED"
        and selected_key != ""
        and summary.get("operator_action_required") is True
        and summary.get("commands_total", 0) > 0
    )


def _missing_entrypoint_commands(report: Dict[str, Any]) -> List[str]:
    commands = report.get("packet", {}).get("commands", [])
    return [
        str(command.get("command", ""))
        for command in commands
        if isinstance(command, dict)
        and str(command.get("command", "")).startswith(("python3 ", "bash "))
        and command.get("existing_entrypoint") is not True
    ]


def _required_artifact_paths(packet: Dict[str, Any]) -> List[str]:
    return [
        str(item.get("path", ""))
        for item in packet.get("required_artifacts", [])
        if isinstance(item, dict) and item.get("path")
    ]


def _artifact_source(item: Dict[str, Any]) -> str:
    source = str(item.get("artifact_source", "")).strip()
    if source:
        return source
    path = str(item.get("path", ""))
    if path.startswith((".tmp/production-raw-evidence-operator-bundle/", ".tmp/external-settlement-evidence/")):
        return "operator_production_evidence"
    return "local_verification_artifact"


def _missing_required_artifact_paths(packet: Dict[str, Any]) -> List[str]:
    return [
        str(item.get("path", ""))
        for item in packet.get("required_artifacts", [])
        if isinstance(item, dict)
        and item.get("path")
        and item.get("currently_exists") is not True
    ]


def _missing_required_artifact_paths_by_source(packet: Dict[str, Any], source: str) -> List[str]:
    return [
        str(item.get("path", ""))
        for item in packet.get("required_artifacts", [])
        if isinstance(item, dict)
        and item.get("path")
        and item.get("currently_exists") is not True
        and _artifact_source(item) == source
    ]


def _packet_commands(packet: Dict[str, Any]) -> List[Dict[str, Any]]:
    commands = packet.get("commands", [])
    return [
        {
            "purpose": command.get("purpose", ""),
            "command": command.get("command", ""),
            "existing_entrypoint": command.get("existing_entrypoint"),
            "requires_operator_input": command.get("requires_operator_input", False),
        }
        for command in commands
        if isinstance(command, dict)
    ]


def _packet_for_key(
    root: Path,
    key: str,
    gaps: Dict[str, Dict[str, Any]],
    routes: Dict[str, Dict[str, Any]],
    next_by_key: Dict[str, Dict[str, Any]],
    replacement_by_key: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    gap = gaps.get(key, {})
    route = routes.get(key, {})
    next_item = next_by_key.get(key, {})
    replacement_items = replacement_by_key.get(key, [])
    if key == "external_settlement":
        return _external_packet(root, key, gap, route, next_item, replacement_items)
    if key:
        return _raw_packet(root, key, gap, route, next_item, replacement_items)
    return {
        "evidence_key": "",
        "packet_kind": "none",
        "operator_action_required": False,
        "required_artifacts": [],
        "required_operator_inputs": [],
        "required_fields": [],
        "commands": [],
        "acceptance_checks": [],
        "fail_closed_rules": [],
        "current_blockers": [],
        "source_artifact_path": "",
        "operator_action": "",
    }


def _missing_entrypoints(packet: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        command
        for command in packet.get("commands", [])
        if isinstance(command, dict)
        and command.get("command", "").startswith(("python3 ", "bash "))
        and command.get("existing_entrypoint") is not True
    ]


def _packet_entry(key: str, packet: Dict[str, Any]) -> Dict[str, Any]:
    command_entries = packet.get("commands", [])
    missing_entrypoints = _missing_entrypoints(packet)
    decision = "OPERATOR_ACTION_REQUIRED" if packet.get("operator_action_required") else "NO_ACTION_REQUIRED"
    summary = {
        "selected_evidence_key": key,
        "required_artifacts_total": len(packet.get("required_artifacts", [])),
        "commands_total": len(command_entries),
        "commands_missing_entrypoints": len(missing_entrypoints),
        "operator_action_required": packet.get("operator_action_required", False),
    }
    synthetic_report = {
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "selected_evidence_key": key,
        "summary": summary,
    }
    return {
        "evidence_key": key,
        "decision": decision,
        "actionable": _packet_actionable(synthetic_report),
        "summary": summary,
        "packet": packet,
        "missing_entrypoints": [
            command.get("command", "") for command in missing_entrypoints
        ],
    }


@dataclass(frozen=True)
class PacketInputs:
    root: Path
    gap_index_path: Path
    source_candidate_path: Path
    next_inputs_path: Path
    replacement_passport_path: Path
    gap_index_display: str = DEFAULT_GAP_INDEX
    source_candidate_display: str = DEFAULT_SOURCE_CANDIDATE_AUDIT
    next_inputs_display: str = DEFAULT_NEXT_INPUTS
    replacement_passport_display: str = DEFAULT_REPLACEMENT_PASSPORT


def _external_packet(
    root: Path,
    key: str,
    gap: Dict[str, Any],
    route: Dict[str, Any],
    next_item: Dict[str, Any],
    replacement_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    evidence_path = str(route.get("required_artifact_path") or gap.get("source_artifact_path") or ".tmp/external-settlement-evidence/settlement-submit.json")
    capture = (
        "python3 -m src.integration.external_settlement --root . --capture-from-rpc "
        "--transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain \"$X0T_DESTINATION_CHAIN\" "
        "--settlement-id \"$X0T_SETTLEMENT_ID\" --rpc-url \"$X0T_BASE_RPC_URL\" "
        "--evidence .tmp/external-settlement-evidence/settlement-submit.json --write-evidence --require-ready"
    )
    preflight = (
        "python3 -m src.integration.external_settlement --root . --preflight-capture-inputs "
        "--transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain \"$X0T_DESTINATION_CHAIN\" "
        "--settlement-id \"$X0T_SETTLEMENT_ID\" --rpc-url \"$X0T_BASE_RPC_URL\" "
        "--evidence .tmp/external-settlement-evidence/settlement-submit.json --require-preflight-ready"
    )
    evidence_wrapper = (
        f"python3 scripts/ops/verify_x0t_external_settlement_evidence.py "
        f"--evidence {evidence_path} --require-ready"
    )
    live_rpc_wrapper = (
        f"python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py "
        f"--evidence {evidence_path} --rpc-url \"$X0T_BASE_RPC_URL\" --require-ready"
    )
    scaffold = (
        "python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py "
        "--write-template-files --force"
    )
    source_candidates = "python3 -m src.integration.evidence_source_candidates --root . --require-ready"
    replacement_passport = (
        "python3 -m src.integration.production_evidence_replacement_passport --root . "
        "--verification-output-json .tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json "
        "--require-valid --require-ready"
    )
    intake = "python3 -m src.integration.production_evidence_intake --root . --require-ready"
    return_acceptance = RETURN_ACCEPTANCE_COMMAND
    input_pipeline = INPUT_PIPELINE_COMMAND
    closeout_review = CLOSEOUT_REVIEW_COMMAND
    completion = "python3 -m src.integration.completion_audit --root . --require-complete"
    gap_index = "python3 -m src.integration.production_gap_index --root . --require-clear"

    return {
        "evidence_key": key,
        "packet_kind": "external_settlement",
        "operator_action_required": True,
        "required_artifacts": [
            {
                "path": evidence_path,
                "purpose": "retained submitted X0T settlement receipt",
                "artifact_source": "operator_production_evidence",
                "currently_exists": (root / evidence_path).exists(),
            },
            {
                "path": ".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
                "purpose": "retained receipt schema gate output",
                "artifact_source": "local_verification_artifact",
                "currently_exists": (root / ".tmp/validation-shards/x0t-external-settlement-evidence-current.json").exists(),
            },
            {
                "path": ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
                "purpose": "live read-only Base RPC receipt verification output",
                "artifact_source": "local_verification_artifact",
                "currently_exists": (root / ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json").exists(),
            },
            {
                "path": ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
                "purpose": "combined external settlement blocker gate output",
                "artifact_source": "local_verification_artifact",
                "currently_exists": (root / ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json").exists(),
            },
        ],
        "required_operator_inputs": [
            "real submitted X0T transaction hash",
            "destination Base chain",
            "settlement_id tied to the integration-spine reward/settlement loop",
            "read-only RPC URL for the same Base chain",
            "retained source commands and explorer URL proving the receipt",
        ],
        "required_fields": EXTERNAL_SETTLEMENT_FIELDS,
        "replacement_passport_summary": _replacement_passport_summary(replacement_items),
        "replacement_passport_items": replacement_items,
        "commands": [
            _command(
                scaffold,
                purpose=(
                    "render template-only external settlement intake files for the operator; "
                    "these templates are not production evidence"
                ),
                existing=_script_exists(root, scaffold),
                required_input=True,
            ),
            _command(
                "export X0T_BASE_RPC_URL='<read-only Base RPC URL for the matching chain>'",
                purpose="operator input; not evidence by itself",
                existing=True,
                required_input=True,
            ),
            _command(
                "export X0T_SETTLEMENT_TX_HASH='<0x-prefixed submitted settlement transaction hash>'",
                existing=True,
                purpose="operator input; not evidence by itself",
                required_input=True,
            ),
            _command(
                "export X0T_DESTINATION_CHAIN='<base-sepolia|base|base-mainnet>'",
                existing=True,
                purpose="operator input; must match the RPC URL and submitted transaction chain",
                required_input=True,
            ),
            _command(
                "export X0T_SETTLEMENT_ID='<non-placeholder settlement id>'",
                existing=True,
                purpose="operator input; not evidence by itself",
                required_input=True,
            ),
            _command(preflight, purpose="validate capture inputs without calling RPC or writing settlement evidence", existing=_script_exists(root, preflight), required_input=True),
            _command(capture, purpose="capture retained receipt from live read-only RPC and validate it", existing=_script_exists(root, capture), required_input=True),
            _command(evidence_wrapper, purpose="rerun retained settlement evidence schema gate", existing=_script_exists(root, evidence_wrapper), required_input=True),
            _command(live_rpc_wrapper, purpose="rerun retained settlement evidence plus live read-only RPC gate", existing=_script_exists(root, live_rpc_wrapper), required_input=True),
            _command(source_candidates, purpose="rerun source-candidate audit", existing=_script_exists(root, source_candidates)),
            _command(replacement_passport, purpose="rerun production evidence replacement passport", existing=_script_exists(root, replacement_passport)),
            _command(intake, purpose="rerun production evidence intake gate", existing=_script_exists(root, intake)),
            _command(return_acceptance, purpose="rerun production input return acceptance after intake", existing=_script_exists(root, return_acceptance)),
            _command(input_pipeline, purpose="rerun production input pipeline before closeout review", existing=_script_exists(root, input_pipeline)),
            _command(closeout_review, purpose="rerun production closeout review before final completion audit", existing=_script_exists(root, closeout_review)),
            _command(completion, purpose="rerun completion audit", existing=_script_exists(root, completion)),
            _command(gap_index, purpose="rerun production gap index", existing=_script_exists(root, gap_index)),
        ],
        "acceptance_checks": [
            "x0t_external_settlement_ready == true",
            "live_rpc_ready == true",
            "verify_x0t_external_settlement_evidence.py reports READY",
            "verify_x0t_external_settlement_live_rpc.py reports READY",
            "source-candidate audit marks external_settlement READY_TO_INSTALL",
            "production evidence replacement passport is PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR",
            "production evidence intake no longer lists external_settlement in pending_evidence_keys",
            "production input pipeline reports READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
        ],
        "fail_closed_rules": [
            "Do not synthesize transaction hashes, block hashes, explorer URLs, or source commands.",
            "Do not mark settlement ready from a non-live or mismatched RPC report.",
            "Do not use template/example settlement-submit.json as evidence.",
            "Do not treat external settlement scaffold templates as production evidence.",
            "Do not mutate NL/SPB/VPN runtime from this packet.",
        ],
        "current_blockers": list(gap.get("top_errors", [])) + [
            reason
            for candidate in route.get("source_candidates", [])
            if isinstance(candidate, dict)
            for reason in candidate.get("not_ready_reasons", [])
            if isinstance(reason, str)
        ],
        "source_artifact_path": evidence_path,
        "operator_action": route.get("required_operator_action") or next_item.get("operator_action") or gap.get("operator_action"),
    }


def _raw_packet(
    root: Path,
    key: str,
    gap: Dict[str, Any],
    route: Dict[str, Any],
    next_item: Dict[str, Any],
    replacement_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    operator_paths: List[str] = [
        str(path)
        for path in route.get("operator_bundle_paths", [])
        if isinstance(path, str)
    ]
    raw_paths: List[str] = [
        str(path)
        for path in route.get("raw_paths", [])
        if isinstance(path, str)
    ]
    collector = _raw_collector_command(route, next_item)
    verifier = _raw_verification_command(route, next_item)
    identity_plan_command = f"python3 -m src.integration.operator_bundle_identity --root . --evidence-key {key} --require-clean"
    identity_patch_dry_run_command = (
        "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . "
        "--identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json"
    )
    identity_patch_command = (
        "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . "
        "--identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json --apply"
    )
    identity_updates = _identity_update_plan(_operator_bundle_candidate(route))
    source_candidates = "python3 -m src.integration.evidence_source_candidates --root . --require-ready"
    replacement_passport = (
        "python3 -m src.integration.production_evidence_replacement_passport --root . "
        "--verification-output-json .tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json "
        "--require-valid --require-ready"
    )
    intake = "python3 -m src.integration.production_evidence_intake --root . --require-ready"
    return_acceptance = RETURN_ACCEPTANCE_COMMAND
    input_pipeline = INPUT_PIPELINE_COMMAND
    closeout_review = CLOSEOUT_REVIEW_COMMAND
    completion = "python3 -m src.integration.completion_audit --root . --require-complete"
    gap_index = "python3 -m src.integration.production_gap_index --root . --require-clear"

    return {
        "evidence_key": key,
        "packet_kind": "raw_production_bundle",
        "operator_action_required": True,
        "required_artifacts": [
            {
                "path": path,
                "purpose": "operator-supplied production source candidate",
                "artifact_source": "operator_production_evidence",
                "currently_exists": (root / path).exists(),
            }
            for path in operator_paths
        ],
        "raw_paths_to_replace": raw_paths or list(gap.get("raw_paths_to_replace", [])),
        "required_operator_inputs": [
            "production environment identifier",
            "operator or CI identity that collected the evidence",
            "exact source_commands for every JSON file",
            "domain-specific production observations required by the collector",
        ] + _raw_domain_operator_inputs(key),
        "required_fields": RAW_PRODUCTION_FIELDS,
        "identity_plan_command": identity_plan_command,
        "identity_patch_dry_run_command": identity_patch_dry_run_command,
        "identity_patch_command": identity_patch_command,
        "identity_updates_total": len(identity_updates),
        "identity_update_plan": identity_updates,
        "replacement_passport_summary": _replacement_passport_summary(replacement_items),
        "replacement_passport_items": replacement_items,
        "commands": [
            _command(
                RAW_TEMPLATE_PACK_COMMAND,
                purpose=(
                    "render template-only raw-evidence bundle files for the operator; "
                    "these templates are not production evidence"
                ),
                existing=_script_exists(root, RAW_TEMPLATE_PACK_COMMAND),
                required_input=True,
            ),
            _command("write real production JSON files to the required operator bundle paths", purpose="operator capture step; must not use local retained evidence", existing=True, required_input=True),
            _command(identity_plan_command, purpose="check operator bundle files match intake manifest identity metadata", existing=_script_exists(root, identity_plan_command), required_input=True),
            _command(identity_patch_dry_run_command, purpose="preview identity-only patch without writing operator bundle files", existing=_script_exists(root, identity_patch_dry_run_command), required_input=True),
            _command(identity_patch_command, purpose="apply identity-only fields after reviewing the dry-run patch report", existing=_script_exists(root, identity_patch_command), required_input=True),
            _command(collector, purpose="run domain collector after evidence files are in place", existing=_script_exists(root, collector), required_input=True),
            _command(verifier, purpose="run domain production evidence gate", existing=_script_exists(root, verifier), required_input=True),
            *_raw_domain_commands(root, key),
            _command(source_candidates, purpose="rerun source-candidate audit", existing=_script_exists(root, source_candidates)),
            _command(replacement_passport, purpose="rerun production evidence replacement passport", existing=_script_exists(root, replacement_passport)),
            _command(intake, purpose="rerun production evidence intake gate", existing=_script_exists(root, intake)),
            _command(return_acceptance, purpose="rerun production input return acceptance after intake", existing=_script_exists(root, return_acceptance)),
            _command(input_pipeline, purpose="rerun production input pipeline before closeout review", existing=_script_exists(root, input_pipeline)),
            _command(closeout_review, purpose="rerun production closeout review before final completion audit", existing=_script_exists(root, closeout_review)),
            _command(completion, purpose="rerun completion audit", existing=_script_exists(root, completion)),
            _command(gap_index, purpose="rerun production gap index", existing=_script_exists(root, gap_index)),
        ],
        "acceptance_checks": [
            f"source-candidate audit marks {key} READY_TO_INSTALL",
            "operator bundle identity report is OPERATOR_BUNDLE_IDENTITY_CLEAN",
            "production evidence replacement passport is PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR",
            "production input pipeline reports READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
            "all listed operator bundle files have production_ready == true",
            "all listed operator bundle files have empty production_promotion_blockers",
            "semantic blocker count for this collector is 0",
        ] + _raw_domain_acceptance_checks(key),
        "fail_closed_rules": [
            "Do not promote local, staging, test, contract-validation, production-like, or component-verification evidence.",
            "Do not treat production raw evidence template pack files as production evidence.",
            "Do not set production_ready=true unless the source artifact is actual production evidence.",
            "Do not remove production_promotion_blockers unless the underlying production fact is fixed.",
            *(
                ["Do not treat live rollout image provenance scaffold templates as production evidence."]
                if key == "safe_rollout_rollback"
                else []
            ),
            "Do not mutate NL/SPB/VPN runtime from this packet.",
        ],
        "current_blockers": list(gap.get("top_errors", [])) + [
            reason
            for candidate in route.get("source_candidates", [])
            if isinstance(candidate, dict)
            for reason in candidate.get("not_ready_reasons", [])
            if isinstance(reason, str)
        ],
        "source_artifact_path": gap.get("source_artifact_path", ""),
        "operator_action": route.get("required_operator_action") or next_item.get("operator_action") or gap.get("operator_action"),
    }


def build_packet(inputs: PacketInputs, target_key: str = "") -> Dict[str, Any]:
    gap_index = _read_json(inputs.gap_index_path)
    source_audit = _read_json(inputs.source_candidate_path)
    next_inputs = _read_json(inputs.next_inputs_path)
    replacement_passport = _read_json(inputs.replacement_passport_path)

    selected_key = _primary_key(gap_index, target_key)
    gaps = _gap_by_key(gap_index)
    routes = _route_by_key(source_audit)
    next_by_key = _next_by_key(next_inputs)
    replacement_by_key = _replacement_items_by_key(replacement_passport)

    packet = _packet_for_key(inputs.root, selected_key, gaps, routes, next_by_key, replacement_by_key)
    selected_entry = _packet_entry(selected_key, packet)
    all_packets = [
        _packet_entry(key, _packet_for_key(inputs.root, key, gaps, routes, next_by_key, replacement_by_key))
        for key in _blocker_keys(gap_index, selected_key)
    ]
    missing_entrypoints_total = sum(
        entry["summary"]["commands_missing_entrypoints"] for entry in all_packets
    )

    report = {
        "schema_version": "x0tta6bl4-integration-spine-operator-evidence-packet-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only operator packet for the next integration-spine production evidence blocker. "
            "It does not collect evidence, write evidence files, submit transactions, contact live "
            "systems, mutate NL/SPB/runtime state, or mark the objective complete."
        ),
        "decision": "OPERATOR_ACTION_REQUIRED" if packet.get("operator_action_required") else "NO_ACTION_REQUIRED",
        "goal_can_be_marked_complete": False,
        "source_artifacts": [
            inputs.gap_index_display,
            inputs.source_candidate_display,
            inputs.next_inputs_display,
            inputs.replacement_passport_display,
        ],
        "selected_evidence_key": selected_key,
        "gap_index_decision": (gap_index or {}).get("decision"),
        "gap_index_summary": (gap_index or {}).get("summary", {}),
        "packet": packet,
        "all_blocker_packets": all_packets,
        "summary": {
            "selected_evidence_key": selected_key,
            "required_artifacts_total": selected_entry["summary"]["required_artifacts_total"],
            "commands_total": selected_entry["summary"]["commands_total"],
            "commands_missing_entrypoints": selected_entry["summary"]["commands_missing_entrypoints"],
            "operator_action_required": selected_entry["summary"]["operator_action_required"],
            "blocker_packets_total": len(all_packets),
            "blocker_packets_actionable": sum(1 for entry in all_packets if entry.get("actionable") is True),
            "blocker_packets_missing_entrypoints": sum(1 for entry in all_packets if entry["summary"]["commands_missing_entrypoints"] > 0),
            "blocker_commands_missing_entrypoints": missing_entrypoints_total,
        },
        "not_verified_yet": [
            f"{entry['evidence_key']} production evidence is not ready"
            for entry in all_packets
            if entry.get("decision") == "OPERATOR_ACTION_REQUIRED"
        ] + [
            "operator must provide real production evidence and rerun the listed gates",
        ] if packet.get("operator_action_required") else [],
    }
    report["actionable"] = _packet_actionable(report)
    return report


def build_packet_index(inputs: PacketInputs) -> Dict[str, Any]:
    gap_index = _read_json(inputs.gap_index_path)
    order = (gap_index or {}).get("operator_priority_order", [])
    evidence_keys = [str(key) for key in order if isinstance(key, str) and key]
    if not evidence_keys:
        primary = _primary_key(gap_index)
        evidence_keys = [primary] if primary else []

    packets = [build_packet(inputs, key) for key in evidence_keys]
    packet_summaries = []
    missing_total = 0
    required_artifacts_total = 0
    missing_artifacts_total = 0
    missing_local_artifacts_total = 0
    missing_operator_artifacts_total = 0
    for packet in packets:
        packet_body = packet.get("packet", {})
        missing_commands = _missing_entrypoint_commands(packet)
        missing_artifacts = _missing_required_artifact_paths(packet_body)
        missing_local_artifacts = _missing_required_artifact_paths_by_source(packet_body, "local_verification_artifact")
        missing_operator_artifacts = _missing_required_artifact_paths_by_source(packet_body, "operator_production_evidence")
        required_artifacts = _required_artifact_paths(packet_body)
        missing_total += len(missing_commands)
        required_artifacts_total += len(required_artifacts)
        missing_artifacts_total += len(missing_artifacts)
        missing_local_artifacts_total += len(missing_local_artifacts)
        missing_operator_artifacts_total += len(missing_operator_artifacts)
        summary = packet.get("summary", {})
        packet_summaries.append({
            "evidence_key": packet.get("selected_evidence_key", ""),
            "packet_kind": packet_body.get("packet_kind", ""),
            "actionable": packet.get("actionable") is True,
            "decision": packet.get("decision"),
            "commands_total": summary.get("commands_total", 0),
            "commands_missing_entrypoints": summary.get("commands_missing_entrypoints", 0),
            "missing_entrypoint_commands": missing_commands,
            "required_artifacts_total": summary.get("required_artifacts_total", 0),
            "required_artifact_paths": required_artifacts,
            "missing_required_artifacts_total": len(missing_artifacts),
            "missing_required_artifact_paths": missing_artifacts,
            "missing_local_required_artifacts_total": len(missing_local_artifacts),
            "missing_local_required_artifact_paths": missing_local_artifacts,
            "missing_operator_required_artifacts_total": len(missing_operator_artifacts),
            "missing_operator_required_artifact_paths": missing_operator_artifacts,
            "raw_paths_to_replace": [
                str(path)
                for path in packet_body.get("raw_paths_to_replace", [])
                if isinstance(path, str)
            ],
            "source_artifact_path": packet_body.get("source_artifact_path", ""),
            "operator_action": packet_body.get("operator_action", ""),
            "operator_action_required": summary.get("operator_action_required", False),
            "required_operator_inputs": [
                str(item)
                for item in packet_body.get("required_operator_inputs", [])
                if isinstance(item, str)
            ],
            "required_fields": [
                str(item)
                for item in packet_body.get("required_fields", [])
                if isinstance(item, str)
            ],
            "identity_plan_command": packet_body.get("identity_plan_command", ""),
            "identity_patch_dry_run_command": packet_body.get("identity_patch_dry_run_command", ""),
            "identity_patch_command": packet_body.get("identity_patch_command", ""),
            "identity_updates_total": packet_body.get("identity_updates_total", 0),
            "identity_update_plan": [
                item
                for item in packet_body.get("identity_update_plan", [])
                if isinstance(item, dict)
            ],
            "replacement_passport_summary": packet_body.get("replacement_passport_summary", {}),
            "replacement_passport_items": [
                item
                for item in packet_body.get("replacement_passport_items", [])
                if isinstance(item, dict)
            ],
            "commands": _packet_commands(packet_body),
            "acceptance_checks": [
                str(check)
                for check in packet_body.get("acceptance_checks", [])
                if isinstance(check, str)
            ],
            "fail_closed_rules": [
                str(rule)
                for rule in packet_body.get("fail_closed_rules", [])
                if isinstance(rule, str)
            ],
            "current_blockers": [
                str(reason)
                for reason in packet_body.get("current_blockers", [])
                if isinstance(reason, str)
            ],
        })

    all_actionable = all(packet.get("actionable") is True for packet in packets)
    local_handoff_complete = missing_total == 0 and missing_local_artifacts_total == 0
    return {
        "schema_version": "x0tta6bl4-integration-spine-operator-evidence-packet-index-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only index of operator packets for every current integration-spine "
            "production evidence blocker. It does not collect evidence, write evidence "
            "files, contact live systems, mutate NL/SPB/runtime state, or mark the objective complete."
        ),
        "decision": "ALL_OPERATOR_PACKETS_ACTIONABLE" if all_actionable else "OPERATOR_PACKET_ENTRYPOINTS_MISSING",
        "all_packets_actionable": all_actionable,
        "local_handoff_complete": local_handoff_complete,
        "goal_can_be_marked_complete": False,
        "source_artifacts": [
            inputs.gap_index_display,
            inputs.source_candidate_display,
            inputs.next_inputs_display,
            inputs.replacement_passport_display,
        ],
        "operator_priority_order": evidence_keys,
        "packet_summaries": packet_summaries,
        "summary": {
            "packets_total": len(packets),
            "actionable_packets": sum(1 for packet in packets if packet.get("actionable") is True),
            "packets_with_missing_entrypoints": sum(1 for item in packet_summaries if item["commands_missing_entrypoints"] > 0),
            "commands_missing_entrypoints_total": missing_total,
            "required_artifacts_total": required_artifacts_total,
            "missing_required_artifacts_total": missing_artifacts_total,
            "missing_local_required_artifacts_total": missing_local_artifacts_total,
            "missing_operator_required_artifacts_total": missing_operator_artifacts_total,
            "existing_required_artifacts_total": required_artifacts_total - missing_artifacts_total,
            "all_packets_actionable": all_actionable,
            "local_handoff_complete": local_handoff_complete,
        },
        "not_verified_yet": [
            *([] if all_actionable else ["one or more operator evidence packets reference missing local collector/verifier entrypoints"]),
            *([] if missing_local_artifacts_total == 0 else ["one or more operator evidence packets reference missing local verification artifacts"]),
            *([] if missing_operator_artifacts_total == 0 else ["operator production evidence artifacts are still missing before completion"]),
        ],
    }


def render_markdown(report: Dict[str, Any]) -> str:
    packet = report.get("packet", {})
    lines = [
        "# Integration Spine Operator Evidence Packet",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Selected evidence key: `{report.get('selected_evidence_key', '')}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Required Artifacts",
        "",
    ]
    for item in packet.get("required_artifacts", []):
        lines.append(f"- `{item.get('path')}` - {item.get('purpose')} - exists: `{item.get('currently_exists')}`")
    lines.extend(["", "## Required Fields", ""])
    for field in packet.get("required_fields", []):
        lines.append(f"- {field}")
    lines.extend(["", "## Commands", ""])
    for command in packet.get("commands", []):
        lines.append(f"- `{command.get('command')}`")
        lines.append(f"  - purpose: {command.get('purpose')}")
        lines.append(f"  - existing entrypoint: `{command.get('existing_entrypoint')}`")
    lines.extend(["", "## Acceptance Checks", ""])
    for check in packet.get("acceptance_checks", []):
        lines.append(f"- {check}")
    lines.extend(["", "## Fail-Closed Rules", ""])
    for rule in packet.get("fail_closed_rules", []):
        lines.append(f"- {rule}")
    entries = report.get("all_blocker_packets", [])
    if len(entries) > 1:
        lines.extend(["", "## All Blocker Packets", ""])
        for entry in entries:
            item = entry.get("packet", {})
            summary = entry.get("summary", {})
            lines.extend([
                f"### {entry.get('evidence_key', '')}",
                "",
                f"- decision: `{entry.get('decision')}`",
                f"- actionable: `{entry.get('actionable')}`",
                f"- packet kind: `{item.get('packet_kind')}`",
                f"- required artifacts: `{summary.get('required_artifacts_total')}`",
                f"- commands: `{summary.get('commands_total')}`",
                f"- missing entrypoints: `{summary.get('commands_missing_entrypoints')}`",
                "",
            ])
            blockers = item.get("current_blockers", [])
            if blockers:
                lines.append("Current blockers:")
                for reason in blockers[:8]:
                    lines.append(f"- {reason}")
                if len(blockers) > 8:
                    lines.append(f"- ... {len(blockers) - 8} more")
                lines.append("")
    lines.append("")
    return "\n".join(lines)


def render_index_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Integration Spine Operator Evidence Packet Index",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"All packets actionable: `{report['all_packets_actionable']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Packet Summary",
        "",
    ]
    for item in report.get("packet_summaries", []):
        lines.append(
            f"- `{item.get('evidence_key')}`: actionable=`{item.get('actionable')}`, "
            f"commands=`{item.get('commands_total')}`, missing_entrypoints=`{item.get('commands_missing_entrypoints')}`, "
            f"missing_local_artifacts=`{item.get('missing_local_required_artifacts_total', 0)}`, "
            f"missing_operator_artifacts=`{item.get('missing_operator_required_artifacts_total', 0)}`"
        )
        if item.get("operator_action"):
            lines.append(f"  - operator action: {item.get('operator_action')}")
        for path in item.get("missing_local_required_artifact_paths", []):
            lines.append(f"  - missing local verification artifact: `{path}`")
        for path in item.get("missing_operator_required_artifact_paths", []):
            lines.append(f"  - missing operator production artifact: `{path}`")
        for command in item.get("missing_entrypoint_commands", []):
            lines.append(f"  - missing: `{command}`")
        if item.get("identity_updates_total"):
            lines.append(f"  - identity updates: `{item.get('identity_updates_total')}`")
        for plan_item in item.get("identity_update_plan", [])[:3]:
            path = plan_item.get("path", "")
            suggested = plan_item.get("suggested_fields", {})
            lines.append(
                "  - identity suggestion: "
                f"`{path}` -> collector_id=`{suggested.get('collector_id')}`, "
                f"raw_id=`{suggested.get('raw_id')}`, file_name=`{suggested.get('file_name')}`"
            )
            patch_ops = plan_item.get("json_patch_operations", [])
            if patch_ops:
                rendered_ops = ", ".join(
                    f"{op.get('op')} {op.get('path')}={op.get('value')}"
                    for op in patch_ops
                    if isinstance(op, dict)
                )
                lines.append(f"  - identity patch ops: `{rendered_ops}`")
        replacement_summary = item.get("replacement_passport_summary", {})
        if replacement_summary.get("items_total"):
            lines.append(
                f"  - replacement passport items: `{replacement_summary.get('items_total')}`, "
                f"blocking=`{replacement_summary.get('items_blocking')}`"
            )
        for replacement in item.get("replacement_passport_items", [])[:3]:
            lines.append(
                "  - replacement requirement: "
                f"`{replacement.get('operator_return_path')}` -> "
                f"{'; '.join(replacement.get('production_evidence_requirements', [])[:2])}"
            )
        for command in item.get("commands", []):
            lines.append(f"  - command: `{command.get('command')}`")
        for check in item.get("acceptance_checks", []):
            lines.append(f"  - acceptance: {check}")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build an operator evidence packet for the next production blocker")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--gap-index", default=DEFAULT_GAP_INDEX)
    parser.add_argument("--source-candidate-audit", default=DEFAULT_SOURCE_CANDIDATE_AUDIT)
    parser.add_argument("--next-inputs", default=DEFAULT_NEXT_INPUTS)
    parser.add_argument("--replacement-passport", default=DEFAULT_REPLACEMENT_PASSPORT)
    parser.add_argument("--evidence-key", default="", help="override the primary blocker evidence key")
    parser.add_argument("--all-blockers", action="store_true", help="write an index of packets for every current blocker")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", help="optional markdown output path")
    parser.add_argument("--require-actionable", action="store_true", help="return 2 unless the packet is actionable or no action is required")
    parser.add_argument("--require-all-actionable", action="store_true", help="return 2 unless every current blocker packet is actionable")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    inputs = PacketInputs(
        root=root,
        gap_index_path=_resolve(root, args.gap_index),
        source_candidate_path=_resolve(root, args.source_candidate_audit),
        next_inputs_path=_resolve(root, args.next_inputs),
        replacement_passport_path=_resolve(root, args.replacement_passport),
        gap_index_display=str(Path(args.gap_index)),
        source_candidate_display=str(Path(args.source_candidate_audit)),
        next_inputs_display=str(Path(args.next_inputs)),
        replacement_passport_display=str(Path(args.replacement_passport)),
    )
    if args.all_blockers:
        report = build_packet_index(inputs)
        output_json = DEFAULT_OUTPUT_ALL_JSON if args.output_json == DEFAULT_OUTPUT_JSON else args.output_json
        write_json(_resolve(root, output_json), report)
        if args.output_md:
            md_path = _resolve(root, args.output_md)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_index_markdown(report), encoding="utf-8")
        print(json.dumps({
            "decision": report["decision"],
            "all_packets_actionable": report["all_packets_actionable"],
            "goal_can_be_marked_complete": False,
            "operator_priority_order": report["operator_priority_order"],
            "summary": report["summary"],
        }, ensure_ascii=True, sort_keys=True))
        if args.require_all_actionable and not report["all_packets_actionable"]:
            return 2
        return 0

    report = build_packet(inputs, args.evidence_key)
    write_json(_resolve(root, args.output_json), report)
    if args.output_md:
        md_path = _resolve(root, args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "actionable": report["actionable"],
        "goal_can_be_marked_complete": False,
        "selected_evidence_key": report["selected_evidence_key"],
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_actionable and not report["actionable"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
