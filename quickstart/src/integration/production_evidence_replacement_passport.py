"""Read-only production evidence replacement passport for integration spine.

The passport consolidates the operator checklist, semantic replacement packet,
and objective coverage audit into a single file-level replacement contract. It
does not collect evidence, copy files, call live systems, or mark the objective
complete.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CHECKLIST = ".tmp/validation-shards/integration-spine-collection-checklist-export-current.json"
DEFAULT_COVERAGE = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"
DEFAULT_SEMANTIC_REPLACEMENTS = ".tmp/validation-shards/integration-spine-semantic-evidence-replacement-packet-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_RAW_OPERATOR_PACKET_INDEX = ".tmp/validation-shards/production-raw-evidence-operator-packet-index-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json"
DEFAULT_VERIFICATION_OUTPUT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json"


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


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, (str, int, float, bool))]


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in _as_list(value) if isinstance(item, dict)]


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _coverage_by_id(coverage: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    rows = _dicts((coverage or {}).get("prompt_to_artifact_checklist"))
    return {str(row.get("id", "")): row for row in rows if row.get("id")}


def _semantic_by_raw_id(semantic: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    groups = _dicts((semantic or {}).get("replacement_groups"))
    return {str(group.get("raw_id", "")): group for group in groups if group.get("raw_id")}


def _external_by_key(semantic: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    items = _dicts((semantic or {}).get("external_replacements"))
    return {str(item.get("evidence_key", "")): item for item in items if item.get("evidence_key")}


def _raw_operator_item_id(collector_id: str, raw_id: str) -> str:
    return f"raw_operator_packet:raw_evidence:{collector_id}:{raw_id}"


def _raw_destination_path(collector_id: str, file_name: str) -> str:
    return f".tmp/{collector_id}-raw-evidence/{file_name}"


def _raw_operator_paths(raw_operator_packet_index: Optional[Dict[str, Any]]) -> List[str]:
    paths: List[str] = []
    for packet in _dicts((raw_operator_packet_index or {}).get("packets")):
        for file_item in _dicts(packet.get("files")):
            path = str(file_item.get("operator_bundle_path", ""))
            if path:
                paths.append(path)
    return paths


def _supplemental_raw_operator_items(
    raw_operator_packet_index: Optional[Dict[str, Any]],
    checklist_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    checklist_paths = {
        str(item.get("operator_bundle_destination_path") or item.get("operator_return_path") or item.get("destination_path", ""))
        for item in checklist_items
        if item.get("kind") == "raw_evidence"
    }
    supplemental: List[Dict[str, Any]] = []
    for packet in _dicts((raw_operator_packet_index or {}).get("packets")):
        collector_id = str(packet.get("collector_id", ""))
        collector_command = str(packet.get("collector_command", ""))
        evidence_gate_command = str(packet.get("evidence_gate_command", ""))
        for file_item in _dicts(packet.get("files")):
            operator_path = str(file_item.get("operator_bundle_path", ""))
            if not operator_path or operator_path in checklist_paths:
                continue
            file_name = str(file_item.get("file_name") or Path(operator_path).name)
            raw_id = str(file_item.get("raw_id") or f"{collector_id}/{file_name}")
            ready = file_item.get("production_ready") is True
            blockers = _strings(file_item.get("blockers"))
            raw_destination = _raw_destination_path(collector_id, file_name)
            validation_commands = [
                "python3 scripts/ops/import_production_raw_evidence_bundle.py "
                "--bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready"
            ]
            if evidence_gate_command:
                validation_commands.append(evidence_gate_command)
            supplemental.append(
                {
                    "item_id": _raw_operator_item_id(collector_id, raw_id),
                    "kind": "raw_evidence",
                    "evidence_key": collector_id,
                    "raw_id": raw_id,
                    "ready": ready,
                    "current_status": "PRODUCTION_EVIDENCE" if ready else "OPERATOR_REQUIRED",
                    "source_path": operator_path,
                    "destination_path": raw_destination,
                    "collector_raw_destination_path": raw_destination,
                    "operator_bundle_destination_path": operator_path,
                    "required_action": (
                        "replace the operator bundle JSON with retained production/live evidence; "
                        "status must be VERIFIED HERE, production_ready=true, and production_promotion_blockers=[]"
                    ),
                    "errors": [] if ready else blockers or ["operator raw evidence file is not production-ready"],
                    "required_statuses": ["VERIFIED HERE"],
                    "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
                    "required_hash_binding_fields": [
                        "evidence_root",
                        "evidence_files[].name",
                        "evidence_files[].path",
                        "evidence_files[].sha256",
                    ],
                    "hash_binding_enforced_by": [
                        "python3 scripts/ops/import_production_raw_evidence_bundle.py "
                        "--bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready"
                    ],
                    "required_chain_contract": {},
                    "validation_commands": validation_commands,
                    "collector_command": collector_command,
                    "coverage_blocking_row_ids": [
                        "goal_audit:production_raw_evidence_operator_packet",
                        "goal_audit:production_evidence_import",
                        "production_evidence_replacement_passport",
                        "required_evidence_consistency",
                        "completion_gate_runner",
                    ],
                }
            )
    return supplemental


def _coverage_links(item: Dict[str, Any], coverage_rows: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for row_id in _strings(item.get("coverage_blocking_row_ids")):
        row = coverage_rows.get(row_id, {})
        links.append(
            {
                "id": row_id,
                "requirement": row.get("requirement", ""),
                "status": row.get("status", ""),
                "local_ready": row.get("local_ready"),
                "production_ready": row.get("production_ready"),
                "blocking_gaps": _strings(row.get("blocking_gaps")),
            }
        )
    return links


def _field_replacements(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    replacements = []
    for replacement in _dicts(group.get("field_replacements")):
        replacements.append(
            {
                "json_pointer": replacement.get("json_pointer", ""),
                "current_value": replacement.get("current_value"),
                "production_evidence_requirement": replacement.get("production_evidence_requirement", ""),
                "blocking_errors": _strings(replacement.get("blocking_errors")),
                "required_actions": _strings(replacement.get("required_actions")),
                "blocker_ids": _strings(replacement.get("blocker_ids")),
            }
        )
    return replacements


def _replacement_contract(
    item: Dict[str, Any],
    semantic_group: Dict[str, Any],
    external_item: Dict[str, Any],
) -> Dict[str, Any]:
    field_replacements = _field_replacements(semantic_group)
    semantic_errors = [
        error
        for replacement in field_replacements
        for error in replacement.get("blocking_errors", [])
    ]
    semantic_actions = [
        action
        for replacement in field_replacements
        for action in replacement.get("required_actions", [])
    ]
    semantic_requirements = [
        str(replacement.get("production_evidence_requirement", ""))
        for replacement in field_replacements
        if replacement.get("production_evidence_requirement")
    ]

    contract = {
        "current_scaffold_path": item.get("source_path", ""),
        "operator_return_path": item.get("operator_bundle_destination_path") or item.get("destination_path", ""),
        "retained_destination_path": item.get("destination_path", ""),
        "collector_raw_destination_path": item.get("collector_raw_destination_path", ""),
        "required_statuses": _strings(item.get("required_statuses")),
        "required_operator_provenance_fields": _strings(item.get("required_operator_provenance_fields")),
        "required_hash_binding_fields": _strings(item.get("required_hash_binding_fields")),
        "required_hash_binding_enforced_by": _strings(item.get("hash_binding_enforced_by")),
        "required_chain_contract": item.get("required_chain_contract") if isinstance(item.get("required_chain_contract"), dict) else {},
        "validation_commands": _strings(item.get("validation_commands")),
        "local_validation_command": semantic_group.get("local_validation_command", ""),
        "collector_command": semantic_group.get("collector_command", ""),
        "final_gate_command": semantic_group.get("verification_command", ""),
        "semantic_field_replacements_total": len(field_replacements),
        "semantic_json_pointers": [
            str(replacement.get("json_pointer", ""))
            for replacement in field_replacements
            if replacement.get("json_pointer")
        ],
        "semantic_blocking_errors": semantic_errors,
        "semantic_required_actions": semantic_actions,
        "production_evidence_requirements": semantic_requirements,
    }
    if external_item:
        contract["external_operator_action"] = external_item.get("operator_action", "")
        contract["external_required_artifact_path"] = external_item.get("required_artifact_path", "")
        contract["external_scaffold_command"] = external_item.get("scaffold_command", "")
        contract["external_verification_command"] = external_item.get("verification_command", "")
        contract["required_chain_contract"] = external_item.get("chain_contract", contract["required_chain_contract"])
    return contract


def _replacement_status(item: Dict[str, Any]) -> str:
    if item.get("ready") is True:
        return "READY_PRODUCTION_EVIDENCE_RETAINED"
    current_status = str(item.get("current_status", ""))
    if current_status == "LOCAL_OBSERVATION":
        return "BLOCKED_LOCAL_OBSERVATION_REPLACEMENT_REQUIRED"
    if current_status == "OPERATOR_REQUIRED":
        return "BLOCKED_OPERATOR_EVIDENCE_REQUIRED"
    return "BLOCKED_PRODUCTION_EVIDENCE_REPLACEMENT_REQUIRED"


def _replacement_item(
    index: int,
    item: Dict[str, Any],
    coverage_rows: Dict[str, Dict[str, Any]],
    semantic_groups: Dict[str, Dict[str, Any]],
    external_items: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    raw_id = str(item.get("raw_id", ""))
    evidence_key = str(item.get("evidence_key", ""))
    semantic_group = semantic_groups.get(raw_id, {}) if raw_id else {}
    external_item = external_items.get(evidence_key, {}) if item.get("kind") == "external_settlement" else {}
    ready = item.get("ready") is True
    return {
        "index": index,
        "item_id": item.get("item_id", ""),
        "kind": item.get("kind", ""),
        "evidence_key": evidence_key,
        "raw_id": raw_id,
        "ready": ready,
        "blocks_production": not ready,
        "current_status": item.get("current_status", ""),
        "replacement_status": _replacement_status(item),
        "source_path": item.get("source_path", ""),
        "operator_return_path": item.get("operator_bundle_destination_path") or item.get("destination_path", ""),
        "retained_destination_path": item.get("destination_path", ""),
        "required_action": item.get("required_action", ""),
        "errors": _strings(item.get("errors")),
        "objective_links": _coverage_links(item, coverage_rows),
        "replacement_contract": _replacement_contract(item, semantic_group, external_item),
    }


@dataclass(frozen=True)
class PassportInputs:
    root: Path
    checklist_path: Path
    coverage_path: Path
    semantic_replacements_path: Path
    return_acceptance_path: Path
    raw_operator_packet_index_path: Optional[Path] = None
    checklist_display: str = DEFAULT_CHECKLIST
    coverage_display: str = DEFAULT_COVERAGE
    semantic_replacements_display: str = DEFAULT_SEMANTIC_REPLACEMENTS
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE
    raw_operator_packet_index_display: str = DEFAULT_RAW_OPERATOR_PACKET_INDEX


def build_passport(inputs: PassportInputs) -> Dict[str, Any]:
    checklist = _read_json(inputs.checklist_path)
    coverage = _read_json(inputs.coverage_path)
    semantic = _read_json(inputs.semantic_replacements_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    raw_operator_packet_index = (
        _read_json(inputs.raw_operator_packet_index_path)
        if inputs.raw_operator_packet_index_path is not None
        else None
    )

    source_errors: List[str] = []
    if checklist is None:
        source_errors.append(f"missing or unreadable checklist export: {inputs.checklist_display}")
    if coverage is None:
        source_errors.append(f"missing or unreadable objective coverage audit: {inputs.coverage_display}")
    if semantic is None:
        source_errors.append(f"missing or unreadable semantic replacement packet: {inputs.semantic_replacements_display}")
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable production input return acceptance: {inputs.return_acceptance_display}")
    elif return_acceptance.get("status") != "VERIFIED HERE" or return_acceptance.get("ok") is not True:
        source_errors.append("production input return acceptance status must be VERIFIED HERE and ok true")
    if inputs.raw_operator_packet_index_path is not None and raw_operator_packet_index is None:
        source_errors.append(
            f"missing or unreadable raw operator packet index: {inputs.raw_operator_packet_index_display}"
        )

    coverage_rows = _coverage_by_id(coverage)
    semantic_groups = _semantic_by_raw_id(semantic)
    external_items = _external_by_key(semantic)
    checklist_items = _dicts((checklist or {}).get("items"))
    supplemental_raw_operator_items = _supplemental_raw_operator_items(raw_operator_packet_index, checklist_items)
    raw_operator_paths = _raw_operator_paths(raw_operator_packet_index)
    checklist_raw_operator_paths = {
        str(item.get("operator_bundle_destination_path") or item.get("operator_return_path") or item.get("destination_path", ""))
        for item in checklist_items
        if item.get("kind") == "raw_evidence"
    }
    raw_operator_paths_covered_by_checklist = sorted(set(raw_operator_paths) & checklist_raw_operator_paths)
    all_items = checklist_items + supplemental_raw_operator_items
    replacement_items = [
        _replacement_item(index, item, coverage_rows, semantic_groups, external_items)
        for index, item in enumerate(all_items, start=1)
    ]

    blocking_items = [item for item in replacement_items if item.get("blocks_production")]
    ready_items = [item for item in replacement_items if item.get("ready") is True]
    raw_items = [item for item in replacement_items if item.get("kind") == "raw_evidence"]
    external = [item for item in replacement_items if item.get("kind") == "external_settlement"]
    item_errors = [
        error
        for item in replacement_items
        for error in item.get("errors", [])
    ]
    semantic_field_replacements_total = sum(
        int(item.get("replacement_contract", {}).get("semantic_field_replacements_total", 0))
        for item in replacement_items
    )
    coverage_blocking_row_ids = sorted(
        {
            link.get("id", "")
            for item in replacement_items
            for link in item.get("objective_links", [])
            if link.get("id")
        }
    )
    current_status_counts: Dict[str, int] = {}
    evidence_key_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}
    for item in replacement_items:
        current_status_counts[str(item.get("current_status", ""))] = current_status_counts.get(str(item.get("current_status", "")), 0) + 1
        evidence_key_counts[str(item.get("evidence_key", ""))] = evidence_key_counts.get(str(item.get("evidence_key", "")), 0) + 1
        kind_counts[str(item.get("kind", ""))] = kind_counts.get(str(item.get("kind", "")), 0) + 1

    coverage_summary = _summary(coverage)
    return_summary = _summary(return_acceptance)
    coverage_raw_installed = _int_value(coverage_summary, "current_raw_files_installed")
    coverage_raw_expected = _int_value(coverage_summary, "current_raw_files_expected")
    return_raw_staged = _int_value(return_summary, "raw_files_staged")
    return_raw_expected = _int_value(return_summary, "raw_files_expected")
    return_raw_local_observation = _int_value(return_summary, "raw_files_local_observation")
    return_raw_ready_to_stage = _int_value(return_summary, "raw_files_ready_to_stage")
    return_raw_destination_existing = _int_value(return_summary, "raw_files_destination_existing")
    return_raw_ready = return_summary.get("raw_ready_to_stage") is True
    production_ready = bool(replacement_items) and not blocking_items and not source_errors
    return {
        "schema_version": "x0tta6bl4-integration-spine-production-evidence-replacement-passport-v2",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
        if production_ready
        else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR",
        "production_ready": production_ready,
        "ready_for_operator_replacement": not production_ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only passport for replacing scaffold, template, mock, or local-observation "
            "inputs with retained production evidence. It does not materialize evidence, run "
            "collectors, submit transactions, contact live clusters/RPC/payment paths, mutate "
            "NL/SPB/VPN runtime, or mark the objective complete."
        ),
        "mutates_files": False,
        "mutates_files_outside_outputs": False,
        "materializes_evidence": False,
        "runs_collectors": False,
        "runs_live_cluster": False,
        "runs_live_customer_path": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "source_of_truth": {
            "collection_checklist_json": inputs.checklist_display,
            "objective_coverage_json": inputs.coverage_display,
            "semantic_replacement_packet_json": inputs.semantic_replacements_display,
            "production_input_return_acceptance_json": inputs.return_acceptance_display,
            "raw_operator_packet_index_json": inputs.raw_operator_packet_index_display,
        },
        "replacement_items": replacement_items,
        "required_evidence_files": [
            {
                "item_id": item.get("item_id"),
                "kind": item.get("kind"),
                "evidence_key": item.get("evidence_key"),
                "raw_id": item.get("raw_id"),
                "ready": item.get("ready"),
                "blocks_production": item.get("blocks_production"),
                "current_status": item.get("current_status"),
                "replacement_status": item.get("replacement_status"),
                "source_path": item.get("source_path"),
                "operator_return_path": item.get("operator_return_path"),
                "retained_destination_path": item.get("retained_destination_path"),
                "required_action": item.get("required_action"),
                "required_statuses": item.get("replacement_contract", {}).get("required_statuses", []),
                "required_operator_provenance_fields": item.get("replacement_contract", {}).get("required_operator_provenance_fields", []),
                "required_hash_binding_fields": item.get("replacement_contract", {}).get("required_hash_binding_fields", []),
                "production_evidence_requirements": item.get("replacement_contract", {}).get("production_evidence_requirements", []),
                "semantic_json_pointers": item.get("replacement_contract", {}).get("semantic_json_pointers", []),
                "validation_commands": item.get("replacement_contract", {}).get("validation_commands", []),
                "objective_blocking_row_ids": [
                    link.get("id", "")
                    for link in item.get("objective_links", [])
                    if link.get("id")
                ],
            }
            for item in replacement_items
        ],
        "item_errors": item_errors,
        "source_errors": source_errors,
        "not_verified_yet": []
        if production_ready
        else [
            "operator replaces every blocking raw/local-observation item with retained production JSON",
            "operator provides a real submitted X0T settlement receipt and matching live RPC verification",
            "rerun collectors, source-candidate audit, production intake, gap index, and completion audit",
            "do not treat scaffold/template/mock/local evidence as production evidence",
        ],
        "summary": {
            "items_total": len(replacement_items),
            "items_ready": len(ready_items),
            "items_blocking": len(blocking_items),
            "raw_evidence_items": len(raw_items),
            "external_settlement_items": len(external),
            "required_evidence_files_total": len(replacement_items),
            "required_evidence_files_ready": len(ready_items),
            "current_status_counts": current_status_counts,
            "kind_counts": kind_counts,
            "evidence_key_counts": evidence_key_counts,
            "semantic_field_replacements_total": semantic_field_replacements_total,
            "raw_operator_packet_files_total": len(raw_operator_paths),
            "raw_operator_packet_files_covered_by_checklist": len(raw_operator_paths_covered_by_checklist),
            "raw_operator_packet_files_added_to_passport": len(supplemental_raw_operator_items),
            "raw_operator_packet_files_production_ready": _int_value(
                _summary(raw_operator_packet_index),
                "operator_bundle_files_production_ready",
            ),
            "raw_operator_packet_files_replacement_required": _int_value(
                _summary(raw_operator_packet_index),
                "operator_bundle_files_replacement_required",
            ),
            "item_errors_total": len(item_errors),
            "source_errors_total": len(source_errors),
            "coverage_blocking_rows_total": len(coverage_blocking_row_ids),
            "coverage_blocking_row_ids": coverage_blocking_row_ids,
            "raw_install_claim_source": "return_acceptance",
            "current_raw_files_installed": return_raw_staged,
            "coverage_raw_files_reported_installed": coverage_raw_installed,
            "coverage_raw_files_expected": coverage_raw_expected,
            "return_acceptance_raw_files_expected": return_raw_expected,
            "return_acceptance_raw_files_staged": return_raw_staged,
            "return_acceptance_raw_files_ready_to_stage": return_raw_ready_to_stage,
            "return_acceptance_raw_files_destination_existing": return_raw_destination_existing,
            "return_acceptance_raw_files_local_observation": return_raw_local_observation,
            "return_acceptance_raw_ready_to_stage": return_raw_ready,
        },
    }


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and value >= 0


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_verification_report(passport: Dict[str, Any], passport_display: str = DEFAULT_OUTPUT) -> Dict[str, Any]:
    """Verify a replacement passport's internal consistency.

    This validates the generated contract only. A blocked passport can be valid
    when it honestly reports missing production evidence.
    """

    errors: List[str] = []
    summary = passport.get("summary", {}) if isinstance(passport.get("summary"), dict) else {}
    replacement_items = _dicts(passport.get("replacement_items"))
    required_files = _dicts(passport.get("required_evidence_files"))
    source_errors = _strings(passport.get("source_errors"))
    item_errors = _strings(passport.get("item_errors"))
    production_ready = passport.get("production_ready") is True

    if passport.get("schema_version") != "x0tta6bl4-integration-spine-production-evidence-replacement-passport-v2":
        errors.append("passport schema_version is not production-evidence-replacement-passport-v2")
    if passport.get("status") != "VERIFIED HERE" or passport.get("ok") is not True:
        errors.append("passport status/ok does not show a verified local read-only report")
    if passport.get("goal_can_be_marked_complete") is not False:
        errors.append("passport must not mark the integration objective complete")
    if any(passport.get(flag) is not False for flag in (
        "mutates_files",
        "mutates_files_outside_outputs",
        "materializes_evidence",
        "runs_collectors",
        "runs_live_cluster",
        "runs_live_customer_path",
        "runs_live_payment_processor",
        "runs_live_registry",
        "runs_live_rpc",
        "submits_transaction",
        "mutates_chain",
        "mutates_nl",
        "mutates_spb",
        "mutates_vpn_runtime",
    )):
        errors.append("passport must stay read-only and non-mutating")

    for key in (
        "items_total",
        "items_ready",
        "items_blocking",
        "raw_evidence_items",
        "external_settlement_items",
        "required_evidence_files_total",
        "required_evidence_files_ready",
        "semantic_field_replacements_total",
        "raw_operator_packet_files_total",
        "raw_operator_packet_files_covered_by_checklist",
        "raw_operator_packet_files_added_to_passport",
        "raw_operator_packet_files_production_ready",
        "raw_operator_packet_files_replacement_required",
        "item_errors_total",
        "source_errors_total",
        "coverage_blocking_rows_total",
        "current_raw_files_installed",
        "coverage_raw_files_reported_installed",
        "coverage_raw_files_expected",
        "return_acceptance_raw_files_expected",
        "return_acceptance_raw_files_staged",
        "return_acceptance_raw_files_ready_to_stage",
        "return_acceptance_raw_files_destination_existing",
        "return_acceptance_raw_files_local_observation",
    ):
        if not _non_negative_int(summary.get(key)):
            errors.append(f"summary.{key} must be a non-negative integer")
    if summary.get("raw_install_claim_source") != "return_acceptance":
        errors.append("summary.raw_install_claim_source must be return_acceptance")
    if summary.get("current_raw_files_installed") != summary.get("return_acceptance_raw_files_staged"):
        errors.append("summary.current_raw_files_installed must equal return_acceptance_raw_files_staged")
    raw_operator_total = summary.get("raw_operator_packet_files_total")
    raw_operator_covered = summary.get("raw_operator_packet_files_covered_by_checklist")
    raw_operator_added = summary.get("raw_operator_packet_files_added_to_passport")
    if raw_operator_total:
        if raw_operator_total != raw_operator_covered + raw_operator_added:
            errors.append(
                "raw operator packet coverage must equal checklist-covered plus passport-added files"
            )

    if summary.get("items_total") != len(replacement_items):
        errors.append("summary.items_total must equal replacement_items length")
    if summary.get("required_evidence_files_total") != len(required_files):
        errors.append("summary.required_evidence_files_total must equal required_evidence_files length")

    ready_items = [item for item in replacement_items if item.get("ready") is True]
    blocking_items = [item for item in replacement_items if item.get("blocks_production") is True]
    raw_items = [item for item in replacement_items if item.get("kind") == "raw_evidence"]
    external_items = [item for item in replacement_items if item.get("kind") == "external_settlement"]
    semantic_fields = sum(
        int((item.get("replacement_contract") or {}).get("semantic_field_replacements_total", 0))
        for item in replacement_items
        if isinstance(item.get("replacement_contract"), dict)
    )

    expected_counts = {
        "items_ready": len(ready_items),
        "items_blocking": len(blocking_items),
        "raw_evidence_items": len(raw_items),
        "external_settlement_items": len(external_items),
        "required_evidence_files_ready": sum(1 for item in required_files if item.get("ready") is True),
        "semantic_field_replacements_total": semantic_fields,
        "item_errors_total": len(item_errors),
        "source_errors_total": len(source_errors),
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            errors.append(f"summary.{key} must equal {expected}")

    if summary.get("kind_counts") != _count_by(replacement_items, "kind"):
        errors.append("summary.kind_counts must match replacement_items")
    if summary.get("evidence_key_counts") != _count_by(replacement_items, "evidence_key"):
        errors.append("summary.evidence_key_counts must match replacement_items")
    if summary.get("current_status_counts") != _count_by(replacement_items, "current_status"):
        errors.append("summary.current_status_counts must match replacement_items")

    required_file_ids = {str(item.get("item_id", "")) for item in required_files}
    replacement_ids = {str(item.get("item_id", "")) for item in replacement_items}
    if required_file_ids != replacement_ids:
        errors.append("required_evidence_files must cover the same item_id set as replacement_items")

    for item in replacement_items:
        if not item.get("item_id"):
            errors.append("replacement item missing item_id")
        if item.get("kind") not in {"raw_evidence", "external_settlement"}:
            errors.append(f"replacement item has unsupported kind: {item.get('kind')}")
        if not item.get("evidence_key"):
            errors.append("replacement item missing evidence_key")
        if not item.get("operator_return_path"):
            errors.append(f"{item.get('item_id')} missing operator_return_path")
        if not item.get("retained_destination_path"):
            errors.append(f"{item.get('item_id')} missing retained_destination_path")
        contract = item.get("replacement_contract", {})
        if not isinstance(contract, dict):
            errors.append(f"{item.get('item_id')} missing replacement_contract")
            continue
        if not contract.get("required_statuses"):
            errors.append(f"{item.get('item_id')} missing required_statuses")
        if item.get("kind") == "raw_evidence":
            if not item.get("raw_id"):
                errors.append(f"{item.get('item_id')} missing raw_id")
            if not contract.get("required_operator_provenance_fields"):
                errors.append(f"{item.get('item_id')} missing required operator provenance fields")
            if not contract.get("validation_commands"):
                errors.append(f"{item.get('item_id')} missing validation commands")
        if item.get("kind") == "external_settlement" and not contract.get("external_required_artifact_path"):
            errors.append(f"{item.get('item_id')} missing external required artifact path")

    if production_ready:
        if passport.get("decision") != "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR":
            errors.append("production-ready passport must have CLEAR decision")
        if passport.get("ready_for_operator_replacement") is not False:
            errors.append("production-ready passport must not require operator replacement")
        if blocking_items:
            errors.append("production-ready passport must have no blocking items")
        if passport.get("not_verified_yet"):
            errors.append("production-ready passport must have empty not_verified_yet")
    else:
        if passport.get("decision") != "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR":
            errors.append("blocked passport must have READY_FOR_OPERATOR decision")
        if passport.get("ready_for_operator_replacement") is not True:
            errors.append("blocked passport must require operator replacement")
        if not blocking_items:
            errors.append("blocked passport must list at least one blocking item")
        if not passport.get("not_verified_yet"):
            errors.append("blocked passport must retain not_verified_yet guidance")
        for item in blocking_items:
            if not str(item.get("replacement_status", "")).startswith("BLOCKED_"):
                errors.append(f"{item.get('item_id')} blocking item must have BLOCKED replacement_status")

    valid = not errors
    expected_decision = (
        "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
        if production_ready
        else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    )
    return {
        "schema_version": "x0tta6bl4-integration-spine-production-evidence-replacement-passport-verification-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
        if valid and production_ready
        else "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
        if valid
        else "INVALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT",
        "valid": valid,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only verification of the replacement passport's internal consistency. "
            "It can validate a blocked passport without treating missing production evidence as complete."
        ),
        "source_artifacts": [passport_display],
        "errors": errors,
        "summary": {
            "checks_total": 7,
            "checks_failed": 0 if valid else len(errors),
            "errors_total": len(errors),
            "passport_decision": passport.get("decision"),
            "expected_passport_decision": expected_decision,
            "passport_production_ready": production_ready,
            "expected_passport_production_ready": production_ready,
            "items_total": summary.get("items_total"),
            "items_ready": summary.get("items_ready"),
            "items_blocking": summary.get("items_blocking"),
            "raw_evidence_items": summary.get("raw_evidence_items"),
            "external_settlement_items": summary.get("external_settlement_items"),
            "required_evidence_files_total": summary.get("required_evidence_files_total"),
            "required_evidence_files_ready": summary.get("required_evidence_files_ready"),
            "semantic_field_replacements_total": summary.get("semantic_field_replacements_total"),
            "raw_operator_packet_files_total": summary.get("raw_operator_packet_files_total"),
            "raw_operator_packet_files_covered_by_checklist": summary.get("raw_operator_packet_files_covered_by_checklist"),
            "raw_operator_packet_files_added_to_passport": summary.get("raw_operator_packet_files_added_to_passport"),
            "raw_operator_packet_files_production_ready": summary.get("raw_operator_packet_files_production_ready"),
            "raw_operator_packet_files_replacement_required": summary.get("raw_operator_packet_files_replacement_required"),
            "item_errors_total": summary.get("item_errors_total"),
            "source_errors_total": summary.get("source_errors_total"),
            "coverage_blocking_rows_total": summary.get("coverage_blocking_rows_total"),
            "coverage_blocking_row_ids": summary.get("coverage_blocking_row_ids", []),
            "raw_install_claim_source": summary.get("raw_install_claim_source"),
            "current_raw_files_installed": summary.get("current_raw_files_installed"),
            "coverage_raw_files_reported_installed": summary.get("coverage_raw_files_reported_installed"),
            "return_acceptance_raw_files_staged": summary.get("return_acceptance_raw_files_staged"),
            "return_acceptance_raw_files_local_observation": summary.get("return_acceptance_raw_files_local_observation"),
            "current_status_counts": summary.get("current_status_counts", {}),
            "kind_counts": summary.get("kind_counts", {}),
            "evidence_key_counts": summary.get("evidence_key_counts", {}),
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Integration Spine Production Evidence Replacement Passport",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Decision: `{report['decision']}`",
        f"Production ready: `{report['production_ready']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Summary",
        "",
    ]
    for key, value in report.get("summary", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Required Evidence Files", ""])
    for item in report.get("required_evidence_files", []):
        lines.append(
            f"- `{item.get('item_id')}`: ready=`{item.get('ready')}`, "
            f"status=`{item.get('current_status')}`, return=`{item.get('operator_return_path')}`"
        )
        for pointer in item.get("semantic_json_pointers", [])[:5]:
            lines.append(f"  - semantic pointer: `{pointer}`")
        for command in item.get("validation_commands", [])[:3]:
            lines.append(f"  - validation: `{command}`")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the integration-spine production evidence replacement passport")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--checklist", default=DEFAULT_CHECKLIST)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE)
    parser.add_argument("--semantic-replacements", default=DEFAULT_SEMANTIC_REPLACEMENTS)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--raw-operator-packet-index", default=DEFAULT_RAW_OPERATOR_PACKET_INDEX)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", help="optional markdown output path")
    parser.add_argument("--verification-output-json", help="optional verification report output path")
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless every replacement item is production ready")
    parser.add_argument("--require-valid", action="store_true", help="return 2 unless the generated passport verification report is valid")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    inputs = PassportInputs(
        root=root,
        checklist_path=_resolve(root, args.checklist),
        coverage_path=_resolve(root, args.coverage),
        semantic_replacements_path=_resolve(root, args.semantic_replacements),
        return_acceptance_path=_resolve(root, args.return_acceptance),
        raw_operator_packet_index_path=_resolve(root, args.raw_operator_packet_index),
        checklist_display=str(Path(args.checklist)),
        coverage_display=str(Path(args.coverage)),
        semantic_replacements_display=str(Path(args.semantic_replacements)),
        return_acceptance_display=str(Path(args.return_acceptance)),
        raw_operator_packet_index_display=str(Path(args.raw_operator_packet_index)),
    )
    report = build_passport(inputs)
    write_json(_resolve(root, args.output_json), report)
    if args.output_md:
        md_path = _resolve(root, args.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    verification = None
    if args.verification_output_json:
        verification = build_verification_report(report, str(Path(args.output_json)))
        write_json(_resolve(root, args.verification_output_json), verification)
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "production_ready": report["production_ready"],
                "goal_can_be_marked_complete": False,
                "verification_valid": None if verification is None else verification["valid"],
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_valid and (verification is None or verification["valid"] is not True):
        return 2
    if args.require_ready and not report["production_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
