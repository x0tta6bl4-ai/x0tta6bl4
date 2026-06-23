"""Read-only required evidence consistency gate for integration spine.

This gate verifies that the current production evidence closure artifacts agree
on the same required evidence files. It validates consistency only; it does not
collect evidence, install bundles, call live systems, or mark the objective
complete.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


DEFAULT_PASSPORT = ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json"
DEFAULT_OPERATOR_PACKET_INDEX = ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json"
DEFAULT_INPUT_MANIFEST = ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_INPUT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_ROLLUP_CONTRACT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_CLOSEOUT = ".tmp/validation-shards/integration-spine-production-closeout-review-current.json"
DEFAULT_RAW_OPERATOR_PACKET_INDEX = ".tmp/validation-shards/production-raw-evidence-operator-packet-index-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"


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
    return [str(item) for item in value if isinstance(item, (str, int, float, bool))] if isinstance(value, list) else []


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _items_by_id(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("item_id", "")): item for item in items if item.get("item_id")}


def _packet_required_items(packet_index: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for summary in _dicts((packet_index or {}).get("packet_summaries")):
        for item in _dicts(summary.get("replacement_passport_items")):
            copied = dict(item)
            copied["packet_evidence_key"] = summary.get("evidence_key", "")
            items.append(copied)
    return items


def _source_decision(source: Optional[Dict[str, Any]], *keys: str) -> str:
    if not isinstance(source, dict):
        return ""
    for key in keys:
        value = source.get(key)
        if value:
            return str(value)
    return ""


def _summary(source: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (source or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _raw_operator_bundle_paths(raw_operator_packet_index: Optional[Dict[str, Any]]) -> Set[str]:
    paths: Set[str] = set()
    for packet in _dicts((raw_operator_packet_index or {}).get("packets")):
        for file_item in _dicts(packet.get("files")):
            path = str(file_item.get("operator_bundle_path", ""))
            if path:
                paths.add(path)
    return paths


def _raw_operator_item_id(collector_id: str, raw_id: str) -> str:
    return f"raw_operator_packet:raw_evidence:{collector_id}:{raw_id}"


def _raw_operator_required_items(raw_operator_packet_index: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for packet in _dicts((raw_operator_packet_index or {}).get("packets")):
        collector_id = str(packet.get("collector_id", ""))
        for file_item in _dicts(packet.get("files")):
            operator_path = str(file_item.get("operator_bundle_path", ""))
            if not operator_path:
                continue
            file_name = str(file_item.get("file_name") or Path(operator_path).name)
            raw_id = str(file_item.get("raw_id") or f"{collector_id}/{file_name}")
            ready = file_item.get("production_ready") is True
            items.append(
                {
                    "item_id": _raw_operator_item_id(collector_id, raw_id),
                    "kind": "raw_evidence",
                    "evidence_key": collector_id,
                    "raw_id": raw_id,
                    "ready": ready,
                    "blocks_production": not ready,
                    "operator_return_path": operator_path,
                    "retained_destination_path": f".tmp/{collector_id}-raw-evidence/{file_name}",
                }
            )
    return items


@dataclass(frozen=True)
class ConsistencyInputs:
    root: Path
    passport_path: Path
    operator_packet_index_path: Path
    input_manifest_path: Path
    return_acceptance_path: Path
    input_pipeline_path: Path
    rollup_contract_path: Path
    closeout_path: Path
    raw_operator_packet_index_path: Path
    passport_display: str = DEFAULT_PASSPORT
    operator_packet_index_display: str = DEFAULT_OPERATOR_PACKET_INDEX
    input_manifest_display: str = DEFAULT_INPUT_MANIFEST
    return_acceptance_display: str = DEFAULT_RETURN_ACCEPTANCE
    input_pipeline_display: str = DEFAULT_INPUT_PIPELINE
    rollup_contract_display: str = DEFAULT_ROLLUP_CONTRACT
    closeout_display: str = DEFAULT_CLOSEOUT
    raw_operator_packet_index_display: str = DEFAULT_RAW_OPERATOR_PACKET_INDEX


def build_report(inputs: ConsistencyInputs) -> Dict[str, Any]:
    passport = _read_json(inputs.passport_path)
    packet_index = _read_json(inputs.operator_packet_index_path)
    input_manifest = _read_json(inputs.input_manifest_path)
    return_acceptance = _read_json(inputs.return_acceptance_path)
    input_pipeline = _read_json(inputs.input_pipeline_path)
    rollup_contract = _read_json(inputs.rollup_contract_path)
    closeout = _read_json(inputs.closeout_path)
    raw_operator_packet_index = _read_json(inputs.raw_operator_packet_index_path)

    source_errors: List[str] = []
    for label, data, display in (
        ("passport", passport, inputs.passport_display),
        ("operator_packet_index", packet_index, inputs.operator_packet_index_display),
        ("input_manifest", input_manifest, inputs.input_manifest_display),
        ("return_acceptance", return_acceptance, inputs.return_acceptance_display),
        ("input_pipeline", input_pipeline, inputs.input_pipeline_display),
        ("rollup_contract", rollup_contract, inputs.rollup_contract_display),
        ("closeout", closeout, inputs.closeout_display),
        ("raw_operator_packet_index", raw_operator_packet_index, inputs.raw_operator_packet_index_display),
    ):
        if data is None:
            source_errors.append(f"missing or unreadable {label}: {display}")

    passport_items = _dicts((passport or {}).get("required_evidence_files"))
    packet_items = _packet_required_items(packet_index)
    raw_operator_items = _raw_operator_required_items(raw_operator_packet_index)
    packet_paths = {str(item.get("operator_return_path", "")) for item in packet_items if item.get("operator_return_path")}
    packet_items = packet_items + [
        item
        for item in raw_operator_items
        if str(item.get("operator_return_path", "")) not in packet_paths
    ]
    passport_by_id = _items_by_id(passport_items)
    packet_by_id = _items_by_id(packet_items)
    passport_ids: Set[str] = set(passport_by_id)
    packet_ids: Set[str] = set(packet_by_id)

    consistency_errors: List[str] = []
    if passport_ids != packet_ids:
        missing_in_packet = sorted(passport_ids - packet_ids)
        extra_in_packet = sorted(packet_ids - passport_ids)
        if missing_in_packet:
            consistency_errors.append(f"operator packet index misses passport item_ids: {missing_in_packet[:10]}")
        if extra_in_packet:
            consistency_errors.append(f"operator packet index has item_ids not in passport: {extra_in_packet[:10]}")
    for item_id in sorted(passport_ids & packet_ids):
        passport_item = passport_by_id[item_id]
        packet_item = packet_by_id[item_id]
        for field in ("kind", "evidence_key", "raw_id", "operator_return_path", "retained_destination_path"):
            if str(passport_item.get(field, "")) != str(packet_item.get(field, "")):
                consistency_errors.append(f"{item_id} differs between passport and packet index on {field}")
    packet_evidence_keys = sorted({
        str(item.get("evidence_key", ""))
        for item in packet_items
        if item.get("evidence_key")
    })
    passport_evidence_keys = sorted({
        str(item.get("evidence_key", ""))
        for item in passport_items
        if item.get("evidence_key")
    })
    if packet_evidence_keys != passport_evidence_keys:
        consistency_errors.append(
            f"packet evidence keys differ from passport evidence keys: {packet_evidence_keys} != {passport_evidence_keys}"
        )

    passport_summary = (passport or {}).get("summary", {}) if isinstance((passport or {}).get("summary"), dict) else {}
    raw_operator_summary = _summary(raw_operator_packet_index)
    raw_operator_paths = _raw_operator_bundle_paths(raw_operator_packet_index)
    passport_raw_paths = {
        str(item.get("operator_return_path", ""))
        for item in passport_items
        if item.get("kind") == "raw_evidence" and item.get("operator_return_path")
    }
    raw_operator_paths_in_passport = sorted(raw_operator_paths & passport_raw_paths)
    raw_operator_paths_missing_from_passport = sorted(raw_operator_paths - passport_raw_paths)
    ready_total = sum(1 for item in passport_items if item.get("ready") is True)
    blocking_total = sum(1 for item in passport_items if item.get("blocks_production") is True)
    production_ready = (
        not source_errors
        and not consistency_errors
        and bool(passport_items)
        and (passport or {}).get("production_ready") is True
        and (raw_operator_packet_index or {}).get("production_ready") is True
        and ready_total == len(passport_items)
        and blocking_total == 0
    )

    input_manifest_decision = _source_decision(input_manifest, "decision")
    return_acceptance_decision = _source_decision(return_acceptance, "decision")
    input_pipeline_decision = _source_decision(input_pipeline, "pipeline_decision", "decision")
    rollup_decision = _source_decision(rollup_contract, "decision")
    closeout_decision = _source_decision(closeout, "decision")
    raw_operator_packet_decision = _source_decision(raw_operator_packet_index, "decision")

    return_summary = _summary(return_acceptance)
    pipeline_summary = _summary(input_pipeline)
    rollup_summary = _summary(rollup_contract)
    closeout_summary = _summary(closeout)

    errors = source_errors + consistency_errors
    decision = (
        "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR"
        if production_ready
        else "INVALID_REQUIRED_EVIDENCE_CONSISTENCY"
        if errors
        else "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-required-evidence-consistency-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "valid": not errors,
        "production_ready": production_ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only consistency report across integration-spine required evidence artifacts. "
            "It validates that gates agree on the same required files, but does not collect, "
            "install, stage, submit, contact live systems, or complete the objective."
        ),
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_artifacts": [
            inputs.passport_display,
            inputs.operator_packet_index_display,
            inputs.input_manifest_display,
            inputs.return_acceptance_display,
            inputs.input_pipeline_display,
            inputs.rollup_contract_display,
            inputs.closeout_display,
            inputs.raw_operator_packet_index_display,
        ],
        "errors": errors,
        "required_evidence_files": [
            {
                "item_id": item.get("item_id", ""),
                "kind": item.get("kind", ""),
                "evidence_key": item.get("evidence_key", ""),
                "raw_id": item.get("raw_id", ""),
                "ready": item.get("ready"),
                "blocks_production": item.get("blocks_production"),
                "operator_return_path": item.get("operator_return_path", ""),
                "retained_destination_path": item.get("retained_destination_path", ""),
                "packet_index_present": item.get("item_id") in packet_ids,
            }
            for item in passport_items
        ],
        "not_verified_yet": []
        if production_ready
        else [
            "required evidence files are still blocked on operator production artifacts",
            "production raw-evidence operator packet must have every listed file production_ready=true",
            "external settlement and raw evidence gates must become ready before consistency can be clear",
        ],
        "summary": {
            "sources_total": 8,
            "source_errors_total": len(source_errors),
            "errors_total": len(errors),
            "passport_decision": (passport or {}).get("decision"),
            "operator_packet_decision": (packet_index or {}).get("decision"),
            "raw_operator_packet_decision": raw_operator_packet_decision,
            "input_manifest_decision": input_manifest_decision,
            "return_acceptance_decision": return_acceptance_decision,
            "input_pipeline_decision": input_pipeline_decision,
            "rollup_decision": rollup_decision,
            "closeout_decision": closeout_decision,
            "required_evidence_files_total": len(passport_items),
            "required_evidence_files_ready": ready_total,
            "required_evidence_files_blocking": blocking_total,
            "packet_required_evidence_files_total": len(packet_items),
            "packet_passport_item_coverage_ready": passport_ids == packet_ids,
            "raw_operator_packet_local_handoff_complete": (raw_operator_packet_index or {}).get("local_handoff_complete"),
            "raw_operator_packet_production_ready": (raw_operator_packet_index or {}).get("production_ready"),
            "raw_operator_packet_files_total": raw_operator_summary.get("raw_files_total"),
            "raw_operator_packet_files_existing": raw_operator_summary.get("operator_bundle_files_existing"),
            "raw_operator_packet_files_production_ready": raw_operator_summary.get("operator_bundle_files_production_ready"),
            "raw_operator_packet_files_replacement_required": raw_operator_summary.get("operator_bundle_files_replacement_required"),
            "raw_operator_packet_readiness_decision": raw_operator_summary.get("raw_readiness_decision"),
            "raw_operator_packet_readiness_ready_for_collectors": raw_operator_summary.get(
                "raw_readiness_ready_for_collectors"
            ),
            "raw_operator_packet_readiness_collectors_ready": raw_operator_summary.get("raw_readiness_collectors_ready"),
            "raw_operator_packet_readiness_collectors_blocked": raw_operator_summary.get("raw_readiness_collectors_blocked"),
            "raw_operator_packet_readiness_collectors_total": raw_operator_summary.get("raw_readiness_collectors_total"),
            "raw_operator_packet_readiness_raw_files_ready": raw_operator_summary.get("raw_readiness_raw_files_ready"),
            "raw_operator_packet_readiness_raw_files_local_observation": raw_operator_summary.get(
                "raw_readiness_raw_files_local_observation"
            ),
            "raw_operator_packet_readiness_raw_files_total": raw_operator_summary.get("raw_readiness_raw_files_total"),
            "raw_operator_packet_production_ready_blocked_by_raw_readiness": raw_operator_summary.get(
                "production_ready_blocked_by_raw_readiness"
            ),
            "raw_operator_packet_paths_total": len(raw_operator_paths),
            "raw_operator_packet_paths_in_passport": len(raw_operator_paths_in_passport),
            "raw_operator_packet_paths_missing_from_passport": len(raw_operator_paths_missing_from_passport),
            "raw_operator_packet_paths_missing_from_passport_sample": raw_operator_paths_missing_from_passport[:10],
            "raw_required_evidence_files_total": sum(1 for item in passport_items if item.get("kind") == "raw_evidence"),
            "raw_required_evidence_files_ready": sum(1 for item in passport_items if item.get("kind") == "raw_evidence" and item.get("ready") is True),
            "external_required_evidence_files_total": sum(1 for item in passport_items if item.get("kind") == "external_settlement"),
            "external_required_evidence_files_ready": sum(1 for item in passport_items if item.get("kind") == "external_settlement" and item.get("ready") is True),
            "kind_counts": _count_by(passport_items, "kind"),
            "evidence_key_counts": _count_by(passport_items, "evidence_key"),
            "input_manifest_goal_can_be_marked_complete": (input_manifest or {}).get("goal_can_be_marked_complete"),
            "return_acceptance_ready_for_pipeline_install": return_summary.get("ready_for_pipeline_install"),
            "return_acceptance_ready_to_stage": return_summary.get("ready_to_stage"),
            "return_acceptance_raw_files_staged": return_summary.get("raw_files_staged"),
            "return_acceptance_raw_files_ready_to_stage": return_summary.get("raw_files_ready_to_stage"),
            "return_acceptance_raw_files_destination_existing": return_summary.get("raw_files_destination_existing"),
            "return_acceptance_raw_files_local_observation": return_summary.get("raw_files_local_observation"),
            "return_acceptance_raw_ready_to_stage": return_summary.get("raw_ready_to_stage"),
            "return_acceptance_external_settlement_live_rpc_checked": return_summary.get("external_settlement_live_rpc_report_found"),
            "return_acceptance_external_settlement_live_rpc_ready": return_summary.get("external_settlement_live_rpc_ready"),
            "return_acceptance_external_settlement_live_rpc_errors_total": return_summary.get("external_artifacts_operator_required"),
            "input_pipeline_external_settlement_ready": pipeline_summary.get("external_settlement_ready"),
            "input_pipeline_raw_files_installed": pipeline_summary.get("raw_files_installed"),
            "input_pipeline_raw_files_reported_installed": pipeline_summary.get("raw_files_installed"),
            "input_pipeline_raw_files_expected": pipeline_summary.get("raw_files_expected"),
            "rollup_evidence_files_total": rollup_summary.get("evidence_files_total"),
            "rollup_evidence_files_valid": rollup_summary.get("evidence_files_valid"),
            "rollup_evidence_files_missing": rollup_summary.get("evidence_files_missing"),
            "rollup_evidence_files_invalid": rollup_summary.get("evidence_files_invalid"),
            "rollup_evidence_files_operator_input_required": rollup_summary.get(
                "evidence_files_operator_input_required"
            ),
            "closeout_ready": closeout_summary.get("ready"),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify required evidence consistency across integration-spine closure artifacts")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--passport", default=DEFAULT_PASSPORT)
    parser.add_argument("--operator-packet-index", default=DEFAULT_OPERATOR_PACKET_INDEX)
    parser.add_argument("--input-manifest", default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--input-pipeline", default=DEFAULT_INPUT_PIPELINE)
    parser.add_argument("--rollup-contract", default=DEFAULT_ROLLUP_CONTRACT)
    parser.add_argument("--closeout", default=DEFAULT_CLOSEOUT)
    parser.add_argument("--raw-operator-packet-index", default=DEFAULT_RAW_OPERATOR_PACKET_INDEX)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-valid", action="store_true", help="return 2 unless the consistency report is valid")
    parser.add_argument("--require-clear", action="store_true", help="return 2 unless all required evidence is production ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    inputs = ConsistencyInputs(
        root=root,
        passport_path=_resolve(root, args.passport),
        operator_packet_index_path=_resolve(root, args.operator_packet_index),
        input_manifest_path=_resolve(root, args.input_manifest),
        return_acceptance_path=_resolve(root, args.return_acceptance),
        input_pipeline_path=_resolve(root, args.input_pipeline),
        rollup_contract_path=_resolve(root, args.rollup_contract),
        closeout_path=_resolve(root, args.closeout),
        raw_operator_packet_index_path=_resolve(root, args.raw_operator_packet_index),
        passport_display=str(Path(args.passport)),
        operator_packet_index_display=str(Path(args.operator_packet_index)),
        input_manifest_display=str(Path(args.input_manifest)),
        return_acceptance_display=str(Path(args.return_acceptance)),
        input_pipeline_display=str(Path(args.input_pipeline)),
        rollup_contract_display=str(Path(args.rollup_contract)),
        closeout_display=str(Path(args.closeout)),
        raw_operator_packet_index_display=str(Path(args.raw_operator_packet_index)),
    )
    report = build_report(inputs)
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["decision"],
        "valid": report["valid"],
        "production_ready": report["production_ready"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_valid and report["valid"] is not True:
        return 2
    if args.require_clear and report["production_ready"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
